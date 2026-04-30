from __future__ import annotations

from datetime import datetime
import copy
import csv
import io
import json
import math
import random
import re
import secrets
from collections import Counter
from typing import Any

from flask import abort, current_app, flash, g, jsonify, redirect, render_template, request, url_for
from flask_login import current_user, login_required
from sqlalchemy.orm.attributes import flag_modified

from ...extensions import db
from ...i18n import DEFAULT_LANG, tr
from ...models.bi import DataSource
from ...models.bi import FileAsset
from ...models.core import Tenant
from ...services.crypto import encrypt_json
from ...services.file_storage_service import store_bytes
from ...services.mlflow_service import log_deployment_event, log_model_created_event, log_sentiment_snapshot_event, log_training_run
from ...services.query_service import QueryExecutionError, execute_sql
from ...services.subscription_service import SubscriptionService
from ...tenancy import enforce_subscription_access_or_redirect, get_current_tenant_id, get_user_module_access
from . import bp


def _(msgid: str, **kwargs):
    return tr(msgid, getattr(g, "lang", DEFAULT_LANG), **kwargs)


def _require_tenant() -> None:
    if not current_user.is_authenticated:
        abort(401)
    if not getattr(g, "tenant", None) or current_user.tenant_id != g.tenant.id:
        abort(403)


def _to_int(value: Any, default: int, min_value: int | None = None, max_value: int | None = None) -> int:
    try:
        out = int(value)
    except Exception:
        out = int(default)
    if min_value is not None:
        out = max(int(min_value), out)
    if max_value is not None:
        out = min(int(max_value), out)
    return out


def _to_number(value: Any) -> float | None:
    try:
        if value is None:
            return None
        if isinstance(value, bool):
            return float(int(value))
        if isinstance(value, (int, float)):
            out = float(value)
            return out if out == out else None
        txt = str(value).strip()
        if not txt:
            return None
        txt = txt.replace(" ", "")
        txt = txt.replace("€", "").replace("$", "").replace("£", "").replace("%", "")
        has_comma = "," in txt
        has_dot = "." in txt
        if has_comma and has_dot:
            if txt.rfind(",") > txt.rfind("."):
                txt = txt.replace(".", "").replace(",", ".")
            else:
                txt = txt.replace(",", "")
        elif has_comma:
            txt = txt.replace(",", ".")
        out = float(txt)
        return out if out == out else None
    except Exception:
        return None


def _numeric_metric_fields(columns: list[Any], rows: list[Any]) -> list[str]:
    metric_fields: list[str] = []
    for idx, col in enumerate(columns):
        seen = 0
        all_numeric = True
        for row in rows:
            if not isinstance(row, (list, tuple)) or idx >= len(row):
                continue
            val = row[idx]
            if val is None or str(val).strip() == "":
                continue
            seen += 1
            if _to_number(val) is None:
                all_numeric = False
                break
        if seen > 0 and all_numeric:
            metric_fields.append(str(col))
    return metric_fields


_SENTIMENT_LEXICON: dict[str, float] = {
    # positive
    "good": 1.0,
    "great": 1.3,
    "excellent": 1.6,
    "happy": 1.2,
    "love": 1.4,
    "amazing": 1.5,
    "helpful": 1.0,
    "fast": 0.7,
    "clear": 0.6,
    "satisfied": 1.1,
    "bon": 1.0,
    "bonne": 1.0,
    "excellent": 1.6,
    "super": 1.3,
    "rapide": 0.7,
    "clair": 0.6,
    "satisfait": 1.1,
    "satisfaite": 1.1,
    "utile": 0.8,
    "otimo": 1.3,
    "ótimo": 1.3,
    "bom": 1.0,
    "boa": 1.0,
    "rapido": 0.7,
    "rápido": 0.7,
    "ajuda": 0.7,
    "feliz": 1.0,
    "excelente": 1.6,
    # negative
    "bad": -1.0,
    "terrible": -1.7,
    "awful": -1.6,
    "slow": -0.8,
    "confusing": -1.0,
    "hate": -1.6,
    "bug": -1.0,
    "broken": -1.5,
    "delay": -0.8,
    "angry": -1.2,
    "mauvais": -1.0,
    "mauvaise": -1.0,
    "lent": -0.8,
    "lente": -0.8,
    "confus": -1.0,
    "confuse": -1.0,
    "erreur": -1.1,
    "panne": -1.5,
    "bug": -1.0,
    "ruim": -1.0,
    "péssimo": -1.7,
    "pessimo": -1.7,
    "lento": -0.8,
    "erro": -1.1,
    "falha": -1.3,
    "odio": -1.5,
}


def _sentiment_tokens(text: str) -> list[str]:
    return re.findall(r"[a-zA-ZÀ-ÿ']+", str(text or "").lower())


def _score_sentiment_text(text: str) -> tuple[float, Counter[str], Counter[str]]:
    pos = Counter()
    neg = Counter()
    score = 0.0
    for token in _sentiment_tokens(text):
        weight = float(_SENTIMENT_LEXICON.get(token, 0.0))
        if weight > 0:
            score += weight
            pos[token] += 1
        elif weight < 0:
            score += weight
            neg[token] += 1
    return score, pos, neg


def _ml_models_state_for_tenant(tenant: Tenant) -> dict[str, Any]:
    settings = tenant.settings_json if isinstance(tenant.settings_json, dict) else {}
    ml_cfg = settings.get("ml_models") if isinstance(settings.get("ml_models"), dict) else {}
    models_raw = ml_cfg.get("models") if isinstance(ml_cfg.get("models"), list) else []

    models: list[dict[str, Any]] = []
    for item in models_raw[:200]:
        if not isinstance(item, dict):
            continue
        model_id = str(item.get("id") or "").strip()
        name = str(item.get("name") or "").strip()
        if not model_id or not name:
            continue
        models.append(
            {
                "id": model_id,
                "name": name,
                "algorithm": str(item.get("algorithm") or "linear_regression").strip(),
                "source_id": _to_int(item.get("source_id"), 0, 0, 2_000_000_000),
                "source_name": str(item.get("source_name") or "").strip(),
                "x_column": str(item.get("x_column") or "").strip(),
                "y_column": str(item.get("y_column") or "").strip(),
                "sql_text": str(item.get("sql_text") or "").strip(),
                "trained_at": str(item.get("trained_at") or ""),
                "metrics": item.get("metrics") if isinstance(item.get("metrics"), dict) else {},
                "params": item.get("params") if isinstance(item.get("params"), dict) else {},
                "model_data": item.get("model_data") if isinstance(item.get("model_data"), dict) else {},
                "mlflow": item.get("mlflow") if isinstance(item.get("mlflow"), dict) else {},
                "deployed": bool(item.get("deployed", False)),
            }
        )

    snapshots_raw = ml_cfg.get("sentiment_snapshots") if isinstance(ml_cfg.get("sentiment_snapshots"), list) else []
    snapshots: list[dict[str, Any]] = []
    for item in snapshots_raw[:200]:
        if not isinstance(item, dict):
            continue
        snapshots.append(
            {
                "id": str(item.get("id") or "").strip() or f"snap_{secrets.token_hex(6)}",
                "created_at": str(item.get("created_at") or "").strip(),
                "source_id": _to_int(item.get("source_id"), 0, 0, 2_000_000_000),
                "source_name": str(item.get("source_name") or "").strip(),
                "text_column": str(item.get("text_column") or "").strip(),
                "sql_text": str(item.get("sql_text") or "").strip()[:12000],
                "rows_analyzed": _to_int(item.get("rows_analyzed"), 0, 0, 5_000_000),
                "summary": item.get("summary") if isinstance(item.get("summary"), dict) else {},
                "top_positive_words": item.get("top_positive_words") if isinstance(item.get("top_positive_words"), list) else [],
                "top_negative_words": item.get("top_negative_words") if isinstance(item.get("top_negative_words"), list) else [],
            }
        )

    return {"settings": settings, "ml_cfg": ml_cfg, "models": models, "sentiment_snapshots": snapshots}


