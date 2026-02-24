from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
from typing import Any

import requests
from celery import shared_task
from flask import current_app
from flask_mail import Message

from audela.extensions import db, mail
from audela.models.project_management import ProjectWorkspace


def _as_dict(value: Any) -> dict:
    return value if isinstance(value, dict) else {}


def _as_list(value: Any) -> list:
    return value if isinstance(value, list) else []


def _parse_day(value: str | None) -> date | None:
    if not value:
        return None
    raw = str(value).strip()
    if not raw:
        return None
    try:
        return datetime.fromisoformat(raw[:10]).date()
    except Exception:
        return None


def _parse_recipients(raw: str | None) -> list[str]:
    if not raw:
        return []
    items = str(raw).replace(";", ",").replace("\n", ",").split(",")
    return [item.strip().lower() for item in items if item and item.strip()]


def _card_owners(card: dict) -> list[str]:
    owners = card.get("owners")
    if isinstance(owners, list) and owners:
        return [str(o).strip() for o in owners if str(o).strip()]
    owner = str(card.get("owner") or "").strip()
    if not owner:
        return []
    return [part.strip() for part in owner.split(",") if part.strip()]


def _manager_email_map(managers: list[dict]) -> dict[str, str]:
    out: dict[str, str] = {}
    for manager in managers:
        name = str(manager.get("name") or "").strip().lower()
        email = str(manager.get("email") or "").strip().lower()
        if name and email:
            out[name] = email
    return out


def _notify_mail(recipients: list[str], subject: str, body: str) -> bool:
    if not recipients:
        return False
    try:
        msg = Message(
            subject=subject,
            recipients=sorted(set(recipients)),
            body=body,
            sender=current_app.config.get("MAIL_DEFAULT_SENDER", "noreply@audela.com"),
        )
        mail.send(msg)
        return True
    except Exception as exc:
        current_app.logger.warning("project_notifications mail failed: %s", exc)
        return False


def _notify_webhook(url: str | None, text: str) -> bool:
    if not url:
        return False
    try:
        response = requests.post(str(url).strip(), json={"text": text}, timeout=10)
        return 200 <= response.status_code < 300
    except Exception as exc:
        current_app.logger.warning("project_notifications webhook failed: %s", exc)
        return False


@shared_task(name="audela.tasks.project_notifications_scan")
def project_notifications_scan() -> dict:
    now = datetime.now(timezone.utc)
    today = now.date()
    cooldown_minutes = max(1, int(current_app.config.get("PROJECT_NOTIFICATIONS_COOLDOWN_MINUTES", 120)))
    cooldown = timedelta(minutes=cooldown_minutes)

    workspaces = ProjectWorkspace.query.all()
    sent_total = 0
    scanned_total = 0
    changed_rows = 0

    for workspace in workspaces:
        state = _as_dict(workspace.state_json)
        notifications = _as_dict(state.get("notifications"))
        channels = _as_dict(notifications.get("channels"))
        triggers = _as_dict(notifications.get("triggers"))
        runtime = _as_dict(notifications.get("runtime"))
        last_sent = _as_dict(runtime.get("last_sent"))

        if not any([channels.get("mail_enabled"), channels.get("slack_enabled"), channels.get("teams_enabled")]):
            continue

        projects = _as_list(state.get("projects"))
        cards = _as_list(state.get("cards"))
        gantt = _as_list(state.get("gantt"))
        managers = _as_list(state.get("managers"))
        manager_emails = _manager_email_map([_as_dict(item) for item in managers])
        settings_recipients = _parse_recipients(channels.get("mail_to"))

        for project in projects:
            project_id = str(project.get("id") or "").strip()
            project_name = str(project.get("name") or "Projet").strip()
            if not project_id:
                continue

            project_cards = [
                _as_dict(card)
                for card in cards
                if str(_as_dict(card).get("project_id") or "") == project_id
            ]
            project_gantt = [
                _as_dict(task)
                for task in gantt
                if str(_as_dict(task).get("project_id") or "") == project_id
            ]

            if triggers.get("project_delay", True):
                delayed_tasks = []
                for task in project_gantt:
                    end_day = _parse_day(task.get("end"))
                    if end_day and end_day < today:
                        delayed_tasks.append(task)
                if delayed_tasks:
                    event_key = f"project_delay:{project_id}"
                    last_iso = str(last_sent.get(event_key) or "").strip()
                    should_send = True
                    if last_iso:
                        try:
                            should_send = (now - datetime.fromisoformat(last_iso)) >= cooldown
                        except Exception:
                            should_send = True
                    if should_send:
                        scanned_total += 1
                        subject = f"[AUDELA] Projet en retard: {project_name}"
                        body = f"Projet: {project_name}\nTâches Gantt en retard: {len(delayed_tasks)}\nDate: {today.isoformat()}"
                        message = f"{subject}\n{body}"

                        if channels.get("mail_enabled"):
                            sent_total += int(_notify_mail(settings_recipients, subject, body))
                        if channels.get("slack_enabled"):
                            sent_total += int(_notify_webhook(channels.get("slack_webhook"), message))
                        if channels.get("teams_enabled"):
                            sent_total += int(_notify_webhook(channels.get("teams_webhook"), message))

                        last_sent[event_key] = now.isoformat()

            if triggers.get("card_delay", True):
                for card in project_cards:
                    if str(card.get("col") or "").lower() == "done":
                        continue
                    due_day = _parse_day(card.get("due_date"))
                    if not due_day or due_day >= today:
                        continue

                    card_id = str(card.get("id") or "")
                    title = str(card.get("title") or "Carte").strip()
                    event_key = f"card_delay:{project_id}:{card_id}"
                    last_iso = str(last_sent.get(event_key) or "").strip()
                    should_send = True
                    if last_iso:
                        try:
                            should_send = (now - datetime.fromisoformat(last_iso)) >= cooldown
                        except Exception:
                            should_send = True
                    if not should_send:
                        continue

                    scanned_total += 1
                    owner_recipients = []
                    for owner in _card_owners(card):
                        owner_email = manager_emails.get(owner.lower())
                        if owner_email:
                            owner_recipients.append(owner_email)
                    mail_recipients = sorted(set(settings_recipients + owner_recipients))

                    subject = f"[AUDELA] Carte en retard: {title}"
                    body = (
                        f"Projet: {project_name}\n"
                        f"Carte: {title}\n"
                        f"Échéance: {due_day.isoformat()}\n"
                        f"Statut: {card.get('col') or '-'}"
                    )
                    message = f"{subject}\n{body}"

                    if channels.get("mail_enabled"):
                        sent_total += int(_notify_mail(mail_recipients, subject, body))
                    if channels.get("slack_enabled"):
                        sent_total += int(_notify_webhook(channels.get("slack_webhook"), message))
                    if channels.get("teams_enabled"):
                        sent_total += int(_notify_webhook(channels.get("teams_webhook"), message))

                    last_sent[event_key] = now.isoformat()

        notifications["runtime"] = {"last_sent": last_sent, "updated_at": now.isoformat()}
        state["notifications"] = notifications
        workspace.state_json = state
        workspace.updated_at = datetime.utcnow()
        changed_rows += 1

    if changed_rows:
        db.session.commit()

    return {
        "ok": True,
        "scanned": scanned_total,
        "sent": sent_total,
        "workspaces": len(workspaces),
        "updated": changed_rows,
    }
