from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
from typing import Any

import requests
from flask import current_app
from sqlalchemy import text
from sqlalchemy.orm.attributes import flag_modified

from ..extensions import db
from ..i18n import DEFAULT_LANG, normalize_lang
from ..models.finance_invoices import FinanceSetting
from .email_service import EmailService


def _as_dict(value: Any) -> dict:
    return value if isinstance(value, dict) else {}


def _as_list(value: Any) -> list:
    return value if isinstance(value, list) else []


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


def _to_float(value: Any) -> float | None:
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


def _compare(observed: float, operator: str, threshold: float) -> bool:
    op = str(operator or "").strip()
    if op == ">":
        return observed > threshold
    if op == ">=":
        return observed >= threshold
    if op == "<":
        return observed < threshold
    if op == "<=":
        return observed <= threshold
    if op == "==":
        return observed == threshold
    if op == "!=":
        return observed != threshold
    return False


def _normalize_agg_func(value: Any) -> str:
    raw = str(value or "AVG").strip().upper()
    aliases = {
        "MEAN": "AVG",
        "STD": "STDDEV",
        "STDDEV_SAMP": "STDDEV",
    }
    normalized = aliases.get(raw, raw)
    return normalized if normalized in {"SUM", "AVG", "COUNT", "MIN", "MAX", "STDDEV"} else "AVG"


def _aggregate_numeric(values: list[float], agg_func: str) -> float | None:
    if not values:
        return None

    func = _normalize_agg_func(agg_func)
    if func == "SUM":
        return float(sum(values))
    if func == "AVG":
        return float(sum(values) / len(values))
    if func == "COUNT":
        return float(len(values))
    if func == "MIN":
        return float(min(values))
    if func == "MAX":
        return float(max(values))
    if func == "STDDEV":
        n = len(values)
        if n <= 1:
            return 0.0
        mean = sum(values) / n
        variance = sum((v - mean) ** 2 for v in values) / (n - 1)
        return float(variance ** 0.5) if variance > 0 else 0.0
    return None


def _to_date_value(value: Any) -> date | None:
    try:
        if value is None:
            return None
        if isinstance(value, datetime):
            return value.date()
        if isinstance(value, date):
            return value

        txt = str(value).strip()
        if not txt:
            return None

        normalized = txt.replace("Z", "+00:00")
        try:
            return datetime.fromisoformat(normalized).date()
        except Exception:
            pass

        probe = txt[:10]
        for fmt in ("%Y-%m-%d", "%Y/%m/%d", "%d/%m/%Y", "%d-%m-%Y"):
            try:
                return datetime.strptime(probe, fmt).date()
            except Exception:
                continue
        return None
    except Exception:
        return None


def _month_shift(day: date, offset_months: int) -> date:
    month_index = (day.year * 12 + (day.month - 1)) + int(offset_months)
    year = month_index // 12
    month = (month_index % 12) + 1
    return date(year, month, 1)


def _resolve_horizon(item: dict[str, Any], today: date) -> tuple[date, date, str]:
    mode = str(item.get("horizon_mode") or "last_days").strip().lower()
    if mode not in {"last_days", "last_months", "current_year", "custom_range"}:
        mode = "last_days"

    if mode == "last_months":
        months = _to_int(item.get("horizon_months"), 3, 1, 240)
        start = _month_shift(date(today.year, today.month, 1), -(months - 1))
        return start, today, mode

    if mode == "current_year":
        return date(today.year, 1, 1), today, mode

    if mode == "custom_range":
        start_day = _to_date_value(item.get("horizon_start"))
        end_day = _to_date_value(item.get("horizon_end"))
        if not start_day or not end_day:
            return today, today, mode
        if end_day < start_day:
            start_day, end_day = end_day, start_day
        return start_day, end_day, mode

    days = _to_int(item.get("horizon_days"), 30, 1, 3650)
    start = today - timedelta(days=max(0, days - 1))
    return start, today, "last_days"


def _find_col_index(columns: list[Any], name: str) -> int:
    target = str(name or "").strip().lower()
    if not target:
        return -1
    for idx, col in enumerate(columns or []):
        if str(col).strip().lower() == target:
            return idx
    return -1


