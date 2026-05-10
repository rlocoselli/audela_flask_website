from __future__ import annotations

from datetime import datetime
import copy
import csv
import io
import json
import math
import os
import random
import re
import secrets
from collections import Counter
from typing import Any
from urllib.parse import parse_qsl, quote, urlencode, urlsplit, urlunsplit

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
from ...services.pdf_export import table_to_pdf_bytes
from ...services.pptx_export import table_to_pptx_bytes
from ...services.mlflow_service import (
    list_tenant_runs,
    log_deployment_event,
    log_model_created_event,
    log_sentiment_snapshot_event,
    log_training_run,
)
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


def _json_safe_scalar(value: Any) -> Any:
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    try:
        return float(value)
    except Exception:
        return str(value)


def _json_safe_rows(rows: list[Any], max_rows: int) -> list[list[Any]]:
    safe_rows: list[list[Any]] = []
    for row in rows[:max_rows]:
        if isinstance(row, (list, tuple)):
            safe_rows.append([_json_safe_scalar(item) for item in row])
        else:
            safe_rows.append([_json_safe_scalar(row)])
    return safe_rows


def _infer_column_type(values: list[Any]) -> str:
    non_null = [v for v in values if v is not None and str(v).strip() != ""]
    if not non_null:
        return "unknown"
    bool_like = 0
    numeric_like = 0
    for val in non_null:
        if isinstance(val, bool):
            bool_like += 1
            continue
        text = str(val).strip().lower()
        if text in {"true", "false", "0", "1", "yes", "no"}:
            bool_like += 1
            continue
        if _to_number(val) is not None:
            numeric_like += 1
    if bool_like == len(non_null):
        return "boolean"
    if numeric_like == len(non_null):
        return "number"
    return "string"


def _parse_predict_values(raw_value: Any) -> list[float]:
    raw = str(raw_value or "").strip()
    if not raw:
        return []
    # Accept comma/semicolon/newline/space separated values for batch predictions.
    chunks = [c for c in re.split(r"[\s,;]+", raw) if c]
    values: list[float] = []
    for chunk in chunks:
        num = _to_number(chunk)
        if num is not None:
            values.append(float(num))
    return values


def _is_allowed_mlflow_return_url(return_to: str, tracking_uri: str) -> bool:
    target = str(return_to or "").strip()
    base = str(tracking_uri or "").strip()
    if not target or not base:
        return False
    try:
        target_parts = urlsplit(target)
        base_parts = urlsplit(base)
    except Exception:
        return False
    if not target_parts.scheme or not target_parts.netloc:
        return False
    return (
        target_parts.scheme.lower() == base_parts.scheme.lower()
        and target_parts.netloc.lower() == base_parts.netloc.lower()
    )


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


def _load_model_prediction_context(model: dict[str, Any], row_limit: int = 320) -> dict[str, Any]:
    src = DataSource.query.filter_by(id=int(model.get("source_id") or 0), tenant_id=g.tenant.id).first()
    if not src:
        return {"ok": False, "error": _("Selecione uma fonte válida.")}

    sql_text = str(model.get("sql_text") or "").strip()
    if not sql_text:
        return {"ok": False, "error": _("SQL model query is required.")}

    try:
        result = execute_sql(src, sql_text, params={"tenant_id": int(g.tenant.id)}, row_limit=max(50, int(row_limit or 320)))
    except QueryExecutionError as exc:
        return {"ok": False, "error": _("Erro ao executar query do modelo: {error}", error=str(exc))}

    columns = [str(c) for c in (result.get("columns") or [])]
    rows = result.get("rows") or []
    if not columns or not rows:
        return {"ok": False, "error": _("La requête doit retourner au moins 1 colonne et des lignes.")}

    algorithm = str(model.get("algorithm") or "linear_regression").strip().lower()
    x_col = str(model.get("x_column") or "").strip()
    y_col = str(model.get("y_column") or "").strip()
    metric_cols = _numeric_metric_fields(columns, rows)

    if not x_col or x_col not in columns:
        x_col = metric_cols[0] if len(metric_cols) >= 1 else columns[0]
    if algorithm != "kmeans_clustering" and (not y_col or y_col not in columns):
        if len(metric_cols) >= 2:
            y_col = metric_cols[1] if metric_cols[0] == x_col else metric_cols[0] if metric_cols[0] != x_col else metric_cols[1]
        elif len(columns) >= 2:
            y_col = columns[1 if columns[0] == x_col else 0]

    x_idx = columns.index(x_col)
    y_idx = columns.index(y_col) if (algorithm != "kmeans_clustering" and y_col in columns) else -1

    pairs: list[tuple[float, float]] = []
    x_values: list[float] = []
    for row in rows:
        if not isinstance(row, (list, tuple)) or x_idx >= len(row):
            continue
        x_val = _to_number(row[x_idx])
        if x_val is None:
            continue
        x_num = float(x_val)
        x_values.append(x_num)
        if y_idx >= 0 and y_idx < len(row):
            y_val = _to_number(row[y_idx])
            if y_val is not None:
                pairs.append((x_num, float(y_val)))

    pairs = sorted(pairs, key=lambda item: item[0])
    x_values = sorted(x_values)
    return {
        "ok": True,
        "source_name": str(src.name or ""),
        "columns": columns,
        "rows": rows,
        "x_column": x_col,
        "y_column": y_col,
        "pairs": pairs,
        "x_values": x_values,
        "domain": {
            "x_min": x_values[0] if x_values else None,
            "x_max": x_values[-1] if x_values else None,
            "train_rows": len(pairs) if pairs else len(x_values),
        },
    }


def _prediction_quality_label(metrics: dict[str, Any]) -> tuple[str, str]:
    fit_indicator = str(metrics.get("fit_indicator") or "balanced").strip().lower()
    if fit_indicator == "good_fit":
        return _("Good fit"), "success"
    if fit_indicator == "overfit":
        return _("Overfit risk"), "warning"
    if fit_indicator == "underfit":
        return _("Underfit risk"), "danger"
    if fit_indicator == "insufficient_data":
        return _("Insufficient data"), "secondary"
    return _("Balanced"), "info"