def _persist_ml_models_state(tenant: Tenant, state: dict[str, Any]) -> None:
    settings = state.get("settings") if isinstance(state.get("settings"), dict) else {}
    ml_cfg = state.get("ml_cfg") if isinstance(state.get("ml_cfg"), dict) else {}
    models = state.get("models") if isinstance(state.get("models"), list) else []
    snapshots = state.get("sentiment_snapshots") if isinstance(state.get("sentiment_snapshots"), list) else []
    ml_cfg["models"] = models[:200]
    ml_cfg["sentiment_snapshots"] = snapshots[:200]
    settings["ml_models"] = ml_cfg
    tenant.settings_json = copy.deepcopy(settings)
    flag_modified(tenant, "settings_json")


def _ml_split_train_test(pairs: list[tuple[float, float]], train_ratio: float) -> tuple[list[tuple[float, float]], list[tuple[float, float]]]:
    safe_ratio = min(0.95, max(0.5, float(train_ratio)))
    idx = max(1, min(len(pairs) - 1, int(round(len(pairs) * safe_ratio))))
    return pairs[:idx], pairs[idx:]


def _ml_fit_model(pairs: list[tuple[float, float]], algorithm: str, params: dict[str, Any]) -> dict[str, Any]:
    algo = str(algorithm or "linear_regression").strip().lower()
    if algo == "moving_average":
        window = _to_int(params.get("window"), 5, 2, 200)
        mean_y = sum(y for _, y in pairs) / len(pairs)
        return {
            "algorithm": algo,
            "window": window,
            "mean_y": mean_y,
            "tail_y": [y for _, y in pairs[-window:]],
        }

    if algo == "mean_baseline":
        mean_y = sum(y for _, y in pairs) / len(pairs)
        return {"algorithm": algo, "mean_y": mean_y}

    if algo == "decision_tree":
        # Single split regression tree (stump) for lightweight supervised modeling.
        sorted_pairs = sorted(pairs, key=lambda item: item[0])
        best_threshold = sorted_pairs[0][0]
        best_left_mean = sum(y for _, y in sorted_pairs) / len(sorted_pairs)
        best_right_mean = best_left_mean
        best_sse = float("inf")
        min_leaf = _to_int(params.get("min_leaf"), 3, 1, 200)
        for idx in range(min_leaf, len(sorted_pairs) - min_leaf + 1):
            left = sorted_pairs[:idx]
            right = sorted_pairs[idx:]
            left_mean = sum(y for _, y in left) / len(left)
            right_mean = sum(y for _, y in right) / len(right)
            sse = sum((y - left_mean) ** 2 for _, y in left) + sum((y - right_mean) ** 2 for _, y in right)
            if sse < best_sse:
                best_sse = sse
                best_threshold = (sorted_pairs[idx - 1][0] + sorted_pairs[idx][0]) / 2.0
                best_left_mean = left_mean
                best_right_mean = right_mean
        return {
            "algorithm": algo,
            "threshold": best_threshold,
            "left_mean": best_left_mean,
            "right_mean": best_right_mean,
            "min_leaf": min_leaf,
        }

    if algo == "random_forest":
        n_estimators = _to_int(params.get("n_estimators"), 15, 5, 200)
        min_leaf = _to_int(params.get("min_leaf"), 3, 1, 200)
        rng = random.Random(42)
        trees: list[dict[str, Any]] = []
        for _ in range(n_estimators):
            sample = [pairs[rng.randrange(0, len(pairs))] for _ in range(len(pairs))]
            tree = _ml_fit_model(sample, "decision_tree", {"min_leaf": min_leaf})
            trees.append(tree)
        return {"algorithm": algo, "trees": trees, "n_estimators": n_estimators, "min_leaf": min_leaf}

    n = float(len(pairs))
    sx = sum(x for x, _ in pairs)
    sy = sum(y for _, y in pairs)
    sxx = sum(x * x for x, _ in pairs)
    sxy = sum(x * y for x, y in pairs)
    denom = (n * sxx) - (sx * sx)
    if abs(denom) < 1e-12:
        slope = 0.0
        intercept = sy / n if n else 0.0
    else:
        slope = ((n * sxy) - (sx * sy)) / denom
        intercept = (sy - (slope * sx)) / n
    return {"algorithm": "linear_regression", "slope": slope, "intercept": intercept}


