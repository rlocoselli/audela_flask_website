from __future__ import annotations

import importlib
from datetime import datetime, timezone
from typing import Any

from .security_sanitizer import safe_error_message


def _to_float(value: Any) -> float | None:
    try:
        if value is None:
            return None
        out = float(value)
        return out if out == out else None
    except Exception:
        return None


def _tracking_uri(config: Any) -> str:
    return str(config.get("MLFLOW_TRACKING_URI") or "").strip()


def is_enabled(config: Any) -> bool:
    uri = _tracking_uri(config)
    if uri:
        return True
    forced = str(config.get("MLFLOW_ENABLED") or "").strip().lower()
    return forced in {"1", "true", "yes", "on"}


def _run_url(tracking_uri: str, experiment_id: str, run_id: str) -> str:
    base = str(tracking_uri or "").strip()
    if not (base.startswith("http://") or base.startswith("https://")):
        return ""
    return f"{base.rstrip('/')}/#/experiments/{experiment_id}/runs/{run_id}"


def _iso_from_ms(value: Any) -> str:
    try:
        millis = int(value)
        if millis <= 0:
            return ""
        return datetime.fromtimestamp(millis / 1000.0, tz=timezone.utc).isoformat()
    except Exception:
        return ""


def list_tenant_runs(*, config: Any, tenant_id: int, max_results: int = 50) -> dict[str, Any]:
    tracking_uri = _tracking_uri(config)
    if not tracking_uri:
        return {"ok": False, "reason": "tracking_uri_missing", "runs": []}

    try:
        mlflow = importlib.import_module("mlflow")
        mlflow_tracking = importlib.import_module("mlflow.tracking")
        MlflowClient = getattr(mlflow_tracking, "MlflowClient")
    except Exception:
        return {"ok": False, "reason": "mlflow_package_missing", "runs": []}

    try:
        mlflow.set_tracking_uri(tracking_uri)
        client = MlflowClient(tracking_uri=tracking_uri)

        exp_name = f"tenant-{int(tenant_id)}-ml-studio"
        exp = mlflow.get_experiment_by_name(exp_name)
        if exp is None:
            return {"ok": True, "runs": []}

        runs = client.search_runs(
            experiment_ids=[str(exp.experiment_id)],
            filter_string=f'tags.tenant_id = "{int(tenant_id)}"',
            max_results=max(1, min(int(max_results), 200)),
            order_by=["attributes.start_time DESC"],
        )

        items: list[dict[str, Any]] = []
        for run in runs:
            info = getattr(run, "info", None)
            data = getattr(run, "data", None)
            run_id = str(getattr(info, "run_id", "") or "")
            experiment_id = str(getattr(info, "experiment_id", "") or "")
            tags = getattr(data, "tags", {}) if data else {}
            metrics = getattr(data, "metrics", {}) if data else {}
            params = getattr(data, "params", {}) if data else {}
            items.append(
                {
                    "run_id": run_id,
                    "experiment_id": experiment_id,
                    "status": str(getattr(info, "status", "") or ""),
                    "lifecycle_stage": str(getattr(info, "lifecycle_stage", "") or ""),
                    "start_time": _iso_from_ms(getattr(info, "start_time", 0)),
                    "end_time": _iso_from_ms(getattr(info, "end_time", 0)),
                    "run_url": _run_url(tracking_uri, experiment_id, run_id),
                    "event": str(tags.get("event") or "training"),
                    "model_id": str(tags.get("model_id") or ""),
                    "algorithm": str(tags.get("algorithm") or params.get("algorithm") or ""),
                    "source_name": str(tags.get("source_name") or ""),
                    "metrics": {
                        "r2": metrics.get("r2"),
                        "mae": metrics.get("mae"),
                        "rmse": metrics.get("rmse"),
                        "silhouette": metrics.get("silhouette"),
                    },
                }
            )

        return {"ok": True, "runs": items}
    except Exception as exc:
        return {
            "ok": False,
            "reason": "mlflow_search_runs_failed",
            "error": safe_error_message(exc, fallback="mlflow run listing failed"),
            "runs": [],
        }


def _training_spec(model: dict[str, Any], source: Any, extra: dict[str, Any] | None = None) -> dict[str, Any]:
    spec: dict[str, Any] = {
        "model_id": str(model.get("id") or ""),
        "model_name": str(model.get("name") or ""),
        "algorithm": str(model.get("algorithm") or ""),
        "source": {
            "id": int(getattr(source, "id", 0) or 0),
            "name": str(getattr(source, "name", "") or ""),
            "type": str(getattr(source, "type", "") or ""),
        },
        "x_column": str(model.get("x_column") or ""),
        "y_column": str(model.get("y_column") or ""),
        "sql_text": str(model.get("sql_text") or ""),
    }
    if isinstance(extra, dict) and extra:
        spec["extra"] = extra
    return spec