def _parse_recipients(raw: str | None) -> list[str]:
    if not raw:
        return []
    parts = str(raw).replace(";", ",").replace("\n", ",").split(",")
    return [p.strip() for p in parts if p and p.strip()]


def _render_template(template: str, payload: dict[str, Any]) -> str:
    out = str(template or "")
    for key, value in payload.items():
        out = out.replace("{{" + str(key) + "}}", str(value))
    return out


def _notify_webhook(url: str | None, text: str) -> bool:
    if not url:
        return False
    try:
        response = requests.post(str(url).strip(), json={"text": text}, timeout=10)
        return 200 <= response.status_code < 300
    except Exception as exc:
        current_app.logger.warning("bi alerting webhook failed: %s", exc)
        return False


def _normalize_source_kind(value: Any) -> str:
    raw = str(value or "question").strip().lower()
    if raw in {"ratio", "finance_ratio"}:
        return "ratio"
    if raw in {"indicator", "finance_indicator"}:
        return "indicator"
    return "question"


def _ratio_indicator_label(entry: dict[str, Any]) -> str:
    labels = _as_dict(entry.get("labels"))
    for code in ("fr", "en", "pt", "es", "it", "de"):
        value = labels.get(code)
        if value:
            return str(value)
    return str(entry.get("name") or "").strip()


def _load_finance_indicator_map(tenant_id: int) -> dict[str, dict[str, Any]]:
    out: dict[str, dict[str, Any]] = {}
    try:
        rows = (
            FinanceSetting.query
            .filter_by(tenant_id=int(tenant_id), key="ratio_module")
            .order_by(FinanceSetting.company_id.asc())
            .all()
        )
        for row in rows:
            payload = _as_dict(row.value_json)
            indicators = _as_list(payload.get("indicators"))
            for raw in indicators:
                item = _as_dict(raw)
                indicator_id = str(item.get("id") or "").strip()
                sql_text = str(item.get("sql") or "").strip()
                if not indicator_id or not sql_text:
                    continue
                ref = f"{int(row.company_id)}:{indicator_id}"
                out[ref] = {
                    "ref": ref,
                    "company_id": int(row.company_id),
                    "indicator_id": indicator_id,
                    "name": str(item.get("name") or indicator_id).strip() or indicator_id,
                    "label": _ratio_indicator_label(item) or indicator_id,
                    "sql": sql_text,
                }
    except Exception as exc:
        current_app.logger.warning("bi alerting indicator catalog failed: %s", exc)
    return out


def _load_finance_ratio_map(tenant_id: int) -> dict[str, dict[str, Any]]:
    out: dict[str, dict[str, Any]] = {}
    try:
        rows = (
            FinanceSetting.query
            .filter_by(tenant_id=int(tenant_id), key="ratio_module")
            .order_by(FinanceSetting.company_id.asc())
            .all()
        )
        for row in rows:
            payload = _as_dict(row.value_json)
            indicators = _as_list(payload.get("indicators"))
            ratios = _as_list(payload.get("ratios"))

            indicator_by_id: dict[str, dict[str, Any]] = {}
            for raw_indicator in indicators:
                indicator = _as_dict(raw_indicator)
                indicator_id = str(indicator.get("id") or "").strip()
                sql_text = str(indicator.get("sql") or "").strip()
                if not indicator_id or not sql_text:
                    continue
                indicator_by_id[indicator_id] = {
                    "id": indicator_id,
                    "sql": sql_text,
                }

            for raw_ratio in ratios:
                ratio = _as_dict(raw_ratio)
                ratio_id = str(ratio.get("id") or "").strip()
                numerator_id = str(ratio.get("numerator_id") or "").strip()
                denominator_id = str(ratio.get("denominator_id") or "").strip()
                numerator = _as_dict(indicator_by_id.get(numerator_id))
                denominator = _as_dict(indicator_by_id.get(denominator_id))
                if not ratio_id or not numerator or not denominator:
                    continue

                try:
                    multiplier = float(ratio.get("multiplier") if ratio.get("multiplier") is not None else 100.0)
                except Exception:
                    multiplier = 100.0

                ref = f"{int(row.company_id)}:{ratio_id}"
                out[ref] = {
                    "ref": ref,
                    "company_id": int(row.company_id),
                    "ratio_id": ratio_id,
                    "name": str(ratio.get("name") or ratio_id).strip() or ratio_id,
                    "label": _ratio_indicator_label(ratio) or ratio_id,
                    "numerator_sql": str(numerator.get("sql") or ""),
                    "denominator_sql": str(denominator.get("sql") or ""),
                    "multiplier": multiplier,
                }
    except Exception as exc:
        current_app.logger.warning("bi alerting ratio catalog failed: %s", exc)
    return out