def _build_prediction_story(
    model: dict[str, Any],
    predictions: list[dict[str, Any]],
    metrics: dict[str, Any],
    context: dict[str, Any],
    algorithm: str,
    accuracy_type: str,
) -> dict[str, Any]:
    quality_label, quality_tone = _prediction_quality_label(metrics)
    insights: list[str] = []
    recommended_actions: list[str] = []
    chart_payloads: list[dict[str, Any]] = []

    domain = context.get("domain") if isinstance(context.get("domain"), dict) else {}
    x_min = _to_number(domain.get("x_min"))
    x_max = _to_number(domain.get("x_max"))
    prediction_values = [float(_to_number(p.get("y_pred")) or 0.0) for p in predictions]
    x_values = [float(_to_number(p.get("x")) or 0.0) for p in predictions]

    requested_outside_domain = False
    if x_values and x_min is not None and x_max is not None:
        requested_outside_domain = any(float(x) < float(x_min) or float(x) > float(x_max) for x in x_values)

    if algorithm == "kmeans_clustering":
        cluster_ids = [int(p.get("cluster_id")) for p in predictions if p.get("cluster_id") is not None]
        if cluster_ids:
            counts = Counter(cluster_ids)
            dominant_cluster, dominant_count = counts.most_common(1)[0]
            insights.append(
                _("Most requested points fall into cluster #{cluster} ({count} point(s)).", cluster=dominant_cluster, count=dominant_count)
            )
            recommended_actions.append(_("Review cluster preview to compare centroid distance and group spread before acting on the segment."))
        chart_payloads.append(
            {
                "kind": "bar",
                "title": _("Cluster assignments"),
                "labels": [str(p.get("x")) for p in predictions],
                "series": [{"name": _("Cluster"), "data": cluster_ids}],
            }
        )
    elif accuracy_type == "classification":
        probas = [float(_to_number(p.get("predicted_proba")) or 0.0) for p in predictions]
        positives = [int(p.get("predicted_class") or 0) for p in predictions]
        avg_proba = (sum(probas) / len(probas)) if probas else 0.0
        pos_rate = (sum(positives) * 100.0 / len(positives)) if positives else 0.0
        insights.append(_("Average probability of the positive class is {value}%.", value=round(avg_proba, 2)))
        insights.append(_("{value}% of requested cases are classified as positive.", value=round(pos_rate, 2)))
        if requested_outside_domain:
            insights.append(_("Some requested X values are outside the training range, so classification confidence should be reviewed manually."))
        recommended_actions.append(_("Focus on cases near the decision threshold to review overrides or business rules."))
        chart_payloads.append(
            {
                "kind": "bar",
                "title": _("Predicted probabilities"),
                "labels": [str(p.get("x")) for p in predictions],
                "series": [{"name": _("Probability %"), "data": probas}],
            }
        )
    else:
        pred_min = min(prediction_values) if prediction_values else 0.0
        pred_max = max(prediction_values) if prediction_values else 0.0
        pred_avg = (sum(prediction_values) / len(prediction_values)) if prediction_values else 0.0
        rmse = _to_number(metrics.get("rmse"))
        history_pairs = context.get("pairs") if isinstance(context.get("pairs"), list) else []
        recent_history = history_pairs[-24:] if history_pairs else []
        recent_actual_avg = (sum(y for _, y in recent_history) / len(recent_history)) if recent_history else None

        if len(prediction_values) >= 2:
            delta = float(prediction_values[-1]) - float(prediction_values[0])
            direction = _("up") if delta > 0 else (_("down") if delta < 0 else _("flat"))
            insights.append(_("Predicted path is trending {direction} across the requested horizon.", direction=direction))
        insights.append(_("Predicted range spans from {low} to {high}.", low=round(pred_min, 4), high=round(pred_max, 4)))
        if recent_actual_avg is not None:
            gap = pred_avg - float(recent_actual_avg)
            if abs(gap) > 1e-9:
                gap_direction = _("above") if gap > 0 else _("below")
                insights.append(
                    _("Average forecast is {direction} the recent actual average by {gap}.", direction=gap_direction, gap=round(abs(gap), 4))
                )
        if rmse is not None:
            confidence_pct = max(0.0, 100.0 - ((float(rmse) / max(abs(pred_avg), 1e-9)) * 100.0)) if abs(pred_avg) > 1e-9 else None
            if confidence_pct is not None:
                insights.append(_("Model uncertainty is roughly ±{rmse} around each point.", rmse=round(float(rmse), 4)))
        if requested_outside_domain:
            insights.append(_("Some requested X values are outside the observed training range. Treat those points as extrapolation."))

        recommended_actions.append(_("Compare forecast points with the fitted historical curve before using them in reporting or planning."))
        recommended_actions.append(_("If the model is used for budgeting, validate out-of-range points with a business assumption note."))

        if recent_history:
            history_x = [round(float(x), 6) for x, _ in recent_history]
            history_actual = [round(float(y), 6) for _, y in recent_history]
            history_fitted = [round(float(_ml_predict(model.get("model_data") or {}, x)), 6) for x, _ in recent_history]
            chart_payloads.append(
                {
                    "kind": "line",
                    "title": _("Historical actual vs fitted"),
                    "labels": history_x,
                    "series": [
                        {"name": _("Actual"), "data": history_actual},
                        {"name": _("Fitted"), "data": history_fitted},
                    ],
                }
            )
        chart_payloads.append(
            {
                "kind": "line",
                "title": _("Requested forecast"),
                "labels": [round(float(x), 6) for x in x_values],
                "series": [{"name": _("Predicted"), "data": [round(float(v), 6) for v in prediction_values]}],
            }
        )

    headline = _("Prediction Lab")
    if accuracy_type == "classification":
        headline = _("Classification prediction")
    elif algorithm == "kmeans_clustering":
        headline = _("Cluster assignment")
    elif len(predictions) > 1:
        headline = _("Forecast scenario")

    summary = {
        "headline": headline,
        "quality_label": quality_label,
        "quality_tone": quality_tone,
        "source_name": context.get("source_name") or model.get("source_name") or "",
        "requested_points": len(predictions),
        "train_rows": int(domain.get("train_rows") or 0),
        "x_min": x_min,
        "x_max": x_max,
    }
    return {
        "summary": summary,
        "insights": insights[:5],
        "recommended_actions": recommended_actions[:4],
        "chart_payloads": chart_payloads[:3],
    }


def _build_prediction_payload(model: dict[str, Any], x_values: list[float]) -> dict[str, Any]:
    model_id = str(model.get("id") or "").strip()
    model_data = model.get("model_data") if isinstance(model.get("model_data"), dict) else {}
    if not model_data:
        return {"ok": False, "error": _("Model is not trained yet.")}

    context = _load_model_prediction_context(model, row_limit=320)
    if not bool(context.get("ok")):
        return {"ok": False, "error": str(context.get("error") or _("Prediction context unavailable."))}

    predictions: list[dict[str, Any]] = []
    algorithm = str(model.get("algorithm") or "").strip().lower()
    metrics = model.get("metrics") if isinstance(model.get("metrics"), dict) else {}
    accuracy_type = str(metrics.get("accuracy_type") or "").strip().lower()
    class_threshold = float(_to_number(model_data.get("classification_threshold")) or 0.5)
    for x_val in x_values:
        y_pred = _ml_predict(model_data, float(x_val))
        row: dict[str, Any] = {
            "x": float(x_val),
            "y_pred": round(float(y_pred), 8),
        }
        if accuracy_type == "classification":
            proba = max(0.0, min(1.0, float(y_pred)))
            row["predicted_proba"] = round(proba * 100.0, 2)
            row["predicted_class"] = int(1 if proba >= class_threshold else 0)
        if algorithm == "kmeans_clustering":
            centroids = [float(_to_number(c) or 0.0) for c in (model_data.get("centroids") or [])]
            if centroids:
                cluster_id = min(range(len(centroids)), key=lambda idx: abs(float(x_val) - centroids[idx]))
                row["cluster_id"] = int(cluster_id)
                row["centroid"] = centroids[cluster_id]
        predictions.append(row)

    story = _build_prediction_story(model, predictions, metrics, context, algorithm, accuracy_type)
    history_pairs = context.get("pairs") if isinstance(context.get("pairs"), list) else []
    history_preview = [
        {
            "x": round(float(x), 6),
            "actual": round(float(y), 6),
            "predicted": round(float(_ml_predict(model_data, x)), 6),
        }
        for x, y in history_pairs[-32:]
    ]

    payload: dict[str, Any] = {
        "ok": True,
        "model_id": model_id,
        "model_name": model.get("name"),
        "algorithm": model.get("algorithm"),
        "x": predictions[0]["x"],
        "y_pred": predictions[0]["y_pred"],
        "predictions": predictions,
        "y_column": model.get("y_column"),
        "x_column": model.get("x_column"),
        "accuracy_type": accuracy_type,
        "classification_threshold": class_threshold if accuracy_type == "classification" else None,
        "metrics": metrics,
        "summary": story.get("summary") or {},
        "insights": story.get("insights") or [],
        "recommended_actions": story.get("recommended_actions") or [],
        "chart_payloads": story.get("chart_payloads") or [],
        "history_preview": history_preview,
    }
    if algorithm == "kmeans_clustering" and predictions:
        first = predictions[0]
        if "cluster_id" in first:
            payload["cluster_id"] = first["cluster_id"]
            payload["centroid"] = first["centroid"]
    return payload


def _prediction_export_table(payload: dict[str, Any]) -> tuple[list[str], list[list[Any]]]:
    rows = payload.get("predictions") if isinstance(payload.get("predictions"), list) else []
    accuracy_type = str(payload.get("accuracy_type") or "").strip().lower()
    algorithm = str(payload.get("algorithm") or "").strip().lower()
    if algorithm == "kmeans_clustering":
        columns = ["x", "centroid", "cluster"]
        values = [[r.get("x"), r.get("y_pred"), r.get("cluster_id")] for r in rows]
        return columns, values
    if accuracy_type == "classification":
        columns = ["x", "predicted_class", "predicted_probability"]
        values = [[r.get("x"), r.get("predicted_class"), r.get("predicted_proba")] for r in rows]
        return columns, values
    columns = ["x", str(payload.get("y_column") or "predicted")]
    values = [[r.get("x"), r.get("y_pred")] for r in rows]
    return columns, values


def _prediction_export_analysis(payload: dict[str, Any]) -> str:
    lines: list[str] = []
    summary = payload.get("summary") if isinstance(payload.get("summary"), dict) else {}
    if summary.get("headline"):
        lines.append(str(summary.get("headline")))
    for item in (payload.get("insights") or [])[:5]:
        lines.append(f"- {item}")
    if payload.get("recommended_actions"):
        lines.append("")
        lines.append("Actions")
        for item in (payload.get("recommended_actions") or [])[:4]:
            lines.append(f"- {item}")
    return "\n".join(str(x) for x in lines if str(x or "").strip())


