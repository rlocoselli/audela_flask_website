from __future__ import annotations

from celery import shared_task
from flask import current_app

from audela.models.core import Tenant
from audela.services.etl_jobs_service import run_due_jobs


@shared_task(name="audela.tasks.etl_jobs_scan")
def etl_jobs_scan() -> dict:
    tenants = Tenant.query.all()
    executed = 0
    errors = 0

    for tenant in tenants:
        out = run_due_jobs(current_app.instance_path, tenant.slug)

        executed += int(out.get("executed") or 0)
        errors += int(out.get("errors") or 0)

    return {
        "ok": True,
        "tenants": len(tenants),
        "executed": executed,
        "errors": errors,
    }
