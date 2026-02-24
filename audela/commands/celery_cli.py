from __future__ import annotations

import click
from flask.cli import with_appcontext


@click.group()
def celery():
    """Celery worker/queue helper commands."""


@celery.command("info")
@with_appcontext
def celery_info():
    from flask import current_app

    broker = current_app.config.get("CELERY_BROKER_URL") or current_app.config.get("REDIS_URL")
    backend = current_app.config.get("CELERY_RESULT_BACKEND") or broker
    click.echo(f"Broker: {broker}")
    click.echo(f"Backend: {backend}")
    click.echo(f"Queue: {current_app.config.get('CELERY_DEFAULT_QUEUE', 'default')}")


@celery.command("ping")
@click.option("--wait", "wait_seconds", default=8, type=int, show_default=True, help="Seconds to wait for task result.")
@with_appcontext
def celery_ping(wait_seconds: int):
    from audela.tasks.system_tasks import celery_healthcheck

    job = celery_healthcheck.delay()
    click.echo(f"Task sent: {job.id}")

    try:
        result = job.get(timeout=max(1, int(wait_seconds)))
        click.echo(f"Result: {result}")
    except Exception as exc:
        click.secho(f"No worker response yet: {exc}", fg="yellow")


@celery.command("scan-project-notifications")
@click.option("--wait", "wait_seconds", default=15, type=int, show_default=True, help="Seconds to wait for task result.")
@with_appcontext
def scan_project_notifications(wait_seconds: int):
    from audela.tasks.project_notifications import project_notifications_scan

    job = project_notifications_scan.delay()
    click.echo(f"Task sent: {job.id}")
    try:
        result = job.get(timeout=max(1, int(wait_seconds)))
        click.echo(f"Result: {result}")
    except Exception as exc:
        click.secho(f"No worker response yet: {exc}", fg="yellow")


def init_celery_cli(app):
    app.cli.add_command(celery)