def _binary_best_threshold(y_true: list[float], y_pred: list[float]) -> float:
    """Pick a stable class threshold for binary tasks using train predictions."""
    if not y_true or not y_pred or len(y_true) != len(y_pred):
        return 0.5

    truth = [int(round(float(v))) for v in y_true]
    probs = [max(0.0, min(1.0, float(v))) for v in y_pred]
    candidates = sorted({0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9, *probs})

    best_thr = 0.5
    best_score = -1.0
    for thr in candidates:
        tp = fp = tn = fn = 0
        for t, p in zip(truth, probs):
            cls = 1 if p >= thr else 0
            if cls == 1 and t == 1:
                tp += 1
            elif cls == 1 and t == 0:
                fp += 1
            elif cls == 0 and t == 0:
                tn += 1
            else:
                fn += 1

        tpr = (tp / (tp + fn)) if (tp + fn) else 0.0
        tnr = (tn / (tn + fp)) if (tn + fp) else 0.0
        balanced_acc = 0.5 * (tpr + tnr)
        pred_pos = tp + fp
        precision = (tp / pred_pos) if pred_pos else 0.0
        # Tie-break with F1 to avoid trivial all-zero/all-one solutions.
        f1 = (2.0 * precision * tpr / (precision + tpr)) if (precision + tpr) else 0.0
        score = balanced_acc + (0.05 * f1)
        if score > best_score:
            best_score = score
            best_thr = float(thr)

    return round(min(0.95, max(0.05, best_thr)), 4)


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
        threshold = float(_to_number(model_data.get("classification_threshold")) or 0.5)
        correct = 0
        for truth, pred in zip(vals_true, vals_pred):
            pred_cls = 1 if float(pred) >= threshold else 0
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
    jupyter_embed_url = str(current_app.config.get("JUPYTER_EMBED_URL") or "").strip()
    jupyterhub_base_url = str(current_app.config.get("JUPYTERHUB_BASE_URL") or "").strip()
    jupyter_embed_token = str(current_app.config.get("JUPYTER_EMBED_TOKEN") or "").strip()
    requested_project = str(request.args.get("project") or "default").strip()
    project_slug = _safe_project_slug(requested_project)
    project_workspace = _ensure_tenant_project_workspace(int(g.tenant.id), project_slug)
    project_tree_rel = project_workspace["jupyter_tree_rel"]
    if jupyterhub_base_url:
        jupyter_embed_url = _build_jupyterhub_project_url(
            jupyterhub_base_url,
            current_user.email,
            project_tree_rel,
        )
    tenant_notebook_rel_url = project_tree_rel.replace("\\", "/")
    if jupyter_embed_url:
        try:
            parsed = urlsplit(jupyter_embed_url)
            path = parsed.path or "/lab"
            normalized = path.rstrip("/")
            if "/lab/tree/" not in path:
                if normalized.endswith("/lab"):
                    path = f"{normalized}/tree/{quote(tenant_notebook_rel_url, safe='/')}"
                elif normalized.endswith("/tree"):
                    path = f"{normalized}/{quote(tenant_notebook_rel_url, safe='/')}"
                else:
                    path = f"{normalized}/lab/tree/{quote(tenant_notebook_rel_url, safe='/')}"
            jupyter_embed_url = urlunsplit((parsed.scheme, parsed.netloc, path, parsed.query, parsed.fragment))
        except Exception:
            pass
    if jupyter_embed_url and jupyter_embed_token:
        try:
            parsed = urlsplit(jupyter_embed_url)
            params = dict(parse_qsl(parsed.query, keep_blank_values=True))
            if "token" not in params:
                params["token"] = jupyter_embed_token
                jupyter_embed_url = urlunsplit(
                    (parsed.scheme, parsed.netloc, parsed.path, urlencode(params), parsed.fragment)
                )
        except Exception:
            pass
    tenant_mlflow_runs: list[dict[str, Any]] = []
    mlflow_runs_error = ""
    if page_key == "mlflow":
        mlflow_result = list_tenant_runs(config=current_app.config, tenant_id=int(g.tenant.id), max_results=40)
        tenant_mlflow_runs = mlflow_result.get("runs") if isinstance(mlflow_result.get("runs"), list) else []
        if not bool(mlflow_result.get("ok")):
            mlflow_runs_error = str(mlflow_result.get("error") or mlflow_result.get("reason") or "")

    # Build a direct link to START_HERE.ipynb so users land on the guided notebook.
    start_here_url = ""
    if jupyter_embed_url:
        try:
            parsed = urlsplit(jupyter_embed_url)
            # Strip any existing /tree/... path so we can construct an exact file link.
            base_lab = parsed.path
            if "/tree/" in base_lab:
                base_lab = base_lab[: base_lab.index("/tree/")]
            start_here_path = f"{base_lab.rstrip('/')}/tree/{quote(project_tree_rel + '/START_HERE.ipynb', safe='/')}"
            start_here_url = urlunsplit((parsed.scheme, parsed.netloc, start_here_path, parsed.query, parsed.fragment))
        except Exception:
            pass

    return render_template(
        "ml/studio.html",
        tenant=g.tenant,
        sources=sources,
        models=models,
        total_models_count=len(all_models),
        visible_models_count=len(models),
        mlflow_embed_url=mlflow_embed_url,
        jupyter_embed_url=jupyter_embed_url,
        jupyterhub_base_url=jupyterhub_base_url,
        selected_project=project_slug,
        workspace_root_rel=project_workspace["workspace_root_rel"],
        notebook_folder_rel=project_workspace["notebook_folder_rel"],
        enabled_kernel_list=_configured_enabled_kernels(),
        enabled_env_list=_configured_prebuilt_envs(),
        notebook_template_version=_notebook_template_version(),
        tenant_mlflow_runs=tenant_mlflow_runs,
        mlflow_runs_error=mlflow_runs_error,
        tenant_notebook_rel=tenant_notebook_rel_url,
        jupyter_start_here_url=start_here_url,
        ml_page_key=page_key,
    )


def _nb_src(*lines: str) -> list[str]:
    """Return a well-formed nbformat source list.

    Each line except the last is terminated with '\\n' so that Jupyter joins
    them correctly into multi-line cell text. Without this every line merges
    into one, producing syntax errors at run time.
    """
    result = []
    for i, line in enumerate(lines):
        result.append(line if i == len(lines) - 1 else line + "\n")
    return result


def _safe_project_slug(value: str) -> str:
    raw = str(value or "").strip().lower()
    if not raw:
        return "default"
    slug = re.sub(r"[^a-z0-9_-]+", "-", raw)
    slug = re.sub(r"-+", "-", slug).strip("-")
    return (slug or "default")[:64]


def _tenant_projects_root(tenant_id: int) -> str:
    project_root = os.path.abspath(os.path.join(current_app.root_path, os.pardir))
    return os.path.join(project_root, "instance", "tenant_files", str(int(tenant_id)), "projects")


