from __future__ import annotations

from celery import shared_task
from flask import current_app

from audela.extensions import db
from audela.models.core import Tenant
from audela.services.alerting_dispatch import dispatch_alerting_for_result
from audela.services.etl_jobs_service import run_due_jobs


@shared_task(name="audela.tasks.etl_jobs_scan")
def etl_jobs_scan() -> dict:
    tenants = Tenant.query.all()
    executed = 0
    errors = 0
    alerts_sent = 0
    runtime_state_changed = False

    for tenant in tenants:
        out = run_due_jobs(current_app.instance_path, tenant.slug)

        tenant_executed = int(out.get("executed") or 0)
        tenant_errors = int(out.get("errors") or 0)

        executed += tenant_executed
        errors += tenant_errors

        alerting_result = dispatch_alerting_for_result(
            tenant,
            {
                "columns": ["executed", "errors"],
                "rows": [[tenant_executed, tenant_errors]],
            },
            source="etl_jobs_scan",
        )
        alerts_sent += int(alerting_result.get("sent") or 0)
        runtime_state_changed = runtime_state_changed or bool(alerting_result.get("state_changed"))

    if runtime_state_changed:
        try:
            db.session.commit()
        except Exception:
            db.session.rollback()

    return {
        "ok": True,
        "tenants": len(tenants),
        "executed": executed,
        "errors": errors,
        "alerts_sent": alerts_sent,
    }