def log_model_created_event(
    *,
    config: Any,
    tenant_id: int,
    model: dict[str, Any],
    source: Any,
    retrain_url: str = "",
) -> dict[str, Any]:
    tracking_uri = _tracking_uri(config)
    if not tracking_uri:
        return {"ok": False, "reason": "tracking_uri_missing"}

    try:
        mlflow = importlib.import_module("mlflow")
    except Exception:
        return {"ok": False, "reason": "mlflow_package_missing"}

    try:
        mlflow.set_tracking_uri(tracking_uri)
        experiment_name = f"tenant-{int(tenant_id)}-ml-studio"
        exp = mlflow.get_experiment_by_name(experiment_name)
        experiment_id = mlflow.create_experiment(experiment_name) if exp is None else exp.experiment_id

        run_name = f"create-{str(model.get('name') or 'ml-studio-model')[:180]}"
        with mlflow.start_run(experiment_id=experiment_id, run_name=run_name) as run:
            run_id = run.info.run_id
            mlflow.set_tags(
                {
                    "app": "audela",
                    "module": "ml_studio",
                    "event": "create",
                    "audela_can_train_from_source": "true",
                    "tenant_id": str(int(tenant_id)),
                    "model_id": str(model.get("id") or ""),
                    "algorithm": str(model.get("algorithm") or ""),
                    "source_id": str(getattr(source, "id", "") or ""),
                    "source_name": str(getattr(source, "name", "") or ""),
                    "audela_retrain_url": str(retrain_url or ""),
                }
            )
            mlflow.log_params(
                {
                    "x_column": str(model.get("x_column") or ""),
                    "y_column": str(model.get("y_column") or ""),
                    "source_type": str(getattr(source, "type", "") or ""),
                }
            )
            if hasattr(mlflow, "log_dict"):
                mlflow.log_dict(_training_spec(model, source), "audela_training_spec.json")
            return {
                "ok": True,
                "run_id": run_id,
                "experiment_id": str(experiment_id),
                "run_url": _run_url(tracking_uri, str(experiment_id), str(run_id)),
            }
    except Exception as exc:
        return {"ok": False, "reason": "mlflow_create_log_failed", "error": safe_error_message(exc, fallback="mlflow create failed")}


def log_training_run(
    *,
    config: Any,
    tenant_id: int,
    model: dict[str, Any],
    metrics: dict[str, Any],
    params: dict[str, Any],
    model_data: dict[str, Any],
    source: Any,
    retrain_url: str = "",
) -> dict[str, Any]:
    """Log one ML Studio training run to MLflow when configured.

    This integration is intentionally lightweight and best-effort:
    if MLflow is unavailable or unreachable, callers should continue normally.
    """
    tracking_uri = _tracking_uri(config)
    if not tracking_uri:
        return {"ok": False, "reason": "tracking_uri_missing"}

    try:
        mlflow = importlib.import_module("mlflow")
    except Exception:
        return {"ok": False, "reason": "mlflow_package_missing"}

    try:
        mlflow.set_tracking_uri(tracking_uri)
        experiment_name = f"tenant-{int(tenant_id)}-ml-studio"
        exp = mlflow.get_experiment_by_name(experiment_name)
        if exp is None:
            experiment_id = mlflow.create_experiment(experiment_name)
        else:
            experiment_id = exp.experiment_id

        run_name = str(model.get("name") or "ml-studio-model")[:200]
        algo = str(model.get("algorithm") or "unknown")

        with mlflow.start_run(experiment_id=experiment_id, run_name=run_name) as run:
            run_id = run.info.run_id
            mlflow.set_tags(
                {
                    "app": "audela",
                    "module": "ml_studio",
                    "audela_can_train_from_source": "true",
                    "tenant_id": str(int(tenant_id)),
                    "model_id": str(model.get("id") or ""),
                    "algorithm": algo,
                    "source_id": str(getattr(source, "id", "") or ""),
                    "source_name": str(getattr(source, "name", "") or ""),
                    "audela_retrain_url": str(retrain_url or ""),
                }
            )

            safe_params = {
                "algorithm": algo,
                "x_column": str(model.get("x_column") or ""),
                "y_column": str(model.get("y_column") or ""),
                "source_type": str(getattr(source, "type", "") or ""),
            }
            for key, value in params.items():
                if value is None:
                    continue
                safe_params[str(key)] = value
            mlflow.log_params(safe_params)

            numeric_metrics: dict[str, float] = {}
            for key, value in metrics.items():
                maybe = _to_float(value)
                if maybe is None:
                    continue
                numeric_metrics[str(key)] = maybe
            if numeric_metrics:
                mlflow.log_metrics(numeric_metrics)

            if hasattr(mlflow, "log_dict"):
                mlflow.log_dict(model_data, "model_data.json")
                mlflow.log_dict(
                    _training_spec(model, source, extra={"params": params, "metrics": metrics}),
                    "audela_training_spec.json",
                )

            run_url = _run_url(tracking_uri, str(experiment_id), str(run_id))
            return {
                "ok": True,
                "run_id": run_id,
                "experiment_id": str(experiment_id),
                "run_url": run_url,
            }
    except Exception as exc:
        return {"ok": False, "reason": "mlflow_logging_failed", "error": safe_error_message(exc, fallback="mlflow logging failed")}