def _ensure_tenant_project_workspace(tenant_id: int, project_slug: str) -> dict[str, str]:
    slug = _safe_project_slug(project_slug)
    projects_root = _tenant_projects_root(tenant_id)
    workspace_root = os.path.join(projects_root, slug)
    scaffold_dirs = [
        "notebooks",
        "src",
        "data",
        "models",
        "pipelines",
    ]
    for rel_dir in scaffold_dirs:
        os.makedirs(os.path.join(workspace_root, rel_dir), exist_ok=True)

    starter_files: dict[str, str] = {
        "requirements.txt": "scikit-learn\npandas\nmlflow\n",
        "environment.yml": "name: audela-project\ndependencies:\n  - python=3.11\n  - pip\n  - pip:\n      - scikit-learn\n      - pandas\n      - mlflow\n",
        "Dockerfile": "FROM python:3.11-slim\nWORKDIR /project\nCOPY requirements.txt /project/requirements.txt\nRUN pip install --no-cache-dir -r requirements.txt\n",
        "mlstudio.yaml": "project:\n  name: " + slug + "\ntracking:\n  provider: mlflow\n",
        os.path.join("src", "__init__.py"): "",
        os.path.join("src", "audela_sdk.py"): _internal_notebook_sdk_source(),
    }
    for filename, content in starter_files.items():
        dst = os.path.join(workspace_root, filename)
        should_refresh = filename in {
            os.path.join("src", "audela_sdk.py"),
        }
        if should_refresh or not os.path.exists(dst):
            with open(dst, "w", encoding="utf-8") as handle:
                handle.write(content)

    notebooks_root = os.path.join(workspace_root, "notebooks")
    example_notebooks: dict[str, dict[str, Any]] = {
        "START_HERE.ipynb": {
            "cells": [
                {
                    "cell_type": "markdown",
                    "metadata": {"language": "markdown"},
                    "source": _nb_src(
                        "# Start Here",
                        f"Project: {slug}",
                        "",
                        "Run these in order:",
                        "1. Open `bi_dataset_explorer.ipynb` to discover BI sources and preview SQL via the SDK.",
                        "2. Open `model_registration_example.ipynb` to see how a model is saved into Audela via the SDK.",
                        "3. Open `../src/audela_sdk.py` if you want to inspect the internal SDK methods.",
                        "4. Download the latest template from ML Studio if you want the most recent guided notebook.",
                    ),
                }
            ],
            "metadata": {"language_info": {"name": "python"}},
            "nbformat": 4,
            "nbformat_minor": 5,
        },
        "bi_dataset_explorer.ipynb": {
            "cells": [
                {
                    "cell_type": "markdown",
                    "metadata": {"language": "markdown"},
                    "source": _nb_src(
                        "# BI Dataset Explorer",
                        "Tenant-scoped example notebook for listing BI sources and previewing SQL output.",
                    ),
                },
                {
                    "cell_type": "code",
                    "metadata": {"language": "python"},
                    "source": _nb_src(
                        "from pathlib import Path",
                        "import sys, os",
                        "sys.path.insert(0, str(Path.cwd().parent / 'src'))",
                        "from audela_sdk import AudelaNotebookSDK",
                        "",
                        "# --- Authentication ---",
                        "# Copy your session cookie: DevTools (F12) > Application > Cookies > 'session' value.",
                        "# Paste it below, or set the AUDELA_SESSION_COOKIE env var before starting Jupyter.",
                        "sdk = AudelaNotebookSDK(",
                        "    base_url='http://127.0.0.1:5000',",
                        "    session_cookie=os.environ.get('AUDELA_SESSION_COOKIE', ''),  # or paste here",
                        ")",
                        "",
                        "def list_sources():",
                        "    data = sdk.list_bi_sources()",
                        "    print(data)",
                        "",
                        "def preview(source_id, sql):",
                        "    data = sdk.preview_bi_dataset(source_id=source_id, sql_text=sql, row_limit=30)",
                        "    print(data)",
                        "",
                        "def schema(source_id, sql):",
                        "    data = sdk.schema_bi_dataset(source_id=source_id, sql_text=sql, row_limit=120)",
                        "    print(data)",
                    ),
                },
            ],
            "metadata": {"language_info": {"name": "python"}},
            "nbformat": 4,
            "nbformat_minor": 5,
        },
        "model_registration_example.ipynb": {
            "cells": [
                {
                    "cell_type": "markdown",
                    "metadata": {"language": "markdown"},
                    "source": _nb_src(
                        "# Model Registration Example",
                        "Tenant-scoped example notebook that posts a model payload to Audela.",
                    ),
                },
                {
                    "cell_type": "code",
                    "metadata": {"language": "python"},
                    "source": _nb_src(
                        "from pathlib import Path",
                        "import sys, os",
                        "sys.path.insert(0, str(Path.cwd().parent / 'src'))",
                        "from audela_sdk import AudelaNotebookSDK, MODEL_BUILDERS",
                        "",
                        "# --- Authentication ---",
                        "# Copy your session cookie: DevTools (F12) > Application > Cookies > 'session' value.",
                        "# Paste it below, or set the AUDELA_SESSION_COOKIE env var before starting Jupyter.",
                        "sdk = AudelaNotebookSDK(",
                        "    base_url='http://127.0.0.1:5000',",
                        "    session_cookie=os.environ.get('AUDELA_SESSION_COOKIE', ''),  # or paste here",
                        ")",
                        "algorithm, model_data = MODEL_BUILDERS['linear_regression'](slope=1.0, intercept=0.0)",
                        "payload = sdk.make_payload(",
                        "    model_name='Tenant Example Model',",
                        "    algorithm=algorithm,",
                        "    source_id=1,",
                        "    sql_text='SELECT 1 AS x, 2 AS y',",
                        "    x_column='x',",
                        "    y_column='y',",
                        "    model_data=model_data,",
                        "    metrics={'r2': 1.0},",
                        "    params={'origin': 'tenant_example'},",
                        ")",
                        "print(sdk.register_model(payload))",
                    ),
                },
            ],
            "metadata": {"language_info": {"name": "python"}},
            "nbformat": 4,
            "nbformat_minor": 5,
        },
    }
    for filename, notebook_json in example_notebooks.items():
        dst = os.path.join(notebooks_root, filename)
        with open(dst, "w", encoding="utf-8") as handle:
            handle.write(json.dumps(notebook_json, ensure_ascii=True, indent=2))

    workspace_root_rel = os.path.join("instance", "tenant_files", str(int(tenant_id)), "projects", slug).replace("\\", "/")
    notebook_folder_rel = os.path.join(workspace_root_rel, "notebooks").replace("\\", "/")
    jupyter_tree_rel = os.path.join(slug, "notebooks").replace("\\", "/")
    return {
        "workspace_root_rel": workspace_root_rel,
        "notebook_folder_rel": notebook_folder_rel,
        "jupyter_tree_rel": jupyter_tree_rel,
    }


def _build_jupyterhub_project_url(base_url: str, user_email: str, project_tree_rel: str) -> str:
    base = str(base_url or "").strip().rstrip("/")
    if not base:
        return ""
    user_slug = _safe_project_slug(str(user_email or "user").split("@", 1)[0])
    tree_path = quote(project_tree_rel.replace("\\", "/"), safe="/")

    if "{username}" in base:
        return base.format(username=user_slug) + f"/lab/tree/{tree_path}"
    if "/user/" in base or base.endswith("/lab"):
        return base + f"/tree/{tree_path}" if base.endswith("/lab") else base + f"/lab/tree/{tree_path}"
    return base + f"/user/{user_slug}/lab/tree/{tree_path}"


def _configured_enabled_kernels() -> list[str]:
    raw = str(current_app.config.get("JUPYTER_SUPPORTED_KERNELS") or "python,r,sql,scala")
    out = [item.strip() for item in raw.split(",") if item.strip()]
    return out or ["python"]


def _configured_prebuilt_envs() -> list[str]:
    raw = str(
        current_app.config.get("JUPYTER_PREBUILT_ENVS")
        or "sklearn,pytorch,tensorflow,xgboost,huggingface"
    )
    out = [item.strip() for item in raw.split(",") if item.strip()]
    return out or ["sklearn"]


def _notebook_template_version() -> str:
    release = str(current_app.config.get("APP_RELEASE") or "dev").strip() or "dev"
    return f"nbtpl-2026.05.10-{release}"


