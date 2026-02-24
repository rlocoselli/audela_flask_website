from __future__ import annotations

from datetime import datetime, timezone

from celery import shared_task


@shared_task(name="audela.tasks.celery_healthcheck")
def celery_healthcheck() -> dict:
    return {
        "ok": True,
        "service": "audela",
        "task": "celery_healthcheck",
        "ts": datetime.now(timezone.utc).isoformat(),
    }
