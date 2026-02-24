from __future__ import annotations

from datetime import timedelta

from celery import Celery, Task


def create_celery(flask_app) -> Celery:
    broker_url = flask_app.config.get("CELERY_BROKER_URL") or flask_app.config.get("REDIS_URL")
    result_backend = flask_app.config.get("CELERY_RESULT_BACKEND") or broker_url

    class FlaskContextTask(Task):
        def __call__(self, *args, **kwargs):
            with flask_app.app_context():
                return self.run(*args, **kwargs)

    celery = Celery(flask_app.import_name, task_cls=FlaskContextTask)
    celery.conf.update(
        broker_url=broker_url,
        result_backend=result_backend,
        task_default_queue=flask_app.config.get("CELERY_DEFAULT_QUEUE", "default"),
        task_ignore_result=bool(flask_app.config.get("CELERY_TASK_IGNORE_RESULT", False)),
        broker_connection_retry_on_startup=True,
        timezone=flask_app.config.get("CELERY_TIMEZONE", "UTC"),
        enable_utc=bool(flask_app.config.get("CELERY_ENABLE_UTC", True)),
        beat_schedule=flask_app.config.get("CELERY_BEAT_SCHEDULE", {}),
    )

    if bool(flask_app.config.get("PROJECT_NOTIFICATIONS_ENABLED", True)):
        every_minutes = max(1, int(flask_app.config.get("PROJECT_NOTIFICATIONS_SCAN_MINUTES", 5)))
        beat_schedule = dict(celery.conf.beat_schedule or {})
        beat_schedule.setdefault(
            "project-notifications-scan",
            {
                "task": "audela.tasks.project_notifications_scan",
                "schedule": timedelta(minutes=every_minutes),
                "args": (),
            },
        )
        celery.conf.beat_schedule = beat_schedule

    if bool(flask_app.config.get("ETL_JOBS_ENABLED", True)):
        every_minutes = max(1, int(flask_app.config.get("ETL_JOBS_SCAN_MINUTES", 1)))
        beat_schedule = dict(celery.conf.beat_schedule or {})
        beat_schedule.setdefault(
            "etl-jobs-scan",
            {
                "task": "audela.tasks.etl_jobs_scan",
                "schedule": timedelta(minutes=every_minutes),
                "args": (),
            },
        )
        celery.conf.beat_schedule = beat_schedule

    celery.autodiscover_tasks(["audela.tasks"])
    celery.set_default()
    return celery


def build_celery() -> Celery:
    from audela import create_app

    flask_app = create_app()
    return create_celery(flask_app)


celery_app = build_celery()


def register_periodic_task(name: str, task: str, schedule, args: tuple | None = None, kwargs: dict | None = None, options: dict | None = None) -> None:
    beat_schedule = dict(celery_app.conf.beat_schedule or {})
    beat_schedule[name] = {
        "task": task,
        "schedule": schedule,
        "args": args or (),
        "kwargs": kwargs or {},
        "options": options or {},
    }
    celery_app.conf.beat_schedule = beat_schedule