def _internal_notebook_sdk_source() -> str:
    return '''from __future__ import annotations

import os
from typing import Any

import requests


def build_linear_regression(*, slope: float, intercept: float) -> tuple[str, dict[str, Any]]:
    return "linear_regression", {"algorithm": "linear_regression", "slope": float(slope), "intercept": float(intercept)}


def build_moving_average(*, tail_y: list[float] | None = None, mean_y: float | None = None) -> tuple[str, dict[str, Any]]:
    if not tail_y and mean_y is None:
        raise ValueError("moving_average requires tail_y or mean_y")
    data: dict[str, Any] = {"algorithm": "moving_average"}
    if tail_y:
        data["tail_y"] = [float(v) for v in tail_y]
    if mean_y is not None:
        data["mean_y"] = float(mean_y)
    return "moving_average", data


def build_mean_baseline(*, mean_y: float) -> tuple[str, dict[str, Any]]:
    return "mean_baseline", {"algorithm": "mean_baseline", "mean_y": float(mean_y)}


def build_decision_tree(*, threshold: float, left_mean: float, right_mean: float) -> tuple[str, dict[str, Any]]:
    return "decision_tree", {
        "algorithm": "decision_tree",
        "threshold": float(threshold),
        "left_mean": float(left_mean),
        "right_mean": float(right_mean),
    }


def build_random_forest(*, trees: list[dict[str, Any]]) -> tuple[str, dict[str, Any]]:
    if not isinstance(trees, list) or not trees:
        raise ValueError("random_forest requires a non-empty trees list")
    return "random_forest", {"algorithm": "random_forest", "trees": trees}


def build_kmeans_clustering(*, centroids: list[Any], cluster_sizes: list[int] | None = None, feature_names: list[str] | None = None) -> tuple[str, dict[str, Any]]:
    if not isinstance(centroids, list) or not centroids:
        raise ValueError("kmeans_clustering requires centroids")
    data: dict[str, Any] = {"algorithm": "kmeans_clustering", "centroids": centroids}
    if cluster_sizes is not None:
        data["cluster_sizes"] = cluster_sizes
    if feature_names is not None:
        data["feature_names"] = feature_names
    return "kmeans_clustering", data


MODEL_BUILDERS = {
    "linear_regression": build_linear_regression,
    "moving_average": build_moving_average,
    "mean_baseline": build_mean_baseline,
    "decision_tree": build_decision_tree,
    "random_forest": build_random_forest,
    "kmeans_clustering": build_kmeans_clustering,
}


class AudelaNotebookSDK:
    def __init__(self, base_url: str = "http://127.0.0.1:5000", session_cookie: str | None = None, auth_token: str | None = None):
        self.base_url = str(base_url).rstrip("/")
        self.session_cookie = session_cookie or os.getenv("AUDELA_SESSION_COOKIE") or ""
        self.auth_token = auth_token or os.getenv("AUDELA_AUTH_TOKEN") or ""

    def _session(self) -> tuple[requests.Session, dict[str, str]]:
        session = requests.Session()
        headers = {"Accept": "application/json"}
        if self.session_cookie:
            session.cookies.set("session", self.session_cookie)
        if self.auth_token:
            headers["Authorization"] = f"Bearer {self.auth_token}"
        return session, headers

    def _get(self, path: str, timeout: int = 60) -> dict[str, Any]:
        session, headers = self._session()
        response = session.get(f"{self.base_url}{path}", headers=headers, timeout=timeout, allow_redirects=False)
        return self._parse(response, path)

    def _post(self, path: str, payload: dict[str, Any], timeout: int = 120) -> dict[str, Any]:
        session, headers = self._session()
        response = session.post(f"{self.base_url}{path}", json=payload, headers=headers, timeout=timeout, allow_redirects=False)
        return self._parse(response, path)

    def _parse(self, response: Any, path: str) -> dict[str, Any]:
        if response.status_code in (301, 302, 303, 307, 308):
            raise RuntimeError(
                f"Audela SDK: '{path}' was redirected (HTTP {response.status_code}). "
                "You are not authenticated. Set AUDELA_SESSION_COOKIE or AUDELA_AUTH_TOKEN "
                "in your kernel environment variables (or pass session_cookie= when creating the SDK)."
            )
        if response.status_code in (401, 403):
            raise RuntimeError(
                f"Audela SDK: authentication error (HTTP {response.status_code}) on '{path}'. "
                "Set AUDELA_SESSION_COOKIE or AUDELA_AUTH_TOKEN."
            )
        ct = response.headers.get("content-type", "")
        if "application/json" not in ct and "ipynb" not in ct:
            raise RuntimeError(
                f"Audela SDK: unexpected content-type '{ct}' (HTTP {response.status_code}) on '{path}'. "
                "Is the Audela server running at the configured BASE_URL?"
            )
        return response.json()

    def list_bi_sources(self) -> dict[str, Any]:
        return self._get("/ml/notebook/bi-sources")

    def preview_bi_dataset(self, *, source_id: int, sql_text: str, row_limit: int = 50) -> dict[str, Any]:
        return self._post("/ml/notebook/bi-preview", {"source_id": int(source_id), "sql_text": str(sql_text), "row_limit": int(row_limit)})

    def schema_bi_dataset(self, *, source_id: int, sql_text: str, row_limit: int = 120) -> dict[str, Any]:
        return self._post("/ml/notebook/bi-schema", {"source_id": int(source_id), "sql_text": str(sql_text), "row_limit": int(row_limit)})

    def register_model(self, payload: dict[str, Any]) -> dict[str, Any]:
        return self._post("/ml/register-notebook-model", payload)

    def make_payload(self, *, model_name: str, algorithm: str, source_id: int, sql_text: str, x_column: str, y_column: str, model_data: dict[str, Any], metrics: dict[str, Any] | None = None, params: dict[str, Any] | None = None) -> dict[str, Any]:
        return {
            "model_name": str(model_name),
            "algorithm": str(algorithm),
            "source_id": int(source_id),
            "sql_text": str(sql_text),
            "x_column": str(x_column),
            "y_column": str(y_column),
            "model_data": model_data,
            "metrics": metrics or {},
            "params": params or {},
        }

    def train_and_register(
        self,
        *,
        model_name: str,
        algorithm: str,
        source_id: int,
        sql_text: str,
        x_column: str,
        y_column: str,
        builder_kwargs: dict[str, Any],
        metrics: dict[str, Any] | None = None,
        params: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """One-shot helper: pick an algorithm, build model_data, create payload, register.

        Example::

            result = sdk.train_and_register(
                model_name="My LR Model",
                algorithm="linear_regression",
                source_id=1,
                sql_text="SELECT month AS x, revenue AS y FROM sales",
                x_column="x",
                y_column="y",
                builder_kwargs={"slope": 1.5, "intercept": 200.0},
                metrics={"r2": 0.93},
            )
            print(result)
        """
        if algorithm not in MODEL_BUILDERS:
            raise ValueError(f"Unsupported algorithm '{algorithm}'. Choose from: {', '.join(sorted(MODEL_BUILDERS))}.")
        _, model_data = MODEL_BUILDERS[algorithm](**builder_kwargs)
        payload = self.make_payload(
            model_name=model_name,
            algorithm=algorithm,
            source_id=source_id,
            sql_text=sql_text,
            x_column=x_column,
            y_column=y_column,
            model_data=model_data,
            metrics=metrics,
            params=params,
        )
        return self.register_model(payload)
'''


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
    if key == "notebooks":
        return redirect(url_for("ml.notebooks_page"))
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


@bp.route("/notebooks")
@login_required
def notebooks_page():
    return _render_ml_page("notebooks")


@bp.get("/notebooks/workspace-init")
@login_required
def notebooks_workspace_init():
    _require_tenant()
    requested_project = str(request.args.get("project") or "default").strip()
    project_slug = _safe_project_slug(requested_project)
    _ensure_tenant_project_workspace(int(g.tenant.id), project_slug)
    flash(_("Workspace notebook prêt pour le projet: %(name)s", name=project_slug), "success")
    return redirect(url_for("ml.notebooks_page", project=project_slug))


@bp.route("/sentiment")
@login_required
def sentiment_page():
    return _render_ml_page("sentiment")


def _allowed_notebook_algorithms() -> set[str]:
    return {
        "linear_regression",
        "moving_average",
        "mean_baseline",
        "decision_tree",
        "random_forest",
        "kmeans_clustering",
    }


def _notebook_builder_specs() -> dict[str, dict[str, Any]]:
    return {
        "linear_regression": {
            "algorithm": "linear_regression",
            "required": ["slope", "intercept"],
            "optional": [],
        },
        "moving_average": {
            "algorithm": "moving_average",
            "required": [],
            "optional": ["tail_y", "mean_y"],
        },
        "mean_baseline": {
            "algorithm": "mean_baseline",
            "required": ["mean_y"],
            "optional": [],
        },
        "decision_tree": {
            "algorithm": "decision_tree",
            "required": ["threshold", "left_mean", "right_mean"],
            "optional": [],
        },
        "random_forest": {
            "algorithm": "random_forest",
            "required": ["trees"],
            "optional": [],
        },
        "kmeans_clustering": {
            "algorithm": "kmeans_clustering",
            "required": ["centroids"],
            "optional": ["cluster_sizes", "feature_names"],
        },
    }


def _validate_notebook_model_data(algorithm: str, model_data: dict[str, Any]) -> tuple[bool, str]:
    algo = str(algorithm or "").strip().lower()
    if algo == "linear_regression":
        if _to_number(model_data.get("slope")) is None and _to_number(model_data.get("intercept")) is None:
            return False, _("linear_regression requires slope/intercept.")
        return True, ""
    if algo == "moving_average":
        has_tail = isinstance(model_data.get("tail_y"), list) and bool(model_data.get("tail_y"))
        has_mean = _to_number(model_data.get("mean_y")) is not None
        if not (has_tail or has_mean):
            return False, _("moving_average requires tail_y or mean_y.")
        return True, ""
    if algo == "mean_baseline":
        if _to_number(model_data.get("mean_y")) is None:
            return False, _("mean_baseline requires mean_y.")
        return True, ""
    if algo == "decision_tree":
        if _to_number(model_data.get("threshold")) is None:
            return False, _("decision_tree requires threshold.")
        if _to_number(model_data.get("left_mean")) is None or _to_number(model_data.get("right_mean")) is None:
            return False, _("decision_tree requires left_mean and right_mean.")
        return True, ""
    if algo == "random_forest":
        trees = model_data.get("trees") if isinstance(model_data.get("trees"), list) else []
        if not trees:
            return False, _("random_forest requires a non-empty trees list.")
        return True, ""
    if algo == "kmeans_clustering":
        centroids = model_data.get("centroids") if isinstance(model_data.get("centroids"), list) else []
        if not centroids:
            return False, _("kmeans_clustering requires centroids.")
        return True, ""
    return False, _("Unsupported algorithm for notebook registration.")