def log_deployment_event(
    *,
    config: Any,
    tenant_id: int,
    model: dict[str, Any],
    training_run_id: str = "",
) -> dict[str, Any]:
    tracking_uri = _tracking_uri(config)
    if not tracking_uri:
        return {"ok": False, "reason": "tracking_uri_missing"}

    try:
        mlflow_tracking = importlib.import_module("mlflow.tracking")
        MlflowClient = getattr(mlflow_tracking, "MlflowClient")
    except Exception:
        return {"ok": False, "reason": "mlflow_package_missing"}

    try:
        client = MlflowClient(tracking_uri=tracking_uri)
        run_id = str(training_run_id or "").strip()
        if run_id:
            client.set_tag(run_id, "deployment_status", "deployed")
            return {"ok": True, "run_id": run_id}

        experiment_name = f"tenant-{int(tenant_id)}-ml-studio"
        mlflow = importlib.import_module("mlflow")

        mlflow.set_tracking_uri(tracking_uri)
        exp = mlflow.get_experiment_by_name(experiment_name)
        experiment_id = mlflow.create_experiment(experiment_name) if exp is None else exp.experiment_id
        with mlflow.start_run(experiment_id=experiment_id, run_name=f"deploy-{model.get('name') or 'model'}") as run:
            mlflow.set_tags(
                {
                    "app": "audela",
                    "module": "ml_studio",
                    "event": "deploy",
                    "tenant_id": str(int(tenant_id)),
                    "model_id": str(model.get("id") or ""),
                    "algorithm": str(model.get("algorithm") or ""),
                    "deployment_status": "deployed",
                }
            )
            return {"ok": True, "run_id": run.info.run_id}
    except Exception as exc:
        return {"ok": False, "reason": "mlflow_deploy_log_failed", "error": safe_error_message(exc, fallback="mlflow deployment logging failed")}


def log_sentiment_snapshot_event(
    *,
    config: Any,
    tenant_id: int,
    source: Any,
    snapshot: dict[str, Any],
) -> dict[str, Any]:
    tracking_uri = _tracking_uri(config)
    if not tracking_uri:
        return {"ok": False, "reason": "tracking_uri_missing"}

    try:
        mlflow = importlib.import_module("mlflow")
    except Exception:
        return {"ok": False, "reason": "mlflow_package_missing"}

    try:
        mlflow.set_tracking_uri(tracking_uri)
        experiment_name = f"tenant-{int(tenant_id)}-ml-studio"
        exp = mlflow.get_experiment_by_name(experiment_name)
        experiment_id = mlflow.create_experiment(experiment_name) if exp is None else exp.experiment_id

        run_name = f"sentiment-{str(getattr(source, 'name', '') or 'source')[:120]}"
        summary = snapshot.get("summary") if isinstance(snapshot.get("summary"), dict) else {}

        with mlflow.start_run(experiment_id=experiment_id, run_name=run_name) as run:
            run_id = run.info.run_id
            mlflow.set_tags(
                {
                    "app": "audela",
                    "module": "ml_studio",
                    "event": "sentiment_snapshot",
                    "tenant_id": str(int(tenant_id)),
                    "source_id": str(getattr(source, "id", "") or ""),
                    "source_name": str(getattr(source, "name", "") or ""),
                    "source_type": str(getattr(source, "type", "") or ""),
                    "text_column": str(snapshot.get("text_column") or ""),
                }
            )

            mlflow.log_params(
                {
                    "sql_text": str(snapshot.get("sql_text") or "")[:500],
                    "rows_analyzed": int(snapshot.get("rows_analyzed") or 0),
                }
            )

            mlflow.log_metrics(
                {
                    "sentiment_positive": float(summary.get("positive") or 0),
                    "sentiment_neutral": float(summary.get("neutral") or 0),
                    "sentiment_negative": float(summary.get("negative") or 0),
                    "sentiment_avg_score": float(summary.get("avg_score") or 0.0),
                }
            )

            if hasattr(mlflow, "log_dict"):
                mlflow.log_dict(snapshot, "sentiment_snapshot.json")

            return {
                "ok": True,
                "run_id": run_id,
                "experiment_id": str(experiment_id),
                "run_url": _run_url(tracking_uri, str(experiment_id), str(run_id)),
            }
    except Exception as exc:
        return {"ok": False, "reason": "mlflow_sentiment_log_failed", "error": safe_error_message(exc, fallback="mlflow sentiment logging failed")}