def _execute_indicator_scalar(sql_text: str, params: dict[str, Any]) -> float | None:
    try:
        rs = db.session.execute(text(sql_text), params)
        row = rs.first()
        if row is None:
            return None
        try:
            raw_value = row[0]
        except Exception:
            return None
        return _to_float(raw_value)
    except Exception as exc:
        current_app.logger.warning("bi alerting indicator execution failed: %s", exc)
        return None


def dispatch_alerting_for_result(
    tenant,
    result: dict[str, Any] | None,
    *,
    source: str,
    question_id: int | None = None,
    lang: str | None = None,
) -> dict[str, Any]:
    """Evaluate tenant BI alerting rules against a query result and dispatch notifications.

    Returns counters and whether tenant settings were mutated (runtime cooldown timestamps).
    """
    out = {
        "evaluated": 0,
        "triggered": 0,
        "sent": 0,
        "state_changed": False,
    }

    try:
        settings = tenant.settings_json if isinstance(getattr(tenant, "settings_json", None), dict) else {}
        alerting = _as_dict(settings.get("alerting"))
        rules = _as_list(alerting.get("rules"))
        if not rules:
            return out

        limits = _as_dict(alerting.get("limits"))
        channels_cfg = _as_dict(alerting.get("channels"))
        messages_cfg = _as_dict(alerting.get("messages"))
        runtime = _as_dict(alerting.get("runtime"))
        last_sent = _as_dict(runtime.get("last_sent"))

        columns = _as_list((result or {}).get("columns"))
        rows = _as_list((result or {}).get("rows"))

        now = datetime.now(timezone.utc)
        cooldown_minutes = _to_int(limits.get("cooldown_minutes"), 30, 0, 10080)
        cooldown = timedelta(minutes=cooldown_minutes)
        max_alerts = _to_int(limits.get("max_alerts_per_run"), 25, 1, 5000)

        default_template = (
            "[{{severity}}] {{rule_name}}\n"
            "{{agg_func}}({{metric_field}}) {{operator}} {{threshold}} | observed={{observed}}\n"
            "period={{horizon_start}}..{{horizon_end}}\n"
            "tenant={{tenant_name}} | {{timestamp}}"
        )
        message_template_default = str(messages_cfg.get("default_template") or default_template).strip() or default_template
        lang_pref = str(messages_cfg.get("default_language") or "auto").strip().lower() or "auto"
        resolved_lang = normalize_lang(lang if lang_pref == "auto" else lang_pref) if lang_pref != "auto" else normalize_lang(lang or DEFAULT_LANG)

        source_key = str(source or "result")
        source_question = int(question_id or 0)
        indicator_map: dict[str, dict[str, Any]] | None = None
        ratio_map: dict[str, dict[str, Any]] | None = None
        tenant_id = int(getattr(tenant, "id", 0) or 0)

        sent_events = 0
        for rule in rules:
            if sent_events >= max_alerts:
                break

            item = _as_dict(rule)
            if not bool(item.get("enabled", True)):
                continue

            source_kind = _normalize_source_kind(item.get("source_kind"))
            indicator_ref = str(item.get("indicator_ref") or "").strip()
            ratio_ref = str(item.get("ratio_ref") or "").strip()
            if source_kind == "question" and ratio_ref:
                source_kind = "ratio"
            elif source_kind == "question" and indicator_ref:
                source_kind = "indicator"
            metric_field = str(item.get("metric_field") or "").strip()
            agg_func = _normalize_agg_func(item.get("agg_func"))
            horizon_start = ""
            horizon_end = ""
            horizon_mode = ""

            if source_kind == "indicator":
                if not indicator_ref:
                    continue
                if indicator_map is None:
                    indicator_map = _load_finance_indicator_map(tenant_id)
                indicator_item = _as_dict(indicator_map.get(indicator_ref))
                if not indicator_item:
                    continue

                start_day, end_day, resolved_mode = _resolve_horizon(item, now.date())
                horizon_start = start_day.isoformat()
                horizon_end = end_day.isoformat()
                horizon_mode = resolved_mode

                observed = _execute_indicator_scalar(
                    str(indicator_item.get("sql") or ""),
                    {
                        "tenant_id": tenant_id,
                        "company_id": int(indicator_item.get("company_id") or 0),
                        "start_date": start_day,
                        "end_date": end_day,
                    },
                )
                if observed is None:
                    continue

                metric_field = metric_field or "value"
                agg_func = "AVG"
                source_rule_key = indicator_ref
                placeholder_question_id = 0
                placeholder_indicator_ref = indicator_ref
                placeholder_ratio_ref = ""
                default_rule_name = str(indicator_item.get("label") or indicator_item.get("name") or indicator_ref)
                date_field = ""
            elif source_kind == "ratio":
                if not ratio_ref:
                    continue
                if ratio_map is None:
                    ratio_map = _load_finance_ratio_map(tenant_id)
                ratio_item = _as_dict(ratio_map.get(ratio_ref))
                if not ratio_item:
                    continue

                start_day, end_day, resolved_mode = _resolve_horizon(item, now.date())
                horizon_start = start_day.isoformat()
                horizon_end = end_day.isoformat()
                horizon_mode = resolved_mode

                params = {
                    "tenant_id": tenant_id,
                    "company_id": int(ratio_item.get("company_id") or 0),
                    "start_date": start_day,
                    "end_date": end_day,
                }
                numerator_value = _execute_indicator_scalar(str(ratio_item.get("numerator_sql") or ""), params)
                denominator_value = _execute_indicator_scalar(str(ratio_item.get("denominator_sql") or ""), params)
                if numerator_value is None or denominator_value is None:
                    continue
                if denominator_value == 0:
                    continue

                try:
                    multiplier = float(ratio_item.get("multiplier") if ratio_item.get("multiplier") is not None else 100.0)
                except Exception:
                    multiplier = 100.0
                observed = float(numerator_value / denominator_value) * multiplier

                metric_field = metric_field or "value"
                agg_func = "AVG"
                source_rule_key = ratio_ref
                placeholder_question_id = 0
                placeholder_indicator_ref = ""
                placeholder_ratio_ref = ratio_ref
                default_rule_name = str(ratio_item.get("label") or ratio_item.get("name") or ratio_ref)
                date_field = ""
            else:
                rule_question = _to_int(item.get("question_id"), 0, 0)
                if source_question <= 0:
                    continue
                if rule_question <= 0 or rule_question != source_question:
                    continue
                if not columns or not rows:
                    continue

                if not metric_field:
                    continue
                col_idx = _find_col_index(columns, metric_field)
                if col_idx < 0:
                    continue

                date_field = str(item.get("date_field") or "").strip()
                filtered_rows = rows
                if date_field:
                    date_idx = _find_col_index(columns, date_field)
                    if date_idx < 0:
                        continue
                    start_day, end_day, resolved_mode = _resolve_horizon(item, now.date())
                    horizon_start = start_day.isoformat()
                    horizon_end = end_day.isoformat()
                    horizon_mode = resolved_mode
                    scoped_rows = []
                    for row in rows:
                        if not isinstance(row, (list, tuple)) or date_idx >= len(row):
                            continue
                        row_day = _to_date_value(row[date_idx])
                        if not row_day:
                            continue
                        if start_day <= row_day <= end_day:
                            scoped_rows.append(row)
                    filtered_rows = scoped_rows

                numeric_values: list[float] = []
                for row in filtered_rows:
                    if not isinstance(row, (list, tuple)) or col_idx >= len(row):
                        continue
                    numeric = _to_float(row[col_idx])
                    if numeric is None:
                        continue
                    numeric_values.append(numeric)

                observed = _aggregate_numeric(numeric_values, agg_func)
                if observed is None:
                    continue

                source_rule_key = str(source_question)
                placeholder_question_id = source_question
                placeholder_indicator_ref = ""
                placeholder_ratio_ref = ""
                default_rule_name = f"{agg_func}({metric_field})"

            operator = str(item.get("operator") or ">=").strip()
            threshold = _to_float(item.get("threshold"))
            if threshold is None:
                continue

            out["evaluated"] += 1
            if not _compare(observed, operator, threshold):
                continue

            out["triggered"] += 1
            rule_id = str(item.get("id") or "") or f"rule_{out['triggered']}"
            event_key = f"{source_key}:{source_kind}:{source_rule_key}:{rule_id}"

            last_iso = str(last_sent.get(event_key) or "").strip()
            if last_iso and cooldown_minutes > 0:
                try:
                    then = datetime.fromisoformat(last_iso)
                    if then.tzinfo is None:
                        then = then.replace(tzinfo=timezone.utc)
                    if (now - then) < cooldown:
                        continue
                except Exception:
                    pass

            severity = str(item.get("severity") or "medium").strip().lower() or "medium"
            rule_name = str(item.get("name") or default_rule_name).strip() or default_rule_name
            placeholders = {
                "tenant_name": str(getattr(tenant, "name", "tenant") or "tenant"),
                "rule_name": rule_name,
                "source_kind": source_kind,
                "metric_field": metric_field,
                "agg_func": agg_func,
                "date_field": date_field,
                "horizon_mode": horizon_mode,
                "horizon_start": horizon_start,
                "horizon_end": horizon_end,
                "operator": operator,
                "threshold": threshold,
                "observed": observed,
                "severity": severity,
                "timestamp": now.isoformat(),
                "source": source_key,
                "question_id": placeholder_question_id,
                "indicator_ref": placeholder_indicator_ref,
                "ratio_ref": placeholder_ratio_ref,
            }

            msg_template = str(item.get("message_template") or "").strip() or message_template_default
            message_text = _render_template(msg_template, placeholders)

            requested_channels = [
                c for c in _as_list(item.get("channels")) if str(c).strip().lower() in {"email", "slack", "teams"}
            ]
            if requested_channels:
                channels = [str(c).strip().lower() for c in requested_channels]
            else:
                channels = [
                    name
                    for name in ("email", "slack", "teams")
                    if bool(_as_dict(channels_cfg.get(name)).get("enabled", False))
                ]

            sent_for_rule = 0
            subject_prefix = str(_as_dict(channels_cfg.get("email")).get("subject_prefix") or "[AUDELA ALERT]").strip() or "[AUDELA ALERT]"
            subject = f"{subject_prefix} [{severity.upper()}] {rule_name}"

            if "email" in channels:
                email_cfg = _as_dict(channels_cfg.get("email"))
                recipients = _parse_recipients(str(email_cfg.get("recipients") or ""))
                if email_cfg.get("enabled") and recipients:
                    sent_for_rule += int(
                        EmailService.send_email(
                            to=recipients,
                            subject=subject,
                            template=None,
                            lang=resolved_lang,
                            body_text=message_text,
                        )
                    )

            if "slack" in channels:
                slack_cfg = _as_dict(channels_cfg.get("slack"))
                if slack_cfg.get("enabled"):
                    sent_for_rule += int(_notify_webhook(slack_cfg.get("webhook_url"), message_text))

            if "teams" in channels:
                teams_cfg = _as_dict(channels_cfg.get("teams"))
                if teams_cfg.get("enabled"):
                    sent_for_rule += int(_notify_webhook(teams_cfg.get("webhook_url"), message_text))

            if sent_for_rule > 0:
                out["sent"] += sent_for_rule
                sent_events += 1
                last_sent[event_key] = now.isoformat()

        if last_sent != _as_dict(runtime.get("last_sent")):
            runtime["last_sent"] = last_sent
            runtime["updated_at"] = now.isoformat()
            alerting["runtime"] = runtime
            settings["alerting"] = alerting
            tenant.settings_json = settings
            flag_modified(tenant, "settings_json")
            out["state_changed"] = True

    except Exception as exc:
        current_app.logger.warning("bi alerting dispatch failed: %s", exc)

    return out