@bp.get("/notebook-template")
@login_required
def notebook_template():
    _require_tenant()
    template_version = _notebook_template_version()
    template = {
        "cells": [
            {
                "cell_type": "markdown",
                "metadata": {"language": "markdown"},
                "source": _nb_src(
                    "# Audela Notebook Model Registration",
                    "This notebook is the guided experimentation layer for ML Studio.",
                    "",
                    "Use it in this order:",
                    "1. Run Cell 2 to configure the target project and BI endpoints.",
                    "2. Run Cell 3 to load helper functions and builders.",
                    "3. Run Cell 4 to inspect the built-in guidance panel.",
                    "4. Run Cell 5 or Cell 6 to explore BI datasets and preview SQL.",
                    "5. Run Cell 7 to build a valid model payload.",
                    "6. Run Cell 8 to use the guided toolbar and save to Audela.",
                    "",
                    f"Template version: {template_version}",
                ),
            },
            {
                "cell_type": "markdown",
                "metadata": {"language": "markdown"},
                "source": _nb_src(
                    "## What this notebook does",
                    "- Connects to your tenant BI sources through the internal SDK",
                    "- Lets you preview SQL before training",
                    "- Restricts model creation to supported builders only",
                    "- Saves the resulting model directly into ML Studio",
                    "",
                    "You only need to import the SDK from the project `src` folder. The cells below show the standard flow.",
                ),
            },
            {
                "cell_type": "code",
                "metadata": {"language": "python"},
                "source": _nb_src(
                    "# 1) Configure Audela target + import the project SDK",
                    "from pathlib import Path",
                    "import sys, os",
                    "sys.path.insert(0, str(Path.cwd().parent / 'src'))",
                    "from audela_sdk import AudelaNotebookSDK, MODEL_BUILDERS",
                    "",
                    "BASE_URL = 'http://127.0.0.1:5000'",
                    "MODEL_NAME = 'Notebook Linear Demo'",
                    "SOURCE_ID = 1  # replace with your BI source id",
                    "SQL_TEXT = 'SELECT month_idx AS x, amount AS y FROM your_training_view'",
                    "X_COLUMN = 'x'",
                    "Y_COLUMN = 'y'",
                    "",
                    "# --- Authentication ---",
                    "# Copy your session cookie from the browser:",
                    "# DevTools (F12) > Application > Cookies > your Audela domain > 'session' value.",
                    "# Paste it below OR set AUDELA_SESSION_COOKIE as an env var before starting Jupyter.",
                    "sdk = AudelaNotebookSDK(",
                    "    base_url=BASE_URL,",
                    "    session_cookie=os.environ.get('AUDELA_SESSION_COOKIE', ''),  # or paste cookie here",
                    ")",
                    "metrics = {'r2': 0.81, 'rmse': 3.2, 'accuracy_type': 'regression'}",
                ),
            },
            {
                "cell_type": "code",
                "metadata": {"language": "python"},
                "source": _nb_src(
                    "# 2) Guided quick-start panel",
                    "def show_quick_start():",
                    "    print('AUDela notebook quick start')",
                    "    print('Step 1: Run datasets = sdk.list_bi_sources()')",
                    "    print('Step 2: Choose a source and test sdk.preview_bi_dataset(...)')",
                    "    print('Step 3: Build model_data with MODEL_BUILDERS[...]')",
                    "    print('Step 4: Create a payload with sdk.make_payload(...)')",
                    "    print('Step 5: Run sdk.register_model(payload) or use the toolbar')",
                    "    print('Supported builders:', ', '.join(sorted(MODEL_BUILDERS.keys())))",
                    "",
                    "show_quick_start()",
                ),
            },
            {
                "cell_type": "code",
                "metadata": {"language": "python"},
                "source": _nb_src(
                    "# 3) Dataset integration helpers (examples)",
                    "# a) List available BI datasets/sources",
                    "datasets = sdk.list_bi_sources()",
                    "",
                    "# b) Preview data (edit source_id/sql_text based on your source)",
                    "# preview = sdk.preview_bi_dataset(source_id=SOURCE_ID, sql_text=SQL_TEXT, row_limit=30)",
                    "# c) Profile schema/types",
                    "# schema = sdk.schema_bi_dataset(source_id=SOURCE_ID, sql_text=SQL_TEXT, row_limit=120)",
                ),
            },
            {
                "cell_type": "code",
                "metadata": {"language": "python"},
                "source": _nb_src(
                    "# 4) Build payload from predefined function + save",
                    "algorithm, model_data = MODEL_BUILDERS['linear_regression'](slope=1.25, intercept=12.0)",
                    "",
                    "payload = sdk.make_payload(",
                    "    model_name=MODEL_NAME,",
                    "    algorithm=algorithm,",
                    "    source_id=SOURCE_ID,",
                    "    sql_text=SQL_TEXT,",
                    "    x_column=X_COLUMN,",
                    "    y_column=Y_COLUMN,",
                    "    model_data=model_data,",
                    "    metrics=metrics,",
                    "    params={'origin': 'jupyter'},",
                    ")",
                    "",
                    "# Optional if not already authenticated: set env AUDELA_SESSION_COOKIE in the notebook kernel.",
                    "print(sdk.register_model(payload))",
                ),
            },
            {
                "cell_type": "code",
                "metadata": {"language": "python"},
                "source": _nb_src(
                    "# 5) Optional guided toolbar in notebook UI",
                    "try:",
                    "    import ipywidgets as widgets",
                    "    from IPython.display import display, clear_output",
                    "",
                    "    project_sql = widgets.Textarea(value=SQL_TEXT, description='SQL', layout=widgets.Layout(width='100%', height='90px'))",
                    "    source_dropdown = widgets.Dropdown(options=[(f'Source #{SOURCE_ID}', SOURCE_ID)], description='Dataset')",
                    "    model_name_input = widgets.Text(value=MODEL_NAME, description='Model')",
                    "    schema_btn = widgets.Button(description='Schema profile', button_style='primary', icon='table')",
                    "    list_btn = widgets.Button(description='List BI datasets', button_style='info', icon='list')",
                    "    preview_btn = widgets.Button(description='Preview BI query', button_style='warning', icon='search')",
                    "    save_btn = widgets.Button(description='Save to Audela', button_style='success', icon='save')",
                    "    save_out = widgets.Output(layout=widgets.Layout(border='1px solid #ddd', padding='6px'))",
                    "    help_html = widgets.HTML('<b>Guide:</b> 1) List datasets  2) Preview SQL  3) Save to Audela')",
                    "",
                    "    def _refresh_sources():",
                    "        data = sdk.list_bi_sources()",
                    "        items = data.get('items') if isinstance(data, dict) else []",
                    "        opts = [(f\"{it.get('name', 'source')} (#{it.get('id', 0)})\", int(it.get('id', 0))) for it in items if int(it.get('id', 0)) > 0]",
                    "        if opts:",
                    "            source_dropdown.options = opts",
                    "            source_dropdown.value = opts[0][1]",
                    "",
                    "    def _on_list(_):",
                    "        with save_out:",
                    "            clear_output()",
                    "            _refresh_sources()",
                    "",
                    "    def _on_preview(_):",
                    "        with save_out:",
                    "            clear_output()",
                    "            print(sdk.preview_bi_dataset(source_id=source_dropdown.value, sql_text=project_sql.value, row_limit=30))",
                    "",
                    "    def _on_schema(_):",
                    "        with save_out:",
                    "            clear_output()",
                    "            print(sdk.schema_bi_dataset(source_id=source_dropdown.value, sql_text=project_sql.value, row_limit=120))",
                    "",
                    "    def _on_save(_):",
                    "        with save_out:",
                    "            clear_output()",
                    "            toolbar_payload = dict(payload)",
                    "            toolbar_payload['source_id'] = int(source_dropdown.value)",
                    "            toolbar_payload['sql_text'] = str(project_sql.value)",
                    "            toolbar_payload['model_name'] = str(model_name_input.value or toolbar_payload.get('model_name') or 'Notebook Model')",
                    "            print(sdk.register_model(toolbar_payload))",
                    "",
                    "    schema_btn.on_click(_on_schema)",
                    "    list_btn.on_click(_on_list)",
                    "    preview_btn.on_click(_on_preview)",
                    "    save_btn.on_click(_on_save)",
                    "    display(help_html, model_name_input, source_dropdown, project_sql, widgets.HBox([list_btn, preview_btn, schema_btn, save_btn]), save_out)",
                    "    _refresh_sources()",
                    "except Exception:",
                    "    print('ipywidgets not available. Install with: pip install ipywidgets')",
                    "    print('Fallback helpers: sdk.list_bi_sources(), sdk.preview_bi_dataset(...), sdk.schema_bi_dataset(...), sdk.register_model(payload)')",
                ),
            },
        ],
        "metadata": {
            "kernelspec": {"display_name": "Python 3", "language": "python", "name": "python3"},
            "language_info": {"name": "python"},
            "audela_template_version": template_version,
        },
        "nbformat": 4,
        "nbformat_minor": 5,
    }

    out = current_app.response_class(
        json.dumps(template, ensure_ascii=True, indent=2),
        mimetype="application/x-ipynb+json",
    )
    out.headers["Content-Disposition"] = 'attachment; filename="audela_model_registration_template.ipynb"'
    return out


