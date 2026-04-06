from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
from typing import Any

import requests
from celery import shared_task
from flask import current_app
from flask_mail import Message

from audela.extensions import db, mail
from audela.i18n import DEFAULT_LANG, normalize_lang, tr
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


def _parse_time_parts(value: str | None) -> tuple[int, int]:
    if not value:
        return 9, 0
    raw = str(value).strip()
    if not raw:
        return 9, 0
    parts = raw.split(":")
    try:
        hour = int(parts[0]) if len(parts) > 0 else 9
        minute = int(parts[1]) if len(parts) > 1 else 0
    except Exception:
        return 9, 0
    return max(0, min(23, hour)), max(0, min(59, minute))


def _parse_int(value: Any, default: int = 0) -> int:
    try:
        return int(value)
    except Exception:
        return default


def _ceremony_start_dt(ceremony: dict, default_tz: timezone = timezone.utc) -> datetime | None:
    start_date = _parse_day(ceremony.get("start_date") or ceremony.get("when"))
    if not start_date:
        return None
    hh, mm = _parse_time_parts(ceremony.get("start_time"))
    return datetime(
        start_date.year,
        start_date.month,
        start_date.day,
        hh,
        mm,
        tzinfo=default_tz,
    )


def _ceremony_occurs_on(
    ceremony: dict,
    base_day: date,
    candidate_day: date,
) -> bool:
    def js_weekday(d: date) -> int:
        # JS Date.getDay() encoding: 0=Sunday..6=Saturday
        return (d.weekday() + 1) % 7

    recurrent = bool(ceremony.get("recurrent"))
    if not recurrent:
        return candidate_day == base_day

    recurrence = str(ceremony.get("recurrence") or "weekly").strip().lower()
    weekdays_raw = ceremony.get("weekdays")
    weekdays: list[int] = []
    if isinstance(weekdays_raw, list):
        weekdays = [x for x in (_parse_int(v, -1) for v in weekdays_raw) if 0 <= x <= 6]
    if not weekdays:
        weekdays = [js_weekday(base_day)]

    if recurrence == "monthly":
        return candidate_day.day == base_day.day

    if js_weekday(candidate_day) not in weekdays:
        return False

    if recurrence == "biweekly":
        weeks = (candidate_day - base_day).days // 7
        return weeks >= 0 and (weeks % 2 == 0)

    return (candidate_day - base_day).days >= 0


def _ceremony_next_occurrences(
    ceremony: dict,
    now: datetime,
    horizon_days: int = 40,
) -> list[datetime]:
    first_dt = _ceremony_start_dt(ceremony)
    if not first_dt:
        return []

    first_day = first_dt.date()
    hh, mm = first_dt.hour, first_dt.minute
    out: list[datetime] = []
    for offset in range(0, max(1, horizon_days) + 1):
        day = now.date() + timedelta(days=offset)
        if not _ceremony_occurs_on(ceremony, first_day, day):
            continue
        occurrence = datetime(day.year, day.month, day.day, hh, mm, tzinfo=timezone.utc)
        if occurrence >= now:
            out.append(occurrence)
    return out


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


def _t(msgid: str, lang: str, **kwargs: Any) -> str:
    return tr(msgid, normalize_lang(lang or DEFAULT_LANG), **kwargs)


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
        notif_lang = normalize_lang(str(notifications.get("lang") or notifications.get("language") or DEFAULT_LANG))
        channels = _as_dict(notifications.get("channels"))
        triggers = _as_dict(notifications.get("triggers"))
        runtime = _as_dict(notifications.get("runtime"))
        last_sent = _as_dict(runtime.get("last_sent"))

        if not any([channels.get("mail_enabled"), channels.get("slack_enabled"), channels.get("teams_enabled")]):
            continue

        projects = _as_list(state.get("projects"))
        cards = _as_list(state.get("cards"))
        gantt = _as_list(state.get("gantt"))
        ceremonies = _as_list(state.get("ceremonies"))
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
            project_ceremonies = [
                _as_dict(item)
                for item in ceremonies
                if str(_as_dict(item).get("project_id") or "") == project_id
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
                        subject = _t("[AUDELA] Projet en retard: {project_name}", notif_lang, project_name=project_name)
                        body = "\n".join([
                            _t("Projet: {project_name}", notif_lang, project_name=project_name),
                            _t("Tâches Gantt en retard: {count}", notif_lang, count=len(delayed_tasks)),
                            _t("Date: {date}", notif_lang, date=today.isoformat()),
                        ])
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

                    subject = _t("[AUDELA] Carte en retard: {title}", notif_lang, title=title)
                    body = "\n".join([
                        _t("Projet: {project_name}", notif_lang, project_name=project_name),
                        _t("Carte: {title}", notif_lang, title=title),
                        _t("Échéance: {due_date}", notif_lang, due_date=due_day.isoformat()),
                        _t("Statut: {status}", notif_lang, status=(card.get('col') or '-')),
                    ])
                    message = f"{subject}\n{body}"

                    if channels.get("mail_enabled"):
                        sent_total += int(_notify_mail(mail_recipients, subject, body))
                    if channels.get("slack_enabled"):
                        sent_total += int(_notify_webhook(channels.get("slack_webhook"), message))
                    if channels.get("teams_enabled"):
                        sent_total += int(_notify_webhook(channels.get("teams_webhook"), message))

                    last_sent[event_key] = now.isoformat()

            if triggers.get("ceremony_reminder", True):
                scope = str(triggers.get("ceremony_scope") or "all").strip().lower()
                global_lead_minutes = max(5, _parse_int(triggers.get("ceremony_lead_minutes"), 60))

                for ceremony in project_ceremonies:
                    if ceremony.get("alert_enabled") is False:
                        continue

                    lead_minutes = max(5, _parse_int(ceremony.get("alert_minutes"), global_lead_minutes))
                    next_occurrences = _ceremony_next_occurrences(ceremony, now)
                    if not next_occurrences:
                        continue

                    ceremony_type = str(ceremony.get("type") or "Cérémonie").strip() or "Cérémonie"
                    for start_dt in next_occurrences:
                        remind_at = start_dt - timedelta(minutes=lead_minutes)
                        if not (remind_at <= now < start_dt):
                            continue

                        event_key = f"ceremony_reminder:{project_id}:{ceremony.get('id') or ''}:{start_dt.isoformat()}"
                        if str(last_sent.get(event_key) or "").strip():
                            continue

                        scanned_total += 1
                        subject = _t("[AUDELA] Rappel cérémonie: {ceremony_type}", notif_lang, ceremony_type=ceremony_type)
                        body = "\n".join([
                            _t("Projet: {project_name}", notif_lang, project_name=project_name),
                            _t("Cérémonie: {ceremony_type}", notif_lang, ceremony_type=ceremony_type),
                            _t("Début: {start}", notif_lang, start=start_dt.isoformat()),
                            _t("Rappel: {minutes} min avant", notif_lang, minutes=lead_minutes),
                        ])
                        message = f"{subject}\n{body}"

                        if channels.get("mail_enabled") and scope in {"all", "mail"}:
                            sent_total += int(_notify_mail(settings_recipients, subject, body))
                        if channels.get("slack_enabled") and scope in {"all", "slack"}:
                            sent_total += int(_notify_webhook(channels.get("slack_webhook"), message))
                        if channels.get("teams_enabled") and scope in {"all", "teams"}:
                            sent_total += int(_notify_webhook(channels.get("teams_webhook"), message))

                        last_sent[event_key] = now.isoformat()
                        break

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