def _ml_fit_kmeans_1d(values: list[float], k: int, max_iter: int = 30) -> dict[str, Any]:
    if not values:
        return {"algorithm": "kmeans_clustering", "centroids": [], "k": 0}
    clean_vals = sorted(float(v) for v in values)
    k = max(2, min(int(k), max(2, min(20, len(clean_vals)))))

    step = max(1, len(clean_vals) // k)
    centroids = [clean_vals[min(i * step, len(clean_vals) - 1)] for i in range(k)]
    for _ in range(max_iter):
        clusters: list[list[float]] = [[] for _ in range(k)]
        for v in clean_vals:
            idx = min(range(k), key=lambda cidx: abs(v - centroids[cidx]))
            clusters[idx].append(v)
        next_centroids = []
        for idx, vals in enumerate(clusters):
            if vals:
                next_centroids.append(sum(vals) / len(vals))
            else:
                next_centroids.append(centroids[idx])
        if all(abs(a - b) < 1e-9 for a, b in zip(centroids, next_centroids)):
            centroids = next_centroids
            break
        centroids = next_centroids

    inertia = 0.0
    for v in clean_vals:
        cidx = min(range(k), key=lambda idx: abs(v - centroids[idx]))
        inertia += (v - centroids[cidx]) ** 2

    return {
        "algorithm": "kmeans_clustering",
        "k": k,
        "centroids": [round(c, 8) for c in centroids],
        "inertia": round(inertia, 8),
    }


def _ml_predict(model_data: dict[str, Any], x_value: float) -> float:
    algo = str(model_data.get("algorithm") or "linear_regression").strip().lower()
    if algo == "moving_average":
        tail = model_data.get("tail_y") if isinstance(model_data.get("tail_y"), list) else []
        vals = [float(v) for v in tail if _to_number(v) is not None]
        if vals:
            return float(sum(vals) / len(vals))
        return float(_to_number(model_data.get("mean_y")) or 0.0)
    if algo == "mean_baseline":
        return float(_to_number(model_data.get("mean_y")) or 0.0)
    if algo == "decision_tree":
        threshold = float(_to_number(model_data.get("threshold")) or 0.0)
        left_mean = float(_to_number(model_data.get("left_mean")) or 0.0)
        right_mean = float(_to_number(model_data.get("right_mean")) or 0.0)
        return left_mean if float(x_value) <= threshold else right_mean
    if algo == "random_forest":
        trees = model_data.get("trees") if isinstance(model_data.get("trees"), list) else []
        preds = [_ml_predict(tree, x_value) for tree in trees if isinstance(tree, dict)]
        if preds:
            return float(sum(preds) / len(preds))
        return 0.0
    if algo == "kmeans_clustering":
        centroids = [float(_to_number(c) or 0.0) for c in (model_data.get("centroids") or [])]
        if not centroids:
            return 0.0
        nearest = min(centroids, key=lambda c: abs(float(x_value) - c))
        return float(nearest)
    slope = float(_to_number(model_data.get("slope")) or 0.0)
    intercept = float(_to_number(model_data.get("intercept")) or 0.0)
    return (slope * float(x_value)) + intercept


def _is_unsupervised_algorithm(algorithm: Any) -> bool:
    return str(algorithm or "").strip().lower() == "kmeans_clustering"


def _cluster_name_by_rank(rank: int, total: int) -> str:
    if total <= 1:
        return "Core cluster"
    if total == 2:
        return ["Lower value", "Higher value"][max(0, min(rank, 1))]
    if total == 3:
        return ["Emerging", "Growth", "Premium"][max(0, min(rank, 2))]
    if total == 4:
        return ["Bronze", "Silver", "Gold", "Platinum"][max(0, min(rank, 3))]
    return f"Cluster {rank + 1}"


def _ml_metrics(
    model_data: dict[str, Any],
    test_pairs: list[tuple[float, float]],
    train_pairs: list[tuple[float, float]] | None = None,
) -> dict[str, Any]:
    algo = str(model_data.get("algorithm") or "").strip().lower()
    if algo == "kmeans_clustering":
        return {
            "mae": None,
            "rmse": None,
            "r2": None,
            "test_rows": len(test_pairs),
            "inertia": model_data.get("inertia"),
            "clusters": model_data.get("k"),
        }

    if not test_pairs:
        return {
            "mae": None,
            "rmse": None,
            "r2": None,
            "test_rows": 0,
            "accuracy": None,
            "accuracy_type": None,
            "fit_indicator": "insufficient_data",
        }

    y_true = [y for _, y in test_pairs]
    y_pred = [_ml_predict(model_data, x) for x, _ in test_pairs]
    abs_err = [abs(a - b) for a, b in zip(y_true, y_pred)]
    sq_err = [(a - b) ** 2 for a, b in zip(y_true, y_pred)]
    mae = sum(abs_err) / len(abs_err)
    rmse = math.sqrt(sum(sq_err) / len(sq_err))

    mean_true = sum(y_true) / len(y_true)
    ss_tot = sum((y - mean_true) ** 2 for y in y_true)
    ss_res = sum((a - b) ** 2 for a, b in zip(y_true, y_pred))
    if ss_tot <= 1e-12:
        r2 = None
    else:
        r2 = 1.0 - (ss_res / ss_tot)

    train_mae = None
    train_rmse = None
    train_r2 = None
    if train_pairs:
        train_true = [y for _, y in train_pairs]
        train_pred = [_ml_predict(model_data, x) for x, _ in train_pairs]
        train_abs = [abs(a - b) for a, b in zip(train_true, train_pred)]
        train_sq = [(a - b) ** 2 for a, b in zip(train_true, train_pred)]
        train_mae = (sum(train_abs) / len(train_abs)) if train_abs else None
        train_rmse = (math.sqrt(sum(train_sq) / len(train_sq)) if train_sq else None)
        train_mean = (sum(train_true) / len(train_true)) if train_true else None
        if train_true and train_mean is not None:
            train_tot = sum((y - train_mean) ** 2 for y in train_true)
            train_res = sum((a - b) ** 2 for a, b in zip(train_true, train_pred))
            train_r2 = None if train_tot <= 1e-12 else (1.0 - (train_res / train_tot))

    def _is_binary(vals: list[float]) -> bool:
        if not vals:
            return False
        return all(abs(v - round(v)) < 1e-9 and int(round(v)) in {0, 1} for v in vals)

    def _binary_accuracy(vals_true: list[float], vals_pred: list[float]) -> float | None:
        if not vals_true or not vals_pred or len(vals_true) != len(vals_pred):
            return None
        correct = 0
        for truth, pred in zip(vals_true, vals_pred):
            pred_cls = 1 if float(pred) >= 0.5 else 0
            truth_cls = int(round(float(truth)))
            if pred_cls == truth_cls:
                correct += 1
        return (float(correct) * 100.0 / float(len(vals_true))) if vals_true else None

    accuracy = None
    train_accuracy = None
    accuracy_type = None
    is_binary_task = _is_binary(y_true)
    if is_binary_task:
        accuracy = _binary_accuracy(y_true, y_pred)
        accuracy_type = "classification"
        if train_pairs:
            train_true_cls = [y for _, y in train_pairs]
            train_pred_cls = [_ml_predict(model_data, x) for x, _ in train_pairs]
            train_accuracy = _binary_accuracy(train_true_cls, train_pred_cls)
    else:
        non_zero_pairs = [(t, p) for t, p in zip(y_true, y_pred) if abs(float(t)) > 1e-12]
        if non_zero_pairs:
            mape = sum(abs((float(t) - float(p)) / float(t)) for t, p in non_zero_pairs) / float(len(non_zero_pairs))
            accuracy = max(0.0, min(100.0, 100.0 * (1.0 - mape)))
            accuracy_type = "regression"

    fit_indicator = "balanced"
    if is_binary_task:
        # For classification, R2 is not the right signal. Use train/test accuracy levels and gap.
        if accuracy is None:
            fit_indicator = "insufficient_data"
        elif train_accuracy is not None:
            acc_gap = float(train_accuracy) - float(accuracy)
            if train_accuracy >= 90.0 and acc_gap >= 8.0:
                fit_indicator = "overfit"
            elif train_accuracy < 65.0 and accuracy < 65.0:
                fit_indicator = "underfit"
            elif train_accuracy >= 80.0 and accuracy >= 75.0 and acc_gap < 8.0:
                fit_indicator = "good_fit"
            else:
                fit_indicator = "balanced"
        else:
            if accuracy >= 80.0:
                fit_indicator = "good_fit"
            elif accuracy < 60.0:
                fit_indicator = "underfit"
            else:
                fit_indicator = "balanced"
    else:
        if r2 is not None and r2 < 0.35:
            fit_indicator = "underfit"
        if train_r2 is not None and r2 is not None:
            gap = float(train_r2) - float(r2)
            if train_r2 >= 0.8 and gap >= 0.2:
                fit_indicator = "overfit"
            elif train_r2 < 0.45 and r2 < 0.45:
                fit_indicator = "underfit"
            elif train_r2 >= 0.65 and r2 >= 0.65 and gap < 0.2:
                fit_indicator = "good_fit"
        elif r2 is not None and r2 >= 0.75:
            fit_indicator = "good_fit"

    return {
        "mae": round(mae, 6),
        "rmse": round(rmse, 6),
        "r2": (round(r2, 6) if r2 is not None else None),
        "train_mae": (round(train_mae, 6) if train_mae is not None else None),
        "train_rmse": (round(train_rmse, 6) if train_rmse is not None else None),
        "train_r2": (round(train_r2, 6) if train_r2 is not None else None),
        "train_accuracy": (round(float(train_accuracy), 2) if train_accuracy is not None else None),
        "accuracy": (round(float(accuracy), 2) if accuracy is not None else None),
        "accuracy_type": accuracy_type,
        "fit_indicator": fit_indicator,
        "test_rows": len(test_pairs),
    }


@bp.before_app_request
def _load_tenant_into_g() -> None:
    tenant_id = get_current_tenant_id()
    if getattr(g, "tenant", None) is None:
        g.tenant = None
        if tenant_id:
            tenant = Tenant.query.get(tenant_id)
            if tenant:
                g.tenant = tenant

    if (
        request.endpoint
        and request.endpoint.startswith("ml.")
        and current_user.is_authenticated
        and getattr(g, "tenant", None)
        and current_user.tenant_id == g.tenant.id
    ):
        redirect_resp = enforce_subscription_access_or_redirect(current_user.tenant_id)
        if redirect_resp is not None:
            return redirect_resp

        access = get_user_module_access(g.tenant, current_user.id)
        if not bool(access.get("ml", True)):
            flash(_("Accès ML Studio désactivé pour votre utilisateur."), "warning")
            return redirect(url_for("tenant.dashboard"))

        if not SubscriptionService.check_feature_access(g.tenant.id, "ml"):
            flash(_("Accès ML Studio non inclus dans votre plan."), "warning")
            return redirect(url_for("billing.plans", product="ml"))


@bp.route("/")
@login_required
def studio():
    return redirect(url_for("ml.supervised_page"), code=302)


def _render_ml_page(page_key: str = "supervised"):
    _require_tenant()
    sources = (
        DataSource.query.filter_by(tenant_id=g.tenant.id)
        .order_by(DataSource.name.asc(), DataSource.id.asc())
        .all()
    )
    state = _ml_models_state_for_tenant(g.tenant)
    all_models = state.get("models") or []
    if page_key == "supervised":
        models = [m for m in all_models if not _is_unsupervised_algorithm(m.get("algorithm"))]
    elif page_key == "unsupervised":
        models = [m for m in all_models if _is_unsupervised_algorithm(m.get("algorithm"))]
    else:
        models = list(all_models)

    mlflow_embed_url = (
        str(current_app.config.get("MLFLOW_EMBED_URL") or "").strip()
        or str(current_app.config.get("MLFLOW_TRACKING_URI") or "").strip()
    )
    return render_template(
        "ml/studio.html",
        tenant=g.tenant,
        sources=sources,
        models=models,
        total_models_count=len(all_models),
        visible_models_count=len(models),
        mlflow_embed_url=mlflow_embed_url,
        ml_page_key=page_key,
    )


def _redirect_to_ml_page(page_key: str | None):
    key = str(page_key or "").strip().lower()
    if key == "overview":
        return redirect(url_for("ml.overview_page"))
    if key == "supervised":
        return redirect(url_for("ml.supervised_page"))
    if key == "unsupervised":
        return redirect(url_for("ml.unsupervised_page"))
    if key == "models":
        return redirect(url_for("ml.models_page"))
    if key == "concepts":
        return redirect(url_for("ml.concepts_page"))
    if key == "mlflow":
        return redirect(url_for("ml.mlflow_page"))
    if key == "sentiment":
        return redirect(url_for("ml.sentiment_page"))
    return redirect(url_for("ml.studio"))


@bp.route("/overview")
@login_required
def overview_page():
    return _render_ml_page("overview")


@bp.route("/supervised")
@login_required
def supervised_page():
    return _render_ml_page("supervised")


@bp.route("/unsupervised")
@login_required
def unsupervised_page():
    return _render_ml_page("unsupervised")


@bp.route("/models")
@login_required
def models_page():
    return _render_ml_page("models")


@bp.route("/concepts")
@login_required
def concepts_page():
    return _render_ml_page("concepts")


@bp.route("/tutorial-mlflow")
@login_required
def tutorial_mlflow_page():
    return redirect(url_for("ml.mlflow_page") + "#mlflow-tutorial")


@bp.route("/mlflow")
@login_required
def mlflow_page():
    return _render_ml_page("mlflow")


@bp.route("/sentiment")
@login_required
def sentiment_page():
    return _render_ml_page("sentiment")


@bp.post("/save")
@login_required
def save_model():
    _require_tenant()
    model_name = str(request.form.get("model_name") or "").strip()
    algorithm = str(request.form.get("algorithm") or "linear_regression").strip().lower()
    source_id = _to_int(request.form.get("source_id"), 0, 0, 2_000_000_000)
    sql_text = str(request.form.get("sql_text") or "").strip()
    x_column = str(request.form.get("x_column") or "").strip()
    y_column = str(request.form.get("y_column") or "").strip()

    if not model_name or not source_id:
        flash(_("Model name and source are required."), "error")
        return redirect(url_for("ml.studio"))

    src = DataSource.query.filter_by(id=source_id, tenant_id=g.tenant.id).first()
    if not src:
        flash(_("Selecione uma fonte válida."), "error")
        return redirect(url_for("ml.studio"))

    state = _ml_models_state_for_tenant(g.tenant)
    models = state.get("models") or []
    models.insert(
        0,
        {
            "id": f"ml_{secrets.token_hex(6)}",
            "name": model_name[:120],
            "algorithm": algorithm,
            "source_id": int(src.id),
            "source_name": str(src.name or ""),
            "x_column": x_column[:120],
            "y_column": y_column[:120],
            "sql_text": sql_text[:12000],
            "trained_at": "",
            "metrics": {},
            "params": {},
            "model_data": {},
            "mlflow": {},
            "deployed": False,
        },
    )
    state["models"] = models[:200]

    created = models[0]
    retrain_url = url_for("ml.retrain_model", model_id=str(created.get("id") or ""), _external=True)
    create_log = log_model_created_event(
        config=current_app.config,
        tenant_id=int(g.tenant.id),
        model=created,
        source=src,
        retrain_url=retrain_url,
    )
    if bool(create_log.get("ok")):
        created["mlflow"] = {
            "run_id": str(create_log.get("run_id") or ""),
            "experiment_id": str(create_log.get("experiment_id") or ""),
            "run_url": str(create_log.get("run_url") or ""),
            "last_sync_at": datetime.utcnow().isoformat(),
        }
    else:
        # Keep save successful even when MLflow is temporarily unavailable.
        created["mlflow"] = {
            "sync_status": "failed",
            "sync_reason": str(create_log.get("reason") or "unknown"),
            "sync_error": str(create_log.get("error") or ""),
            "last_sync_at": datetime.utcnow().isoformat(),
        }

    _persist_ml_models_state(g.tenant, state)
    db.session.commit()
    flash(_("Modèle enregistré."), "success")
    if not bool(create_log.get("ok")):
        flash(_("Modèle enregistré, mais synchronisation MLflow indisponible."), "warning")
    return redirect(url_for("ml.studio"))


@bp.post("/sample-data")
@login_required
def generate_sample_data():
    _require_tenant()

    rng = random.Random(42)
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(
        [
            "employee_id",
            "age",
            "salary",
            "is_manager",
            "tenure_years",
            "performance_score",
            "department",
            "city",
        ]
    )

    departments = ["Engineering", "Sales", "Finance", "Operations", "HR"]
    cities = ["Paris", "Lyon", "Marseille", "Toulouse", "Bordeaux"]
    for idx in range(1, 241):
        age = rng.randint(22, 62)
        is_manager = 1 if rng.random() < 0.22 else 0
        tenure_years = round(max(0.4, rng.gauss(6.2, 3.4)), 2)
        performance_score = round(min(5.0, max(1.8, rng.gauss(3.6, 0.7))), 2)
        base = 22000 + (age * 950) + (tenure_years * 1600) + (performance_score * 3800)
        manager_bonus = 18500 if is_manager else 0
        salary = int(max(23000, min(180000, base + manager_bonus + rng.gauss(0, 5200))))
        writer.writerow(
            [
                idx,
                age,
                salary,
                is_manager,
                tenure_years,
                performance_score,
                departments[(idx - 1) % len(departments)],
                cities[(idx - 1) % len(cities)],
            ]
        )

    stored = store_bytes(
        int(g.tenant.id),
        "ml_samples",
        "ml_training_employees.csv",
        output.getvalue().encode("utf-8"),
    )

    schema_json = {
        "columns": [
            {"name": "employee_id", "type": "INTEGER"},
            {"name": "age", "type": "INTEGER"},
            {"name": "salary", "type": "INTEGER"},
            {"name": "is_manager", "type": "INTEGER"},
            {"name": "tenure_years", "type": "DOUBLE"},
            {"name": "performance_score", "type": "DOUBLE"},
            {"name": "department", "type": "TEXT"},
            {"name": "city", "type": "TEXT"},
        ]
    }
    asset = FileAsset(
        tenant_id=int(g.tenant.id),
        folder_id=None,
        name="ML Training Employees Sample",
        original_filename=stored.original_filename,
        source_type="upload",
        file_format=stored.file_format,
        storage_path=stored.rel_path,
        size_bytes=int(stored.size_bytes),
        sha256=stored.sha256,
        schema_json=schema_json,
    )
    db.session.add(asset)
    db.session.flush()

    workspace_name = "ML Sample Workspace"
    ws = DataSource.query.filter_by(tenant_id=g.tenant.id, type="workspace", name=workspace_name).first()
    ws_cfg = {
        "files": [{"file_id": int(asset.id), "table": "employees_sample"}],
        "max_rows": 20000,
        "starter_sql": "SELECT age, salary, is_manager, tenure_years, performance_score FROM employees_sample ORDER BY employee_id LIMIT 200",
    }
    ws_policy = {"read_only": True, "max_rows": 20000, "timeout_seconds": 30}
    if ws is None:
        ws = DataSource(
            tenant_id=g.tenant.id,
            name=workspace_name,
            type="workspace",
            config_encrypted=encrypt_json(ws_cfg),
            policy_json=ws_policy,
        )
        db.session.add(ws)
        db.session.flush()
    else:
        ws.config_encrypted = encrypt_json(ws_cfg)
        ws.policy_json = ws_policy

    state = _ml_models_state_for_tenant(g.tenant)
    models = state.get("models") or []
    existing_names = {str(m.get("name") or "").strip().lower() for m in models if isinstance(m, dict)}

    sample_models: list[dict[str, Any]] = [
        {
            "id": f"ml_{secrets.token_hex(6)}",
            "name": "Sample Salary by Age",
            "algorithm": "linear_regression",
            "source_id": int(ws.id),
            "source_name": workspace_name,
            "x_column": "age",
            "y_column": "salary",
            "sql_text": "SELECT age, salary, is_manager, tenure_years, performance_score FROM employees_sample",
            "trained_at": "",
            "metrics": {},
            "params": {},
            "model_data": {},
            "mlflow": {},
            "deployed": False,
        },
        {
            "id": f"ml_{secrets.token_hex(6)}",
            "name": "Sample Manager Flag",
            "algorithm": "decision_tree",
            "source_id": int(ws.id),
            "source_name": workspace_name,
            "x_column": "salary",
            "y_column": "is_manager",
            "sql_text": "SELECT salary, is_manager, age, tenure_years, performance_score FROM employees_sample",
            "trained_at": "",
            "metrics": {},
            "params": {},
            "model_data": {},
            "mlflow": {},
            "deployed": False,
        },
        {
            "id": f"ml_{secrets.token_hex(6)}",
            "name": "Sample Employee Clusters",
            "algorithm": "kmeans_clustering",
            "source_id": int(ws.id),
            "source_name": workspace_name,
            "x_column": "salary",
            "y_column": "",
            "sql_text": "SELECT salary, age, tenure_years, performance_score FROM employees_sample",
            "trained_at": "",
            "metrics": {},
            "params": {},
            "model_data": {},
            "mlflow": {},
            "deployed": False,
        },
    ]

    added = 0
    for model in sample_models:
        if str(model.get("name") or "").strip().lower() in existing_names:
            continue
        models.insert(0, model)
        existing_names.add(str(model.get("name") or "").strip().lower())
        added += 1

    state["models"] = models[:200]
    _persist_ml_models_state(g.tenant, state)
    db.session.commit()

    flash(
        _(
            "Sample data ready: source '{source}' with {rows} rows and {models} sample models.",
            source=workspace_name,
            rows=240,
            models=added,
        ),
        "success",
    )
    flash(
        _(
            "Try these queries: SELECT age, salary, is_manager FROM employees_sample and SELECT salary, age, tenure_years, performance_score FROM employees_sample.",
        ),
        "info",
    )
    return redirect(url_for("ml.studio"))


@bp.post("/edit")
@login_required
def edit_model():
    _require_tenant()
    model_id = str(request.form.get("model_id") or "").strip()
    model_name = str(request.form.get("model_name") or "").strip()
    algorithm = str(request.form.get("algorithm") or "linear_regression").strip().lower()
    source_id = _to_int(request.form.get("source_id"), 0, 0, 2_000_000_000)
    sql_text = str(request.form.get("sql_text") or "").strip()
    x_column = str(request.form.get("x_column") or "").strip()
    y_column = str(request.form.get("y_column") or "").strip()

    if not model_id:
        flash(_("Modèle introuvable."), "error")
        return redirect(url_for("ml.studio"))
    if not model_name or not source_id:
        flash(_("Model name and source are required."), "error")
        return redirect(url_for("ml.studio"))

    src = DataSource.query.filter_by(id=source_id, tenant_id=g.tenant.id).first()
    if not src:
        flash(_("Selecione uma fonte válida."), "error")
        return redirect(url_for("ml.studio"))

    state = _ml_models_state_for_tenant(g.tenant)
    models = state.get("models") or []
    model = next((m for m in models if str(m.get("id")) == model_id), None)
    if not model:
        flash(_("Modèle introuvable."), "error")
        return redirect(url_for("ml.studio"))

    signature_before = (
        str(model.get("algorithm") or "").strip().lower(),
        int(_to_int(model.get("source_id"), 0, 0, 2_000_000_000)),
        str(model.get("sql_text") or "").strip(),
        str(model.get("x_column") or "").strip(),
        str(model.get("y_column") or "").strip(),
    )

    model["name"] = model_name[:120]
    model["algorithm"] = algorithm
    model["source_id"] = int(src.id)
    model["source_name"] = str(src.name or "")
    model["sql_text"] = sql_text[:12000]
    model["x_column"] = x_column[:120]
    model["y_column"] = y_column[:120]

    signature_after = (
        str(model.get("algorithm") or "").strip().lower(),
        int(_to_int(model.get("source_id"), 0, 0, 2_000_000_000)),
        str(model.get("sql_text") or "").strip(),
        str(model.get("x_column") or "").strip(),
        str(model.get("y_column") or "").strip(),
    )

    if signature_before != signature_after:
        model["trained_at"] = ""
        model["metrics"] = {}
        model["params"] = {}
        model["model_data"] = {}
        model["deployed"] = False
        mlflow_info = model.get("mlflow") if isinstance(model.get("mlflow"), dict) else {}
        next_mlflow = dict(mlflow_info)
        next_mlflow["sync_status"] = "stale"
        next_mlflow["last_sync_at"] = datetime.utcnow().isoformat()
        model["mlflow"] = next_mlflow

    _persist_ml_models_state(g.tenant, state)
    db.session.commit()
    flash(_("Modèle mis à jour."), "success")
    return redirect(url_for("ml.studio"))


def _train_model_internal(
    model_id: str,
    train_ratio: float,
    window: int,
    n_estimators: int,
    k_clusters: int,
) -> tuple[bool, str]:
    state = _ml_models_state_for_tenant(g.tenant)
    models = state.get("models") or []
    model = next((m for m in models if str(m.get("id")) == model_id), None)
    if not model:
        return False, _("Modèle introuvable.")

    src = DataSource.query.filter_by(id=int(model.get("source_id") or 0), tenant_id=g.tenant.id).first()
    if not src:
        return False, _("Selecione uma fonte válida.")

    sql_text = str(model.get("sql_text") or "").strip()
    if not sql_text:
        return False, _("SQL model query is required.")

    try:
        result = execute_sql(src, sql_text, params={"tenant_id": int(g.tenant.id)}, row_limit=2500)
    except QueryExecutionError as exc:
        return False, _("Erro ao executar query do modelo: {error}", error=str(exc))

    columns = [str(c) for c in (result.get("columns") or [])]
    rows = result.get("rows") or []
    if len(columns) < 1 or not rows:
        return False, _("La requête doit retourner au moins 1 colonne et des lignes.")

    x_col = str(model.get("x_column") or "").strip()
    y_col = str(model.get("y_column") or "").strip()
    if not x_col or x_col not in columns:
        metric_cols = _numeric_metric_fields(columns, rows)
        x_col = metric_cols[0] if len(metric_cols) >= 2 else columns[0]
    algo = str(model.get("algorithm") or "linear_regression").strip().lower()
    if algo != "kmeans_clustering":
        if not y_col or y_col not in columns:
            metric_cols = _numeric_metric_fields(columns, rows)
            y_col = metric_cols[1] if len(metric_cols) >= 2 else columns[min(1, len(columns) - 1)]

    x_idx = columns.index(x_col)
    y_idx = columns.index(y_col) if (y_col in columns and algo != "kmeans_clustering") else -1
    pairs: list[tuple[float, float]] = []
    x_values: list[float] = []
    for row in rows:
        if not isinstance(row, (list, tuple)) or x_idx >= len(row):
            continue
        x_val = _to_number(row[x_idx])
        if x_val is None:
            continue
        x_values.append(float(x_val))
        if y_idx >= 0 and y_idx < len(row):
            y_val = _to_number(row[y_idx])
            if y_val is not None:
                pairs.append((float(x_val), float(y_val)))

    if algo == "kmeans_clustering":
        if len(x_values) < 8:
            return False, _("Pas assez de lignes numériques pour entraîner le modèle (minimum 8).")
        model_data = _ml_fit_kmeans_1d(x_values, k_clusters)
        metrics = _ml_metrics(model_data, [])
        metrics["train_rows"] = len(x_values)
        metrics["total_rows"] = len(x_values)
        params = {"k_clusters": k_clusters, "train_ratio": train_ratio}
    else:
        if len(pairs) < 8:
            return False, _("Pas assez de lignes numériques pour entraîner le modèle (minimum 8).")

        pairs = sorted(pairs, key=lambda item: item[0])
        train_pairs, test_pairs = _ml_split_train_test(pairs, train_ratio)
        params = {
            "train_ratio": train_ratio,
            "window": window,
            "n_estimators": n_estimators,
            "k_clusters": k_clusters,
        }
        model_data = _ml_fit_model(train_pairs, algo, params)
        metrics = _ml_metrics(model_data, test_pairs, train_pairs)
        metrics["train_rows"] = len(train_pairs)
        metrics["total_rows"] = len(pairs)

    model["x_column"] = x_col
    model["y_column"] = y_col if algo != "kmeans_clustering" else ""
    model["trained_at"] = datetime.utcnow().isoformat()
    model["params"] = params
    model["model_data"] = model_data
    model["metrics"] = metrics

    retrain_url = url_for("ml.retrain_model", model_id=str(model.get("id") or ""), _external=True)
    mlflow_result = log_training_run(
        config=current_app.config,
        tenant_id=int(g.tenant.id),
        model=model,
        metrics=metrics,
        params=params,
        model_data=model_data,
        source=src,
        retrain_url=retrain_url,
    )
    if bool(mlflow_result.get("ok")):
        model["mlflow"] = {
            "run_id": str(mlflow_result.get("run_id") or ""),
            "experiment_id": str(mlflow_result.get("experiment_id") or ""),
            "run_url": str(mlflow_result.get("run_url") or ""),
            "last_sync_at": datetime.utcnow().isoformat(),
        }

    _persist_ml_models_state(g.tenant, state)
    db.session.commit()
    if bool(mlflow_result.get("ok")):
        return True, _("Modèle entraîné avec succès. Run MLflow synchronisé.")
    return True, _("Modèle entraîné avec succès.")


@bp.post("/train")
@login_required
def train_model():
    _require_tenant()
    model_id = str(request.form.get("model_id") or "").strip()
    train_ratio = float(_to_number(request.form.get("train_ratio")) or 0.8)
    window = _to_int(request.form.get("window"), 5, 2, 200)
    n_estimators = _to_int(request.form.get("n_estimators"), 15, 5, 200)
    k_clusters = _to_int(request.form.get("k_clusters"), 3, 2, 20)
    return_page = str(request.form.get("return_page") or "").strip().lower()

    ok, message = _train_model_internal(model_id, train_ratio, window, n_estimators, k_clusters)
    flash(message, "success" if ok else "error")
    return _redirect_to_ml_page(return_page)


@bp.get("/retrain/<model_id>")
@login_required
def retrain_model(model_id: str):
    _require_tenant()
    train_ratio = float(_to_number(request.args.get("train_ratio")) or 0.8)
    window = _to_int(request.args.get("window"), 5, 2, 200)
    n_estimators = _to_int(request.args.get("n_estimators"), 15, 5, 200)
    k_clusters = _to_int(request.args.get("k_clusters"), 3, 2, 20)

    ok, message = _train_model_internal(str(model_id or "").strip(), train_ratio, window, n_estimators, k_clusters)
    flash(message, "success" if ok else "error")

    return_to = str(request.args.get("return_to") or "").strip()
    tracking_uri = str(current_app.config.get("MLFLOW_TRACKING_URI") or "").strip()
    if return_to and tracking_uri and return_to.startswith(tracking_uri):
        return redirect(return_to)
    return redirect(url_for("ml.studio"))


@bp.post("/deploy")
@login_required
def deploy_model():
    _require_tenant()
    model_id = str(request.form.get("model_id") or "").strip()
    state = _ml_models_state_for_tenant(g.tenant)
    models = state.get("models") or []

    target = None
    for model in models:
        is_target = str(model.get("id")) == model_id
        model["deployed"] = bool(is_target)
        if is_target:
            target = model

    if not target:
        flash(_("Modèle introuvable."), "error")
        return redirect(url_for("ml.studio"))

    if not isinstance(target.get("model_data"), dict) or not target.get("model_data"):
        flash(_("Entraînez d'abord le modèle avant déploiement."), "warning")
        return redirect(url_for("ml.studio"))

    mlflow_info = target.get("mlflow") if isinstance(target.get("mlflow"), dict) else {}
    deploy_log = log_deployment_event(
        config=current_app.config,
        tenant_id=int(g.tenant.id),
        model=target,
        training_run_id=str(mlflow_info.get("run_id") or ""),
    )
    if bool(deploy_log.get("ok")):
        next_mlflow = dict(mlflow_info)
        next_mlflow["deployment_logged_at"] = datetime.utcnow().isoformat()
        target["mlflow"] = next_mlflow

    _persist_ml_models_state(g.tenant, state)
    db.session.commit()
    flash(_("Modèle déployé."), "success")
    return redirect(url_for("ml.studio"))


@bp.post("/delete")
@login_required
def delete_model():
    _require_tenant()
    model_id = str(request.form.get("model_id") or "").strip()

    state = _ml_models_state_for_tenant(g.tenant)
    models = state.get("models") or []
    next_models = [m for m in models if str(m.get("id")) != model_id]
    if len(next_models) == len(models):
        flash(_("Modèle introuvable."), "error")
        return redirect(url_for("ml.studio"))

    state["models"] = next_models
    _persist_ml_models_state(g.tenant, state)
    db.session.commit()
    flash(_("Modèle supprimé."), "success")
    return redirect(url_for("ml.studio"))


@bp.get("/predict")
@login_required
def predict_model():
    _require_tenant()
    model_id = str(request.args.get("model_id") or "").strip()
    x_raw = request.args.get("x")
    x_val = _to_number(x_raw)
    if not model_id or x_val is None:
        return jsonify({"ok": False, "error": _("Model and numeric x are required.")}), 400

    state = _ml_models_state_for_tenant(g.tenant)
    model = next((m for m in (state.get("models") or []) if str(m.get("id")) == model_id), None)
    if not model:
        return jsonify({"ok": False, "error": _("Modèle introuvable.")}), 404

    model_data = model.get("model_data") if isinstance(model.get("model_data"), dict) else {}
    if not model_data:
        return jsonify({"ok": False, "error": _("Model is not trained yet.")}), 400

    y_pred = _ml_predict(model_data, float(x_val))
    algorithm = str(model.get("algorithm") or "").strip().lower()
    payload: dict[str, Any] = {
        "ok": True,
        "model_id": model_id,
        "model_name": model.get("name"),
        "algorithm": model.get("algorithm"),
        "x": float(x_val),
        "y_pred": round(float(y_pred), 8),
        "y_column": model.get("y_column"),
    }
    if algorithm == "kmeans_clustering":
        centroids = [float(_to_number(c) or 0.0) for c in (model_data.get("centroids") or [])]
        if centroids:
            cluster_id = min(range(len(centroids)), key=lambda idx: abs(float(x_val) - centroids[idx]))
            payload["cluster_id"] = int(cluster_id)
            payload["centroid"] = centroids[cluster_id]
    return jsonify(
        payload
    )


@bp.get("/clusters/<model_id>")
@login_required
def cluster_preview(model_id: str):
    _require_tenant()
    target_id = str(model_id or "").strip()
    state = _ml_models_state_for_tenant(g.tenant)
    model = next((m for m in (state.get("models") or []) if str(m.get("id")) == target_id), None)
    if not model:
        return jsonify({"ok": False, "error": _("Modèle introuvable.")}), 404
    if not _is_unsupervised_algorithm(model.get("algorithm")):
        return jsonify({"ok": False, "error": _("Visualisation clusters disponible uniquement pour K-Means.")}), 400

    model_data = model.get("model_data") if isinstance(model.get("model_data"), dict) else {}
    centroids = [float(_to_number(c) or 0.0) for c in (model_data.get("centroids") or [])]
    if not centroids:
        return jsonify({"ok": False, "error": _("Entraînez le modèle de clustering avant visualisation.")}), 400

    src = DataSource.query.filter_by(id=int(model.get("source_id") or 0), tenant_id=g.tenant.id).first()
    if not src:
        return jsonify({"ok": False, "error": _("Selecione uma fonte válida.")}), 400

    sql_text = str(model.get("sql_text") or "").strip()
    if not sql_text:
        return jsonify({"ok": False, "error": _("SQL model query is required.")}), 400

    try:
        result = execute_sql(src, sql_text, params={"tenant_id": int(g.tenant.id)}, row_limit=1200)
    except QueryExecutionError as exc:
        return jsonify({"ok": False, "error": _("Erro ao executar query do modelo: {error}", error=str(exc))}), 400

    columns = [str(c) for c in (result.get("columns") or [])]
    rows = result.get("rows") or []
    if not columns or not rows:
        return jsonify({"ok": False, "error": _("La requête doit retourner des lignes pour visualiser les clusters.")}), 400

    x_col = str(model.get("x_column") or "").strip()
    if not x_col or x_col not in columns:
        metric_cols = _numeric_metric_fields(columns, rows)
        x_col = metric_cols[0] if metric_cols else columns[0]
    x_idx = columns.index(x_col)

    numeric_indices = [idx for idx, col in enumerate(columns) if str(col) != x_col and str(col) in _numeric_metric_fields(columns, rows)]
    secondary_idx = numeric_indices[0] if numeric_indices else -1

    points: list[dict[str, Any]] = []
    counts = [0 for _ in range(len(centroids))]
    sums = [0.0 for _ in range(len(centroids))]

    for ridx, row in enumerate(rows):
        if not isinstance(row, (list, tuple)) or x_idx >= len(row):
            continue
        x_val = _to_number(row[x_idx])
        if x_val is None:
            continue
        cidx = min(range(len(centroids)), key=lambda idx: abs(float(x_val) - centroids[idx]))
        counts[cidx] += 1
        sums[cidx] += float(x_val)

        y_plot = float(cidx) + (((ridx % 9) - 4) * 0.035)
        y_val = None
        if secondary_idx >= 0 and secondary_idx < len(row):
            y_val = _to_number(row[secondary_idx])

        points.append(
            {
                "x": round(float(x_val), 6),
                "y": round(float(y_plot), 6),
                "cluster": int(cidx),
                "secondary": (round(float(y_val), 6) if y_val is not None else None),
            }
        )

    centroid_order = sorted(range(len(centroids)), key=lambda idx: centroids[idx])
    rank_by_cluster = {cluster_idx: rank for rank, cluster_idx in enumerate(centroid_order)}

    clusters: list[dict[str, Any]] = []
    total = max(1, len(points))
    for idx, centroid in enumerate(centroids):
        rank = rank_by_cluster.get(idx, idx)
        avg_value = (sums[idx] / counts[idx]) if counts[idx] > 0 else centroid
        clusters.append(
            {
                "id": int(idx),
                "centroid": round(float(centroid), 6),
                "name": _cluster_name_by_rank(rank, len(centroids)),
                "count": int(counts[idx]),
                "share_pct": round((float(counts[idx]) * 100.0) / float(total), 2),
                "avg_value": round(float(avg_value), 6),
            }
        )

    return jsonify(
        {
            "ok": True,
            "model_id": target_id,
            "model_name": str(model.get("name") or ""),
            "x_label": x_col,
            "points": points[:500],
            "clusters": clusters,
            "total_points": len(points),
        }
    )


@bp.get("/query-data/<model_id>")
@login_required
def query_data_preview(model_id: str):
    _require_tenant()

    target_id = str(model_id or "").strip()
    page = _to_int(request.args.get("page"), 1, 1, 10_000)
    page_size = _to_int(request.args.get("page_size"), 25, 5, 100)

    state = _ml_models_state_for_tenant(g.tenant)
    model = next((m for m in (state.get("models") or []) if str(m.get("id")) == target_id), None)
    if not model:
        return jsonify({"ok": False, "error": _("Modèle introuvable.")}), 404

    src = DataSource.query.filter_by(id=int(model.get("source_id") or 0), tenant_id=g.tenant.id).first()
    if not src:
        return jsonify({"ok": False, "error": _("Selecione uma fonte válida.")}), 400

    sql_text = str(model.get("sql_text") or "").strip()
    if not sql_text:
        return jsonify({"ok": False, "error": _("SQL model query is required.")}), 400

    end_idx = page * page_size
    start_idx = max(0, (page - 1) * page_size)
    hard_cap = 5000
    row_limit = min(hard_cap, end_idx + 1)

    try:
        result = execute_sql(src, sql_text, params={"tenant_id": int(g.tenant.id)}, row_limit=row_limit)
    except QueryExecutionError as exc:
        return jsonify({"ok": False, "error": _("Erro ao executar query do modelo: {error}", error=str(exc))}), 400

    columns = [str(c) for c in (result.get("columns") or [])]
    all_rows = result.get("rows") or []
    chunk_rows = all_rows[start_idx:end_idx]
    has_more = len(all_rows) > end_idx and end_idx < hard_cap

    return jsonify(
        {
            "ok": True,
            "model_id": target_id,
            "model_name": str(model.get("name") or ""),
            "columns": columns,
            "rows": chunk_rows,
            "page": page,
            "page_size": page_size,
            "has_more": bool(has_more),
            "loaded_rows": min(len(all_rows), hard_cap),
            "elapsed_ms": result.get("elapsed_ms"),
        }
    )


@bp.post("/query-preview")
@login_required
def query_preview_from_form():
    _require_tenant()

    source_id = _to_int(request.form.get("source_id"), 0, 0, 2_000_000_000)
    sql_text = str(request.form.get("sql_text") or "").strip()
    page = _to_int(request.form.get("page"), 1, 1, 10_000)
    page_size = _to_int(request.form.get("page_size"), 25, 5, 100)

    if not source_id:
        return jsonify({"ok": False, "error": _("Model name and source are required.")}), 400
    if not sql_text:
        return jsonify({"ok": False, "error": _("SQL model query is required.")}), 400

    src = DataSource.query.filter_by(id=source_id, tenant_id=g.tenant.id).first()
    if not src:
        return jsonify({"ok": False, "error": _("Selecione uma fonte válida.")}), 400

    end_idx = page * page_size
    start_idx = max(0, (page - 1) * page_size)
    hard_cap = 5000
    row_limit = min(hard_cap, end_idx + 1)

    try:
        result = execute_sql(src, sql_text, params={"tenant_id": int(g.tenant.id)}, row_limit=row_limit)
    except QueryExecutionError as exc:
        return jsonify({"ok": False, "error": _("Erro ao executar query do modelo: {error}", error=str(exc))}), 400

    columns = [str(c) for c in (result.get("columns") or [])]
    all_rows = result.get("rows") or []
    chunk_rows = all_rows[start_idx:end_idx]
    has_more = len(all_rows) > end_idx and end_idx < hard_cap

    return jsonify(
        {
            "ok": True,
            "columns": columns,
            "rows": chunk_rows,
            "page": page,
            "page_size": page_size,
            "has_more": bool(has_more),
            "loaded_rows": min(len(all_rows), hard_cap),
            "elapsed_ms": result.get("elapsed_ms"),
        }
    )


@bp.post("/sentiment-evaluate")
@login_required
def sentiment_evaluate():
    _require_tenant()

    source_id = _to_int(request.form.get("source_id"), 0, 0, 2_000_000_000)
    sql_text = str(request.form.get("sql_text") or "").strip()
    text_column = str(request.form.get("text_column") or "").strip()
    limit_rows = _to_int(request.form.get("limit_rows"), 500, 20, 5000)

    if not source_id:
        return jsonify({"ok": False, "error": _("Selecione uma fonte válida.")}), 400
    if not sql_text:
        return jsonify({"ok": False, "error": _("SQL model query is required.")}), 400

    src = DataSource.query.filter_by(id=source_id, tenant_id=g.tenant.id).first()
    if not src:
        return jsonify({"ok": False, "error": _("Selecione uma fonte válida.")}), 400

    try:
        result = execute_sql(src, sql_text, params={"tenant_id": int(g.tenant.id)}, row_limit=limit_rows)
    except QueryExecutionError as exc:
        return jsonify({"ok": False, "error": _("Erro ao executar query do modelo: {error}", error=str(exc))}), 400

    columns = [str(c) for c in (result.get("columns") or [])]
    rows = result.get("rows") or []

    # Be tolerant to row shapes across engines/adapters (list/tuple/dict/Row).
    def _row_value(row: Any, col_idx: int, col_name: str) -> Any:
        if isinstance(row, (list, tuple)):
            return row[col_idx] if 0 <= col_idx < len(row) else None
        if isinstance(row, dict):
            if col_name in row:
                return row.get(col_name)
            # Fallback for case-insensitive dict keys.
            lower_map = {str(k).lower(): v for k, v in row.items()}
            return lower_map.get(str(col_name).lower())
        # SQLAlchemy Row can expose mapping via _mapping.
        mapping = getattr(row, "_mapping", None)
        if mapping is not None:
            if col_name in mapping:
                return mapping.get(col_name)
            lower_map = {str(k).lower(): v for k, v in mapping.items()}
            return lower_map.get(str(col_name).lower())
        return None
    if not columns or not rows:
        return jsonify({"ok": False, "error": _("La requête doit retourner au moins 1 colonne et des lignes.")}), 400

    if text_column and text_column in columns:
        text_idx = columns.index(text_column)
    else:
        text_idx = -1
        for idx, _ in enumerate(columns):
            col_name = columns[idx]
            sample_values = []
            for row in rows[:50]:
                val = _row_value(row, idx, col_name)
                if val is not None:
                    sample_values.append(str(val))
            if sample_values and any(any(ch.isalpha() for ch in txt) for txt in sample_values):
                text_idx = idx
                break

    if text_idx < 0:
        return jsonify({"ok": False, "error": _("Impossible d'identifier une colonne texte pour le sentiment.")}), 400

    selected_col = columns[text_idx]
    total = 0
    positive = 0
    neutral = 0
    negative = 0
    score_sum = 0.0
    pos_counter: Counter[str] = Counter()
    neg_counter: Counter[str] = Counter()
    samples: list[dict[str, Any]] = []

    for row in rows:
        raw_text = _row_value(row, text_idx, selected_col)
        if raw_text is None:
            continue
        txt = str(raw_text).strip()
        if not txt:
            continue
        total += 1
        score, pos_words, neg_words = _score_sentiment_text(txt)
        score_sum += score
        pos_counter.update(pos_words)
        neg_counter.update(neg_words)
        if score > 0.15:
            positive += 1
            cls = "positive"
        elif score < -0.15:
            negative += 1
            cls = "negative"
        else:
            neutral += 1
            cls = "neutral"
        if len(samples) < 12:
            samples.append({"text": txt[:220], "score": round(score, 4), "label": cls})

    if total == 0:
        return jsonify({"ok": False, "error": _("Aucun commentaire texte exploitable trouvé.")}), 400

    top_positive = [{"word": w, "count": int(c)} for w, c in pos_counter.most_common(15)]
    top_negative = [{"word": w, "count": int(c)} for w, c in neg_counter.most_common(15)]
    avg_score = score_sum / float(total)

    return jsonify(
        {
            "ok": True,
            "column": selected_col,
            "rows_analyzed": total,
            "summary": {
                "positive": positive,
                "neutral": neutral,
                "negative": negative,
                "avg_score": round(avg_score, 6),
            },
            "top_positive_words": top_positive,
            "top_negative_words": top_negative,
            "samples": samples,
        }
    )


@bp.get("/sentiment-snapshots")
@login_required
def sentiment_snapshots_list():
    _require_tenant()
    state = _ml_models_state_for_tenant(g.tenant)
    snapshots = state.get("sentiment_snapshots") or []
    return jsonify({"ok": True, "snapshots": snapshots[:100]})


@bp.post("/sentiment-snapshots/save")
@login_required
def sentiment_snapshots_save():
    _require_tenant()

    source_id = _to_int(request.form.get("source_id"), 0, 0, 2_000_000_000)
    text_column = str(request.form.get("text_column") or "").strip()
    sql_text = str(request.form.get("sql_text") or "").strip()[:12000]
    analysis_json = str(request.form.get("analysis_json") or "").strip()

    if not source_id or not analysis_json:
        return jsonify({"ok": False, "error": _("Sélectionnez une source et lancez d'abord l'analyse.")}), 400

    try:
        analysis = json.loads(analysis_json)
    except Exception:
        return jsonify({"ok": False, "error": _("Impossible de sauvegarder le snapshot.")}), 400

    source_name = ""
    src = DataSource.query.filter_by(id=source_id, tenant_id=g.tenant.id).first()
    if src:
        source_name = str(src.name or "")

    snapshot = {
        "id": f"snap_{secrets.token_hex(6)}",
        "created_at": datetime.utcnow().isoformat(timespec="seconds") + "Z",
        "source_id": int(source_id),
        "source_name": source_name,
        "text_column": text_column,
        "sql_text": sql_text,
        "rows_analyzed": _to_int(analysis.get("rows_analyzed"), 0, 0, 5_000_000),
        "summary": analysis.get("summary") if isinstance(analysis.get("summary"), dict) else {},
        "top_positive_words": analysis.get("top_positive_words") if isinstance(analysis.get("top_positive_words"), list) else [],
        "top_negative_words": analysis.get("top_negative_words") if isinstance(analysis.get("top_negative_words"), list) else [],
    }

    state = _ml_models_state_for_tenant(g.tenant)
    snapshots = state.get("sentiment_snapshots") or []
    snapshots.insert(0, snapshot)
    state["sentiment_snapshots"] = snapshots[:200]
    _persist_ml_models_state(g.tenant, state)
    db.session.commit()

    return jsonify({"ok": True, "message": _("Snapshot sauvegardé."), "snapshot": snapshot})


@bp.post("/sentiment-snapshots/log-mlflow")
@login_required
def sentiment_snapshots_log_mlflow():
    _require_tenant()

    source_id = _to_int(request.form.get("source_id"), 0, 0, 2_000_000_000)
    text_column = str(request.form.get("text_column") or "").strip()
    sql_text = str(request.form.get("sql_text") or "").strip()[:12000]
    analysis_json = str(request.form.get("analysis_json") or "").strip()

    if not source_id or not analysis_json:
        return jsonify({"ok": False, "error": _("Sélectionnez une source et lancez d'abord l'analyse.")}), 400

    src = DataSource.query.filter_by(id=source_id, tenant_id=g.tenant.id).first()
    if not src:
        return jsonify({"ok": False, "error": _("Selecione uma fonte válida.")}), 400

    try:
        analysis = json.loads(analysis_json)
    except Exception:
        return jsonify({"ok": False, "error": _("Impossible de sauvegarder le snapshot.")}), 400

    snapshot = {
        "created_at": datetime.utcnow().isoformat(timespec="seconds") + "Z",
        "source_id": int(source_id),
        "source_name": str(src.name or ""),
        "text_column": text_column,
        "sql_text": sql_text,
        "rows_analyzed": _to_int(analysis.get("rows_analyzed"), 0, 0, 5_000_000),
        "summary": analysis.get("summary") if isinstance(analysis.get("summary"), dict) else {},
        "top_positive_words": analysis.get("top_positive_words") if isinstance(analysis.get("top_positive_words"), list) else [],
        "top_negative_words": analysis.get("top_negative_words") if isinstance(analysis.get("top_negative_words"), list) else [],
    }

    mlflow_log = log_sentiment_snapshot_event(
        config=current_app.config,
        tenant_id=int(g.tenant.id),
        source=src,
        snapshot=snapshot,
    )

    if not bool(mlflow_log.get("ok")):
        return jsonify({"ok": False, "error": _("MLflow indisponible pour ce snapshot."), "details": mlflow_log}), 400

    return jsonify(
        {
            "ok": True,
            "message": _("Snapshot envoyé vers MLflow."),
            "mlflow": {
                "run_id": str(mlflow_log.get("run_id") or ""),
                "experiment_id": str(mlflow_log.get("experiment_id") or ""),
                "run_url": str(mlflow_log.get("run_url") or ""),
            },
        }
    )