@bp.get("/notebook-integration")
@login_required
def notebook_integration_info():
    _require_tenant()
    host_origin = request.host_url.rstrip("/")
    return jsonify(
        {
            "ok": True,
            "template_version": _notebook_template_version(),
            "template_url": url_for("ml.notebook_template"),
            "tutorial_url": url_for("ml.notebook_tutorial"),
            "register_url": url_for("ml.register_notebook_model"),
            "bi_sources_url": url_for("ml.notebook_bi_sources"),
            "bi_preview_url": url_for("ml.notebook_bi_preview"),
            "bi_schema_url": url_for("ml.notebook_bi_schema"),
            "builder_specs": _notebook_builder_specs(),
            "tenant_notebook_folder": os.path.join("instance", "tenant_files", str(int(g.tenant.id)), "notebooks").replace("\\\\", "/"),
            "required_fields": [
                "model_name",
                "algorithm",
                "source_id",
                "sql_text",
                "model_data",
            ],
            "supported_algorithms": sorted(list(_allowed_notebook_algorithms())),
            "notes": [
                "Use your authenticated browser session/cookie when posting from Jupyter.",
                "Prefer JSON model_data compatible with built-in ML Studio algorithms.",
            ],
            "embed_troubleshooting": {
                "symptom": "If iframe says the site refused to connect, Jupyter is blocking frame ancestors.",
                "local_quick_start": "./scripts/start_jupyter_embed.sh",
                "expected_origin": host_origin,
            },
        }
    )


@bp.get("/notebook-tutorial")
@login_required
def notebook_tutorial():
    _require_tenant()
    return jsonify(
        {
            "ok": True,
            "title": "Notebook Integration Detailed Tutorial",
            "template_version": _notebook_template_version(),
            "steps": [
                {
                    "step": 1,
                    "title": "Prepare tenant project workspace",
                    "details": [
                        "Open ML Studio > Notebooks.",
                        "Type project name and click Prepare workspace.",
                        "Workspace is created under tenant_files/<tenant>/projects/<project>/.",
                    ],
                },
                {
                    "step": 2,
                    "title": "Open template notebook",
                    "details": [
                        "Click Download template notebook.",
                        "Open notebook in Jupyter project notebooks folder.",
                    ],
                },
                {
                    "step": 3,
                    "title": "Connect BI datasets from notebook",
                    "details": [
                        "Use sdk.list_bi_sources() to discover tenant BI sources.",
                        "Use sdk.preview_bi_dataset(source_id, sql_text) to validate query output.",
                        "Use the predefined toolbar buttons (List BI datasets / Preview BI query).",
                    ],
                },
                {
                    "step": 4,
                    "title": "Build and save model into ML Studio",
                    "details": [
                        "Use MODEL_BUILDERS for supported algorithms.",
                        "Run sdk.register_model(payload) or click Save to Audela button.",
                        "Data is posted to /ml/register-notebook-model and validated server-side.",
                    ],
                },
                {
                    "step": 5,
                    "title": "Use model lifecycle",
                    "details": [
                        "Open Models page and run Predict/Deploy.",
                        "Track experiments and run history with MLflow integration.",
                    ],
                },
            ],
        }
    )


@bp.get("/notebook/bi-sources")
@login_required
def notebook_bi_sources():
    _require_tenant()
    sources = (
        DataSource.query.filter_by(tenant_id=g.tenant.id)
        .order_by(DataSource.name.asc(), DataSource.id.asc())
        .all()
    )
    return jsonify(
        {
            "ok": True,
            "count": len(sources),
            "items": [
                {
                    "id": int(src.id),
                    "name": str(src.name or ""),
                    "type": str(src.type or ""),
                }
                for src in sources
            ],
        }
    )


@bp.post("/notebook/bi-preview")
@login_required
def notebook_bi_preview():
    _require_tenant()
    payload = request.get_json(silent=True) or {}
    source_id = _to_int(payload.get("source_id"), 0, 0, 2_000_000_000)
    sql_text = str(payload.get("sql_text") or "").strip()
    row_limit = _to_int(payload.get("row_limit"), 50, 1, 500)

    if not source_id or not sql_text:
        return jsonify({"ok": False, "error": _("source_id and sql_text are required.")}), 400

    src = DataSource.query.filter_by(id=source_id, tenant_id=g.tenant.id).first()
    if not src:
        return jsonify({"ok": False, "error": _("Selecione uma fonte válida.")}), 400

    try:
        result = execute_sql(src, sql_text, params={"tenant_id": int(g.tenant.id)}, row_limit=row_limit)
    except QueryExecutionError as exc:
        return jsonify({"ok": False, "error": _("Erro ao executar query: {error}", error=str(exc))}), 400

    columns = [str(c) for c in (result.get("columns") or [])]
    rows = result.get("rows") or []
    safe_rows = _json_safe_rows(rows, row_limit)
    return jsonify(
        {
            "ok": True,
            "source_id": int(src.id),
            "source_name": str(src.name or ""),
            "columns": columns,
            "rows": safe_rows,
            "row_count": len(safe_rows),
        }
    )


@bp.post("/notebook/bi-schema")
@login_required
def notebook_bi_schema():
    _require_tenant()
    payload = request.get_json(silent=True) or {}
    source_id = _to_int(payload.get("source_id"), 0, 0, 2_000_000_000)
    sql_text = str(payload.get("sql_text") or "").strip()
    row_limit = _to_int(payload.get("row_limit"), 120, 5, 500)

    if not source_id or not sql_text:
        return jsonify({"ok": False, "error": _("source_id and sql_text are required.")}), 400

    src = DataSource.query.filter_by(id=source_id, tenant_id=g.tenant.id).first()
    if not src:
        return jsonify({"ok": False, "error": _("Selecione uma fonte válida.")}), 400

    try:
        result = execute_sql(src, sql_text, params={"tenant_id": int(g.tenant.id)}, row_limit=row_limit)
    except QueryExecutionError as exc:
        return jsonify({"ok": False, "error": _("Erro ao executar query: {error}", error=str(exc))}), 400

    columns = [str(c) for c in (result.get("columns") or [])]
    rows = result.get("rows") or []
    safe_rows = _json_safe_rows(rows, row_limit)

    profile: list[dict[str, Any]] = []
    for idx, col in enumerate(columns):
        values = [row[idx] for row in safe_rows if isinstance(row, list) and idx < len(row)]
        inferred = _infer_column_type(values)
        non_null = sum(1 for v in values if v is not None and str(v).strip() != "")
        sample = values[:5]
        profile.append(
            {
                "name": col,
                "inferred_type": inferred,
                "non_null": non_null,
                "sample": sample,
            }
        )

    return jsonify(
        {
            "ok": True,
            "source_id": int(src.id),
            "source_name": str(src.name or ""),
            "row_count": len(safe_rows),
            "profile": profile,
        }
    )


