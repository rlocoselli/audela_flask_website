from __future__ import annotations

import json
import os
import time
import uuid
from datetime import datetime
from typing import Any

from flask import current_app

from audela.etl.engine import ETLEngine
from audela.etl.workflow_loader import normalize_workflow


def _safe_name(name: str) -> str:
    return "".join(ch if ch.isalnum() or ch in ("_", "-") else "_" for ch in str(name)).strip("_")


def workflows_dir(instance_path: str, tenant_slug: str | None) -> str:
    slug = tenant_slug or "global"
    path = os.path.join(instance_path, "etl_workflows", slug)
    os.makedirs(path, exist_ok=True)
    return path


def jobs_file(instance_path: str, tenant_slug: str | None) -> str:
    return os.path.join(workflows_dir(instance_path, tenant_slug), "jobs.json")


def load_jobs(instance_path: str, tenant_slug: str | None) -> list[dict]:
    path = jobs_file(instance_path, tenant_slug)
    if not os.path.exists(path):
        return []
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        return data if isinstance(data, list) else []
    except Exception:
        return []


def save_jobs(instance_path: str, tenant_slug: str | None, jobs: list[dict]) -> None:
    path = jobs_file(instance_path, tenant_slug)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(jobs, f, ensure_ascii=False, indent=2)


def load_workflow_payload(instance_path: str, tenant_slug: str | None, workflow_name: str) -> dict:
    safe = _safe_name(workflow_name)
    if not safe:
        raise ValueError("invalid workflow name")

    d = workflows_dir(instance_path, tenant_slug)
    raw_path = os.path.join(d, f"{safe}.drawflow.json")
    json_path = os.path.join(d, f"{safe}.json")
    yaml_path = os.path.join(d, f"{safe}.yaml")
    yml_path = os.path.join(d, f"{safe}.yml")

    if os.path.exists(raw_path):
        with open(raw_path, "r", encoding="utf-8") as f:
            raw = json.load(f)
        return normalize_workflow(raw)

    if os.path.exists(json_path):
        with open(json_path, "r", encoding="utf-8") as f:
            return json.load(f)

    for p in (yaml_path, yml_path):
        if os.path.exists(p):
            import yaml  # type: ignore

            with open(p, "r", encoding="utf-8") as f:
                data = yaml.safe_load(f)
            return data if isinstance(data, dict) else {}

    raise FileNotFoundError(f"workflow not found: {safe}")


def upsert_job(instance_path: str, tenant_slug: str | None, payload: dict[str, Any]) -> dict:
    jobs = load_jobs(instance_path, tenant_slug)
    now = datetime.utcnow().isoformat()

    job_id = str(payload.get("id") or "").strip()
    if not job_id:
        job_id = uuid.uuid4().hex[:12]

    name = str(payload.get("name") or "").strip() or f"job-{job_id[:6]}"
    workflow_name = _safe_name(str(payload.get("workflow_name") or ""))
    if not workflow_name:
        raise ValueError("workflow_name required")

    interval_minutes = int(payload.get("interval_minutes") or 60)
    interval_minutes = max(1, interval_minutes)
    enabled = bool(payload.get("enabled", True))

    item = None
    for row in jobs:
        if str(row.get("id") or "") == job_id:
            item = row
            break

    if item is None:
        item = {
            "id": job_id,
            "created_at": now,
            "last_run_at": None,
            "last_status": None,
            "last_message": None,
            "history": [],
        }
        jobs.append(item)

    item["name"] = name
    item["workflow_name"] = workflow_name
    item["interval_minutes"] = interval_minutes
    item["enabled"] = enabled
    item["updated_at"] = now

    save_jobs(instance_path, tenant_slug, jobs)
    return item


def delete_job(instance_path: str, tenant_slug: str | None, job_id: str) -> bool:
    jobs = load_jobs(instance_path, tenant_slug)
    before = len(jobs)
    jobs = [j for j in jobs if str(j.get("id") or "") != str(job_id)]
    if len(jobs) == before:
        return False
    save_jobs(instance_path, tenant_slug, jobs)
    return True


def run_job(instance_path: str, tenant_slug: str | None, job_id: str, trigger: str = "manual") -> dict:
    jobs = load_jobs(instance_path, tenant_slug)
    job = None
    for row in jobs:
        if str(row.get("id") or "") == str(job_id):
            job = row
            break
    if job is None:
        raise KeyError("job not found")

    start = time.time()
    now = datetime.utcnow().isoformat()
    status = "success"
    message = "ok"
    result: dict[str, Any] = {}

    try:
        wf = load_workflow_payload(instance_path, tenant_slug, str(job.get("workflow_name") or ""))
        engine = ETLEngine()
        result = engine.run(wf, app=current_app)
    except Exception as exc:
        status = "error"
        message = str(exc)
        result = {"ok": False, "error": str(exc)}

    elapsed_ms = int((time.time() - start) * 1000)
    hist = job.get("history") if isinstance(job.get("history"), list) else []
    hist.append({
        "at": now,
        "status": status,
        "message": message,
        "duration_ms": elapsed_ms,
        "trigger": trigger,
    })

    job["history"] = hist[-25:]
    job["last_run_at"] = now
    job["last_status"] = status
    job["last_message"] = message
    job["updated_at"] = now

    save_jobs(instance_path, tenant_slug, jobs)

    return {
        "ok": status == "success",
        "status": status,
        "message": message,
        "duration_ms": elapsed_ms,
        "result": result,
        "job": job,
    }


def run_due_jobs(instance_path: str, tenant_slug: str | None) -> dict:
    jobs = load_jobs(instance_path, tenant_slug)
    now = datetime.utcnow()
    executed = 0
    errors = 0

    for job in jobs:
        if not bool(job.get("enabled", True)):
            continue
        interval_minutes = max(1, int(job.get("interval_minutes") or 60))
        last_run_raw = str(job.get("last_run_at") or "").strip()

        due = True
        if last_run_raw:
            try:
                last_run = datetime.fromisoformat(last_run_raw)
                due = (now - last_run).total_seconds() >= (interval_minutes * 60)
            except Exception:
                due = True

        if not due:
            continue

        try:
            run_job(instance_path, tenant_slug, str(job.get("id") or ""), trigger="scheduler")
            executed += 1
        except Exception:
            errors += 1

    return {"ok": True, "executed": executed, "errors": errors, "total": len(jobs)}