@bp.post("/register-notebook-model")
@login_required
def register_notebook_model():
    _require_tenant()
    payload = request.get_json(silent=True) or {}

    model_name = str(payload.get("model_name") or "").strip()
    algorithm = str(payload.get("algorithm") or "").strip().lower()
    source_id = _to_int(payload.get("source_id"), 0, 0, 2_000_000_000)
    sql_text = str(payload.get("sql_text") or "").strip()
    x_column = str(payload.get("x_column") or "").strip()
    y_column = str(payload.get("y_column") or "").strip()
    model_data = payload.get("model_data") if isinstance(payload.get("model_data"), dict) else {}
    metrics = payload.get("metrics") if isinstance(payload.get("metrics"), dict) else {}
    params = payload.get("params") if isinstance(payload.get("params"), dict) else {}

    if not model_name or not source_id or not sql_text:
        return jsonify({"ok": False, "error": _("model_name, source_id and sql_text are required.")}), 400

    if algorithm not in _allowed_notebook_algorithms():
        return jsonify({"ok": False, "error": _("Unsupported algorithm for notebook registration.")}), 400

    valid_data, err_msg = _validate_notebook_model_data(algorithm, model_data)
    if not valid_data:
        return jsonify({"ok": False, "error": err_msg}), 400

    src = DataSource.query.filter_by(id=source_id, tenant_id=g.tenant.id).first()
    if not src:
        return jsonify({"ok": False, "error": _("Selecione uma fonte válida.")}), 400

    state = _ml_models_state_for_tenant(g.tenant)
    models = state.get("models") or []
    model_entry = {
        "id": f"ml_{secrets.token_hex(6)}",
        "name": model_name[:120],
        "algorithm": algorithm,
        "source_id": int(src.id),
        "source_name": str(src.name or ""),
        "x_column": x_column[:120],
        "y_column": y_column[:120],
        "sql_text": sql_text[:12000],
        "trained_at": datetime.utcnow().isoformat(),
        "metrics": metrics,
        "params": params,
        "model_data": model_data,
        "mlflow": {},
        "deployed": False,
        "import_origin": "jupyter_notebook",
    }
    models.insert(0, model_entry)
    state["models"] = models[:200]

    _persist_ml_models_state(g.tenant, state)
    db.session.commit()

    return jsonify(
        {
            "ok": True,
            "model_id": model_entry["id"],
            "model_name": model_entry["name"],
            "redirect_url": url_for("ml.models_page"),
        }
    )


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
        tenure_years = round(min(35.0, max(0.4, (age - 22) * 0.45 + rng.gauss(0, 1.4))), 2)
        performance_score = round(min(5.0, max(1.8, 3.0 + ((age - 22) * 0.02) + rng.gauss(0, 0.45))), 2)

        # Manager flag follows a latent score so classification has clearer structure.
        manager_score = (0.05 * age) + (0.16 * tenure_years) + (0.9 * (performance_score - 3.0)) + rng.gauss(0, 0.55)
        is_manager = 1 if manager_score >= 3.6 else 0

        # Preserve a dominant linear trend for age->salary regression quality.
        base = 18000 + (age * 1750)
        manager_bonus = 17000 if is_manager else 0
        salary = int(max(23000, min(180000, base + (tenure_years * 850) + (performance_score * 1900) + manager_bonus + rng.gauss(0, 900))))
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
    existing_by_name = {
        str(m.get("name") or "").strip().lower(): m
        for m in models
        if isinstance(m, dict)
    }

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
            "algorithm": "random_forest",
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

    prepared_ids: list[str] = []
    added = 0
    refreshed = 0
    for model in sample_models:
        model_key = str(model.get("name") or "").strip().lower()
        existing = existing_by_name.get(model_key)
        if existing is not None:
            existing.update(
                {
                    "algorithm": model.get("algorithm"),
                    "source_id": model.get("source_id"),
                    "source_name": model.get("source_name"),
                    "x_column": model.get("x_column"),
                    "y_column": model.get("y_column"),
                    "sql_text": model.get("sql_text"),
                    "trained_at": "",
                    "metrics": {},
                    "params": {},
                    "model_data": {},
                    "mlflow": {},
                    "deployed": False,
                }
            )
            prepared_ids.append(str(existing.get("id") or ""))
            refreshed += 1
            continue

        models.insert(0, model)
        existing_by_name[model_key] = model
        prepared_ids.append(str(model.get("id") or ""))
        added += 1

    state["models"] = models[:200]
    _persist_ml_models_state(g.tenant, state)
    db.session.commit()

    trained_ok = 0
    trained_ko = 0
    for model_id in [mid for mid in prepared_ids if mid]:
        ok, _msg = _train_model_internal(model_id, 0.85, 5, 45, 3)
        if ok:
            trained_ok += 1
        else:
            trained_ko += 1

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
    if refreshed > 0:
        flash(
            _(
                "Sample models refreshed: {count}.",
                count=refreshed,
            ),
            "info",
        )
    flash(
        _(
            "Sample training completed: {ok} successful, {ko} failed.",
            ok=trained_ok,
            ko=trained_ko,
        ),
        "info" if trained_ko == 0 else "warning",
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
        train_true_vals = [y for _, y in train_pairs]
        if train_true_vals and all(int(round(float(v))) in {0, 1} for v in train_true_vals):
            train_pred_vals = [_ml_predict(model_data, x) for x, _ in train_pairs]
            model_data["classification_threshold"] = _binary_best_threshold(train_true_vals, train_pred_vals)
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
    if _is_allowed_mlflow_return_url(return_to, tracking_uri):
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
    x_values = _parse_predict_values(x_raw)
    if not model_id or not x_values:
        return jsonify({"ok": False, "error": _("Model and numeric x are required.")}), 400
    if len(x_values) > 200:
        return jsonify({"ok": False, "error": _("Model and numeric x are required.")}), 400

    state = _ml_models_state_for_tenant(g.tenant)
    model = next((m for m in (state.get("models") or []) if str(m.get("id")) == model_id), None)
    if not model:
        return jsonify({"ok": False, "error": _("Modèle introuvable.")}), 404

    payload = _build_prediction_payload(model, x_values)
    if not bool(payload.get("ok")):
        return jsonify(payload), 400
    return jsonify(payload)


@bp.post("/predict/export/pdf")
@login_required
def predict_export_pdf():
    _require_tenant()
    payload = request.get_json(silent=True) or {}
    model_id = str(payload.get("model_id") or "").strip()
    x_values = _parse_predict_values(payload.get("x"))
    if not model_id or not x_values:
        return jsonify({"ok": False, "error": _("Model and numeric x are required.")}), 400

    state = _ml_models_state_for_tenant(g.tenant)
    model = next((m for m in (state.get("models") or []) if str(m.get("id")) == model_id), None)
    if not model:
        return jsonify({"ok": False, "error": _("Modèle introuvable.")}), 404

    prediction_payload = _build_prediction_payload(model, x_values)
    if not bool(prediction_payload.get("ok")):
        return jsonify(prediction_payload), 400

    title = str(payload.get("title") or prediction_payload.get("model_name") or _("Forecast report")).strip() or str(_("Forecast report"))
    style_guide = str(payload.get("style_guide") or "").strip()
    columns, rows = _prediction_export_table(prediction_payload)
    pdf_bytes = table_to_pdf_bytes(
        title,
        columns,
        rows,
        style_guide=style_guide,
        insight_lines=[str(x) for x in (prediction_payload.get("insights") or []) + (prediction_payload.get("recommended_actions") or [])],
        context_lines=[
            f"Model: {prediction_payload.get('model_name') or ''}",
            f"Algorithm: {prediction_payload.get('algorithm') or ''}",
            f"Source: {((prediction_payload.get('summary') or {}).get('source_name') or '')}",
        ],
    )
    resp = current_app.response_class(pdf_bytes, mimetype="application/pdf")
    safe_name = re.sub(r"[^a-zA-Z0-9_-]+", "_", title)[:60].strip("_") or "forecast_report"
    resp.headers["Content-Disposition"] = f'attachment; filename="{safe_name}.pdf"'
    return resp


@bp.post("/predict/export/ppt")
@login_required
def predict_export_ppt():
    _require_tenant()
    payload = request.get_json(silent=True) or {}
    model_id = str(payload.get("model_id") or "").strip()
    x_values = _parse_predict_values(payload.get("x"))
    if not model_id or not x_values:
        return jsonify({"ok": False, "error": _("Model and numeric x are required.")}), 400

    state = _ml_models_state_for_tenant(g.tenant)
    model = next((m for m in (state.get("models") or []) if str(m.get("id")) == model_id), None)
    if not model:
        return jsonify({"ok": False, "error": _("Modèle introuvable.")}), 404

    prediction_payload = _build_prediction_payload(model, x_values)
    if not bool(prediction_payload.get("ok")):
        return jsonify(prediction_payload), 400

    title = str(payload.get("title") or prediction_payload.get("model_name") or _("Forecast deck")).strip() or str(_("Forecast deck"))
    style_guide = str(payload.get("style_guide") or "").strip()
    columns, rows = _prediction_export_table(prediction_payload)
    pptx_bytes = table_to_pptx_bytes(
        title=title,
        source_name=str(((prediction_payload.get("summary") or {}).get("source_name") or model.get("source_name") or "")),
        analysis=_prediction_export_analysis(prediction_payload),
        columns=columns,
        rows=rows,
        style_guide=style_guide,
    )
    resp = current_app.response_class(
        pptx_bytes,
        mimetype="application/vnd.openxmlformats-officedocument.presentationml.presentation",
    )
    safe_name = re.sub(r"[^a-zA-Z0-9_-]+", "_", title)[:60].strip("_") or "forecast_deck"
    resp.headers["Content-Disposition"] = f'attachment; filename="{safe_name}.pptx"'
    return resp


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
