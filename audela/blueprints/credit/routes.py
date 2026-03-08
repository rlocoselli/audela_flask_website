from __future__ import annotations

from datetime import date, datetime, timedelta
from decimal import Decimal
from copy import deepcopy
import csv
import io
import calendar
import json
import re
from urllib.parse import urlencode
from html import escape as html_escape
from html import unescape as html_unescape

from flask import abort, flash, g, jsonify, make_response, redirect, render_template, request, send_file, url_for
from flask_login import current_user, login_required
from markupsafe import escape
from sqlalchemy import false, func, or_
from sqlalchemy.exc import IntegrityError

from ...extensions import db
from ...i18n import DEFAULT_LANG, tr
from ...models.core import Role, Tenant, User
from ...models.bi import FileAsset, FileFolder
from ...models.credit import (
    CreditApproval,
    CreditApprovalWorkflowStep,
    CreditAnalystFunction,
    CreditAnalystGroup,
    CreditAnalystGroupMember,
    CreditBorrower,
    CreditCollateralType,
    CreditCollateral,
    CreditCountry,
    CreditDeal,
    CreditDocument,
    CreditFacilityType,
    CreditFacility,
    CreditFinancialStatement,
    CreditGuaranteeType,
    CreditGuarantor,
    CreditMemo,
    CreditMemoTemplate,
    CreditMemoTemplateVersion,
    CreditBacklogTask,
    CreditRating,
    CreditRatioSnapshot,
    CreditSector,
)
from ...services.ai_service import analyze_with_ai
from ...services.subscription_service import SubscriptionService
from ...tenancy import get_current_tenant_id, get_user_menu_access, get_user_module_access
from . import bp


def _(msgid: str, **kwargs):
    return tr(msgid, getattr(g, "lang", DEFAULT_LANG), **kwargs)


def _require_tenant() -> None:
    if not current_user.is_authenticated:
        abort(401)
    if not getattr(g, "tenant", None) or current_user.tenant_id != g.tenant.id:
        abort(403)


def _to_decimal(value: str | None, default: str = "0") -> Decimal:
    try:
        return Decimal((value or default).strip())
    except Exception:
        return Decimal(default)


def _to_int(value: str | None) -> int | None:
    try:
        out = int(value or 0)
    except Exception:
        return None
    return out if out > 0 else None


def _to_decimal_loose(value: str | None, default: str = "0") -> Decimal:
    raw = str(value or "").strip()
    if not raw:
        return Decimal(default)

    cleaned = raw.replace(" ", "").replace("\u00a0", "")
    # Handle both 1,234.56 and 1.234,56 forms.
    if "," in cleaned and "." in cleaned:
        if cleaned.rfind(",") > cleaned.rfind("."):
            cleaned = cleaned.replace(".", "").replace(",", ".")
        else:
            cleaned = cleaned.replace(",", "")
    else:
        cleaned = cleaned.replace(",", ".")

    try:
        return Decimal(cleaned)
    except Exception:
        return Decimal(default)


_FINANCIAL_CSV_FIELDS: tuple[str, ...] = (
    "borrower_id",
    "period_label",
    "fiscal_year",
    "revenue",
    "ebitda",
    "total_debt",
    "cash",
    "net_income",
    "spreading_status",
)


_CREDIT_IMPLEMENTATION_PHASES: tuple[tuple[str, tuple[str, ...]], ...] = (
    (
        "Phase 1 - MVP",
        (
            "Deal Intake",
            "Workflow & Case Management",
            "Customer & Counterparty Management",
            "Deal Modelling",
            "Financial Spreading",
            "Credit Risk Analysis",
            "Approvals & Credit Committee",
            "Reporting, Audit & Administration",
        ),
    ),
    (
        "Phase 2",
        (
            "Collateral & Covenant Management",
            "Pricing & Profitability",
            "Limits, Compliance & Controls",
            "Documentation & Conditions Precedent",
            "Booking & Core Banking Integration",
        ),
    ),
    (
        "Phase 3",
        (
            "Monitoring, Amendments & Renewals",
            "Deal Modelling - Advanced Scenarios",
            "Documentation & Conditions Precedent - Advanced Generation",
            "Reporting, Audit & Administration - Advanced Analytics",
        ),
    ),
)


_CREDIT_IMPLEMENTATION_EPICS: tuple[dict[str, object], ...] = (
    {
        "code": "deal_intake",
        "title": "Deal Intake",
        "objective": "Capture new requests quickly and consistently.",
        "priority": "high",
        "stories": (
            "Create deal from scratch with mandatory fields by product type.",
            "Attach financials, KYC and business plan files.",
            "Save draft and resume later.",
        ),
    },
    {
        "code": "workflow_case",
        "title": "Workflow & Case Management",
        "objective": "Control routing, SLA and traceability across review stages.",
        "priority": "very_high",
        "stories": (
            "Assign tasks automatically on submission.",
            "Support reassignment, escalations and reminders.",
            "Show full workflow history and approval timeline.",
        ),
    },
    {
        "code": "customer_counterparty",
        "title": "Customer & Counterparty Management",
        "objective": "Centralize borrower, related-party and group exposure data.",
        "priority": "high",
        "stories": (
            "Link multiple obligors to one credit case.",
            "Aggregate exposure by group hierarchy.",
            "Display KYC and AML flags in the credit file.",
        ),
    },
    {
        "code": "deal_modelling",
        "title": "Deal Modelling",
        "objective": "Model single and multi-facility transactions accurately.",
        "priority": "very_high",
        "stories": (
            "Model tranches, tenors, repayment profiles and utilization assumptions.",
            "Support fees, floating/fixed rates and multi-currency terms.",
            "Compare alternative structures for same borrower.",
        ),
    },
    {
        "code": "financial_spreading",
        "title": "Financial Spreading",
        "objective": "Standardize and version borrower financial statements.",
        "priority": "very_high",
        "stories": (
            "Spread 3-5 years with raw vs adjusted views.",
            "Map borrower chart labels to bank standard line items.",
            "Import from template, CSV and PDF with mapping validation.",
        ),
    },
    {
        "code": "credit_risk_analysis",
        "title": "Credit Risk Analysis",
        "objective": "Generate consistent risk assessment and memo recommendations.",
        "priority": "very_high",
        "stories": (
            "Auto-calculate ratios from spread data.",
            "Run rating scorecards with override reasons.",
            "Compare base, downside and stress scenarios.",
        ),
    },
    {
        "code": "collateral_covenants",
        "title": "Collateral & Covenant Management",
        "objective": "Capture mitigants and contractual monitoring rules.",
        "priority": "high",
        "stories": (
            "Register collateral and apply haircut policies.",
            "Link collateral to one or more facilities.",
            "Define and test covenant thresholds.",
        ),
    },
    {
        "code": "pricing_profitability",
        "title": "Pricing & Profitability",
        "objective": "Validate deal economics against policy hurdles.",
        "priority": "high",
        "stories": (
            "Compute expected revenue and profitability metrics.",
            "Evaluate risk-based pricing and FTP impacts.",
            "Capture and approve pricing exceptions.",
        ),
    },
    {
        "code": "approvals_committee",
        "title": "Approvals & Credit Committee",
        "objective": "Formalize decisions, conditions and delegation controls.",
        "priority": "very_high",
        "stories": (
            "Apply approval matrix by amount, risk and product.",
            "Generate committee pack automatically.",
            "Record conditional decisions and policy exceptions.",
        ),
    },
    {
        "code": "documentation_cp",
        "title": "Documentation & Conditions Precedent",
        "objective": "Control legal readiness before booking and disbursement.",
        "priority": "high",
        "stories": (
            "Track product and jurisdiction checklists.",
            "Monitor missing documents and CP blockers.",
            "Track signature and legal review status.",
        ),
    },
    {
        "code": "limits_compliance_controls",
        "title": "Limits, Compliance & Controls",
        "objective": "Prevent policy and regulatory breaches in workflow.",
        "priority": "very_high",
        "stories": (
            "Run limit checks by borrower, group, country and sector.",
            "Block progression when mandatory controls fail.",
            "Log and approve policy exceptions with traceability.",
        ),
    },
    {
        "code": "booking_integration",
        "title": "Booking & Core Banking Integration",
        "objective": "Push approved deals downstream and reconcile outcomes.",
        "priority": "high",
        "stories": (
            "Send approved facilities to core systems.",
            "Track booking success/failure and references.",
            "Support reconciliation between origination and core records.",
        ),
    },
    {
        "code": "monitoring_amendments_renewals",
        "title": "Monitoring, Amendments & Renewals",
        "objective": "Manage full lifecycle changes after origination.",
        "priority": "medium_high",
        "stories": (
            "Launch amendment and renewal workflows from existing facilities.",
            "Compare approved terms versus amended terms.",
            "Handle waivers, breaches and restructuring cases.",
        ),
    },
    {
        "code": "reporting_audit_admin",
        "title": "Reporting, Audit & Administration",
        "objective": "Provide operational oversight, governance and admin controls.",
        "priority": "high",
        "stories": (
            "Publish SLA and approval turnaround dashboards.",
            "Expose full audit trail for data and decisions.",
            "Manage roles, products, workflows and reference data.",
        ),
    },
)


_BACKLOG_PRIORITY_TO_TASK: dict[str, str] = {
    "very_high": "critical",
    "high": "high",
    "medium_high": "normal",
}


def _seed_credit_implementation_backlog(tenant_id: int, actor_user_id: int | None) -> tuple[int, int]:
    created = 0
    skipped = 0
    existing_titles = {
        str(t[0])
        for t in db.session.query(CreditBacklogTask.title)
        .filter(CreditBacklogTask.tenant_id == tenant_id)
        .all()
        if t and t[0]
    }

    for epic in _CREDIT_IMPLEMENTATION_EPICS:
        title = f"[EPIC] {epic['title']}"
        if title in existing_titles:
            skipped += 1
            continue

        stories = epic.get("stories") if isinstance(epic.get("stories"), tuple) else ()
        stories_block = "\n".join([f"- {s}" for s in stories])
        description = (
            f"Objective: {epic['objective']}\n"
            f"Priority: {epic['priority']}\n"
            "Key backlog items:\n"
            f"{stories_block}"
        )

        db.session.add(
            CreditBacklogTask(
                tenant_id=tenant_id,
                title=title,
                description=description,
                status="todo",
                priority=_BACKLOG_PRIORITY_TO_TASK.get(str(epic["priority"]), "normal"),
                created_by_user_id=actor_user_id,
            )
        )
        created += 1

    if created:
        db.session.commit()
    return created, skipped


def _default_financial_csv_mapping() -> dict[str, str]:
    return {field: field for field in _FINANCIAL_CSV_FIELDS}


def _get_credit_settings(tenant: Tenant | None) -> dict:
    base = tenant.settings_json if tenant and isinstance(getattr(tenant, "settings_json", None), dict) else {}
    credit = base.get("credit") if isinstance(base.get("credit"), dict) else {}
    return {k: v for k, v in credit.items()}


def _save_credit_settings(tenant: Tenant, payload: dict) -> None:
    root = tenant.settings_json if isinstance(getattr(tenant, "settings_json", None), dict) else {}
    new_root = dict(root)
    new_root["credit"] = payload
    tenant.settings_json = new_root


def _credit_assignment_scopes(tenant: Tenant | None) -> dict[str, dict[str, dict[str, list[int]]]]:
    cfg = _get_credit_settings(tenant)
    raw = cfg.get("assignment_scopes") if isinstance(cfg.get("assignment_scopes"), dict) else {}
    users_raw = raw.get("users") if isinstance(raw.get("users"), dict) else {}
    groups_raw = raw.get("groups") if isinstance(raw.get("groups"), dict) else {}
    out: dict[str, dict[str, dict[str, list[int]]]] = {"users": {}, "groups": {}}

    def _ints(values) -> list[int]:
        parsed: list[int] = []
        for v in (values or []):
            try:
                iv = int(v)
            except Exception:
                continue
            if iv > 0:
                parsed.append(iv)
        return sorted(set(parsed))

    for uid, row in users_raw.items():
        uid_key = str(uid or "").strip()
        if not uid_key.isdigit() or not isinstance(row, dict):
            continue
        out["users"][uid_key] = {
            "sector_ids": _ints(row.get("sector_ids")),
            "country_ids": _ints(row.get("country_ids")),
            "rating_ids": _ints(row.get("rating_ids")),
        }

    for gid, row in groups_raw.items():
        gid_key = str(gid or "").strip()
        if not gid_key.isdigit() or not isinstance(row, dict):
            continue
        out["groups"][gid_key] = {
            "sector_ids": _ints(row.get("sector_ids")),
            "country_ids": _ints(row.get("country_ids")),
            "rating_ids": _ints(row.get("rating_ids")),
        }

    return out


def _save_credit_assignment_scope(
    tenant: Tenant,
    target_type: str,
    target_id: int,
    sector_ids: list[int],
    country_ids: list[int],
    rating_ids: list[int],
) -> None:
    ttype = str(target_type or "").strip().lower()
    if ttype not in {"user", "group"}:
        return
    try:
        tid = int(target_id)
    except Exception:
        return
    if tid <= 0:
        return

    cfg = _get_credit_settings(tenant)
    root = cfg.get("assignment_scopes") if isinstance(cfg.get("assignment_scopes"), dict) else {}
    users = root.get("users") if isinstance(root.get("users"), dict) else {}
    groups = root.get("groups") if isinstance(root.get("groups"), dict) else {}
    new_users = dict(users)
    new_groups = dict(groups)
    payload = {
        "sector_ids": sorted({int(v) for v in sector_ids if int(v) > 0}),
        "country_ids": sorted({int(v) for v in country_ids if int(v) > 0}),
        "rating_ids": sorted({int(v) for v in rating_ids if int(v) > 0}),
    }

    if ttype == "user":
        new_users[str(tid)] = payload
    else:
        new_groups[str(tid)] = payload

    cfg["assignment_scopes"] = {"users": new_users, "groups": new_groups}
    _save_credit_settings(tenant, cfg)


def _clear_credit_assignment_scope(tenant: Tenant, target_type: str, target_id: int) -> None:
    ttype = str(target_type or "").strip().lower()
    try:
        tid = int(target_id)
    except Exception:
        return
    if ttype not in {"user", "group"} or tid <= 0:
        return

    cfg = _get_credit_settings(tenant)
    root = cfg.get("assignment_scopes") if isinstance(cfg.get("assignment_scopes"), dict) else {}
    users = root.get("users") if isinstance(root.get("users"), dict) else {}
    groups = root.get("groups") if isinstance(root.get("groups"), dict) else {}
    new_users = dict(users)
    new_groups = dict(groups)

    if ttype == "user":
        new_users.pop(str(tid), None)
    else:
        new_groups.pop(str(tid), None)

    cfg["assignment_scopes"] = {"users": new_users, "groups": new_groups}
    _save_credit_settings(tenant, cfg)


def _scope_for_user_or_groups(
    tenant: Tenant,
    user_id: int,
    group_ids: list[int],
) -> list[dict[str, list[int]]]:
    scopes = _credit_assignment_scopes(tenant)
    out: list[dict[str, list[int]]] = []

    direct = scopes.get("users", {}).get(str(int(user_id))) if isinstance(scopes.get("users"), dict) else None
    if isinstance(direct, dict):
        out.append(direct)

    group_scopes = scopes.get("groups", {}) if isinstance(scopes.get("groups"), dict) else {}
    for gid in group_ids:
        row = group_scopes.get(str(int(gid))) if isinstance(group_scopes, dict) else None
        if isinstance(row, dict):
            out.append(row)
    return out


def _scope_counts_union(scopes: list[dict[str, list[int]]]) -> dict[str, int]:
    sectors: set[int] = set()
    countries: set[int] = set()
    ratings: set[int] = set()
    for scope in scopes:
        if not isinstance(scope, dict):
            continue
        sectors.update(int(v) for v in (scope.get("sector_ids") or []) if int(v) > 0)
        countries.update(int(v) for v in (scope.get("country_ids") or []) if int(v) > 0)
        ratings.update(int(v) for v in (scope.get("rating_ids") or []) if int(v) > 0)
    return {
        "sector_count": len(sectors),
        "country_count": len(countries),
        "rating_count": len(ratings),
    }


def _borrower_matches_scope(borrower: CreditBorrower | None, scope: dict[str, list[int]] | None) -> bool:
    if not borrower or not isinstance(scope, dict):
        return True

    sector_ids = [int(v) for v in (scope.get("sector_ids") or []) if int(v) > 0]
    country_ids = [int(v) for v in (scope.get("country_ids") or []) if int(v) > 0]
    rating_ids = [int(v) for v in (scope.get("rating_ids") or []) if int(v) > 0]

    if sector_ids and int(borrower.sector_id or 0) not in sector_ids:
        return False
    if country_ids and int(borrower.country_id or 0) not in country_ids:
        return False
    if rating_ids and int(borrower.rating_id or 0) not in rating_ids:
        return False
    return True


def _borrower_visible_for_user(tenant: Tenant, user_id: int, borrower: CreditBorrower | None) -> bool:
    if not borrower:
        return False
    if _can_manage_credit_backoffice():
        return True

    group_ids, function_codes_unused = _credit_user_group_scope(tenant.id, user_id)
    active_scopes = _scope_for_user_or_groups(tenant, user_id, group_ids)
    if not active_scopes:
        return True

    return any(_borrower_matches_scope(borrower, scope) for scope in active_scopes)


def _financial_csv_templates(tenant: Tenant | None) -> list[dict[str, object]]:
    cfg = _get_credit_settings(tenant)
    raw = cfg.get("financial_csv_templates") if isinstance(cfg.get("financial_csv_templates"), list) else []

    out: list[dict[str, object]] = []
    seen: set[str] = set()
    for item in raw:
        if not isinstance(item, dict):
            continue
        name = str(item.get("name") or "").strip()
        if not name:
            continue
        key = name.lower()
        if key in seen:
            continue
        seen.add(key)
        mapping = item.get("mapping") if isinstance(item.get("mapping"), dict) else {}
        cleaned_mapping: dict[str, str] = {}
        for fld in _FINANCIAL_CSV_FIELDS:
            val = str(mapping.get(fld) or "").strip()
            if val:
                cleaned_mapping[fld] = val
        out.append({"name": name, "mapping": cleaned_mapping})
    return out


def _save_financial_csv_templates(tenant: Tenant, templates: list[dict[str, object]]) -> None:
    cfg = _get_credit_settings(tenant)
    cfg["financial_csv_templates"] = templates
    _save_credit_settings(tenant, cfg)


def _find_financial_csv_template(tenant: Tenant, template_name: str | None) -> dict[str, str] | None:
    key = str(template_name or "").strip().lower()
    if not key:
        return None
    for item in _financial_csv_templates(tenant):
        name = str(item.get("name") or "").strip().lower()
        if name == key:
            mapping = item.get("mapping") if isinstance(item.get("mapping"), dict) else {}
            return {k: str(v) for k, v in mapping.items()}
    return None


def _memo_template_snippets(tenant: Tenant | None) -> list[dict[str, str]]:
    cfg = _get_credit_settings(tenant)
    raw = cfg.get("memo_template_snippets") if isinstance(cfg.get("memo_template_snippets"), list) else []
    out: list[dict[str, str]] = []
    seen: set[str] = set()
    for item in raw:
        if not isinstance(item, dict):
            continue
        name = str(item.get("name") or "").strip()
        content = str(item.get("content") or "").strip()
        snippet_id = str(item.get("id") or "").strip() or f"snip-{len(out) + 1}"
        if not name or not content:
            continue
        key = snippet_id.lower()
        if key in seen:
            continue
        seen.add(key)
        out.append({"id": snippet_id[:64], "name": name[:120], "content": content[:8000]})
    return out


def _save_memo_template_snippets(tenant: Tenant, snippets: list[dict[str, str]]) -> None:
    cfg = _get_credit_settings(tenant)
    cfg["memo_template_snippets"] = snippets
    _save_credit_settings(tenant, cfg)


def _definition_section_fingerprint(definition: dict[str, object]) -> list[dict[str, str]]:
    sections = definition.get("sections") if isinstance(definition.get("sections"), list) else []
    out: list[dict[str, str]] = []
    for sec in sections:
        if not isinstance(sec, dict):
            continue
        sec_id = str(sec.get("id") or "")
        title = str(sec.get("title") or "")
        sec_type = str(sec.get("type") or "")
        binding = str(sec.get("binding") or "")
        visibility_rule = str(sec.get("visibility_rule") or "")
        content = str(sec.get("content") or "")
        signature = "|".join([title, sec_type, binding, visibility_rule, content])
        out.append({"id": sec_id, "title": title, "type": sec_type, "signature": signature})
    return out


def _memo_template_compare_summary(a: dict[str, object], b: dict[str, object]) -> dict[str, object]:
    a_fp = _definition_section_fingerprint(a)
    b_fp = _definition_section_fingerprint(b)

    a_by_id = {x["id"]: x for x in a_fp if x.get("id")}
    b_by_id = {x["id"]: x for x in b_fp if x.get("id")}

    a_ids = set(a_by_id.keys())
    b_ids = set(b_by_id.keys())
    added_ids = sorted(list(b_ids - a_ids))
    removed_ids = sorted(list(a_ids - b_ids))

    changed: list[dict[str, str]] = []
    for sec_id in sorted(list(a_ids & b_ids)):
        if a_by_id[sec_id].get("signature") != b_by_id[sec_id].get("signature"):
            changed.append(
                {
                    "id": sec_id,
                    "title_a": str(a_by_id[sec_id].get("title") or ""),
                    "title_b": str(b_by_id[sec_id].get("title") or ""),
                }
            )

    return {
        "count_a": len(a_fp),
        "count_b": len(b_fp),
        "added": [{"id": i, "title": str(b_by_id.get(i, {}).get("title") or i)} for i in added_ids[:12]],
        "removed": [{"id": i, "title": str(a_by_id.get(i, {}).get("title") or i)} for i in removed_ids[:12]],
        "changed": changed[:20],
    }


def _html_to_text(src: str) -> str:
    # First unescape entities so encoded HTML like &lt;div&gt; can be cleaned as tags.
    raw = html_unescape(str(src or ""))
    no_style = re.sub(r"<style[\s\S]*?</style>", "", raw, flags=re.IGNORECASE)
    no_script = re.sub(r"<script[\s\S]*?</script>", "", no_style, flags=re.IGNORECASE)
    with_breaks = re.sub(r"<(br|/p|/div|/section|/h1|/h2|/h3|/h4|/h5|/h6|/li|/tr)\s*/?>", "\n", no_script, flags=re.IGNORECASE)
    no_tags = re.sub(r"<[^>]+>", "", with_breaks)
    text = html_unescape(no_tags)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def _mapping_from_form(form, prefix: str = "map_") -> dict[str, str]:
    out: dict[str, str] = {}
    for field in _FINANCIAL_CSV_FIELDS:
        val = str(form.get(f"{prefix}{field}") or "").strip()
        if val:
            out[field] = val
    return out


def _extract_pdf_text(pdf_bytes: bytes, max_chars: int = 24000) -> str:
    try:
        import pdfplumber
    except Exception:
        return ""

    chunks: list[str] = []
    try:
        with pdfplumber.open(io.BytesIO(pdf_bytes)) as pdf:
            for page in pdf.pages[:30]:
                txt = (page.extract_text() or "").strip()
                if txt:
                    chunks.append(txt)
                if sum(len(c) for c in chunks) >= max_chars:
                    break
    except Exception:
        return ""

    out = "\n".join(chunks)
    return out[:max_chars]


def _parse_first_json_object(text: str) -> dict | None:
    if not text:
        return None
    s = str(text).strip()
    try:
        parsed = json.loads(s)
        return parsed if isinstance(parsed, dict) else None
    except Exception:
        pass

    start = s.find("{")
    end = s.rfind("}")
    if start >= 0 and end > start:
        try:
            parsed = json.loads(s[start : end + 1])
            return parsed if isinstance(parsed, dict) else None
        except Exception:
            return None
    return None


def _ai_extract_financial_payload(pdf_text: str, lang: str | None = None) -> dict | None:
    if not pdf_text.strip():
        return None

    prompt = (
        "Extract one annual financial statement from the document text. "
        "Return ONLY one compact JSON object with keys: "
        "period_label, fiscal_year, revenue, ebitda, total_debt, cash, net_income, spreading_status, confidence. "
        "Use numeric values only (no currency symbols), spreading_status in [in_progress, completed, needs_review]. "
        "If uncertain, keep best estimate and set confidence below 0.7."
    )
    ai = analyze_with_ai(
        data_bundle={
            "question": "credit_pdf_spreading",
            "source": "credit_financial_statement_pdf",
            "result": {"pdf_text": pdf_text[:18000]},
        },
        user_message=prompt,
        lang=lang,
    )
    if not isinstance(ai, dict):
        return None

    parsed = _parse_first_json_object(str(ai.get("analysis") or ""))
    if parsed:
        return parsed

    raw = _parse_first_json_object(str(ai.get("raw") or ""))
    return raw if isinstance(raw, dict) else None


_CREDIT_SYSTEM_ROLES: tuple[tuple[str, str], ...] = (
    ("credit_admin", "Administration credit et workflow"),
    ("credit_analyst", "Analyste credit"),
    ("credit_approver", "Approbateur credit"),
    ("credit_viewer", "Lecture seule credit"),
)


def _seed_credit_system_roles() -> None:
    changed = False
    for code, description in _CREDIT_SYSTEM_ROLES:
        if Role.query.filter_by(code=code).first():
            continue
        db.session.add(Role(code=code, description=description))
        changed = True
    if changed:
        db.session.commit()


def _has_credit_role(*codes: str) -> bool:
    for code in codes:
        if current_user.has_role(code):
            return True
    return False


def _can_manage_credit_backoffice() -> bool:
    return _has_credit_role("tenant_admin", "credit_admin")


def _can_record_approval_decisions() -> bool:
    return _has_credit_role("tenant_admin", "credit_admin", "credit_approver")


def _can_create_credit_task() -> bool:
    return _has_credit_role("tenant_admin", "credit_admin", "credit_analyst", "credit_approver")


def _can_edit_memo_templates() -> bool:
    return _has_credit_role("tenant_admin", "credit_admin", "credit_analyst")


def _can_publish_memo_templates() -> bool:
    return _has_credit_role("tenant_admin", "credit_admin", "credit_approver")


def _can_view_memo_templates() -> bool:
    return _has_credit_role("tenant_admin", "credit_admin", "credit_analyst", "credit_approver", "credit_viewer")


_MEMO_TEMPLATE_TYPES: tuple[tuple[str, str], ...] = (
    ("full_credit_memo", "Full credit memo"),
    ("short_form_note", "Short-form credit note"),
    ("annual_review_memo", "Annual review memo"),
    ("amendment_waiver_memo", "Amendment / waiver memo"),
    ("committee_summary_pack", "Committee summary pack"),
    ("covenant_breach_memo", "Covenant breach memo"),
    ("collateral_summary", "Collateral summary"),
    ("deal_approval_cover_sheet", "Deal approval cover sheet"),
)

_MEMO_TOOLBOX_COMPONENTS: tuple[tuple[str, str], ...] = (
    ("heading", "Title / heading"),
    ("paragraph", "Paragraph"),
    ("text_block", "Text block"),
    ("data_field", "Data field"),
    ("table", "Table"),
    ("repeating_list", "Repeating list"),
    ("section", "Section container"),
    ("approval_block", "Approval block"),
    ("conditional", "Conditional block"),
    ("divider", "Divider"),
    ("page_break", "Page break"),
    ("comment", "Comment / instruction block"),
)

_MEMO_DATA_EXPLORER: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("Deal", ("Deal.Code", "Deal.ProductType", "Deal.Currency", "Deal.RequestedAmount", "Deal.Purpose", "Deal.Status")),
    ("Borrower", ("Borrower.Name", "Borrower.Country", "Borrower.Sector", "Borrower.InternalRating")),
    ("Financials", ("Financials.Period", "Financials.FiscalYear", "Financials.Revenue", "Financials.EBITDA", "Financials.TotalDebt", "Financials.Cash", "Financials.NetIncome")),
    ("Ratios", ("Ratios.DSCR", "Ratios.Leverage", "Ratios.Liquidity", "Ratios.RiskGrade")),
    ("Workflow", ("Workflow.ApproverName", "Workflow.CurrentStage", "Workflow.LastDecision", "Workflow.DecidedAt")),
)


def _default_memo_template_definition() -> dict[str, object]:
    return {
        "meta": {
            "layout": "grid",
            "page": {"size": "A4", "margin": 24, "header": "", "footer": ""},
            "theme": {"font": "Source Sans Pro", "primaryColor": "#0b4f6c"},
        },
        "sections": [
            {
                "id": "sec-exec-summary",
                "name": "Executive Summary",
                "type": "paragraph",
                "title": "Executive Summary",
                "content": "The borrower {Borrower.Name} requests {Deal.Currency} {Deal.RequestedAmount} for {Deal.Purpose}.",
                "binding": "",
                "visibility_rule": "",
                "mandatory": True,
                "locked": False,
                "page_break": False,
                "style": {"font_size": 14, "align": "left", "color": "#102a43"},
            },
            {
                "id": "sec-fin-analysis",
                "name": "Financial Analysis",
                "type": "table",
                "title": "Financial Analysis",
                "content": "",
                "binding": "Financials",
                "visibility_rule": "",
                "mandatory": True,
                "locked": False,
                "page_break": False,
                "style": {"font_size": 12, "align": "left", "color": "#243b53"},
            },
            {
                "id": "sec-recommendation",
                "name": "Recommendation",
                "type": "paragraph",
                "title": "Recommendation",
                "content": "Recommendation: review",
                "binding": "",
                "visibility_rule": "",
                "mandatory": True,
                "locked": False,
                "page_break": False,
                "style": {"font_size": 13, "align": "left", "color": "#102a43"},
            },
        ],
    }


def _sanitize_memo_template_definition(raw: object) -> dict[str, object]:
    src = raw if isinstance(raw, dict) else {}
    meta = src.get("meta") if isinstance(src.get("meta"), dict) else {}
    sections_raw = src.get("sections") if isinstance(src.get("sections"), list) else []

    sections: list[dict[str, object]] = []
    for idx, item in enumerate(sections_raw, start=1):
        if not isinstance(item, dict):
            continue
        section_id = str(item.get("id") or f"sec-{idx}").strip() or f"sec-{idx}"
        section_type = str(item.get("type") or "text_block").strip().lower()
        if section_type not in {
            "heading",
            "paragraph",
            "text_block",
            "data_field",
            "table",
            "repeating_list",
            "section",
            "approval_block",
            "conditional",
            "divider",
            "page_break",
            "comment",
        }:
            section_type = "text_block"

        style = item.get("style") if isinstance(item.get("style"), dict) else {}
        sections.append(
            {
                "id": section_id[:120],
                "name": str(item.get("name") or item.get("title") or section_id).strip()[:180],
                "type": section_type,
                "title": str(item.get("title") or "").strip()[:180],
                "content": str(item.get("content") or "")[:12000],
                "binding": str(item.get("binding") or "").strip()[:180],
                "visibility_rule": str(item.get("visibility_rule") or "").strip()[:500],
                "mandatory": bool(item.get("mandatory")),
                "locked": bool(item.get("locked")),
                "page_break": bool(item.get("page_break")),
                "style": {
                    "font_size": int(style.get("font_size") or 12),
                    "align": str(style.get("align") or "left")[:20],
                    "color": str(style.get("color") or "#243b53")[:20],
                },
            }
        )

    if not sections:
        return _default_memo_template_definition()

    return {
        "meta": {
            "layout": str(meta.get("layout") or "grid"),
            "page": meta.get("page") if isinstance(meta.get("page"), dict) else {"size": "A4", "margin": 24},
            "theme": meta.get("theme") if isinstance(meta.get("theme"), dict) else {"font": "Source Sans Pro", "primaryColor": "#0b4f6c"},
        },
        "sections": sections,
    }


def _latest_memo_template_version(template_id: int, tenant_id: int) -> CreditMemoTemplateVersion | None:
    return (
        CreditMemoTemplateVersion.query.filter_by(template_id=template_id, tenant_id=tenant_id)
        .order_by(CreditMemoTemplateVersion.version_no.desc(), CreditMemoTemplateVersion.id.desc())
        .first()
    )


def _resolve_memo_template_definition(
    template: CreditMemoTemplate,
    version: CreditMemoTemplateVersion | None,
) -> dict[str, object]:
    current = _sanitize_memo_template_definition((version.definition_json if version else None) or _default_memo_template_definition())
    if not template.base_template_id:
        return current

    base = CreditMemoTemplate.query.filter_by(id=template.base_template_id, tenant_id=template.tenant_id).first()
    if not base:
        return current

    base_version = None
    if base.published_version_no:
        base_version = CreditMemoTemplateVersion.query.filter_by(
            tenant_id=template.tenant_id,
            template_id=base.id,
            version_no=base.published_version_no,
        ).first()
    if not base_version:
        base_version = _latest_memo_template_version(base.id, template.tenant_id)
    if not base_version:
        return current

    base_def = _sanitize_memo_template_definition(base_version.definition_json or _default_memo_template_definition())
    merged = deepcopy(base_def)
    merged_sections = [dict(s, inherited=True) for s in base_def.get("sections", []) if isinstance(s, dict)]
    merged_sections.extend([dict(s, inherited=False) for s in current.get("sections", []) if isinstance(s, dict)])
    merged["sections"] = merged_sections
    return merged


def _memo_preview_context(tenant_id: int, deal_id: int | None = None) -> dict[str, object]:
    deal = None
    if deal_id:
        deal = CreditDeal.query.filter_by(id=deal_id, tenant_id=tenant_id).first()
    if not deal:
        deal = CreditDeal.query.filter_by(tenant_id=tenant_id).order_by(CreditDeal.updated_at.desc()).first()

    borrower = (
        CreditBorrower.query.filter_by(id=deal.borrower_id, tenant_id=tenant_id).first()
        if deal and deal.borrower_id
        else CreditBorrower.query.filter_by(tenant_id=tenant_id).order_by(CreditBorrower.updated_at.desc()).first()
    )

    statement = None
    ratio = None
    if borrower:
        statement = (
            CreditFinancialStatement.query.filter_by(tenant_id=tenant_id, borrower_id=borrower.id)
            .order_by(CreditFinancialStatement.created_at.desc())
            .first()
        )
        ratio = (
            CreditRatioSnapshot.query.filter_by(tenant_id=tenant_id, borrower_id=borrower.id)
            .order_by(CreditRatioSnapshot.created_at.desc())
            .first()
        )

    latest_approval = CreditApproval.query.filter_by(tenant_id=tenant_id).order_by(CreditApproval.created_at.desc()).first()

    return {
        "Deal": {
            "Code": getattr(deal, "code", "DEAL-001"),
            "ProductType": getattr(deal, "product_type", "Term Loan"),
            "Currency": getattr(deal, "currency", "EUR"),
            "RequestedAmount": float(getattr(deal, "requested_amount", 0) or 0),
            "Purpose": getattr(deal, "purpose", "Working capital"),
            "Status": getattr(deal, "status", "pipeline"),
        },
        "Borrower": {
            "Name": getattr(borrower, "name", "Sample Borrower"),
            "Country": getattr(borrower, "country", "FR"),
            "Sector": getattr(borrower, "sector", "General"),
            "InternalRating": getattr(borrower, "internal_rating", "BBB"),
        },
        "Financials": {
            "Period": getattr(statement, "period_label", "FY"),
            "FiscalYear": getattr(statement, "fiscal_year", date.today().year),
            "Revenue": float(getattr(statement, "revenue", 0) or 0),
            "EBITDA": float(getattr(statement, "ebitda", 0) or 0),
            "TotalDebt": float(getattr(statement, "total_debt", 0) or 0),
            "Cash": float(getattr(statement, "cash", 0) or 0),
            "NetIncome": float(getattr(statement, "net_income", 0) or 0),
        },
        "Ratios": {
            "DSCR": float(getattr(ratio, "dscr", 0) or 0),
            "Leverage": float(getattr(ratio, "leverage", 0) or 0),
            "Liquidity": float(getattr(ratio, "liquidity", 0) or 0),
            "RiskGrade": getattr(ratio, "risk_grade", "BB"),
        },
        "Workflow": {
            "ApproverName": getattr(getattr(latest_approval, "actor_user", None), "email", "n/a"),
            "CurrentStage": getattr(latest_approval, "stage", "analyst_review"),
            "LastDecision": getattr(latest_approval, "decision", "pending"),
            "DecidedAt": str(getattr(latest_approval, "decided_at", "") or ""),
        },
    }


def _resolve_context_value(payload: dict[str, object], path: str) -> object:
    cur: object = payload
    for chunk in [p for p in str(path or "").split(".") if p]:
        if isinstance(cur, dict) and chunk in cur:
            cur = cur.get(chunk)
        else:
            return None
    return cur


def _replace_tokens(text: str, payload: dict[str, object]) -> str:
    def _rep(match: re.Match[str]) -> str:
        key = (match.group(1) or "").strip()
        value = _resolve_context_value(payload, key)
        if value is None:
            return ""
        if isinstance(value, float):
            return f"{value:,.2f}"
        return str(value)

    return re.sub(r"\{([A-Za-z0-9_.]+)\}", _rep, text or "")


def _to_num(value: object) -> Decimal | None:
    try:
        return Decimal(str(value))
    except Exception:
        return None


def _eval_visibility(rule: str, payload: dict[str, object]) -> bool:
    src = str(rule or "").strip()
    if not src:
        return True

    parts = re.split(r"\s+(AND|OR)\s+", src, flags=re.IGNORECASE)

    def _eval_atom(expr: str) -> bool:
        m = re.match(
            r"^\s*([A-Za-z0-9_.]+)\s*(==|!=|>=|<=|>|<|contains|not contains|is empty|is not empty)\s*(.*?)\s*$",
            expr,
            flags=re.IGNORECASE,
        )
        if not m:
            return False
        key, op, rhs = m.group(1), m.group(2).lower(), m.group(3)
        left = _resolve_context_value(payload, key)
        rhs_clean = rhs.strip().strip("\"").strip("'")

        if op == "is empty":
            return left in (None, "", [], {})
        if op == "is not empty":
            return left not in (None, "", [], {})
        if op == "contains":
            return rhs_clean.lower() in str(left or "").lower()
        if op == "not contains":
            return rhs_clean.lower() not in str(left or "").lower()

        if op in {">", ">=", "<", "<="}:
            left_num = _to_num(left)
            right_num = _to_num(rhs_clean)
            if left_num is None or right_num is None:
                return False
            if op == ">":
                return left_num > right_num
            if op == ">=":
                return left_num >= right_num
            if op == "<":
                return left_num < right_num
            return left_num <= right_num

        if op == "==":
            return str(left or "").strip().lower() == rhs_clean.lower()
        if op == "!=":
            return str(left or "").strip().lower() != rhs_clean.lower()
        return False

    outcome = _eval_atom(parts[0]) if parts else True
    i = 1
    while i + 1 < len(parts):
        connector = str(parts[i]).upper()
        right = _eval_atom(parts[i + 1])
        outcome = (outcome and right) if connector == "AND" else (outcome or right)
        i += 2
    return outcome


def _validate_memo_template_definition(definition: dict[str, object], payload: dict[str, object]) -> list[dict[str, str]]:
    findings: list[dict[str, str]] = []
    sections = definition.get("sections") if isinstance(definition.get("sections"), list) else []
    if not sections:
        findings.append({"severity": "error", "message": _("Template has no sections.")})
        return findings

    ids: set[str] = set()
    for idx, sec in enumerate(sections, start=1):
        if not isinstance(sec, dict):
            findings.append({"severity": "error", "message": _("Invalid section object at position {idx}.", idx=idx)})
            continue

        sec_id = str(sec.get("id") or "")
        if sec_id and sec_id in ids:
            findings.append({"severity": "warning", "message": _("Duplicate section id: {id}", id=sec_id)})
        ids.add(sec_id)

        title = str(sec.get("title") or "")
        if not title:
            findings.append({"severity": "warning", "message": _("Section {idx} has no title.", idx=idx)})

        binding = str(sec.get("binding") or "").strip()
        if binding and _resolve_context_value(payload, binding) is None:
            findings.append({"severity": "warning", "message": _("Unknown binding: {binding}", binding=binding)})

        rule = str(sec.get("visibility_rule") or "").strip()
        if rule and not _eval_visibility(rule, payload):
            findings.append({"severity": "info", "message": _("Section hidden by rule: {rule}", rule=rule)})

        if bool(sec.get("mandatory")) and not str(sec.get("content") or "").strip() and not binding:
            findings.append({"severity": "warning", "message": _("Mandatory section {idx} has no content or binding.", idx=idx)})

    return findings


def _render_memo_template_html(
    template_name: str,
    definition: dict[str, object],
    payload: dict[str, object],
) -> str:
    sections = definition.get("sections") if isinstance(definition.get("sections"), list) else []
    blocks: list[str] = []

    for sec in sections:
        if not isinstance(sec, dict):
            continue
        if not _eval_visibility(str(sec.get("visibility_rule") or ""), payload):
            continue

        title = html_escape(str(sec.get("title") or ""), quote=True)
        section_type = str(sec.get("type") or "text_block")
        binding = str(sec.get("binding") or "")
        raw_content = str(sec.get("content") or "")
        content = _replace_tokens(raw_content, payload)

        if section_type == "table" and binding == "Financials":
            f = payload.get("Financials") if isinstance(payload.get("Financials"), dict) else {}
            table_html = (
                "<table class='memo-table'><thead><tr><th>Period</th><th>Revenue</th><th>EBITDA</th><th>Total Debt</th><th>Cash</th><th>Net Income</th></tr></thead>"
                f"<tbody><tr><td>{html_escape(str(f.get('Period', '')), quote=True)} {html_escape(str(f.get('FiscalYear', '')), quote=True)}</td>"
                f"<td>{html_escape(str(f.get('Revenue', '')), quote=True)}</td>"
                f"<td>{html_escape(str(f.get('EBITDA', '')), quote=True)}</td>"
                f"<td>{html_escape(str(f.get('TotalDebt', '')), quote=True)}</td>"
                f"<td>{html_escape(str(f.get('Cash', '')), quote=True)}</td>"
                f"<td>{html_escape(str(f.get('NetIncome', '')), quote=True)}</td></tr></tbody></table>"
            )
            blocks.append(f"<section class='memo-section'><h3>{title}</h3>{table_html}</section>")
            continue

        if section_type == "data_field" and binding:
            val = _resolve_context_value(payload, binding)
            body = html_escape(str(val if val is not None else ""), quote=True)
        elif section_type == "divider":
            body = "<hr>"
        elif section_type == "approval_block":
            wf = payload.get("Workflow") if isinstance(payload.get("Workflow"), dict) else {}
            body = (
                "<div class='approval-block'>"
                f"<div><strong>Approver:</strong> {html_escape(str(wf.get('ApproverName', '')), quote=True)}</div>"
                f"<div><strong>Stage:</strong> {html_escape(str(wf.get('CurrentStage', '')), quote=True)}</div>"
                f"<div><strong>Decision:</strong> {html_escape(str(wf.get('LastDecision', '')), quote=True)}</div>"
                "</div>"
            )
        else:
            body = html_escape(content, quote=True).replace("\n", "<br>")

        blocks.append(f"<section class='memo-section'><h3>{title}</h3><div>{body}</div></section>")
        if bool(sec.get("page_break")):
            blocks.append("<div class='page-break'></div>")

    body_html = "\n".join(blocks) if blocks else "<p>No visible sections.</p>"
    return (
        "<!doctype html><html><head><meta charset='utf-8'><title>"
        + html_escape(template_name, quote=True)
        + "</title><style>body{font-family:Arial,sans-serif;padding:28px;color:#102a43;}"
        ".memo-section{margin:0 0 18px 0;padding:14px;border:1px solid #d9e2ec;border-radius:8px;background:#fff;}"
        ".memo-section h3{margin:0 0 10px 0;font-size:18px;color:#0b4f6c;}"
        ".memo-table{width:100%;border-collapse:collapse;}"
        ".memo-table th,.memo-table td{border:1px solid #bcccdc;padding:6px 8px;font-size:12px;}"
        ".memo-table th{background:#f0f4f8;text-align:left;}"
        ".approval-block{display:grid;gap:4px;}"
        ".page-break{page-break-after:always;height:1px;}"
        "</style></head><body>"
        + body_html
        + "</body></html>"
    )


def _memo_template_export_response(title: str, html: str, fmt: str):
    format_key = str(fmt or "html").strip().lower()
    if format_key == "doc":
        format_key = "word"
    safe_name = re.sub(r"[^a-zA-Z0-9_-]+", "_", title or "credit_memo_template")

    if format_key == "word":
        resp = make_response(html)
        resp.headers["Content-Type"] = "application/msword"
        resp.headers["Content-Disposition"] = f"attachment; filename={safe_name}.doc"
        return resp

    if format_key == "pdf":
        payload = None
        try:
            from weasyprint import HTML  # type: ignore

            payload = HTML(string=html).write_pdf()
        except Exception:
            payload = _pdf_bytes_from_html(title or "Credit memo", html)

        resp = make_response(payload)
        resp.headers["Content-Type"] = "application/pdf"
        resp.headers["Content-Disposition"] = f"inline; filename={safe_name}.pdf"
        resp.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
        resp.headers["Pragma"] = "no-cache"
        resp.headers["Expires"] = "0"
        return resp

    resp = make_response(html)
    resp.headers["Content-Type"] = "text/html; charset=utf-8"
    resp.headers["Content-Disposition"] = f"attachment; filename={safe_name}.html"
    return resp


def _pdf_bytes_from_html(title: str, html_src: str) -> bytes:
    """Create a styled PDF from memo HTML with section/table support."""
    try:
        from io import BytesIO
        from xml.sax.saxutils import escape as xml_escape
        from reportlab.lib import colors
        from reportlab.lib.enums import TA_LEFT
        from reportlab.lib.pagesizes import A4
        from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
        from reportlab.platypus import PageBreak, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

        html = str(html_src or "")
        buffer = BytesIO()
        doc = SimpleDocTemplate(
            buffer,
            pagesize=A4,
            leftMargin=36,
            rightMargin=36,
            topMargin=34,
            bottomMargin=30,
            title=title or "Credit memo",
        )

        styles = getSampleStyleSheet()
        title_style = ParagraphStyle(
            "MemoTitle",
            parent=styles["Heading1"],
            fontName="Helvetica-Bold",
            fontSize=17,
            leading=21,
            alignment=TA_LEFT,
            textColor=colors.HexColor("#0b4f6c"),
            spaceAfter=10,
        )
        h3_style = ParagraphStyle(
            "MemoH3",
            parent=styles["Heading3"],
            fontName="Helvetica-Bold",
            fontSize=12.5,
            leading=15,
            textColor=colors.HexColor("#102a43"),
            spaceAfter=6,
            spaceBefore=5,
        )
        body_style = ParagraphStyle(
            "MemoBody",
            parent=styles["BodyText"],
            fontName="Helvetica",
            fontSize=10,
            leading=14,
            textColor=colors.HexColor("#243b53"),
            spaceAfter=8,
        )

        def _to_para_text(raw_html: str) -> str:
            plain = _html_to_text(raw_html)
            if not plain.strip():
                return ""
            return xml_escape(plain).replace("\n", "<br/>")

        story = [Paragraph(xml_escape(title or "Credit memo"), title_style), Spacer(1, 6)]

        page_break_pattern = re.compile(
            r"<div[^>]*class=['\"]?[^'\">]*page-break[^'\">]*['\"]?[^>]*>\s*</div>",
            flags=re.IGNORECASE,
        )
        section_pattern = re.compile(r"<section[^>]*>([\s\S]*?)</section>", flags=re.IGNORECASE)
        h3_pattern = re.compile(r"<h3[^>]*>([\s\S]*?)</h3>", flags=re.IGNORECASE)
        div_pattern = re.compile(r"<div[^>]*>([\s\S]*?)</div>", flags=re.IGNORECASE)
        table_pattern = re.compile(r"<table[^>]*>([\s\S]*?)</table>", flags=re.IGNORECASE)
        row_pattern = re.compile(r"<tr[^>]*>([\s\S]*?)</tr>", flags=re.IGNORECASE)
        cell_pattern = re.compile(r"<t[dh][^>]*>([\s\S]*?)</t[dh]>", flags=re.IGNORECASE)

        parts = re.split(page_break_pattern, html)
        for idx, part in enumerate(parts):
            part = str(part or "")
            section_matches = list(section_pattern.finditer(part))
            if not section_matches:
                fallback_text = _to_para_text(part)
                if fallback_text:
                    story.append(Paragraph(fallback_text, body_style))
            else:
                for sec in section_matches:
                    sec_html = sec.group(1)
                    title_match = h3_pattern.search(sec_html)
                    sec_title = _html_to_text(title_match.group(1) if title_match else "")
                    if sec_title:
                        story.append(Paragraph(xml_escape(sec_title), h3_style))

                    body_match = div_pattern.search(sec_html)
                    body_html = body_match.group(1) if body_match else sec_html

                    table_match = table_pattern.search(body_html)
                    if table_match:
                        table_html = table_match.group(1)
                        rows: list[list[str]] = []
                        for row_match in row_pattern.finditer(table_html):
                            row_html = row_match.group(1)
                            cells: list[str] = []
                            for cell_match in cell_pattern.finditer(row_html):
                                cell_txt = _html_to_text(cell_match.group(1)).replace("\n", " ").strip()
                                cells.append(cell_txt)
                            if cells:
                                rows.append(cells)

                        if rows:
                            max_cols = max(len(r) for r in rows)
                            normalized = [r + [""] * (max_cols - len(r)) for r in rows]
                            col_width = (A4[0] - doc.leftMargin - doc.rightMargin) / max(1, max_cols)
                            table = Table(normalized, colWidths=[col_width] * max_cols, repeatRows=1)
                            table.setStyle(
                                TableStyle(
                                    [
                                        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#f0f4f8")),
                                        ("TEXTCOLOR", (0, 0), (-1, 0), colors.HexColor("#102a43")),
                                        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                                        ("FONTNAME", (0, 1), (-1, -1), "Helvetica"),
                                        ("FONTSIZE", (0, 0), (-1, -1), 9),
                                        ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#bcccdc")),
                                        ("VALIGN", (0, 0), (-1, -1), "TOP"),
                                        ("LEFTPADDING", (0, 0), (-1, -1), 6),
                                        ("RIGHTPADDING", (0, 0), (-1, -1), 6),
                                        ("TOPPADDING", (0, 0), (-1, -1), 4),
                                        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
                                    ]
                                )
                            )
                            story.append(table)
                            story.append(Spacer(1, 8))

                        body_without_table = table_pattern.sub("", body_html)
                        body_text = _to_para_text(body_without_table)
                        if body_text:
                            story.append(Paragraph(body_text, body_style))
                    else:
                        body_text = _to_para_text(body_html)
                        if body_text:
                            story.append(Paragraph(body_text, body_style))
                    story.append(Spacer(1, 4))

            if idx < len(parts) - 1 and len(story) > 1:
                story.append(PageBreak())

        doc.build(story)
        payload = buffer.getvalue()
        buffer.close()
        if payload.startswith(b"%PDF"):
            return payload
    except Exception:
        pass

    return _pdf_bytes_from_text(title, _html_to_text(html_src))


def _pdf_bytes_from_text(title: str, text_src: str) -> bytes:
    """Create a valid PDF payload from plain text with robust fallbacks."""
    # Try ReportLab first for multi-page rendering.
    try:
        from io import BytesIO
        from reportlab.lib.pagesizes import A4
        from reportlab.lib.utils import simpleSplit
        from reportlab.pdfgen import canvas

        lines = [ln.strip() for ln in str(text_src or "").splitlines()]
        if not any(lines):
            lines = [title or "Credit memo"]

        buffer = BytesIO()
        pdf = canvas.Canvas(buffer, pagesize=A4)
        width, height = A4
        margin = 40
        y = height - margin

        pdf.setTitle(title or "Credit memo")
        pdf.setFont("Helvetica-Bold", 13)
        for tline in simpleSplit(title or "Credit memo", "Helvetica-Bold", 13, width - (2 * margin)):
            if y < margin:
                pdf.showPage()
                y = height - margin
                pdf.setFont("Helvetica-Bold", 13)
            pdf.drawString(margin, y, tline)
            y -= 16

        y -= 6
        pdf.setFont("Helvetica", 10)
        for line in lines:
            wrapped = simpleSplit(line or " ", "Helvetica", 10, width - (2 * margin)) or [" "]
            for chunk in wrapped:
                if y < margin:
                    pdf.showPage()
                    y = height - margin
                    pdf.setFont("Helvetica", 10)
                pdf.drawString(margin, y, chunk)
                y -= 13

        pdf.save()
        payload = buffer.getvalue()
        buffer.close()
        if payload.startswith(b"%PDF"):
            return payload
    except Exception:
        pass

    # Last-resort pure-Python single-page PDF builder.
    lines = [ln.strip() for ln in str(text_src or "").splitlines()]
    if not any(lines):
        lines = [title or "Credit memo"]

    def _esc(s: str) -> str:
        return s.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")

    commands = ["BT", "/F1 12 Tf", "50 800 Td", f"({_esc(title or 'Credit memo')}) Tj", "0 -20 Td", "/F1 10 Tf"]
    for line in lines[:120]:
        commands.append(f"({_esc(line or ' ')}) Tj")
        commands.append("0 -13 Td")
    commands.append("ET")
    stream_text = "\n".join(commands).encode("latin-1", errors="replace")

    objects = [
        b"1 0 obj\n<< /Type /Catalog /Pages 2 0 R >>\nendobj\n",
        b"2 0 obj\n<< /Type /Pages /Kids [3 0 R] /Count 1 >>\nendobj\n",
        b"3 0 obj\n<< /Type /Page /Parent 2 0 R /MediaBox [0 0 595 842] /Resources << /Font << /F1 4 0 R >> >> /Contents 5 0 R >>\nendobj\n",
        b"4 0 obj\n<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>\nendobj\n",
        (f"5 0 obj\n<< /Length {len(stream_text)} >>\nstream\n".encode("ascii") + stream_text + b"\nendstream\nendobj\n"),
    ]

    out = bytearray(b"%PDF-1.4\n")
    offsets = [0]
    for obj in objects:
        offsets.append(len(out))
        out.extend(obj)

    xref_pos = len(out)
    out.extend(f"xref\n0 {len(objects) + 1}\n".encode("ascii"))
    out.extend(b"0000000000 65535 f \n")
    for off in offsets[1:]:
        out.extend(f"{off:010d} 00000 n \n".encode("ascii"))
    out.extend(
        (
            f"trailer\n<< /Size {len(objects) + 1} /Root 1 0 R >>\n"
            f"startxref\n{xref_pos}\n%%EOF\n"
        ).encode("ascii")
    )
    return bytes(out)


def _credit_user_group_scope(tenant_id: int, user_id: int) -> tuple[list[int], list[str]]:
    rows = (
        CreditAnalystGroupMember.query.join(CreditAnalystGroup)
        .filter(
            CreditAnalystGroup.tenant_id == tenant_id,
            CreditAnalystGroupMember.user_id == user_id,
        )
        .all()
    )
    group_ids = sorted({int(r.group_id) for r in rows if r.group_id})
    function_codes = sorted(
        {
            str(r.function_ref.code if r.function_ref else r.function_name)
            for r in rows
            if (r.function_ref and r.function_ref.code) or r.function_name
        }
    )
    return group_ids, function_codes


_ML_LANGS = ("fr", "en", "pt", "es", "it", "de")

_REF_KIND_MODEL_MAP = {
    "countries": CreditCountry,
    "sectors": CreditSector,
    "ratings": CreditRating,
    "facility_types": CreditFacilityType,
    "collateral_types": CreditCollateralType,
    "guarantee_types": CreditGuaranteeType,
}


def _ml_values(form, prefix: str) -> dict[str, str | None]:
    out: dict[str, str | None] = {}
    for lang in _ML_LANGS:
        key = f"{prefix}_{lang}"
        out[key] = (form.get(key) or "").strip() or None
    return out


def _seed_credit_references() -> None:
    changed = False

    if CreditCountry.query.count() == 0:
        for iso_code, fr, en, pt, es, it, de in [
            ("FR", "France", "France", "Franca", "Francia", "Francia", "Frankreich"),
            ("PT", "Portugal", "Portugal", "Portugal", "Portugal", "Portogallo", "Portugal"),
            ("ES", "Espagne", "Spain", "Espanha", "Espana", "Spagna", "Spanien"),
            ("IT", "Italie", "Italy", "Italia", "Italia", "Italia", "Italien"),
            ("DE", "Allemagne", "Germany", "Alemanha", "Alemania", "Germania", "Deutschland"),
            ("BE", "Belgique", "Belgium", "Belgica", "Belgica", "Belgio", "Belgien"),
            ("CH", "Suisse", "Switzerland", "Suica", "Suiza", "Svizzera", "Schweiz"),
            ("LU", "Luxembourg", "Luxembourg", "Luxemburgo", "Luxemburgo", "Lussemburgo", "Luxemburg"),
            ("MA", "Maroc", "Morocco", "Marrocos", "Marruecos", "Marocco", "Marokko"),
            ("SN", "Senegal", "Senegal", "Senegal", "Senegal", "Senegal", "Senegal"),
        ]:
            db.session.add(
                CreditCountry(
                    iso_code=iso_code,
                    name=en,
                    name_fr=fr,
                    name_en=en,
                    name_pt=pt,
                    name_es=es,
                    name_it=it,
                    name_de=de,
                )
            )
        changed = True

    if CreditSector.query.count() == 0:
        for code, fr, en, pt, es, it, de in [
            ("agri_food", "Agroalimentaire", "Agri-food", "Agroalimentar", "Agroalimentario", "Agroalimentare", "Lebensmittel"),
            ("transport", "Transport", "Transport", "Transporte", "Transporte", "Trasporto", "Transport"),
            ("hospitality", "Hotellerie", "Hospitality", "Hotelaria", "Hoteleria", "Ospitalita", "Gastgewerbe"),
            ("manufacturing", "Industrie", "Manufacturing", "Industria", "Manufactura", "Manifattura", "Produktion"),
            ("retail", "Distribution", "Retail", "Varejo", "Comercio", "Retail", "Einzelhandel"),
            ("energy", "Energie", "Energy", "Energia", "Energia", "Energia", "Energie"),
            ("healthcare", "Sante", "Healthcare", "Saude", "Salud", "Sanita", "Gesundheit"),
            ("construction", "Construction", "Construction", "Construcao", "Construccion", "Costruzione", "Bauwesen"),
            ("services", "Services", "Services", "Servicos", "Servicios", "Servizi", "Dienstleistungen"),
            ("technology", "Technologie", "Technology", "Tecnologia", "Tecnologia", "Tecnologia", "Technologie"),
        ]:
            db.session.add(
                CreditSector(
                    code=code,
                    name=en,
                    name_fr=fr,
                    name_en=en,
                    name_pt=pt,
                    name_es=es,
                    name_it=it,
                    name_de=de,
                )
            )
        changed = True

    if CreditRating.query.count() == 0:
        for rank, code in enumerate(["AAA", "AA", "A", "BBB", "BB", "B", "CCC"], start=1):
            db.session.add(
                CreditRating(
                    code=code,
                    rank_order=rank,
                    label_fr=code,
                    label_en=code,
                    label_pt=code,
                    label_es=code,
                    label_it=code,
                    label_de=code,
                )
            )
        changed = True

    if CreditFacilityType.query.count() == 0:
        for code, fr, en, pt, es, it, de in [
            ("term_loan", "Pret a terme", "Term loan", "Emprestimo a prazo", "Prestamo a plazo", "Prestito a termine", "Darlehen"),
            ("revolving_line", "Ligne revolving", "Revolving line", "Linha rotativa", "Linea revolvente", "Linea revolving", "Revolvierende Linie"),
            ("bridge_loan", "Pret relais", "Bridge loan", "Emprestimo ponte", "Prestamo puente", "Prestito ponte", "Uberbruckungskredit"),
            ("capex_lease", "Credit-bail capex", "Capex lease", "Leasing capex", "Leasing capex", "Leasing capex", "Capex-Leasing"),
            ("overdraft", "Decouvert", "Overdraft", "Cheque especial", "Descubierto", "Scoperto", "Uberziehung"),
        ]:
            db.session.add(
                CreditFacilityType(
                    code=code,
                    label=en,
                    label_fr=fr,
                    label_en=en,
                    label_pt=pt,
                    label_es=es,
                    label_it=it,
                    label_de=de,
                )
            )
        changed = True

    if CreditCollateralType.query.count() == 0:
        for code, fr, en, pt, es, it, de in [
            ("real_estate", "Immobilier", "Real estate", "Imovel", "Inmueble", "Immobile", "Immobilien"),
            ("receivables", "Creances", "Receivables", "Recebiveis", "Cuentas por cobrar", "Crediti", "Forderungen"),
            ("equipment", "Equipements", "Equipment", "Equipamentos", "Equipos", "Attrezzature", "Anlagen"),
            ("cash_pledge", "Nantissement cash", "Cash pledge", "Penhor em dinheiro", "Prenda de efectivo", "Pegno in contanti", "Barpfand"),
            ("inventory", "Stocks", "Inventory", "Estoque", "Inventario", "Magazzino", "Lagerbestand"),
            ("other", "Autre", "Other", "Outro", "Otro", "Altro", "Andere"),
        ]:
            db.session.add(
                CreditCollateralType(
                    code=code,
                    label=en,
                    label_fr=fr,
                    label_en=en,
                    label_pt=pt,
                    label_es=es,
                    label_it=it,
                    label_de=de,
                )
            )
        changed = True

    if CreditGuaranteeType.query.count() == 0:
        for code, fr, en, pt, es, it, de in [
            ("personal", "Garantie personnelle", "Personal guarantee", "Garantia pessoal", "Garantia personal", "Garanzia personale", "Personliche Garantie"),
            ("corporate", "Garantie corporate", "Corporate guarantee", "Garantia corporativa", "Garantia corporativa", "Garanzia corporate", "Unternehmensgarantie"),
            ("joint", "Garantie conjointe", "Joint guarantee", "Garantia solidaria", "Garantia conjunta", "Garanzia congiunta", "Gemeinsame Garantie"),
            ("limited", "Garantie limitee", "Limited guarantee", "Garantia limitada", "Garantia limitada", "Garanzia limitata", "Begrenzte Garantie"),
        ]:
            db.session.add(
                CreditGuaranteeType(
                    code=code,
                    label=en,
                    label_fr=fr,
                    label_en=en,
                    label_pt=pt,
                    label_es=es,
                    label_it=it,
                    label_de=de,
                )
            )
        changed = True

    if changed:
        db.session.commit()


def _credit_feature_enabled(tenant: Tenant | None) -> bool:
    if not tenant:
        return False
    return SubscriptionService.check_feature_access(tenant.id, "credit")


def _credit_menu_key_for_endpoint(endpoint: str | None) -> str | None:
    name = str(endpoint or "").split(".", 1)[-1].strip().lower()
    mapping = {
        "overview": "overview",
        "borrowers": "borrowers",
        "deals": "deals",
        "facilities": "facilities",
        "collateral": "collateral",
        "guarantors": "guarantors",
        "financials": "statements",
        "ratios": "ratios",
        "memos": "memos",
        "memo_pdf": "memos",
        "memos_generate_from_template": "memos",
        "memos_ai_draft": "memos",
        "memo_templates": "memos",
        "memo_template_designer": "memos",
        "memo_template_designer_export": "memos",
        "approvals": "approvals",
        "backlog": "backlog",
        "approval_workflow": "workflow",
        "approval_uam": "workflow",
        "documents": "documents",
    }
    return mapping.get(name)


@bp.before_app_request
def _load_tenant_into_g() -> None:
    tenant_id = get_current_tenant_id()
    if getattr(g, "tenant", None) is None:
        g.tenant = None
        if tenant_id:
            tenant = Tenant.query.get(tenant_id)
            if tenant:
                g.tenant = tenant

    if (
        request.endpoint
        and request.endpoint.startswith("credit.")
        and current_user.is_authenticated
        and getattr(g, "tenant", None)
        and current_user.tenant_id == g.tenant.id
    ):
        _seed_credit_system_roles()
        module_access = get_user_module_access(g.tenant, current_user.id)
        if not module_access.get("credit", module_access.get("bi", True)):
            flash(_("Accès Audela Credit désactivé pour votre utilisateur."), "warning")
            return redirect(url_for("tenant.dashboard"))

        bi_menu_access = get_user_menu_access(g.tenant, current_user.id, "bi")
        if not bi_menu_access.get("credit_origination", True):
            flash(_("Accès menu Audela Credit désactivé pour votre utilisateur."), "warning")
            return redirect(url_for("tenant.dashboard"))

        credit_menu_access = get_user_menu_access(g.tenant, current_user.id, "credit")
        endpoint_key = _credit_menu_key_for_endpoint(request.endpoint)
        if endpoint_key and not credit_menu_access.get(endpoint_key, True):
            flash(_("Accès à cette section Credit désactivé pour votre utilisateur."), "warning")
            return redirect(url_for("credit.overview"))

        if not _credit_feature_enabled(g.tenant):
            flash(_("Le produit Audela Credit n'est pas disponible dans votre plan actuel."), "warning")
            return redirect(url_for("billing.plans", product="credit"))


@bp.app_context_processor
def _credit_layout_context():
    tenant = getattr(g, "tenant", None)
    module_access = get_user_module_access(tenant, getattr(current_user, "id", None))
    bi_menu_access = get_user_menu_access(tenant, getattr(current_user, "id", None), "bi")
    credit_menu_access = get_user_menu_access(tenant, getattr(current_user, "id", None), "credit")
    return {
        "module_access": module_access,
        "bi_menu_access": bi_menu_access,
        "credit_menu_access": credit_menu_access,
    }


def _base_metrics(tenant_id: int) -> dict:
    deals_count = CreditDeal.query.filter_by(tenant_id=tenant_id).count()
    borrowers_count = CreditBorrower.query.filter_by(tenant_id=tenant_id).count()
    memo_count = CreditMemo.query.filter_by(tenant_id=tenant_id).count()
    pending_approvals = CreditApproval.query.filter_by(tenant_id=tenant_id, decision="pending").count()
    pipeline_amount = (
        db.session.query(func.coalesce(func.sum(CreditDeal.requested_amount), 0))
        .filter(CreditDeal.tenant_id == tenant_id)
        .scalar()
    )
    return {
        "deals_count": int(deals_count or 0),
        "borrowers_count": int(borrowers_count or 0),
        "memo_count": int(memo_count or 0),
        "pending_approvals": int(pending_approvals or 0),
        "pipeline_amount": float(pipeline_amount or 0),
    }


def _parse_iso_date(raw_value: str | None) -> date | None:
    val = (raw_value or "").strip()
    if not val:
        return None
    try:
        return datetime.strptime(val, "%Y-%m-%d").date()
    except Exception:
        return None


def _credit_filters_from_request() -> dict:
    date_from_raw = (request.args.get("date_from") or "").strip()
    date_to_raw = (request.args.get("date_to") or "").strip()
    deal_status = (request.args.get("deal_status") or "").strip()
    approval_stage = (request.args.get("approval_stage") or "").strip()
    approval_decision = (request.args.get("approval_decision") or "").strip()
    borrower_id_raw = (request.args.get("borrower_id") or "").strip()
    risk_grade = (request.args.get("risk_grade") or "").strip()

    return {
        "date_from_raw": date_from_raw,
        "date_to_raw": date_to_raw,
        "date_from": _parse_iso_date(date_from_raw),
        "date_to": _parse_iso_date(date_to_raw),
        "deal_status": deal_status,
        "approval_stage": approval_stage,
        "approval_decision": approval_decision,
        "borrower_id_raw": borrower_id_raw,
        "borrower_id": _to_int(borrower_id_raw),
        "risk_grade": risk_grade,
    }


def _credit_filters_query_string(filters: dict) -> str:
    payload = {
        "date_from": filters.get("date_from_raw") or "",
        "date_to": filters.get("date_to_raw") or "",
        "deal_status": filters.get("deal_status") or "",
        "approval_stage": filters.get("approval_stage") or "",
        "approval_decision": filters.get("approval_decision") or "",
        "borrower_id": filters.get("borrower_id_raw") or "",
        "risk_grade": filters.get("risk_grade") or "",
    }
    compact = {k: v for k, v in payload.items() if v}
    return urlencode(compact)


def _credit_filter_predicates(tenant_id: int, filters: dict) -> dict[str, list]:
    date_from: date | None = filters.get("date_from")
    date_to: date | None = filters.get("date_to")
    deal_status: str = filters.get("deal_status") or ""
    approval_stage: str = filters.get("approval_stage") or ""
    approval_decision: str = filters.get("approval_decision") or ""
    borrower_id: int | None = filters.get("borrower_id")
    risk_grade: str = filters.get("risk_grade") or ""

    deal_where: list = [CreditDeal.tenant_id == tenant_id]
    approval_where: list = [CreditApproval.tenant_id == tenant_id]
    memo_where: list = [CreditMemo.tenant_id == tenant_id]
    ratio_where: list = [CreditRatioSnapshot.tenant_id == tenant_id]

    if deal_status:
        deal_where.append(CreditDeal.status == deal_status)
    if approval_stage:
        approval_where.append(CreditApproval.stage == approval_stage)
    if approval_decision:
        approval_where.append(CreditApproval.decision == approval_decision)

    if borrower_id:
        deal_where.append(CreditDeal.borrower_id == borrower_id)
        memo_where.append(CreditMemo.borrower_id == borrower_id)
        memo_ids_q = db.session.query(CreditMemo.id).filter(
            CreditMemo.tenant_id == tenant_id,
            CreditMemo.borrower_id == borrower_id,
        )
        approval_where.append(CreditApproval.memo_id.in_(memo_ids_q))
        ratio_where.append(CreditRatioSnapshot.borrower_id == borrower_id)

    if risk_grade:
        ratio_where.append(CreditRatioSnapshot.risk_grade == risk_grade)
        grade_borrowers_q = db.session.query(CreditRatioSnapshot.borrower_id).filter(*ratio_where).distinct()
        deal_where.append(CreditDeal.borrower_id.in_(grade_borrowers_q))
        memo_where.append(CreditMemo.borrower_id.in_(grade_borrowers_q))
        approval_memo_ids_q = db.session.query(CreditMemo.id).filter(
            CreditMemo.tenant_id == tenant_id,
            CreditMemo.borrower_id.in_(grade_borrowers_q),
        )
        approval_where.append(CreditApproval.memo_id.in_(approval_memo_ids_q))

    if date_from:
        start_dt = datetime.combine(date_from, datetime.min.time())
        deal_where.append(CreditDeal.created_at >= start_dt)
        approval_where.append(CreditApproval.created_at >= start_dt)
        memo_where.append(CreditMemo.created_at >= start_dt)
        ratio_where.append(CreditRatioSnapshot.created_at >= start_dt)
    if date_to:
        end_dt = datetime.combine(date_to, datetime.max.time())
        deal_where.append(CreditDeal.created_at <= end_dt)
        approval_where.append(CreditApproval.created_at <= end_dt)
        memo_where.append(CreditMemo.created_at <= end_dt)
        ratio_where.append(CreditRatioSnapshot.created_at <= end_dt)

    return {
        "deal": deal_where,
        "approval": approval_where,
        "memo": memo_where,
        "ratio": ratio_where,
    }


def _credit_filter_options(tenant_id: int) -> dict[str, list]:
    deal_statuses = [
        row[0]
        for row in db.session.query(CreditDeal.status)
        .filter(CreditDeal.tenant_id == tenant_id)
        .distinct()
        .order_by(CreditDeal.status.asc())
        .all()
        if row[0]
    ]
    approval_stages = [
        row[0]
        for row in db.session.query(CreditApproval.stage)
        .filter(CreditApproval.tenant_id == tenant_id)
        .distinct()
        .order_by(CreditApproval.stage.asc())
        .all()
        if row[0]
    ]
    approval_decisions = [
        row[0]
        for row in db.session.query(CreditApproval.decision)
        .filter(CreditApproval.tenant_id == tenant_id)
        .distinct()
        .order_by(CreditApproval.decision.asc())
        .all()
        if row[0]
    ]
    borrowers = [
        {"id": b.id, "name": b.name}
        for b in CreditBorrower.query.filter_by(tenant_id=tenant_id).order_by(CreditBorrower.name.asc()).all()
    ]
    risk_grades = [
        row[0]
        for row in db.session.query(CreditRatioSnapshot.risk_grade)
        .filter(CreditRatioSnapshot.tenant_id == tenant_id)
        .distinct()
        .order_by(CreditRatioSnapshot.risk_grade.asc())
        .all()
        if row[0]
    ]

    return {
        "deal_statuses": deal_statuses,
        "approval_stages": approval_stages,
        "approval_decisions": approval_decisions,
        "borrowers": borrowers,
        "risk_grades": risk_grades,
    }


def _display_deal_status(value: str) -> str:
    mapping = {
        "in_review": _("In review"),
        "memo": _("Credit memo"),
        "approved": _("Approved"),
        "rejected": _("Rejected"),
        "pending": _("Pending"),
        "draft": _("Draft"),
        "booked": _("Booked"),
        "review": _("Review"),
        "approve_with_conditions": _("Approve with conditions"),
    }
    if value in mapping:
        return mapping[value]
    return str(value or "").replace("_", " ")


def _display_approval_stage(value: str) -> str:
    mapping = {code: label for code, label in _approval_stage_options()}
    if value in mapping:
        return mapping[value]
    return str(value or "").replace("_", " ")


def _display_approval_decision(value: str) -> str:
    mapping = {
        "pending": _("Pending"),
        "approved": _("Approved"),
        "rejected": _("Rejected"),
        "review": _("Review"),
        "approve": _("Approve"),
        "approve_with_conditions": _("Approve with conditions"),
    }
    if value in mapping:
        return mapping[value]
    return str(value or "").replace("_", " ")


def _credit_filter_label_maps(filter_options: dict[str, list]) -> dict[str, dict[str, str]]:
    return {
        "deal_status": {
            str(v): _display_deal_status(str(v))
            for v in (filter_options.get("deal_statuses") or [])
        },
        "approval_stage": {
            str(v): _display_approval_stage(str(v))
            for v in (filter_options.get("approval_stages") or [])
        },
        "approval_decision": {
            str(v): _display_approval_decision(str(v))
            for v in (filter_options.get("approval_decisions") or [])
        },
    }


def _credit_active_filter_tags(filters: dict, filter_options: dict[str, list], label_maps: dict[str, dict[str, str]]) -> list[str]:
    tags: list[str] = []

    if filters.get("date_from_raw"):
        tags.append(f"{_('From')}: {filters['date_from_raw']}")
    if filters.get("date_to_raw"):
        tags.append(f"{_('To')}: {filters['date_to_raw']}")

    borrower_id = filters.get("borrower_id")
    if borrower_id:
        borrower_name = next((b.get("name") for b in filter_options.get("borrowers", []) if b.get("id") == borrower_id), None)
        if borrower_name:
            tags.append(f"{_('Borrower')}: {borrower_name}")

    if filters.get("risk_grade"):
        tags.append(f"{_('Risk grade')}: {filters['risk_grade']}")
    if filters.get("deal_status"):
        label = label_maps.get("deal_status", {}).get(filters["deal_status"], filters["deal_status"])
        tags.append(f"{_('Deal status')}: {label}")
    if filters.get("approval_stage"):
        label = label_maps.get("approval_stage", {}).get(filters["approval_stage"], filters["approval_stage"])
        tags.append(f"{_('Approval stage')}: {label}")
    if filters.get("approval_decision"):
        label = label_maps.get("approval_decision", {}).get(filters["approval_decision"], filters["approval_decision"])
        tags.append(f"{_('Decision')}: {label}")

    return tags


def _approval_stage_options() -> list[tuple[str, str]]:
    return [
        ("analyst_review", _("Analyst review")),
        ("risk_manager", _("Risk manager")),
        ("credit_committee", _("Credit committee")),
    ]


def _maybe_create_backlog_task_for_pending_approval(approval: CreditApproval) -> None:
    if approval.decision != "pending" or not approval.memo:
        return

    workflow_step = approval.workflow_step
    if not workflow_step and approval.workflow_step_id:
        workflow_step = CreditApprovalWorkflowStep.query.filter_by(
            id=approval.workflow_step_id,
            tenant_id=approval.tenant_id,
        ).first()

    assigned_group_id = approval.analyst_group_id or getattr(workflow_step, "group_id", None)
    assigned_user_id = _assignee_user_for_workflow_step(
        approval.tenant_id,
        workflow_step,
        approval.memo.borrower if approval.memo else None,
    )

    existing = (
        CreditBacklogTask.query.filter_by(
            tenant_id=approval.tenant_id,
            memo_id=approval.memo_id,
            workflow_step_id=approval.workflow_step_id,
            assigned_group_id=assigned_group_id,
            assigned_user_id=assigned_user_id,
        )
        .filter(CreditBacklogTask.status.in_(["todo", "in_progress"]))
        .first()
    )
    if existing:
        return

    due_date = None
    if workflow_step and workflow_step.sla_days and int(workflow_step.sla_days) > 0:
        due_date = date.today() + timedelta(days=int(workflow_step.sla_days))

    db.session.add(
        CreditBacklogTask(
            tenant_id=approval.tenant_id,
            memo_id=approval.memo_id,
            deal_id=approval.memo.deal_id,
            borrower_id=approval.memo.borrower_id,
            workflow_step_id=approval.workflow_step_id,
            title=_("Approval pending for memo: {title}", title=approval.memo.title),
            description=approval.comments,
            status="todo",
            priority="high",
            due_date=due_date,
            assigned_user_id=assigned_user_id,
            assigned_group_id=assigned_group_id,
            created_by_user_id=approval.actor_user_id,
        )
    )


def _deal_status_is_analysis(status: str | None) -> bool:
    return (str(status or "").strip().lower() or "in_review") in {
        "in_review",
        "analysis",
        "analyst_review",
    }


def _analysis_workflow_step_for_tenant(tenant_id: int) -> CreditApprovalWorkflowStep | None:
    steps = _workflow_steps_ordered(tenant_id)
    if not steps:
        return None

    for step in steps:
        stage = str(step.stage or "").strip().lower()
        if stage in {"analyst_review", "analysis", "in_review"}:
            return step
    return steps[0]


def _assignee_user_for_workflow_step(
    tenant_id: int,
    step: CreditApprovalWorkflowStep | None,
    borrower: CreditBorrower | None = None,
) -> int | None:
    if not step or not step.group_id:
        return None

    tenant = Tenant.query.get(tenant_id)

    base_q = (
        CreditAnalystGroupMember.query.join(CreditAnalystGroup)
        .filter(
            CreditAnalystGroup.tenant_id == tenant_id,
            CreditAnalystGroupMember.group_id == step.group_id,
        )
        .order_by(CreditAnalystGroupMember.id.asc())
    )

    scoped_q = base_q
    if step.function_id:
        scoped_q = scoped_q.filter(CreditAnalystGroupMember.function_id == step.function_id)
    elif step.function_name:
        scoped_q = scoped_q.filter(CreditAnalystGroupMember.function_name == step.function_name)

    members = scoped_q.all() or base_q.all()
    if not members:
        return None

    if borrower:
        for member in members:
            member_scopes = _scope_for_user_or_groups(tenant, int(member.user_id or 0), [int(member.group_id or 0)]) if tenant and member.user_id else []
            if not member_scopes:
                return int(member.user_id) if member.user_id else None
            if any(_borrower_matches_scope(borrower, scope) for scope in member_scopes):
                return int(member.user_id) if member.user_id else None

    first = members[0]
    return int(first.user_id) if first and first.user_id else None


def _create_analysis_backlog_task(
    tenant_id: int,
    deal_id: int | None,
    borrower_id: int | None,
    memo_id: int | None,
    title: str,
    description: str,
    actor_user_id: int | None,
    workflow_step: CreditApprovalWorkflowStep | None = None,
) -> None:
    step = workflow_step or _analysis_workflow_step_for_tenant(tenant_id)
    if not step:
        return

    borrower = CreditBorrower.query.filter_by(id=borrower_id, tenant_id=tenant_id).first() if borrower_id else None
    assigned_group_id = step.group_id
    assigned_user_id = _assignee_user_for_workflow_step(tenant_id, step, borrower)
    existing = (
        CreditBacklogTask.query.filter_by(
            tenant_id=tenant_id,
            memo_id=memo_id,
            deal_id=deal_id,
            borrower_id=borrower_id,
            workflow_step_id=step.id,
            assigned_group_id=assigned_group_id,
            assigned_user_id=assigned_user_id,
        )
        .filter(CreditBacklogTask.status.in_(["todo", "in_progress"]))
        .first()
    )
    if existing:
        return

    due_date = None
    if step.sla_days and int(step.sla_days) > 0:
        due_date = date.today() + timedelta(days=int(step.sla_days))

    db.session.add(
        CreditBacklogTask(
            tenant_id=tenant_id,
            memo_id=memo_id,
            deal_id=deal_id,
            borrower_id=borrower_id,
            workflow_step_id=step.id,
            title=title,
            description=description,
            status="todo",
            priority="high",
            due_date=due_date,
            assigned_user_id=assigned_user_id,
            assigned_group_id=assigned_group_id,
            created_by_user_id=actor_user_id,
        )
    )


def _maybe_create_backlog_task_for_new_deal_analysis(deal: CreditDeal, actor_user_id: int | None) -> None:
    if not _deal_status_is_analysis(deal.status):
        return

    _create_analysis_backlog_task(
        tenant_id=deal.tenant_id,
        deal_id=deal.id,
        borrower_id=deal.borrower_id,
        memo_id=None,
        title=_("Deal analysis task: {deal_code}", deal_code=deal.code),
        description=_("Auto-created from deal creation for workflow analysis step."),
        actor_user_id=actor_user_id,
    )


def _maybe_create_backlog_task_for_new_facility_analysis(facility: CreditFacility, actor_user_id: int | None) -> None:
    status = (str(facility.status or "").strip().lower() or "draft")
    if status not in {"draft", "analysis", "in_review"}:
        return

    deal = facility.deal
    if not deal:
        return

    _create_analysis_backlog_task(
        tenant_id=facility.tenant_id,
        deal_id=facility.deal_id,
        borrower_id=deal.borrower_id,
        memo_id=None,
        title=_("Facility analysis task: {deal_code}", deal_code=deal.code),
        description=_("Auto-created from facility creation for workflow analysis step."),
        actor_user_id=actor_user_id,
    )


def _maybe_create_backlog_task_for_new_memo_analysis(memo: CreditMemo, actor_user_id: int | None) -> None:
    if not memo:
        return

    _create_analysis_backlog_task(
        tenant_id=memo.tenant_id,
        deal_id=memo.deal_id,
        borrower_id=memo.borrower_id,
        memo_id=memo.id,
        title=_("Memo analysis task: {memo_title}", memo_title=(memo.title or _("Credit Memo"))),
        description=_("Auto-created from memo creation for workflow analysis step."),
        actor_user_id=actor_user_id,
    )


def _maybe_create_initial_pending_approval_for_memo(
    memo: CreditMemo,
    actor_user_id: int | None,
) -> CreditApproval | None:
    if not memo or not memo.id:
        return None

    # Ensure each tenant has a workflow before creating the first pending approval.
    _seed_default_approval_workflow(memo.tenant_id)

    existing = (
        CreditApproval.query.filter_by(
            tenant_id=memo.tenant_id,
            memo_id=memo.id,
        )
        .order_by(CreditApproval.id.asc())
        .first()
    )
    if existing:
        return None

    ordered_steps = _workflow_steps_ordered(memo.tenant_id)
    if not ordered_steps:
        return None

    first_step = ordered_steps[0]
    analyst_function = None
    if first_step.function_ref:
        analyst_function = first_step.function_ref.code
    elif first_step.function_name:
        analyst_function = first_step.function_name

    approval = CreditApproval(
        tenant_id=memo.tenant_id,
        memo_id=memo.id,
        stage=first_step.stage,
        decision="pending",
        comments=_("Auto-created from memo creation."),
        workflow_step_id=first_step.id,
        analyst_group_id=first_step.group_id,
        analyst_function_id=first_step.function_id,
        analyst_function=analyst_function,
        actor_user_id=actor_user_id,
        decided_at=None,
    )
    db.session.add(approval)
    db.session.flush()
    _maybe_create_backlog_task_for_pending_approval(approval)
    return approval


def _seed_default_analyst_functions(tenant_id: int) -> None:
    defaults = [
        ("analyst", _("Analyst")),
        ("risk_manager", _("Risk manager")),
        ("credit_committee", _("Credit committee")),
    ]

    changed = False
    for code, label in defaults:
        row = CreditAnalystFunction.query.filter_by(tenant_id=tenant_id, code=code).first()
        if row:
            if row.label != label:
                row.label = label
                changed = True
            continue
        db.session.add(CreditAnalystFunction(tenant_id=tenant_id, code=code, label=label))
        changed = True

    if changed:
        db.session.commit()


def _seed_default_approval_workflow(tenant_id: int) -> None:
    _seed_default_analyst_functions(tenant_id)
    exists = CreditApprovalWorkflowStep.query.filter_by(tenant_id=tenant_id).count() > 0
    if exists:
        return

    fn_by_code = {
        fn.code: fn
        for fn in CreditAnalystFunction.query.filter_by(tenant_id=tenant_id).all()
    }
    default_fn_code = {
        "analyst_review": "analyst",
        "risk_manager": "risk_manager",
        "credit_committee": "credit_committee",
    }

    for idx, (stage, label) in enumerate(_approval_stage_options(), start=1):
        db.session.add(
            CreditApprovalWorkflowStep(
                tenant_id=tenant_id,
                step_order=idx,
                stage=stage,
                step_name=label,
                function_id=getattr(fn_by_code.get(default_fn_code.get(stage, "")), "id", None),
                function_name=default_fn_code.get(stage),
                is_required=True,
            )
        )
    db.session.commit()


def _workflow_steps_ordered(tenant_id: int) -> list[CreditApprovalWorkflowStep]:
    return (
        CreditApprovalWorkflowStep.query.filter_by(tenant_id=tenant_id)
        .order_by(CreditApprovalWorkflowStep.step_order.asc(), CreditApprovalWorkflowStep.id.asc())
        .all()
    )


def _workflow_step_for_approval(
    approval: CreditApproval,
    ordered_steps: list[CreditApprovalWorkflowStep],
) -> CreditApprovalWorkflowStep | None:
    if approval.workflow_step_id:
        for step in ordered_steps:
            if step.id == approval.workflow_step_id:
                return step
    for step in ordered_steps:
        if step.stage == approval.stage:
            return step
    return None


def _expected_workflow_step_for_memo(
    tenant_id: int,
    memo_id: int,
    ordered_steps: list[CreditApprovalWorkflowStep],
) -> tuple[CreditApprovalWorkflowStep | None, str | None]:
    if not ordered_steps:
        return None, _("No approval workflow is configured.")

    approvals = (
        CreditApproval.query.filter_by(tenant_id=tenant_id, memo_id=memo_id)
        .order_by(CreditApproval.created_at.asc(), CreditApproval.id.asc())
        .all()
    )
    if not approvals:
        return ordered_steps[0], None

    last = approvals[-1]
    if last.decision == "rejected":
        return None, _("Workflow is closed for this memo (already rejected).")

    last_step = _workflow_step_for_approval(last, ordered_steps)
    if not last_step:
        return ordered_steps[0], _("Previous approval is not mapped to current workflow. Restart from first step.")

    if last.decision == "pending":
        return last_step, None

    try:
        idx = next(i for i, step in enumerate(ordered_steps) if step.id == last_step.id)
    except StopIteration:
        return ordered_steps[0], _("Previous approval is not mapped to current workflow. Restart from first step.")

    next_idx = idx + 1
    if next_idx >= len(ordered_steps):
        return None, _("Workflow is already completed for this memo.")

    return ordered_steps[next_idx], None


def _approval_summaries_for_memos(tenant_id: int, memo_ids: list[int]) -> dict[int, dict[str, object]]:
    clean_ids = [int(v) for v in memo_ids if int(v) > 0]
    if not clean_ids:
        return {}

    ordered_steps = _workflow_steps_ordered(tenant_id)
    approvals = (
        CreditApproval.query.filter(
            CreditApproval.tenant_id == tenant_id,
            CreditApproval.memo_id.in_(clean_ids),
        )
        .order_by(CreditApproval.memo_id.asc(), CreditApproval.created_at.asc(), CreditApproval.id.asc())
        .all()
    )

    grouped: dict[int, list[CreditApproval]] = {mid: [] for mid in clean_ids}
    for row in approvals:
        if row.memo_id in grouped:
            grouped[int(row.memo_id)].append(row)

    out: dict[int, dict[str, object]] = {}
    for memo_id in clean_ids:
        memo_rows = grouped.get(memo_id, [])
        approved_dates = [a.decided_at for a in memo_rows if a.decision == "approved" and a.decided_at]
        latest_approved_at = max(approved_dates) if approved_dates else None

        if ordered_steps:
            expected_step, workflow_msg = _expected_workflow_step_for_memo(tenant_id, memo_id, ordered_steps)
            current_task = expected_step.step_name if expected_step else (workflow_msg or _("Completed"))
        else:
            current_task = _("No approval workflow is configured.")

        approvals_by_step_id: dict[int, CreditApproval] = {}
        for approval in memo_rows:
            step = _workflow_step_for_approval(approval, ordered_steps)
            if step:
                approvals_by_step_id[int(step.id)] = approval

        phase_lines: list[str] = []
        for step in ordered_steps:
            approval = approvals_by_step_id.get(int(step.id))
            step_name = step.step_name or step.stage or _("Workflow step")
            if not approval:
                marker = _("Current task") if (expected_step and expected_step.id == step.id) else _("Not started")
                phase_lines.append(_("{step}: {status}", step=step_name, status=marker))
                continue

            actor_email = approval.actor_user.email if approval.actor_user else _("Unknown approver")
            approved_on = approval.decided_at or approval.created_at
            approved_on_txt = approved_on.strftime("%d/%m/%Y") if approved_on else "-"
            decision = str(approval.decision or "").strip().lower()
            if decision == "approved":
                phase_lines.append(
                    _("{step}: approved by {actor} on {date}", step=step_name, actor=actor_email, date=approved_on_txt)
                )
            elif decision == "rejected":
                phase_lines.append(
                    _("{step}: rejected by {actor} on {date}", step=step_name, actor=actor_email, date=approved_on_txt)
                )
            else:
                phase_lines.append(_("{step}: pending", step=step_name))

        out[memo_id] = {
            "approved_at": latest_approved_at,
            "current_task": current_task,
            "phases": phase_lines,
        }

    return out


def _approval_logs_for_memos(tenant_id: int, memo_ids: list[int]) -> dict[int, list[dict[str, str]]]:
    clean_ids = [int(v) for v in memo_ids if int(v) > 0]
    if not clean_ids:
        return {}

    workflow_steps = _workflow_steps_ordered(tenant_id)
    step_label_by_id = {
        int(step.id): str(step.step_name or step.stage or _("Workflow step"))
        for step in workflow_steps
        if step.id
    }
    step_label_by_stage = {
        str(step.stage or ""): str(step.step_name or step.stage or _("Workflow step"))
        for step in workflow_steps
        if step.stage
    }

    rows = (
        CreditApproval.query.filter(
            CreditApproval.tenant_id == tenant_id,
            CreditApproval.memo_id.in_(clean_ids),
        )
        .order_by(CreditApproval.memo_id.asc(), CreditApproval.created_at.asc(), CreditApproval.id.asc())
        .all()
    )

    out: dict[int, list[dict[str, str]]] = {memo_id: [] for memo_id in clean_ids}
    for row in rows:
        memo_id = int(row.memo_id or 0)
        if memo_id not in out:
            continue

        step_label = ""
        if row.workflow_step_id and int(row.workflow_step_id) in step_label_by_id:
            step_label = step_label_by_id[int(row.workflow_step_id)]
        elif row.stage and str(row.stage) in step_label_by_stage:
            step_label = step_label_by_stage[str(row.stage)]
        else:
            step_label = _display_approval_stage(str(row.stage or "")) or _("Workflow step")

        decided_on = row.decided_at or row.created_at
        decided_on_txt = decided_on.strftime("%d/%m/%Y %H:%M") if decided_on else "-"
        actor_email = row.actor_user.email if row.actor_user else _("Unknown approver")
        comments = (row.comments or "").strip()

        out[memo_id].append(
            {
                "stage": step_label,
                "decision": _display_approval_decision(str(row.decision or "pending")),
                "actor": actor_email,
                "date": decided_on_txt,
                "comments": comments or "-",
            }
        )

    return out


def _sync_entity_approval_dates_for_memo(memo: CreditMemo | None, approved_at: datetime | None) -> None:
    if not memo or not approved_at:
        return

    memo.approval_date = approved_at

    if memo.deal_id:
        deal = CreditDeal.query.filter_by(id=memo.deal_id, tenant_id=memo.tenant_id).first()
        if deal:
            deal.approval_date = approved_at

        facilities = CreditFacility.query.filter_by(tenant_id=memo.tenant_id, deal_id=memo.deal_id).all()
        for facility in facilities:
            facility.approval_date = approved_at

    if memo.borrower_id:
        statements = CreditFinancialStatement.query.filter_by(
            tenant_id=memo.tenant_id,
            borrower_id=memo.borrower_id,
        ).all()
        for statement in statements:
            statement.approval_date = approved_at


def _user_can_sign_pending_approval(
    tenant: Tenant,
    user_id: int,
    workflow_step: CreditApprovalWorkflowStep | None,
    borrower: CreditBorrower | None,
) -> bool:
    if not workflow_step:
        return False

    q = (
        CreditAnalystGroupMember.query.join(CreditAnalystGroup)
        .filter(
            CreditAnalystGroup.tenant_id == tenant.id,
            CreditAnalystGroupMember.user_id == user_id,
        )
    )

    if workflow_step.group_id:
        q = q.filter(CreditAnalystGroupMember.group_id == workflow_step.group_id)
    if workflow_step.function_id:
        q = q.filter(CreditAnalystGroupMember.function_id == workflow_step.function_id)
    elif workflow_step.function_name:
        q = q.filter(CreditAnalystGroupMember.function_name == workflow_step.function_name)

    matches = q.all()
    if not matches:
        return False

    if not borrower:
        return True

    for member in matches:
        member_scopes = _scope_for_user_or_groups(tenant, int(member.user_id or 0), [int(member.group_id or 0)]) if member.user_id else []
        if not member_scopes:
            return True
        if any(_borrower_matches_scope(borrower, scope) for scope in member_scopes):
            return True
    return False


def _overview_chart_data(tenant_id: int, filter_predicates: dict | None = None) -> dict:
    where = filter_predicates or _credit_filter_predicates(tenant_id, _credit_filters_from_request())
    deal_where = where["deal"]
    approval_where = where["approval"]

    deal_status_rows = (
        db.session.query(
            CreditDeal.status,
            func.count(CreditDeal.id),
            func.coalesce(func.sum(CreditDeal.requested_amount), 0),
        )
        .filter(*deal_where)
        .group_by(CreditDeal.status)
        .all()
    )

    approval_stage_rows = (
        db.session.query(CreditApproval.stage, func.count(CreditApproval.id))
        .filter(*approval_where)
        .group_by(CreditApproval.stage)
        .all()
    )

    today = date.today()
    month_slots: list[tuple[int, int]] = []
    year = today.year
    month = today.month
    for _ in range(6):
        month_slots.append((year, month))
        month -= 1
        if month == 0:
            month = 12
            year -= 1
    month_slots.reverse()

    deals = CreditDeal.query.filter(*deal_where).all()
    counts_by_month: dict[tuple[int, int], int] = {slot: 0 for slot in month_slots}
    for d in deals:
        if not d.created_at:
            continue
        slot = (d.created_at.year, d.created_at.month)
        if slot in counts_by_month:
            counts_by_month[slot] += 1

    month_labels = [f"{calendar.month_abbr[m]} {str(y)[2:]}" for y, m in month_slots]
    month_values = [counts_by_month[slot] for slot in month_slots]

    return {
        "deal_status": {
            "labels": [str(row[0] or "unknown") for row in deal_status_rows],
            "counts": [int(row[1] or 0) for row in deal_status_rows],
            "amounts": [float(row[2] or 0) for row in deal_status_rows],
        },
        "approval_stage": {
            "labels": [str(row[0] or "unknown") for row in approval_stage_rows],
            "counts": [int(row[1] or 0) for row in approval_stage_rows],
        },
        "deals_trend": {
            "labels": month_labels,
            "counts": month_values,
        },
    }


@bp.route("/")
@login_required
def root():
    _require_tenant()
    return redirect(url_for("credit.overview"))


@bp.route("/overview")
@login_required
def overview():
    _require_tenant()
    filters = _credit_filters_from_request()
    filter_predicates = _credit_filter_predicates(g.tenant.id, filters)
    filter_options = _credit_filter_options(g.tenant.id)
    filter_labels = _credit_filter_label_maps(filter_options)
    active_filter_tags = _credit_active_filter_tags(filters, filter_options, filter_labels)

    deals_count = db.session.query(func.count(CreditDeal.id)).filter(*filter_predicates["deal"]).scalar()
    borrowers_count = (
        db.session.query(func.count(func.distinct(CreditDeal.borrower_id)))
        .filter(*filter_predicates["deal"])
        .scalar()
    )
    pending_approvals = (
        db.session.query(func.count(CreditApproval.id))
        .filter(*(filter_predicates["approval"] + [CreditApproval.decision == "pending"]))
        .scalar()
    )
    pipeline_amount = (
        db.session.query(func.coalesce(func.sum(CreditDeal.requested_amount), 0))
        .filter(*filter_predicates["deal"])
        .scalar()
    )
    metrics = {
        "deals_count": int(deals_count or 0),
        "borrowers_count": int(borrowers_count or 0),
        "memo_count": 0,
        "pending_approvals": int(pending_approvals or 0),
        "pipeline_amount": float(pipeline_amount or 0),
    }

    chart_data = _overview_chart_data(g.tenant.id, filter_predicates=filter_predicates)
    latest_deals = (
        CreditDeal.query.filter(*filter_predicates["deal"])
        .order_by(CreditDeal.updated_at.desc())
        .limit(8)
        .all()
    )
    latest_memos = (
        CreditMemo.query.filter(*filter_predicates["memo"])
        .order_by(CreditMemo.updated_at.desc())
        .limit(8)
        .all()
    )
    return render_template(
        "credit/overview.html",
        tenant=g.tenant,
        metrics=metrics,
        chart_data=chart_data,
        latest_deals=latest_deals,
        latest_memos=latest_memos,
        filters=filters,
        filter_options=filter_options,
        filter_labels=filter_labels,
        active_filter_tags=active_filter_tags,
    )


@bp.route("/borrowers", methods=["GET", "POST"])
@login_required
def borrowers():
    _require_tenant()
    _seed_credit_references()
    countries = CreditCountry.query.order_by(CreditCountry.name.asc()).all()
    sectors = CreditSector.query.order_by(CreditSector.name.asc()).all()
    ratings = CreditRating.query.order_by(CreditRating.rank_order.asc()).all()
    selected_sector_id = _to_int(request.args.get("sector_id"))
    selected_country_id = _to_int(request.args.get("country_id"))
    selected_rating_id = _to_int(request.args.get("rating_id"))
    search_name = (request.args.get("q") or "").strip()
    edit_borrower_id = _to_int(request.args.get("borrower_id"))

    sector_ids = {s.id for s in sectors}
    country_ids = {c.id for c in countries}
    rating_ids = {r.id for r in ratings}

    if selected_sector_id and selected_sector_id not in sector_ids:
        selected_sector_id = None
        flash(_("Secteur invalide."), "warning")
    if selected_country_id and selected_country_id not in country_ids:
        selected_country_id = None
        flash(_("Pays invalide."), "warning")
    if selected_rating_id and selected_rating_id not in rating_ids:
        selected_rating_id = None
        flash(_("Rating invalide."), "warning")

    if request.method == "POST":
        action = (request.form.get("action") or "create").strip().lower()

        if action == "update":
            borrower_id = _to_int(request.form.get("borrower_id"))
            borrower = CreditBorrower.query.filter_by(id=borrower_id, tenant_id=g.tenant.id).first() if borrower_id else None
            if not borrower:
                flash(_("Borrower invalide."), "warning")
                return redirect(url_for("credit.borrowers"))
            if not _borrower_visible_for_user(g.tenant, current_user.id, borrower):
                flash(_("Borrower out of your UAM scope."), "warning")
                return redirect(url_for("credit.borrowers", mode="search"))

            country_id = _to_int(request.form.get("country_id"))
            sector_id = _to_int(request.form.get("sector_id"))
            rating_id = _to_int(request.form.get("rating_id"))

            country = CreditCountry.query.filter_by(id=country_id).first() if country_id else None
            sector = CreditSector.query.filter_by(id=sector_id).first() if sector_id else None
            rating = CreditRating.query.filter_by(id=rating_id).first() if rating_id else None

            if country_id and not country:
                flash(_("Pays invalide."), "warning")
                return redirect(url_for("credit.borrowers", mode="edit", borrower_id=borrower.id))
            if sector_id and not sector:
                flash(_("Secteur invalide."), "warning")
                return redirect(url_for("credit.borrowers", mode="edit", borrower_id=borrower.id))
            if rating_id and not rating:
                flash(_("Rating invalide."), "warning")
                return redirect(url_for("credit.borrowers", mode="edit", borrower_id=borrower.id))

            borrower.name = (request.form.get("name") or "").strip()
            borrower.sector_id = getattr(sector, "id", None)
            borrower.country_id = getattr(country, "id", None)
            borrower.rating_id = getattr(rating, "id", None)
            borrower.sector = sector.display_name(getattr(g, "lang", DEFAULT_LANG)) if sector else None
            borrower.country = country.display_name(getattr(g, "lang", DEFAULT_LANG)) if country else None
            borrower.internal_rating = getattr(rating, "code", None)
            if not borrower.name:
                flash(_("Nom du borrower requis."), "warning")
                return redirect(url_for("credit.borrowers", mode="edit", borrower_id=borrower.id))

            db.session.commit()
            flash(_("Borrower modifié."), "success")
            return redirect(url_for("credit.borrowers", mode="search"))

        country_id = _to_int(request.form.get("country_id"))
        sector_id = _to_int(request.form.get("sector_id"))
        rating_id = _to_int(request.form.get("rating_id"))

        country = CreditCountry.query.filter_by(id=country_id).first() if country_id else None
        sector = CreditSector.query.filter_by(id=sector_id).first() if sector_id else None
        rating = CreditRating.query.filter_by(id=rating_id).first() if rating_id else None

        if country_id and not country:
            flash(_("Pays invalide."), "warning")
            return redirect(url_for("credit.borrowers"))
        if sector_id and not sector:
            flash(_("Secteur invalide."), "warning")
            return redirect(url_for("credit.borrowers"))
        if rating_id and not rating:
            flash(_("Rating invalide."), "warning")
            return redirect(url_for("credit.borrowers"))

        borrower = CreditBorrower(
            tenant_id=g.tenant.id,
            name=(request.form.get("name") or "").strip(),
            sector_id=getattr(sector, "id", None),
            country_id=getattr(country, "id", None),
            rating_id=getattr(rating, "id", None),
            sector=sector.display_name(getattr(g, "lang", DEFAULT_LANG)) if sector else None,
            country=country.display_name(getattr(g, "lang", DEFAULT_LANG)) if country else None,
            internal_rating=getattr(rating, "code", None),
        )
        if not borrower.name:
            flash(_("Nom du borrower requis."), "warning")
            return redirect(url_for("credit.borrowers"))
        db.session.add(borrower)
        db.session.commit()
        flash(_("Borrower ajouté."), "success")
        return redirect(url_for("credit.borrowers"))

    query = CreditBorrower.query.filter_by(tenant_id=g.tenant.id)
    if selected_sector_id:
        query = query.filter(CreditBorrower.sector_id == selected_sector_id)
    if selected_country_id:
        query = query.filter(CreditBorrower.country_id == selected_country_id)
    if selected_rating_id:
        query = query.filter(CreditBorrower.rating_id == selected_rating_id)
    if search_name:
        query = query.filter(CreditBorrower.name.ilike(f"%{search_name}%"))

    rows = query.order_by(CreditBorrower.created_at.desc()).all()
    rows = [b for b in rows if _borrower_visible_for_user(g.tenant, current_user.id, b)]
    edit_borrower = CreditBorrower.query.filter_by(id=edit_borrower_id, tenant_id=g.tenant.id).first() if edit_borrower_id else None
    if edit_borrower and not _borrower_visible_for_user(g.tenant, current_user.id, edit_borrower):
        edit_borrower = None

    return render_template(
        "credit/borrowers.html",
        tenant=g.tenant,
        borrowers=rows,
        countries=countries,
        sectors=sectors,
        ratings=ratings,
        selected_sector_id=selected_sector_id,
        selected_country_id=selected_country_id,
        selected_rating_id=selected_rating_id,
        search_name=search_name,
        edit_borrower=edit_borrower,
    )


@bp.route("/deals", methods=["GET", "POST"])
@login_required
def deals():
    _require_tenant()
    borrowers = CreditBorrower.query.filter_by(tenant_id=g.tenant.id).order_by(CreditBorrower.name.asc()).all()
    edit_deal_id = _to_int(request.args.get("edit_id"))

    if request.method == "POST":
        action = (request.form.get("action") or "create").strip().lower()
        if action == "update":
            deal_id = int(request.form.get("deal_id") or 0)
            deal = CreditDeal.query.filter_by(id=deal_id, tenant_id=g.tenant.id).first()
            if not deal:
                flash(_("Deal invalide."), "warning")
                return redirect(url_for("credit.deals", mode="search"))

            borrower_id = int(request.form.get("borrower_id") or 0)
            borrower = CreditBorrower.query.filter_by(id=borrower_id, tenant_id=g.tenant.id).first()
            if not borrower:
                flash(_("Borrower invalide."), "warning")
                return redirect(url_for("credit.deals", mode="search", edit_id=deal.id))
            if not _borrower_visible_for_user(g.tenant, current_user.id, borrower):
                flash(_("Borrower out of your UAM scope."), "warning")
                return redirect(url_for("credit.deals", mode="search"))

            code = (request.form.get("code") or "").strip()
            if not code:
                flash(_("Code deal requis."), "warning")
                return redirect(url_for("credit.deals", mode="search", edit_id=deal.id))

            deal.borrower_id = borrower.id
            deal.code = code[:64]
            deal.purpose = (request.form.get("purpose") or "").strip() or None
            deal.requested_amount = _to_decimal(request.form.get("requested_amount"), "0")
            deal.status = (request.form.get("status") or "in_review").strip() or "in_review"
            if str(deal.status).strip().lower() == "approved" and not deal.approval_date:
                deal.approval_date = datetime.utcnow()
            db.session.commit()
            flash(_("Deal mis à jour."), "success")
            return redirect(url_for("credit.deals", mode="search"))

        borrower_id = int(request.form.get("borrower_id") or 0)
        borrower = CreditBorrower.query.filter_by(id=borrower_id, tenant_id=g.tenant.id).first()
        if not borrower:
            flash(_("Borrower invalide."), "warning")
            return redirect(url_for("credit.deals"))
        if not _borrower_visible_for_user(g.tenant, current_user.id, borrower):
            flash(_("Borrower out of your UAM scope."), "warning")
            return redirect(url_for("credit.deals", mode="search"))

        deal = CreditDeal(
            tenant_id=g.tenant.id,
            borrower_id=borrower.id,
            code=(request.form.get("code") or "").strip(),
            purpose=(request.form.get("purpose") or "").strip() or None,
            requested_amount=_to_decimal(request.form.get("requested_amount"), "0"),
            status=(request.form.get("status") or "in_review").strip() or "in_review",
        )
        if str(deal.status).strip().lower() == "approved" and not deal.approval_date:
            deal.approval_date = datetime.utcnow()
        if not deal.code:
            flash(_("Code deal requis."), "warning")
            return redirect(url_for("credit.deals"))
        db.session.add(deal)
        db.session.flush()
        _maybe_create_backlog_task_for_new_deal_analysis(deal, getattr(current_user, "id", None))
        db.session.commit()
        flash(_("Deal ajouté."), "success")
        return redirect(url_for("credit.deals"))

    selected_borrower_id = _to_int(request.args.get("borrower_id"))
    selected_status = (request.args.get("status") or "").strip().lower()
    allowed_statuses = {"in_review", "memo", "approved", "rejected"}

    borrower_ids = {b.id for b in borrowers}
    if selected_borrower_id and selected_borrower_id not in borrower_ids:
        selected_borrower_id = None
        flash(_("Borrower invalide."), "warning")
    if selected_status and selected_status not in allowed_statuses:
        selected_status = ""

    query = CreditDeal.query.filter_by(tenant_id=g.tenant.id)
    if selected_borrower_id:
        query = query.filter(CreditDeal.borrower_id == selected_borrower_id)
    if selected_status:
        query = query.filter(CreditDeal.status == selected_status)

    rows = query.order_by(CreditDeal.updated_at.desc()).all()
    rows = [d for d in rows if _borrower_visible_for_user(g.tenant, current_user.id, d.borrower)]
    edit_deal = CreditDeal.query.filter_by(id=edit_deal_id, tenant_id=g.tenant.id).first() if edit_deal_id else None

    deal_ids = [int(d.id) for d in rows]
    deal_memo_by_deal: dict[int, CreditMemo] = {}
    if deal_ids:
        deal_memos = (
            CreditMemo.query.filter(
                CreditMemo.tenant_id == g.tenant.id,
                CreditMemo.deal_id.in_(deal_ids),
            )
            .order_by(CreditMemo.updated_at.desc(), CreditMemo.id.desc())
            .all()
        )
        for memo in deal_memos:
            if memo.deal_id and int(memo.deal_id) not in deal_memo_by_deal:
                deal_memo_by_deal[int(memo.deal_id)] = memo

    deal_memo_ids = [int(m.id) for m in deal_memo_by_deal.values()]
    memo_summaries = _approval_summaries_for_memos(g.tenant.id, deal_memo_ids)
    memo_logs = _approval_logs_for_memos(g.tenant.id, deal_memo_ids)
    deal_approval_info: dict[int, dict[str, object]] = {}
    for d in rows:
        memo = deal_memo_by_deal.get(int(d.id))
        if memo:
            info = dict(memo_summaries.get(int(memo.id), {}))
            info["logs"] = memo_logs.get(int(memo.id), [])
            deal_approval_info[int(d.id)] = info
        else:
            deal_approval_info[int(d.id)] = {
                "approved_at": None,
                "current_task": _("No memo"),
                "phases": [],
                "logs": [],
            }

    return render_template(
        "credit/deals.html",
        tenant=g.tenant,
        deals=rows,
        borrowers=borrowers,
        selected_borrower_id=selected_borrower_id,
        selected_status=selected_status,
        edit_deal=edit_deal,
        deal_approval_info=deal_approval_info,
    )


@bp.route("/deals/export.csv")
@login_required
def deals_export_csv():
    _require_tenant()

    borrowers = CreditBorrower.query.filter_by(tenant_id=g.tenant.id).order_by(CreditBorrower.name.asc()).all()
    selected_borrower_id = _to_int(request.args.get("borrower_id"))
    selected_status = (request.args.get("status") or "").strip().lower()
    allowed_statuses = {"in_review", "memo", "approved", "rejected"}

    borrower_ids = {b.id for b in borrowers}
    if selected_borrower_id and selected_borrower_id not in borrower_ids:
        selected_borrower_id = None
    if selected_status and selected_status not in allowed_statuses:
        selected_status = ""

    query = CreditDeal.query.filter_by(tenant_id=g.tenant.id)
    if selected_borrower_id:
        query = query.filter(CreditDeal.borrower_id == selected_borrower_id)
    if selected_status:
        query = query.filter(CreditDeal.status == selected_status)

    rows = query.order_by(CreditDeal.updated_at.desc()).all()
    rows = [d for d in rows if _borrower_visible_for_user(g.tenant, current_user.id, d.borrower)]

    deal_ids = [int(d.id) for d in rows]
    deal_memo_by_deal: dict[int, CreditMemo] = {}
    if deal_ids:
        deal_memos = (
            CreditMemo.query.filter(
                CreditMemo.tenant_id == g.tenant.id,
                CreditMemo.deal_id.in_(deal_ids),
            )
            .order_by(CreditMemo.updated_at.desc(), CreditMemo.id.desc())
            .all()
        )
        for memo in deal_memos:
            if memo.deal_id and int(memo.deal_id) not in deal_memo_by_deal:
                deal_memo_by_deal[int(memo.deal_id)] = memo

    deal_memo_ids = [int(m.id) for m in deal_memo_by_deal.values()]
    memo_summaries = _approval_summaries_for_memos(g.tenant.id, deal_memo_ids)
    memo_logs = _approval_logs_for_memos(g.tenant.id, deal_memo_ids)

    buffer = io.StringIO()
    writer = csv.writer(buffer)
    writer.writerow(
        [
            _("Code"),
            _("Borrower"),
            _("Purpose"),
            _("Amount"),
            _("Status"),
            _("Approval date"),
            _("Current task"),
            _("Approvals"),
        ]
    )

    for deal in rows:
        memo = deal_memo_by_deal.get(int(deal.id))
        summary = memo_summaries.get(int(memo.id), {}) if memo else {}
        logs = memo_logs.get(int(memo.id), []) if memo else []
        history_text = " | ".join(
            [
                f"{item.get('stage', '-')}: {item.get('decision', '-')}; {item.get('actor', '-')}; {item.get('date', '-')}"
                for item in logs
            ]
        )

        approved_dt = getattr(deal, "approval_date", None) or summary.get("approved_at")
        approved_txt = approved_dt.strftime("%d/%m/%Y") if approved_dt else "-"

        writer.writerow(
            [
                deal.code,
                deal.borrower.name if deal.borrower else "-",
                deal.purpose or "-",
                f"{float(deal.requested_amount or 0):.2f}",
                _display_deal_status(str(deal.status or "")),
                approved_txt,
                summary.get("current_task") or "-",
                history_text or "-",
            ]
        )

    response = make_response(buffer.getvalue())
    response.headers["Content-Type"] = "text/csv; charset=utf-8"
    response.headers["Content-Disposition"] = "attachment; filename=credit_deals.csv"
    return response


@bp.route("/facilities", methods=["GET", "POST"])
@login_required
def facilities():
    _require_tenant()
    _seed_credit_references()
    deals = CreditDeal.query.filter_by(tenant_id=g.tenant.id).order_by(CreditDeal.code.asc()).all()
    facility_types = CreditFacilityType.query.order_by(CreditFacilityType.label.asc()).all()
    edit_facility_id = _to_int(request.args.get("edit_id"))

    if request.method == "POST":
        action = (request.form.get("action") or "create").strip().lower()
        if action == "update":
            facility_id = int(request.form.get("facility_id") or 0)
            row = CreditFacility.query.filter_by(id=facility_id, tenant_id=g.tenant.id).first()
            if not row:
                flash(_("Facility invalide."), "warning")
                return redirect(url_for("credit.facilities", mode="search"))

            deal_id = int(request.form.get("deal_id") or 0)
            deal = CreditDeal.query.filter_by(id=deal_id, tenant_id=g.tenant.id).first()
            if not deal:
                flash(_("Deal invalide."), "warning")
                return redirect(url_for("credit.facilities", mode="search", edit_id=row.id))
            if not _borrower_visible_for_user(g.tenant, current_user.id, deal.borrower):
                flash(_("Borrower out of your UAM scope."), "warning")
                return redirect(url_for("credit.facilities", mode="search"))

            facility_type_id = _to_int(request.form.get("facility_type_id"))
            facility_type_ref = CreditFacilityType.query.filter_by(id=facility_type_id).first() if facility_type_id else None
            if not facility_type_ref:
                flash(_("Type de facility invalide."), "warning")
                return redirect(url_for("credit.facilities", mode="search", edit_id=row.id))

            row.deal_id = deal.id
            row.facility_type_id = facility_type_ref.id
            row.facility_type = facility_type_ref.code
            row.approved_amount = _to_decimal(request.form.get("approved_amount"), "0")
            row.tenor_months = int(request.form.get("tenor_months") or 0) or None
            row.interest_rate = _to_decimal(request.form.get("interest_rate"), "0")
            row.status = (request.form.get("status") or "draft").strip() or "draft"
            db.session.commit()
            flash(_("Facility mise à jour."), "success")
            return redirect(url_for("credit.facilities", mode="search"))

        deal_id = int(request.form.get("deal_id") or 0)
        deal = CreditDeal.query.filter_by(id=deal_id, tenant_id=g.tenant.id).first()
        if not deal:
            flash(_("Deal invalide."), "warning")
            return redirect(url_for("credit.facilities"))
        if not _borrower_visible_for_user(g.tenant, current_user.id, deal.borrower):
            flash(_("Borrower out of your UAM scope."), "warning")
            return redirect(url_for("credit.facilities", mode="search"))

        facility_type_id = _to_int(request.form.get("facility_type_id"))
        facility_type_ref = CreditFacilityType.query.filter_by(id=facility_type_id).first() if facility_type_id else None
        if not facility_type_ref:
            flash(_("Type de facility invalide."), "warning")
            return redirect(url_for("credit.facilities"))

        row = CreditFacility(
            tenant_id=g.tenant.id,
            deal_id=deal.id,
            facility_type_id=facility_type_ref.id,
            facility_type=facility_type_ref.code,
            approved_amount=_to_decimal(request.form.get("approved_amount"), "0"),
            tenor_months=int(request.form.get("tenor_months") or 0) or None,
            interest_rate=_to_decimal(request.form.get("interest_rate"), "0"),
            status=(request.form.get("status") or "draft").strip(),
        )
        db.session.add(row)
        db.session.flush()
        _maybe_create_backlog_task_for_new_facility_analysis(row, getattr(current_user, "id", None))
        db.session.commit()
        flash(_("Facility ajoutée."), "success")
        return redirect(url_for("credit.facilities"))

    selected_deal_id = _to_int(request.args.get("deal_id"))
    selected_type_id = _to_int(request.args.get("facility_type_id"))
    selected_status = (request.args.get("status") or "").strip().lower()
    allowed_statuses = {"draft", "approved", "booked"}

    deal_ids = {d.id for d in deals}
    type_ids = {t.id for t in facility_types}
    if selected_deal_id and selected_deal_id not in deal_ids:
        selected_deal_id = None
        flash(_("Deal invalide."), "warning")
    if selected_type_id and selected_type_id not in type_ids:
        selected_type_id = None
        flash(_("Type de facility invalide."), "warning")
    if selected_status and selected_status not in allowed_statuses:
        selected_status = ""

    query = CreditFacility.query.filter_by(tenant_id=g.tenant.id)
    if selected_deal_id:
        query = query.filter(CreditFacility.deal_id == selected_deal_id)
    if selected_type_id:
        query = query.filter(CreditFacility.facility_type_id == selected_type_id)
    if selected_status:
        query = query.filter(CreditFacility.status == selected_status)

    rows = query.order_by(CreditFacility.created_at.desc()).all()
    rows = [f for f in rows if _borrower_visible_for_user(g.tenant, current_user.id, f.deal.borrower if f.deal else None)]
    edit_facility = CreditFacility.query.filter_by(id=edit_facility_id, tenant_id=g.tenant.id).first() if edit_facility_id else None

    facility_deal_ids = sorted({int(f.deal_id) for f in rows if f.deal_id})
    deal_memo_by_deal: dict[int, CreditMemo] = {}
    if facility_deal_ids:
        deal_memos = (
            CreditMemo.query.filter(
                CreditMemo.tenant_id == g.tenant.id,
                CreditMemo.deal_id.in_(facility_deal_ids),
            )
            .order_by(CreditMemo.updated_at.desc(), CreditMemo.id.desc())
            .all()
        )
        for memo in deal_memos:
            if memo.deal_id and int(memo.deal_id) not in deal_memo_by_deal:
                deal_memo_by_deal[int(memo.deal_id)] = memo

    deal_memo_ids = [int(m.id) for m in deal_memo_by_deal.values()]
    memo_summaries = _approval_summaries_for_memos(g.tenant.id, deal_memo_ids)
    memo_logs = _approval_logs_for_memos(g.tenant.id, deal_memo_ids)
    facility_approval_info: dict[int, dict[str, object]] = {}
    for f in rows:
        memo = deal_memo_by_deal.get(int(f.deal_id or 0))
        if memo:
            data = dict(memo_summaries.get(int(memo.id), {}))
            data["logs"] = memo_logs.get(int(memo.id), [])
            facility_approval_info[int(f.id)] = data
        else:
            facility_approval_info[int(f.id)] = {
                "approved_at": None,
                "current_task": _("No memo"),
                "phases": [],
                "logs": [],
            }

    return render_template(
        "credit/facilities.html",
        tenant=g.tenant,
        facilities=rows,
        deals=deals,
        facility_types=facility_types,
        selected_deal_id=selected_deal_id,
        selected_type_id=selected_type_id,
        selected_status=selected_status,
        edit_facility=edit_facility,
        facility_approval_info=facility_approval_info,
    )


@bp.route("/collateral", methods=["GET", "POST"])
@login_required
def collateral():
    _require_tenant()
    _seed_credit_references()
    borrowers = CreditBorrower.query.filter_by(tenant_id=g.tenant.id).order_by(CreditBorrower.name.asc()).all()
    deals = CreditDeal.query.filter_by(tenant_id=g.tenant.id).order_by(CreditDeal.code.asc()).all()
    collateral_types = CreditCollateralType.query.order_by(CreditCollateralType.label.asc()).all()

    if request.method == "POST":
        borrower_id = int(request.form.get("borrower_id") or 0)
        borrower = CreditBorrower.query.filter_by(id=borrower_id, tenant_id=g.tenant.id).first()
        if not borrower:
            flash(_("Borrower invalide."), "warning")
            return redirect(url_for("credit.collateral"))

        collateral_type_id = _to_int(request.form.get("collateral_type_id"))
        collateral_type_ref = CreditCollateralType.query.filter_by(id=collateral_type_id).first() if collateral_type_id else None
        if not collateral_type_ref:
            flash(_("Type de collatéral invalide."), "warning")
            return redirect(url_for("credit.collateral"))

        deal_id = int(request.form.get("deal_id") or 0) or None
        row = CreditCollateral(
            tenant_id=g.tenant.id,
            borrower_id=borrower.id,
            deal_id=deal_id,
            collateral_type_id=collateral_type_ref.id,
            collateral_type=collateral_type_ref.code,
            description=(request.form.get("description") or "").strip() or None,
            market_value=_to_decimal(request.form.get("market_value"), "0"),
            haircut_pct=_to_decimal(request.form.get("haircut_pct"), "0"),
        )
        db.session.add(row)
        db.session.commit()
        flash(_("Collateral ajouté."), "success")
        return redirect(url_for("credit.collateral"))

    selected_borrower_id = _to_int(request.args.get("borrower_id"))
    selected_deal_id = _to_int(request.args.get("deal_id"))
    selected_type_id = _to_int(request.args.get("collateral_type_id"))

    borrower_ids = {b.id for b in borrowers}
    deal_ids = {d.id for d in deals}
    type_ids = {t.id for t in collateral_types}

    if selected_borrower_id and selected_borrower_id not in borrower_ids:
        selected_borrower_id = None
        flash(_("Borrower invalide."), "warning")
    if selected_deal_id and selected_deal_id not in deal_ids:
        selected_deal_id = None
        flash(_("Deal invalide."), "warning")
    if selected_type_id and selected_type_id not in type_ids:
        selected_type_id = None
        flash(_("Type de collatéral invalide."), "warning")

    query = CreditCollateral.query.filter_by(tenant_id=g.tenant.id)
    if selected_borrower_id:
        query = query.filter(CreditCollateral.borrower_id == selected_borrower_id)
    if selected_deal_id:
        query = query.filter(CreditCollateral.deal_id == selected_deal_id)
    if selected_type_id:
        query = query.filter(CreditCollateral.collateral_type_id == selected_type_id)

    rows = query.order_by(CreditCollateral.created_at.desc()).all()
    return render_template(
        "credit/collateral.html",
        tenant=g.tenant,
        collateral=rows,
        borrowers=borrowers,
        deals=deals,
        collateral_types=collateral_types,
        selected_borrower_id=selected_borrower_id,
        selected_deal_id=selected_deal_id,
        selected_type_id=selected_type_id,
    )


@bp.route("/guarantors", methods=["GET", "POST"])
@login_required
def guarantors():
    _require_tenant()
    _seed_credit_references()
    borrowers = CreditBorrower.query.filter_by(tenant_id=g.tenant.id).order_by(CreditBorrower.name.asc()).all()
    deals = CreditDeal.query.filter_by(tenant_id=g.tenant.id).order_by(CreditDeal.code.asc()).all()
    guarantee_types = CreditGuaranteeType.query.order_by(CreditGuaranteeType.label.asc()).all()

    if request.method == "POST":
        borrower_id = int(request.form.get("borrower_id") or 0)
        borrower = CreditBorrower.query.filter_by(id=borrower_id, tenant_id=g.tenant.id).first()
        if not borrower:
            flash(_("Borrower invalide."), "warning")
            return redirect(url_for("credit.guarantors"))

        guarantee_type_id = _to_int(request.form.get("guarantee_type_id"))
        guarantee_type_ref = CreditGuaranteeType.query.filter_by(id=guarantee_type_id).first() if guarantee_type_id else None
        if not guarantee_type_ref:
            flash(_("Type de garantie invalide."), "warning")
            return redirect(url_for("credit.guarantors"))

        row = CreditGuarantor(
            tenant_id=g.tenant.id,
            borrower_id=borrower.id,
            deal_id=int(request.form.get("deal_id") or 0) or None,
            name=(request.form.get("name") or "").strip(),
            guarantee_type_id=guarantee_type_ref.id,
            guarantee_type=guarantee_type_ref.code,
            amount=_to_decimal(request.form.get("amount"), "0"),
        )
        if not row.name:
            flash(_("Nom du garant requis."), "warning")
            return redirect(url_for("credit.guarantors"))

        db.session.add(row)
        db.session.commit()
        flash(_("Garant ajouté."), "success")
        return redirect(url_for("credit.guarantors"))

    selected_borrower_id = _to_int(request.args.get("borrower_id"))
    selected_deal_id = _to_int(request.args.get("deal_id"))
    selected_type_id = _to_int(request.args.get("guarantee_type_id"))

    borrower_ids = {b.id for b in borrowers}
    deal_ids = {d.id for d in deals}
    type_ids = {t.id for t in guarantee_types}

    if selected_borrower_id and selected_borrower_id not in borrower_ids:
        selected_borrower_id = None
        flash(_("Borrower invalide."), "warning")
    if selected_deal_id and selected_deal_id not in deal_ids:
        selected_deal_id = None
        flash(_("Deal invalide."), "warning")
    if selected_type_id and selected_type_id not in type_ids:
        selected_type_id = None
        flash(_("Type de garantie invalide."), "warning")

    query = CreditGuarantor.query.filter_by(tenant_id=g.tenant.id)
    if selected_borrower_id:
        query = query.filter(CreditGuarantor.borrower_id == selected_borrower_id)
    if selected_deal_id:
        query = query.filter(CreditGuarantor.deal_id == selected_deal_id)
    if selected_type_id:
        query = query.filter(CreditGuarantor.guarantee_type_id == selected_type_id)

    rows = query.order_by(CreditGuarantor.created_at.desc()).all()
    return render_template(
        "credit/guarantors.html",
        tenant=g.tenant,
        guarantors=rows,
        borrowers=borrowers,
        deals=deals,
        guarantee_types=guarantee_types,
        selected_borrower_id=selected_borrower_id,
        selected_deal_id=selected_deal_id,
        selected_type_id=selected_type_id,
    )


def _create_ratio_snapshot_for_statement(statement: CreditFinancialStatement) -> None:
    dscr = None
    leverage = None
    liquidity = None
    if statement.total_debt and statement.total_debt != 0:
        leverage = (
            statement.total_debt / (statement.ebitda if statement.ebitda else Decimal("1"))
            if statement.ebitda
            else None
        )
    if statement.total_debt:
        dscr = (statement.ebitda / statement.total_debt) if statement.total_debt != 0 else None
    liquidity = (statement.cash / statement.total_debt) if statement.total_debt else None

    grade = "A" if dscr and dscr >= Decimal("1.3") else ("BBB" if dscr and dscr >= Decimal("1.0") else "BB")
    db.session.add(
        CreditRatioSnapshot(
            tenant_id=statement.tenant_id,
            borrower_id=statement.borrower_id,
            statement_id=statement.id,
            snapshot_date=date.today(),
            dscr=dscr,
            leverage=leverage,
            liquidity=liquidity,
            risk_grade=grade,
        )
    )


@bp.route("/financials", methods=["GET", "POST"])
@login_required
def financials():
    _require_tenant()
    _seed_default_analyst_functions(g.tenant.id)
    credit_mode = (request.args.get("mode") or "search").strip().lower()
    borrowers = CreditBorrower.query.filter_by(tenant_id=g.tenant.id).order_by(CreditBorrower.name.asc()).all()
    users = User.query.filter_by(tenant_id=g.tenant.id).order_by(User.email.asc()).all()
    functions = CreditAnalystFunction.query.filter_by(tenant_id=g.tenant.id).order_by(CreditAnalystFunction.label.asc()).all()
    csv_templates = _financial_csv_templates(g.tenant)
    edit_statement_id = _to_int(request.args.get("statement_id")) if credit_mode == "edit" else None

    if request.method == "POST":
        action = (request.form.get("action") or "create").strip().lower()
        if action == "update":
            statement_id = _to_int(request.form.get("statement_id"))
            statement = (
                CreditFinancialStatement.query.filter_by(id=statement_id, tenant_id=g.tenant.id).first()
                if statement_id
                else None
            )
            if not statement:
                flash(_("État financier introuvable."), "warning")
                return redirect(url_for("credit.financials", mode="search"))

            borrower_id = int(request.form.get("borrower_id") or 0)
            borrower = CreditBorrower.query.filter_by(id=borrower_id, tenant_id=g.tenant.id).first()
            if not borrower:
                flash(_("Borrower invalide."), "warning")
                return redirect(url_for("credit.financials", mode="edit", statement_id=statement.id))

            analyst_user_id = _to_int(request.form.get("analyst_user_id"))
            analyst_function_id = _to_int(request.form.get("analyst_function_id"))
            analyst_user = User.query.filter_by(id=analyst_user_id, tenant_id=g.tenant.id).first() if analyst_user_id else None
            analyst_function = (
                CreditAnalystFunction.query.filter_by(id=analyst_function_id, tenant_id=g.tenant.id).first()
                if analyst_function_id
                else None
            )
            if analyst_user_id and not analyst_user:
                flash(_("Analyste invalide."), "warning")
                return redirect(url_for("credit.financials", mode="edit", statement_id=statement.id))
            if analyst_function_id and not analyst_function:
                flash(_("Fonction analyste invalide."), "warning")
                return redirect(url_for("credit.financials", mode="edit", statement_id=statement.id))

            statement.borrower_id = borrower.id
            statement.period_label = (request.form.get("period_label") or "FY").strip() or "FY"
            statement.fiscal_year = int(request.form.get("fiscal_year") or date.today().year)
            statement.revenue = _to_decimal(request.form.get("revenue"), "0")
            statement.ebitda = _to_decimal(request.form.get("ebitda"), "0")
            statement.total_debt = _to_decimal(request.form.get("total_debt"), "0")
            statement.cash = _to_decimal(request.form.get("cash"), "0")
            statement.net_income = _to_decimal(request.form.get("net_income"), "0")
            statement.spreading_status = (request.form.get("spreading_status") or "in_progress").strip() or "in_progress"
            statement.analyst_user_id = getattr(analyst_user, "id", None)
            statement.analyst_function_id = getattr(analyst_function, "id", None)
            statement.import_source = statement.import_source or "manual"

            db.session.query(CreditRatioSnapshot).filter_by(
                tenant_id=g.tenant.id,
                statement_id=statement.id,
            ).delete(synchronize_session=False)
            _create_ratio_snapshot_for_statement(statement)
            db.session.commit()
            flash(_("État financier modifié."), "success")
            return redirect(url_for("credit.financials", mode="search", borrower_id=statement.borrower_id))

        borrower_id = int(request.form.get("borrower_id") or 0)
        borrower = CreditBorrower.query.filter_by(id=borrower_id, tenant_id=g.tenant.id).first()
        if not borrower:
            flash(_("Borrower invalide."), "warning")
            return redirect(url_for("credit.financials"))

        analyst_user_id = _to_int(request.form.get("analyst_user_id"))
        analyst_function_id = _to_int(request.form.get("analyst_function_id"))
        analyst_user = User.query.filter_by(id=analyst_user_id, tenant_id=g.tenant.id).first() if analyst_user_id else None
        analyst_function = (
            CreditAnalystFunction.query.filter_by(id=analyst_function_id, tenant_id=g.tenant.id).first()
            if analyst_function_id
            else None
        )
        if analyst_user_id and not analyst_user:
            flash(_("Analyste invalide."), "warning")
            return redirect(url_for("credit.financials"))
        if analyst_function_id and not analyst_function:
            flash(_("Fonction analyste invalide."), "warning")
            return redirect(url_for("credit.financials"))

        statement = CreditFinancialStatement(
            tenant_id=g.tenant.id,
            borrower_id=borrower.id,
            period_label=(request.form.get("period_label") or "FY").strip(),
            fiscal_year=int(request.form.get("fiscal_year") or date.today().year),
            revenue=_to_decimal(request.form.get("revenue"), "0"),
            ebitda=_to_decimal(request.form.get("ebitda"), "0"),
            total_debt=_to_decimal(request.form.get("total_debt"), "0"),
            cash=_to_decimal(request.form.get("cash"), "0"),
            net_income=_to_decimal(request.form.get("net_income"), "0"),
            spreading_status=(request.form.get("spreading_status") or "in_progress").strip(),
            imported_by_user_id=getattr(current_user, "id", None),
            analyst_user_id=getattr(analyst_user, "id", None),
            analyst_function_id=getattr(analyst_function, "id", None),
            import_source="manual",
        )
        db.session.add(statement)
        db.session.flush()
        _create_ratio_snapshot_for_statement(statement)
        db.session.commit()
        flash(_("États financiers et snapshot ratios enregistrés."), "success")
        return redirect(url_for("credit.financials"))

    selected_borrower_id = _to_int(request.args.get("borrower_id"))
    borrower_ids = {b.id for b in borrowers}
    if selected_borrower_id and selected_borrower_id not in borrower_ids:
        selected_borrower_id = None
        flash(_("Borrower invalide."), "warning")

    edit_statement = (
        CreditFinancialStatement.query.filter_by(id=edit_statement_id, tenant_id=g.tenant.id).first()
        if edit_statement_id
        else None
    )
    if edit_statement_id and not edit_statement:
        flash(_("État financier introuvable."), "warning")
        return redirect(url_for("credit.financials", mode="search", borrower_id=selected_borrower_id))

    query = CreditFinancialStatement.query.filter_by(tenant_id=g.tenant.id)
    if selected_borrower_id:
        query = query.filter(CreditFinancialStatement.borrower_id == selected_borrower_id)

    rows = query.order_by(CreditFinancialStatement.created_at.desc()).all()

    borrower_ids_for_rows = sorted({int(r.borrower_id) for r in rows if r.borrower_id})
    borrower_memo_by_borrower: dict[int, CreditMemo] = {}
    if borrower_ids_for_rows:
        borrower_memos = (
            CreditMemo.query.filter(
                CreditMemo.tenant_id == g.tenant.id,
                CreditMemo.borrower_id.in_(borrower_ids_for_rows),
            )
            .order_by(CreditMemo.updated_at.desc(), CreditMemo.id.desc())
            .all()
        )
        for memo in borrower_memos:
            if memo.borrower_id and int(memo.borrower_id) not in borrower_memo_by_borrower:
                borrower_memo_by_borrower[int(memo.borrower_id)] = memo

    borrower_memo_ids = [int(m.id) for m in borrower_memo_by_borrower.values()]
    memo_summaries = _approval_summaries_for_memos(g.tenant.id, borrower_memo_ids)
    memo_logs = _approval_logs_for_memos(g.tenant.id, borrower_memo_ids)
    financial_approval_info: dict[int, dict[str, object]] = {}
    for row in rows:
        memo = borrower_memo_by_borrower.get(int(row.borrower_id or 0))
        if memo:
            data = dict(memo_summaries.get(int(memo.id), {}))
            data["logs"] = memo_logs.get(int(memo.id), [])
            financial_approval_info[int(row.id)] = data
        else:
            financial_approval_info[int(row.id)] = {
                "approved_at": None,
                "current_task": _("No memo"),
                "phases": [],
                "logs": [],
            }

    return render_template(
        "credit/financials.html",
        tenant=g.tenant,
        financials=rows,
        borrowers=borrowers,
        selected_borrower_id=selected_borrower_id,
        users=users,
        functions=functions,
        edit_statement=edit_statement,
        financial_approval_info=financial_approval_info,
        csv_templates=csv_templates,
        csv_fields=_FINANCIAL_CSV_FIELDS,
        default_mapping=_default_financial_csv_mapping(),
        current_year=date.today().year,
    )


@bp.route("/financials/<int:statement_id>/delete", methods=["POST"])
@login_required
def financials_delete(statement_id: int):
    _require_tenant()
    statement = CreditFinancialStatement.query.filter_by(id=statement_id, tenant_id=g.tenant.id).first()
    if not statement:
        flash(_("État financier introuvable."), "warning")
        return redirect(url_for("credit.financials", mode="search"))

    selected_borrower_id = _to_int(request.form.get("borrower_id"))
    db.session.query(CreditRatioSnapshot).filter_by(
        tenant_id=g.tenant.id,
        statement_id=statement.id,
    ).delete(synchronize_session=False)
    db.session.delete(statement)
    db.session.commit()
    flash(_("État financier supprimé."), "success")
    return redirect(url_for("credit.financials", mode="search", borrower_id=selected_borrower_id or statement.borrower_id))


@bp.route("/financials/csv-template", methods=["POST"])
@login_required
def financials_csv_template():
    _require_tenant()

    action = (request.form.get("action") or "").strip().lower()
    templates = _financial_csv_templates(g.tenant)

    if action == "save":
        name = str(request.form.get("template_name") or "").strip()
        if not name:
            flash(_("Template name is required."), "warning")
            return redirect(url_for("credit.financials"))

        mapping = _default_financial_csv_mapping()
        mapping.update(_mapping_from_form(request.form))

        replaced = False
        for item in templates:
            item_name = str(item.get("name") or "").strip().lower()
            if item_name == name.lower():
                item["name"] = name
                item["mapping"] = mapping
                replaced = True
                break
        if not replaced:
            templates.append({"name": name, "mapping": mapping})

        _save_financial_csv_templates(g.tenant, templates)
        db.session.commit()
        flash(_("CSV mapping template saved."), "success")
        return redirect(url_for("credit.financials"))

    if action == "delete":
        name = str(request.form.get("template_name") or "").strip().lower()
        if not name:
            flash(_("Template name is required."), "warning")
            return redirect(url_for("credit.financials"))

        kept = [t for t in templates if str(t.get("name") or "").strip().lower() != name]
        _save_financial_csv_templates(g.tenant, kept)
        db.session.commit()
        flash(_("CSV mapping template deleted."), "success")
        return redirect(url_for("credit.financials"))

    flash(_("Unknown template action."), "warning")
    return redirect(url_for("credit.financials"))


@bp.route("/financials/import", methods=["POST"])
@login_required
def financials_import():
    _require_tenant()
    _seed_default_analyst_functions(g.tenant.id)

    upload = request.files.get("file")
    if not upload or not upload.filename:
        flash(_("Fichier d'import requis."), "warning")
        return redirect(url_for("credit.financials"))

    analyst_user_id = _to_int(request.form.get("analyst_user_id"))
    analyst_function_id = _to_int(request.form.get("analyst_function_id"))
    analyst_user = User.query.filter_by(id=analyst_user_id, tenant_id=g.tenant.id).first() if analyst_user_id else None
    analyst_function = (
        CreditAnalystFunction.query.filter_by(id=analyst_function_id, tenant_id=g.tenant.id).first()
        if analyst_function_id
        else None
    )
    if analyst_user_id and not analyst_user:
        flash(_("Analyste invalide."), "warning")
        return redirect(url_for("credit.financials"))
    if analyst_function_id and not analyst_function:
        flash(_("Fonction analyste invalide."), "warning")
        return redirect(url_for("credit.financials"))

    try:
        payload = upload.read().decode("utf-8-sig")
    except Exception:
        flash(_("Impossible de lire le fichier CSV."), "warning")
        return redirect(url_for("credit.financials"))

    reader = csv.DictReader(io.StringIO(payload))
    if not reader.fieldnames:
        flash(_("CSV invalide: en-têtes manquants."), "warning")
        return redirect(url_for("credit.financials"))

    template_name = str(request.form.get("template_name") or "").strip()
    template_mapping = _find_financial_csv_template(g.tenant, template_name)
    if not template_name or not template_mapping:
        flash(_("Please select a valid mapping template."), "warning")
        return redirect(url_for("credit.financials"))

    mapping = _default_financial_csv_mapping()
    mapping.update(template_mapping)

    headers = {str(h).strip() for h in reader.fieldnames if h is not None}
    required_fields = [
        "borrower_id",
        "period_label",
        "fiscal_year",
        "revenue",
        "ebitda",
        "total_debt",
        "cash",
        "net_income",
    ]
    missing = sorted([mapping[fld] for fld in required_fields if not str(mapping.get(fld) or "").strip() or str(mapping.get(fld) or "").strip() not in headers])
    if missing:
        flash(_("CSV invalide: colonnes manquantes ({cols}).", cols=", ".join(missing)), "warning")
        return redirect(url_for("credit.financials"))

    imported = 0
    skipped = 0
    file_name = upload.filename or "upload.csv"
    for row in reader:
        borrower_id = _to_int((row.get(mapping["borrower_id"]) or "").strip())
        borrower = CreditBorrower.query.filter_by(id=borrower_id, tenant_id=g.tenant.id).first() if borrower_id else None
        if not borrower:
            skipped += 1
            continue

        try:
            fiscal_year = int((row.get(mapping["fiscal_year"]) or "").strip() or date.today().year)
        except Exception:
            skipped += 1
            continue

        spreading_col = str(mapping.get("spreading_status") or "").strip()
        spreading_value = (row.get(spreading_col) or "").strip() if spreading_col in headers else "in_progress"

        statement = CreditFinancialStatement(
            tenant_id=g.tenant.id,
            borrower_id=borrower.id,
            period_label=(row.get(mapping["period_label"]) or "FY").strip() or "FY",
            fiscal_year=fiscal_year,
            revenue=_to_decimal_loose(row.get(mapping["revenue"]), "0"),
            ebitda=_to_decimal_loose(row.get(mapping["ebitda"]), "0"),
            total_debt=_to_decimal_loose(row.get(mapping["total_debt"]), "0"),
            cash=_to_decimal_loose(row.get(mapping["cash"]), "0"),
            net_income=_to_decimal_loose(row.get(mapping["net_income"]), "0"),
            spreading_status=spreading_value or "in_progress",
            imported_by_user_id=getattr(current_user, "id", None),
            analyst_user_id=getattr(analyst_user, "id", None),
            analyst_function_id=getattr(analyst_function, "id", None),
            import_source=f"csv:{file_name}",
        )
        db.session.add(statement)
        db.session.flush()
        _create_ratio_snapshot_for_statement(statement)
        imported += 1

    db.session.commit()
    if imported == 0:
        flash(_("Aucune ligne importée."), "warning")
    else:
        flash(_("Import états financiers terminé: {ok} importées, {ko} ignorées.", ok=imported, ko=skipped), "success")
    return redirect(url_for("credit.financials"))


@bp.route("/financials/import-pdf-ai", methods=["POST"])
@login_required
def financials_import_pdf_ai():
    _require_tenant()
    _seed_default_analyst_functions(g.tenant.id)

    upload = request.files.get("pdf_file")
    if not upload or not upload.filename:
        flash(_("PDF file is required."), "warning")
        return redirect(url_for("credit.financials"))

    borrower_id = _to_int(request.form.get("borrower_id"))
    borrower = CreditBorrower.query.filter_by(id=borrower_id, tenant_id=g.tenant.id).first() if borrower_id else None
    if not borrower:
        flash(_("Borrower invalide."), "warning")
        return redirect(url_for("credit.financials"))

    analyst_user_id = _to_int(request.form.get("analyst_user_id"))
    analyst_function_id = _to_int(request.form.get("analyst_function_id"))
    analyst_user = User.query.filter_by(id=analyst_user_id, tenant_id=g.tenant.id).first() if analyst_user_id else None
    analyst_function = (
        CreditAnalystFunction.query.filter_by(id=analyst_function_id, tenant_id=g.tenant.id).first()
        if analyst_function_id
        else None
    )
    if analyst_user_id and not analyst_user:
        flash(_("Analyste invalide."), "warning")
        return redirect(url_for("credit.financials"))
    if analyst_function_id and not analyst_function:
        flash(_("Fonction analyste invalide."), "warning")
        return redirect(url_for("credit.financials"))

    pdf_bytes = upload.read() or b""
    if not pdf_bytes:
        flash(_("Unable to read PDF file."), "warning")
        return redirect(url_for("credit.financials"))

    pdf_text = _extract_pdf_text(pdf_bytes)
    if not pdf_text.strip():
        flash(_("No readable text found in PDF."), "warning")
        return redirect(url_for("credit.financials"))

    payload = _ai_extract_financial_payload(pdf_text, getattr(g, "lang", None))
    if not payload:
        flash(_("AI could not extract a valid financial statement from this PDF."), "warning")
        return redirect(url_for("credit.financials"))

    fiscal_year = _to_int(str(payload.get("fiscal_year") or "")) or date.today().year
    period_label = str(payload.get("period_label") or "FY").strip() or "FY"
    spreading_status = str(payload.get("spreading_status") or "needs_review").strip() or "needs_review"
    if spreading_status not in {"in_progress", "completed", "needs_review"}:
        spreading_status = "needs_review"

    statement = CreditFinancialStatement(
        tenant_id=g.tenant.id,
        borrower_id=borrower.id,
        period_label=period_label,
        fiscal_year=fiscal_year,
        revenue=_to_decimal_loose(str(payload.get("revenue") or "0"), "0"),
        ebitda=_to_decimal_loose(str(payload.get("ebitda") or "0"), "0"),
        total_debt=_to_decimal_loose(str(payload.get("total_debt") or "0"), "0"),
        cash=_to_decimal_loose(str(payload.get("cash") or "0"), "0"),
        net_income=_to_decimal_loose(str(payload.get("net_income") or "0"), "0"),
        spreading_status=spreading_status,
        imported_by_user_id=getattr(current_user, "id", None),
        analyst_user_id=getattr(analyst_user, "id", None),
        analyst_function_id=getattr(analyst_function, "id", None),
        import_source=f"pdf_ai:{upload.filename or 'upload.pdf'}",
    )
    db.session.add(statement)
    db.session.flush()
    _create_ratio_snapshot_for_statement(statement)
    db.session.commit()

    confidence = payload.get("confidence")
    if confidence is None:
        flash(_("AI PDF import completed."), "success")
    else:
        flash(_("AI PDF import completed (confidence: {value}).", value=confidence), "success")
    return redirect(url_for("credit.financials"))


@bp.route("/ratios")
@login_required
def ratios():
    _require_tenant()
    selected_borrower_id = _to_int(request.args.get("borrower_id"))
    selected_risk_grade = (request.args.get("risk_grade") or "").strip()
    date_from_raw = (request.args.get("date_from") or "").strip()
    date_to_raw = (request.args.get("date_to") or "").strip()
    max_rows = _to_int(request.args.get("limit")) or 200
    max_rows = max(20, min(max_rows, 1000))

    date_from = _parse_iso_date(date_from_raw)
    date_to = _parse_iso_date(date_to_raw)

    borrowers = CreditBorrower.query.filter_by(tenant_id=g.tenant.id).order_by(CreditBorrower.name.asc()).all()
    borrower_ids = {b.id for b in borrowers}
    if selected_borrower_id and selected_borrower_id not in borrower_ids:
        selected_borrower_id = None
        flash(_("Borrower invalide."), "warning")

    base_filters: list = [CreditRatioSnapshot.tenant_id == g.tenant.id]
    if selected_borrower_id:
        base_filters.append(CreditRatioSnapshot.borrower_id == selected_borrower_id)
    if selected_risk_grade:
        base_filters.append(CreditRatioSnapshot.risk_grade == selected_risk_grade)
    if date_from:
        base_filters.append(CreditRatioSnapshot.snapshot_date >= date_from)
    if date_to:
        base_filters.append(CreditRatioSnapshot.snapshot_date <= date_to)

    rows = (
        CreditRatioSnapshot.query.filter(*base_filters)
        .order_by(CreditRatioSnapshot.snapshot_date.desc(), CreditRatioSnapshot.id.desc())
        .limit(max_rows)
        .all()
    )

    # Keep one latest snapshot per borrower after filters.
    snapshot_map: dict[int, CreditRatioSnapshot] = {}
    for row in rows:
        if row.borrower_id not in snapshot_map:
            snapshot_map[row.borrower_id] = row
    borrower_snapshots = sorted(snapshot_map.values(), key=lambda r: (r.borrower.name.lower() if r.borrower else ""))

    risk_grade_options = [
        rg
        for (rg,) in db.session.query(CreditRatioSnapshot.risk_grade)
        .filter(CreditRatioSnapshot.tenant_id == g.tenant.id, CreditRatioSnapshot.risk_grade.isnot(None))
        .distinct()
        .order_by(CreditRatioSnapshot.risk_grade.asc())
        .all()
        if rg
    ]

    chart_labels: list[str] = []
    chart_dscr: list[float | None] = []
    chart_leverage: list[float | None] = []
    chart_liquidity: list[float | None] = []
    if selected_borrower_id:
        trend_rows = (
            CreditRatioSnapshot.query.filter(*base_filters)
            .order_by(CreditRatioSnapshot.snapshot_date.asc(), CreditRatioSnapshot.id.asc())
            .limit(36)
            .all()
        )
        for row in trend_rows:
            chart_labels.append(row.snapshot_date.strftime("%Y-%m-%d") if row.snapshot_date else "")
            chart_dscr.append(float(row.dscr) if row.dscr is not None else None)
            chart_leverage.append(float(row.leverage) if row.leverage is not None else None)
            chart_liquidity.append(float(row.liquidity) if row.liquidity is not None else None)
    else:
        # Compare latest borrower snapshots when no specific borrower is selected.
        for row in borrower_snapshots[:24]:
            chart_labels.append(row.borrower.name if row.borrower else str(row.borrower_id))
            chart_dscr.append(float(row.dscr) if row.dscr is not None else None)
            chart_leverage.append(float(row.leverage) if row.leverage is not None else None)
            chart_liquidity.append(float(row.liquidity) if row.liquidity is not None else None)

    chart_payload = {
        "labels": chart_labels,
        "dscr": chart_dscr,
        "leverage": chart_leverage,
        "liquidity": chart_liquidity,
        "selected_borrower": selected_borrower_id,
    }

    return render_template(
        "credit/ratios.html",
        tenant=g.tenant,
        ratios=rows,
        borrowers=borrowers,
        borrower_snapshots=borrower_snapshots,
        selected_borrower_id=selected_borrower_id,
        selected_risk_grade=selected_risk_grade,
        risk_grade_options=risk_grade_options,
        date_from_raw=date_from_raw,
        date_to_raw=date_to_raw,
        max_rows=max_rows,
        chart_payload=chart_payload,
    )


@bp.route("/references")
@login_required
def references():
    _require_tenant()
    _seed_credit_references()

    edit_kind = (request.args.get("edit_kind") or "").strip()
    edit_id = _to_int(request.args.get("edit_id"))
    edit_row = None
    model = _REF_KIND_MODEL_MAP.get(edit_kind)
    if model and edit_id:
        edit_row = model.query.filter_by(id=edit_id).first()

    return render_template(
        "credit/references.html",
        tenant=g.tenant,
        countries=CreditCountry.query.order_by(CreditCountry.name.asc()).all(),
        sectors=CreditSector.query.order_by(CreditSector.name.asc()).all(),
        ratings=CreditRating.query.order_by(CreditRating.rank_order.asc()).all(),
        facility_types=CreditFacilityType.query.order_by(CreditFacilityType.code.asc()).all(),
        collateral_types=CreditCollateralType.query.order_by(CreditCollateralType.code.asc()).all(),
        guarantee_types=CreditGuaranteeType.query.order_by(CreditGuaranteeType.code.asc()).all(),
        edit_kind=edit_kind,
        edit_row=edit_row,
    )


@bp.route("/references/<string:ref_kind>", methods=["POST"])
@login_required
def references_save(ref_kind: str):
    _require_tenant()
    _seed_credit_references()
    row_id = _to_int(request.form.get("id"))

    if ref_kind == "countries":
        row = CreditCountry.query.filter_by(id=row_id).first() if row_id else None
        if row_id and not row:
            flash(_("Reference row not found."), "warning")
            return redirect(url_for("credit.references"))

        iso_code = (request.form.get("iso_code") or "").strip().upper()
        names = _ml_values(request.form, "name")
        canonical = names.get("name_en") or names.get("name_fr") or next((v for v in names.values() if v), None)
        if not iso_code or len(iso_code) != 2 or not canonical:
            flash(_("Country code and name are required."), "warning")
            return redirect(url_for("credit.references"))

        dup_code_q = CreditCountry.query.filter(CreditCountry.iso_code == iso_code)
        dup_name_q = CreditCountry.query.filter(CreditCountry.name == canonical)
        if row:
            dup_code_q = dup_code_q.filter(CreditCountry.id != row.id)
            dup_name_q = dup_name_q.filter(CreditCountry.id != row.id)
        if dup_code_q.first():
            flash(_("Country code already exists."), "warning")
            return redirect(url_for("credit.references"))
        if dup_name_q.first():
            flash(_("Country name already exists."), "warning")
            return redirect(url_for("credit.references"))

        if row:
            row.iso_code = iso_code
            row.name = canonical
            for key, value in names.items():
                setattr(row, key, value)
        else:
            db.session.add(CreditCountry(iso_code=iso_code, name=canonical, **names))

    elif ref_kind == "sectors":
        row = CreditSector.query.filter_by(id=row_id).first() if row_id else None
        if row_id and not row:
            flash(_("Reference row not found."), "warning")
            return redirect(url_for("credit.references"))

        code = (request.form.get("code") or "").strip().lower()
        names = _ml_values(request.form, "name")
        canonical = names.get("name_en") or names.get("name_fr") or next((v for v in names.values() if v), None)
        if not code or not canonical:
            flash(_("Sector code and name are required."), "warning")
            return redirect(url_for("credit.references"))

        dup_code_q = CreditSector.query.filter(CreditSector.code == code)
        dup_name_q = CreditSector.query.filter(CreditSector.name == canonical)
        if row:
            dup_code_q = dup_code_q.filter(CreditSector.id != row.id)
            dup_name_q = dup_name_q.filter(CreditSector.id != row.id)
        if dup_code_q.first():
            flash(_("Sector code already exists."), "warning")
            return redirect(url_for("credit.references"))
        if dup_name_q.first():
            flash(_("Sector name already exists."), "warning")
            return redirect(url_for("credit.references"))

        if row:
            row.code = code
            row.name = canonical
            for key, value in names.items():
                setattr(row, key, value)
        else:
            db.session.add(CreditSector(code=code, name=canonical, **names))

    elif ref_kind == "ratings":
        row = CreditRating.query.filter_by(id=row_id).first() if row_id else None
        if row_id and not row:
            flash(_("Reference row not found."), "warning")
            return redirect(url_for("credit.references"))

        code = (request.form.get("code") or "").strip().upper()
        rank_order = _to_int(request.form.get("rank_order")) or 0
        labels = _ml_values(request.form, "label")
        if not code:
            flash(_("Rating code is required."), "warning")
            return redirect(url_for("credit.references"))

        dup_code_q = CreditRating.query.filter(CreditRating.code == code)
        if row:
            dup_code_q = dup_code_q.filter(CreditRating.id != row.id)
        if dup_code_q.first():
            flash(_("Rating code already exists."), "warning")
            return redirect(url_for("credit.references"))

        if row:
            row.code = code
            row.rank_order = rank_order
            for key, value in labels.items():
                setattr(row, key, value)
        else:
            db.session.add(CreditRating(code=code, rank_order=rank_order, **labels))

    elif ref_kind == "facility_types":
        row = CreditFacilityType.query.filter_by(id=row_id).first() if row_id else None
        if row_id and not row:
            flash(_("Reference row not found."), "warning")
            return redirect(url_for("credit.references"))

        code = (request.form.get("code") or "").strip().lower()
        labels = _ml_values(request.form, "label")
        canonical = labels.get("label_en") or labels.get("label_fr") or next((v for v in labels.values() if v), None)
        if not code or not canonical:
            flash(_("Type code and label are required."), "warning")
            return redirect(url_for("credit.references"))

        dup_code_q = CreditFacilityType.query.filter(CreditFacilityType.code == code)
        if row:
            dup_code_q = dup_code_q.filter(CreditFacilityType.id != row.id)
        if dup_code_q.first():
            flash(_("Type code already exists."), "warning")
            return redirect(url_for("credit.references"))

        if row:
            row.code = code
            row.label = canonical
            for key, value in labels.items():
                setattr(row, key, value)
        else:
            db.session.add(CreditFacilityType(code=code, label=canonical, **labels))

    elif ref_kind == "collateral_types":
        row = CreditCollateralType.query.filter_by(id=row_id).first() if row_id else None
        if row_id and not row:
            flash(_("Reference row not found."), "warning")
            return redirect(url_for("credit.references"))

        code = (request.form.get("code") or "").strip().lower()
        labels = _ml_values(request.form, "label")
        canonical = labels.get("label_en") or labels.get("label_fr") or next((v for v in labels.values() if v), None)
        if not code or not canonical:
            flash(_("Type code and label are required."), "warning")
            return redirect(url_for("credit.references"))

        dup_code_q = CreditCollateralType.query.filter(CreditCollateralType.code == code)
        if row:
            dup_code_q = dup_code_q.filter(CreditCollateralType.id != row.id)
        if dup_code_q.first():
            flash(_("Type code already exists."), "warning")
            return redirect(url_for("credit.references"))

        if row:
            row.code = code
            row.label = canonical
            for key, value in labels.items():
                setattr(row, key, value)
        else:
            db.session.add(CreditCollateralType(code=code, label=canonical, **labels))

    elif ref_kind == "guarantee_types":
        row = CreditGuaranteeType.query.filter_by(id=row_id).first() if row_id else None
        if row_id and not row:
            flash(_("Reference row not found."), "warning")
            return redirect(url_for("credit.references"))

        code = (request.form.get("code") or "").strip().lower()
        labels = _ml_values(request.form, "label")
        canonical = labels.get("label_en") or labels.get("label_fr") or next((v for v in labels.values() if v), None)
        if not code or not canonical:
            flash(_("Type code and label are required."), "warning")
            return redirect(url_for("credit.references"))

        dup_code_q = CreditGuaranteeType.query.filter(CreditGuaranteeType.code == code)
        if row:
            dup_code_q = dup_code_q.filter(CreditGuaranteeType.id != row.id)
        if dup_code_q.first():
            flash(_("Type code already exists."), "warning")
            return redirect(url_for("credit.references"))

        if row:
            row.code = code
            row.label = canonical
            for key, value in labels.items():
                setattr(row, key, value)
        else:
            db.session.add(CreditGuaranteeType(code=code, label=canonical, **labels))

    else:
        abort(404)

    try:
        db.session.commit()
    except IntegrityError:
        db.session.rollback()
        flash(_("Duplicate reference values."), "warning")
        return redirect(url_for("credit.references"))

    if row_id:
        flash(_("Reference row updated."), "success")
    else:
        flash(_("Reference row saved."), "success")
    return redirect(url_for("credit.references"))


@bp.route("/references/<string:ref_kind>/<int:row_id>/delete", methods=["POST"])
@login_required
def references_delete(ref_kind: str, row_id: int):
    _require_tenant()

    model = _REF_KIND_MODEL_MAP.get(ref_kind)
    if not model:
        abort(404)

    row = model.query.filter_by(id=row_id).first()
    if not row:
        flash(_("Reference row not found."), "warning")
        return redirect(url_for("credit.references"))

    try:
        db.session.delete(row)
        db.session.commit()
        flash(_("Reference row deleted."), "success")
    except IntegrityError:
        db.session.rollback()
        flash(_("Reference row is in use and cannot be deleted."), "warning")

    return redirect(url_for("credit.references"))


@bp.route("/memo-templates", methods=["GET", "POST"])
@login_required
def memo_templates():
    _require_tenant()
    if not _can_view_memo_templates():
        flash(_("Backoffice role required to manage workflow."), "warning")
        return redirect(url_for("credit.memos"))

    if request.method == "POST":
        if not _can_edit_memo_templates():
            flash(_("You do not have permission to edit memo templates."), "warning")
            return redirect(url_for("credit.memo_templates"))

        name = (request.form.get("name") or "").strip()
        memo_type = (request.form.get("memo_type") or "full_credit_memo").strip()
        description = (request.form.get("description") or "").strip() or None
        base_template_id = _to_int(request.form.get("base_template_id"))
        base_template = None
        if base_template_id:
            base_template = CreditMemoTemplate.query.filter_by(id=base_template_id, tenant_id=g.tenant.id).first()
            if not base_template:
                flash(_("Template invalide."), "warning")
                return redirect(url_for("credit.memo_templates"))

        if not name:
            flash(_("Template name is required."), "warning")
            return redirect(url_for("credit.memo_templates"))

        if memo_type not in {code for code, _ in _MEMO_TEMPLATE_TYPES}:
            memo_type = "full_credit_memo"

        row = CreditMemoTemplate(
            tenant_id=g.tenant.id,
            name=name,
            memo_type=memo_type,
            description=description,
            status="draft",
            base_template_id=getattr(base_template, "id", None),
            created_by_user_id=getattr(current_user, "id", None),
        )
        db.session.add(row)
        db.session.flush()

        v1 = CreditMemoTemplateVersion(
            tenant_id=g.tenant.id,
            template_id=row.id,
            version_no=1,
            status="draft",
            definition_json=_default_memo_template_definition(),
            change_notes="Initial version",
            created_by_user_id=getattr(current_user, "id", None),
        )
        db.session.add(v1)
        db.session.commit()
        flash(_("Template created."), "success")
        return redirect(url_for("credit.memo_template_designer", template_id=row.id))

    templates = (
        CreditMemoTemplate.query.filter_by(tenant_id=g.tenant.id)
        .order_by(CreditMemoTemplate.updated_at.desc(), CreditMemoTemplate.id.desc())
        .all()
    )
    return render_template(
        "credit/memo_templates.html",
        tenant=g.tenant,
        templates=templates,
        memo_types=_MEMO_TEMPLATE_TYPES,
    )


@bp.route("/memo-templates/<int:template_id>/designer", methods=["GET", "POST"])
@login_required
def memo_template_designer(template_id: int):
    _require_tenant()
    if not _can_view_memo_templates():
        flash(_("Backoffice role required to manage workflow."), "warning")
        return redirect(url_for("credit.memos"))

    row = CreditMemoTemplate.query.filter_by(id=template_id, tenant_id=g.tenant.id).first()
    if not row:
        flash(_("Template invalide."), "warning")
        return redirect(url_for("credit.memo_templates"))

    version_id = _to_int(request.args.get("version_id"))
    version = None
    if version_id:
        version = CreditMemoTemplateVersion.query.filter_by(
            id=version_id,
            tenant_id=g.tenant.id,
            template_id=row.id,
        ).first()
    if not version:
        version = _latest_memo_template_version(row.id, g.tenant.id)

    selected_deal_id = _to_int(request.values.get("test_deal_id"))
    preview_context = _memo_preview_context(g.tenant.id, selected_deal_id)

    resolved_definition = _resolve_memo_template_definition(row, version)
    working_definition = resolved_definition
    validation_findings = _validate_memo_template_definition(working_definition, preview_context)
    preview_html = _render_memo_template_html(row.name, working_definition, preview_context)
    snippets = _memo_template_snippets(g.tenant)

    compare_version_id = _to_int(request.values.get("compare_version_id"))
    compare_version = None
    compare_definition = None
    compare_preview_html = None
    compare_summary = None

    if request.method == "POST":
        action = (request.form.get("action") or "save").strip().lower()
        raw_json = (request.form.get("definition_json") or "").strip()
        change_notes = (request.form.get("change_notes") or "").strip() or None
        export_format = (request.form.get("export_format") or "html").strip().lower()

        if raw_json:
            try:
                parsed = json.loads(raw_json)
            except Exception:
                flash(_("Invalid template JSON."), "warning")
                return redirect(url_for("credit.memo_template_designer", template_id=row.id, version_id=getattr(version, "id", None)))
            working_definition = _sanitize_memo_template_definition(parsed)
        else:
            working_definition = _sanitize_memo_template_definition(working_definition)

        validation_findings = _validate_memo_template_definition(working_definition, preview_context)
        preview_html = _render_memo_template_html(row.name, working_definition, preview_context)

        if action == "save_snippet":
            snippet_name = (request.form.get("snippet_name") or "").strip()
            snippet_content = (request.form.get("snippet_content") or "").strip()
            snippet_id = (request.form.get("snippet_id") or "").strip() or f"snip-{int(datetime.utcnow().timestamp())}"

            if not snippet_name or not snippet_content:
                flash(_("Snippet name and content are required."), "warning")
            else:
                updated = [s for s in snippets if str(s.get("id") or "") != snippet_id]
                updated.insert(0, {"id": snippet_id[:64], "name": snippet_name[:120], "content": snippet_content[:8000]})
                _save_memo_template_snippets(g.tenant, updated[:80])
                db.session.commit()
                snippets = _memo_template_snippets(g.tenant)
                flash(_("Snippet saved."), "success")

            return redirect(
                url_for(
                    "credit.memo_template_designer",
                    template_id=row.id,
                    version_id=getattr(version, "id", None),
                    test_deal_id=selected_deal_id,
                    compare_version_id=compare_version_id,
                )
            )
        elif action == "delete_snippet":
            snippet_id = (request.form.get("snippet_id") or "").strip()
            if snippet_id:
                updated = [s for s in snippets if str(s.get("id") or "") != snippet_id]
                _save_memo_template_snippets(g.tenant, updated)
                db.session.commit()
                snippets = _memo_template_snippets(g.tenant)
                flash(_("Snippet deleted."), "success")

            return redirect(
                url_for(
                    "credit.memo_template_designer",
                    template_id=row.id,
                    version_id=getattr(version, "id", None),
                    test_deal_id=selected_deal_id,
                    compare_version_id=compare_version_id,
                )
            )

        if action == "preview":
            pass
        elif action == "validate":
            errors = len([f for f in validation_findings if f.get("severity") == "error"])
            warnings = len([f for f in validation_findings if f.get("severity") == "warning"])
            flash(_("Validation complete: {errors} errors, {warnings} warnings.", errors=errors, warnings=warnings), "info")
        elif action == "export":
            return _memo_template_export_response(row.name, preview_html, export_format)
        elif action == "save":
            if not _can_edit_memo_templates():
                flash(_("You do not have permission to edit memo templates."), "warning")
                return redirect(url_for("credit.memo_template_designer", template_id=row.id, version_id=getattr(version, "id", None)))

            if version:
                version.definition_json = working_definition
                version.validation_json = validation_findings
                version.change_notes = change_notes
                version.status = "draft"
                version.created_by_user_id = getattr(current_user, "id", None)
            else:
                version = CreditMemoTemplateVersion(
                    tenant_id=g.tenant.id,
                    template_id=row.id,
                    version_no=1,
                    status="draft",
                    definition_json=working_definition,
                    validation_json=validation_findings,
                    change_notes=change_notes or "Initial version",
                    created_by_user_id=getattr(current_user, "id", None),
                )
                db.session.add(version)

            row.status = "draft"
            db.session.commit()
            flash(_("Template saved."), "success")
            return redirect(url_for("credit.memo_template_designer", template_id=row.id, version_id=getattr(version, "id", None), test_deal_id=selected_deal_id))
        elif action == "save_version":
            if not _can_edit_memo_templates():
                flash(_("You do not have permission to edit memo templates."), "warning")
                return redirect(url_for("credit.memo_template_designer", template_id=row.id, version_id=getattr(version, "id", None)))

            latest = _latest_memo_template_version(row.id, g.tenant.id)
            next_no = (latest.version_no if latest else 0) + 1
            new_version = CreditMemoTemplateVersion(
                tenant_id=g.tenant.id,
                template_id=row.id,
                version_no=next_no,
                status="in_review",
                definition_json=working_definition,
                validation_json=validation_findings,
                change_notes=change_notes or _("New version"),
                created_by_user_id=getattr(current_user, "id", None),
            )
            db.session.add(new_version)
            row.status = "in_review"
            db.session.commit()
            flash(_("New template version saved."), "success")
            return redirect(url_for("credit.memo_template_designer", template_id=row.id, version_id=new_version.id, test_deal_id=selected_deal_id))
        elif action == "publish":
            if not _can_publish_memo_templates():
                flash(_("You do not have permission to record approval decisions."), "warning")
                return redirect(url_for("credit.memo_template_designer", template_id=row.id, version_id=getattr(version, "id", None)))

            latest = _latest_memo_template_version(row.id, g.tenant.id)
            next_no = (latest.version_no if latest else 0) + 1
            published_version = CreditMemoTemplateVersion(
                tenant_id=g.tenant.id,
                template_id=row.id,
                version_no=next_no,
                status="published",
                definition_json=working_definition,
                validation_json=validation_findings,
                change_notes=change_notes or _("Published version"),
                effective_date=date.today(),
                created_by_user_id=getattr(current_user, "id", None),
                approved_by_user_id=getattr(current_user, "id", None),
                published_at=datetime.utcnow(),
            )
            db.session.add(published_version)
            row.status = "published"
            row.published_version_no = next_no
            row.approved_by_user_id = getattr(current_user, "id", None)
            row.published_at = datetime.utcnow()
            db.session.commit()
            flash(_("Template published."), "success")
            return redirect(url_for("credit.memo_template_designer", template_id=row.id, version_id=published_version.id, test_deal_id=selected_deal_id))
        else:
            flash(_("Unknown template action."), "warning")

    versions = (
        CreditMemoTemplateVersion.query.filter_by(tenant_id=g.tenant.id, template_id=row.id)
        .order_by(CreditMemoTemplateVersion.version_no.desc(), CreditMemoTemplateVersion.id.desc())
        .all()
    )

    if compare_version_id:
        compare_version = CreditMemoTemplateVersion.query.filter_by(
            id=compare_version_id,
            tenant_id=g.tenant.id,
            template_id=row.id,
        ).first()
    if compare_version and version and compare_version.id != version.id:
        compare_definition = _sanitize_memo_template_definition(compare_version.definition_json or _default_memo_template_definition())
        compare_preview_html = _render_memo_template_html(f"{row.name} (v{compare_version.version_no})", compare_definition, preview_context)
        compare_summary = _memo_template_compare_summary(
            _sanitize_memo_template_definition(version.definition_json or _default_memo_template_definition()),
            compare_definition,
        )

    templates = (
        CreditMemoTemplate.query.filter_by(tenant_id=g.tenant.id)
        .order_by(CreditMemoTemplate.updated_at.desc(), CreditMemoTemplate.id.desc())
        .all()
    )
    deals = CreditDeal.query.filter_by(tenant_id=g.tenant.id).order_by(CreditDeal.updated_at.desc()).all()

    return render_template(
        "credit/memo_template_designer.html",
        tenant=g.tenant,
        template_row=row,
        templates=templates,
        versions=versions,
        current_version=version,
        memo_types=_MEMO_TEMPLATE_TYPES,
        toolbox_components=_MEMO_TOOLBOX_COMPONENTS,
        data_explorer=_MEMO_DATA_EXPLORER,
        selected_deal_id=selected_deal_id,
        deals=deals,
        preview_context=preview_context,
        validation_findings=validation_findings,
        preview_html=preview_html,
        compare_version_id=compare_version_id,
        compare_version=compare_version,
        compare_preview_html=compare_preview_html,
        compare_summary=compare_summary,
        snippets=snippets,
        working_definition_json=json.dumps(working_definition, ensure_ascii=True),
        can_edit_templates=_can_edit_memo_templates(),
        can_publish_templates=_can_publish_memo_templates(),
    )


@bp.route("/memo-templates/<int:template_id>/designer/export", methods=["GET"])
@login_required
def memo_template_designer_export(template_id: int):
    _require_tenant()
    if not _can_view_memo_templates():
        flash(_("Backoffice role required to manage workflow."), "warning")
        return redirect(url_for("credit.memos"))

    row = CreditMemoTemplate.query.filter_by(id=template_id, tenant_id=g.tenant.id).first()
    if not row:
        flash(_("Template invalide."), "warning")
        return redirect(url_for("credit.memo_templates"))

    version_id = _to_int(request.args.get("version_id"))
    version = None
    if version_id:
        version = CreditMemoTemplateVersion.query.filter_by(
            id=version_id,
            tenant_id=g.tenant.id,
            template_id=row.id,
        ).first()
    if not version:
        version = _latest_memo_template_version(row.id, g.tenant.id)

    selected_deal_id = _to_int(request.args.get("test_deal_id"))
    preview_context = _memo_preview_context(g.tenant.id, selected_deal_id)
    resolved_definition = _resolve_memo_template_definition(row, version)
    preview_html = _render_memo_template_html(row.name, resolved_definition, preview_context)
    export_format = (request.args.get("format") or "html").strip().lower()
    return _memo_template_export_response(row.name, preview_html, export_format)


@bp.route("/memos", methods=["GET", "POST"])
@login_required
def memos():
    _require_tenant()
    _seed_default_approval_workflow(g.tenant.id)
    deals = CreditDeal.query.filter_by(tenant_id=g.tenant.id).order_by(CreditDeal.updated_at.desc()).all()
    borrowers = CreditBorrower.query.filter_by(tenant_id=g.tenant.id).order_by(CreditBorrower.name.asc()).all()
    borrowers = [b for b in borrowers if _borrower_visible_for_user(g.tenant, current_user.id, b)]
    visible_borrower_ids = {int(b.id) for b in borrowers}
    deals = [d for d in deals if int(d.borrower_id or 0) in visible_borrower_ids]
    selected_template_id = _to_int(request.args.get("template_id"))
    selected_deal_id = _to_int(request.args.get("deal_id"))
    focus_memo_id = _to_int(request.args.get("focus_memo_id"))
    published_templates = (
        CreditMemoTemplate.query.filter_by(tenant_id=g.tenant.id, status="published")
        .order_by(CreditMemoTemplate.updated_at.desc(), CreditMemoTemplate.id.desc())
        .all()
    )

    if request.method == "POST":
        borrower_id = int(request.form.get("borrower_id") or 0) or None
        deal_id = int(request.form.get("deal_id") or 0) or None
        borrower_ref = CreditBorrower.query.filter_by(id=borrower_id, tenant_id=g.tenant.id).first() if borrower_id else None
        deal_ref = CreditDeal.query.filter_by(id=deal_id, tenant_id=g.tenant.id).first() if deal_id else None
        if deal_ref and not _borrower_visible_for_user(g.tenant, current_user.id, deal_ref.borrower):
            flash(_("Borrower out of your UAM scope."), "warning")
            return redirect(url_for("credit.memos", mode="search"))
        if borrower_ref and not _borrower_visible_for_user(g.tenant, current_user.id, borrower_ref):
            flash(_("Borrower out of your UAM scope."), "warning")
            return redirect(url_for("credit.memos", mode="search"))

        row = CreditMemo(
            tenant_id=g.tenant.id,
            deal_id=deal_id,
            borrower_id=borrower_id,
            title=(request.form.get("title") or "").strip() or _("Credit Memo"),
            recommendation=(request.form.get("recommendation") or "review").strip(),
            summary_text=(request.form.get("summary_text") or "").strip(),
            prepared_by_user_id=getattr(current_user, "id", None),
        )
        if not row.summary_text:
            flash(_("Le résumé du memo est requis."), "warning")
            return redirect(url_for("credit.memos"))
        db.session.add(row)
        db.session.flush()
        _maybe_create_initial_pending_approval_for_memo(row, getattr(current_user, "id", None))
        _maybe_create_backlog_task_for_new_memo_analysis(row, getattr(current_user, "id", None))
        db.session.commit()
        flash(_("Credit memo créé."), "success")
        return redirect(url_for("credit.memos"))

    rows = CreditMemo.query.filter_by(tenant_id=g.tenant.id).order_by(CreditMemo.updated_at.desc()).all()
    rows = [m for m in rows if _borrower_visible_for_user(g.tenant, current_user.id, m.borrower)]
    memo_ids = [int(m.id) for m in rows]
    memo_approval_info = _approval_summaries_for_memos(g.tenant.id, memo_ids)
    memo_logs = _approval_logs_for_memos(g.tenant.id, memo_ids)
    for memo_id in memo_ids:
        data = dict(memo_approval_info.get(memo_id, {}))
        data["logs"] = memo_logs.get(memo_id, [])
        memo_approval_info[memo_id] = data
    return render_template(
        "credit/memos.html",
        tenant=g.tenant,
        memos=rows,
        deals=deals,
        borrowers=borrowers,
        published_templates=published_templates,
        selected_template_id=selected_template_id,
        selected_deal_id=selected_deal_id,
        focus_memo_id=focus_memo_id,
        memo_approval_info=memo_approval_info,
    )


@bp.route("/memos/export.csv")
@login_required
def memos_export_csv():
    _require_tenant()

    rows = CreditMemo.query.filter_by(tenant_id=g.tenant.id).order_by(CreditMemo.updated_at.desc()).all()
    rows = [m for m in rows if _borrower_visible_for_user(g.tenant, current_user.id, m.borrower)]

    memo_ids = [int(m.id) for m in rows]
    memo_approval_info = _approval_summaries_for_memos(g.tenant.id, memo_ids)
    memo_logs = _approval_logs_for_memos(g.tenant.id, memo_ids)

    buffer = io.StringIO()
    writer = csv.writer(buffer)
    writer.writerow(
        [
            _("Title"),
            _("Deal"),
            _("Recommendation"),
            _("Updated"),
            _("Approval date"),
            _("Current task"),
            _("Approvals"),
        ]
    )

    for memo in rows:
        ap = memo_approval_info.get(int(memo.id), {})
        logs = memo_logs.get(int(memo.id), [])
        history_text = " | ".join(
            [
                f"{item.get('stage', '-')}: {item.get('decision', '-')}; {item.get('actor', '-')}; {item.get('date', '-')}"
                for item in logs
            ]
        )

        approved_dt = getattr(memo, "approval_date", None) or ap.get("approved_at")
        approved_txt = approved_dt.strftime("%d/%m/%Y") if approved_dt else "-"

        writer.writerow(
            [
                memo.title or "-",
                memo.deal.code if memo.deal else "-",
                _display_approval_decision(str(memo.recommendation or "review")),
                memo.updated_at.strftime("%d/%m/%Y") if memo.updated_at else "-",
                approved_txt,
                ap.get("current_task") or "-",
                history_text or "-",
            ]
        )

    response = make_response(buffer.getvalue())
    response.headers["Content-Type"] = "text/csv; charset=utf-8"
    response.headers["Content-Disposition"] = "attachment; filename=credit_memos.csv"
    return response


@bp.route("/memos/generate-from-template", methods=["POST"])
@login_required
def memos_generate_from_template():
    _require_tenant()

    template_id = _to_int(request.form.get("template_id"))
    deal_id = _to_int(request.form.get("deal_id"))
    recommendation = (request.form.get("recommendation") or "review").strip() or "review"

    if not template_id or not deal_id:
        flash(_("Template and deal are required."), "warning")
        return redirect(url_for("credit.memos", mode="add"))

    template = CreditMemoTemplate.query.filter_by(id=template_id, tenant_id=g.tenant.id).first()
    deal = CreditDeal.query.filter_by(id=deal_id, tenant_id=g.tenant.id).first()
    if not template or not deal:
        flash(_("Invalid template or deal."), "warning")
        return redirect(url_for("credit.memos", mode="add"))
    if not _borrower_visible_for_user(g.tenant, current_user.id, deal.borrower):
        flash(_("Borrower out of your UAM scope."), "warning")
        return redirect(url_for("credit.memos", mode="search"))

    if template.status != "published" or not template.published_version_no:
        flash(_("Selected template is not published."), "warning")
        return redirect(url_for("credit.memos", mode="add"))

    published_version = CreditMemoTemplateVersion.query.filter_by(
        tenant_id=g.tenant.id,
        template_id=template.id,
        version_no=template.published_version_no,
    ).first()
    if not published_version:
        flash(_("Published template version not found."), "warning")
        return redirect(url_for("credit.memos", mode="add"))

    definition = _sanitize_memo_template_definition(published_version.definition_json or _default_memo_template_definition())
    payload = _memo_preview_context(g.tenant.id, deal.id)
    html = _render_memo_template_html(template.name, definition, payload)
    summary_text = _html_to_text(html)
    title = (request.form.get("title") or "").strip() or f"{template.name} - {deal.code}"

    memo = CreditMemo(
        tenant_id=g.tenant.id,
        deal_id=deal.id,
        borrower_id=deal.borrower_id,
        title=title[:180],
        recommendation=recommendation,
        summary_text=summary_text[:65000],
        ai_generated=False,
        ai_response_json={
            "generated_from_template": {
                "template_id": template.id,
                "template_name": template.name,
                "template_version_no": published_version.version_no,
            }
        },
        prepared_by_user_id=getattr(current_user, "id", None),
    )
    db.session.add(memo)
    db.session.flush()
    _maybe_create_initial_pending_approval_for_memo(memo, getattr(current_user, "id", None))
    _maybe_create_backlog_task_for_new_memo_analysis(memo, getattr(current_user, "id", None))
    db.session.commit()

    flash(_("Final credit memo generated from published template."), "success")
    return redirect(url_for("credit.memos", mode="search", focus_memo_id=memo.id))


@bp.route("/memos/ai-draft", methods=["POST"])
@login_required
def memos_ai_draft():
    _require_tenant()

    deal_id = int(request.form.get("deal_id") or 0)
    deal = CreditDeal.query.filter_by(id=deal_id, tenant_id=g.tenant.id).first()
    if not deal:
        flash(_("Deal invalide pour IA."), "warning")
        return redirect(url_for("credit.memos"))
    if not _borrower_visible_for_user(g.tenant, current_user.id, deal.borrower):
        flash(_("Borrower out of your UAM scope."), "warning")
        return redirect(url_for("credit.memos", mode="search"))

    borrower = CreditBorrower.query.filter_by(id=deal.borrower_id, tenant_id=g.tenant.id).first()
    last_statement = (
        CreditFinancialStatement.query.filter_by(tenant_id=g.tenant.id, borrower_id=deal.borrower_id)
        .order_by(CreditFinancialStatement.created_at.desc())
        .first()
    )
    last_ratio = (
        CreditRatioSnapshot.query.filter_by(tenant_id=g.tenant.id, borrower_id=deal.borrower_id)
        .order_by(CreditRatioSnapshot.created_at.desc())
        .first()
    )

    guidance = (request.form.get("guidance") or "").strip()
    data_bundle = {
        "question": "credit_memo_ai",
        "source": "credit_module",
        "result": {
            "borrower": {
                "name": getattr(borrower, "name", None),
                "sector": getattr(borrower, "sector", None),
                "rating": getattr(borrower, "internal_rating", None),
            },
            "deal": {
                "code": deal.code,
                "purpose": deal.purpose,
                "requested_amount": float(deal.requested_amount or 0),
                "status": deal.status,
            },
            "financial_statement": {
                "period": getattr(last_statement, "period_label", None),
                "fiscal_year": getattr(last_statement, "fiscal_year", None),
                "revenue": float(getattr(last_statement, "revenue", 0) or 0),
                "ebitda": float(getattr(last_statement, "ebitda", 0) or 0),
                "total_debt": float(getattr(last_statement, "total_debt", 0) or 0),
                "cash": float(getattr(last_statement, "cash", 0) or 0),
            },
            "ratio_snapshot": {
                "dscr": float(getattr(last_ratio, "dscr", 0) or 0),
                "leverage": float(getattr(last_ratio, "leverage", 0) or 0),
                "liquidity": float(getattr(last_ratio, "liquidity", 0) or 0),
                "risk_grade": getattr(last_ratio, "risk_grade", None),
            },
        },
    }

    prompt = (
        "Generate a concise credit memo in markdown with sections: Executive summary, "
        "Risk analysis, Strengths, Weaknesses, Recommendation. "
        "Provide one final recommendation: approve, approve_with_conditions, or reject. "
        "Use factual underwriting tone."
    )
    if guidance:
        prompt += " Additional guidance from analyst: " + guidance

    ai_result = analyze_with_ai(data_bundle=data_bundle, user_message=prompt, lang=getattr(g, "lang", None))
    summary = str(ai_result.get("analysis") or "").strip()
    if not summary:
        summary = _(
            "Unable to generate AI memo. Please review financials, ratios and collateral manually before committee."
        )

    text_l = summary.lower()
    recommendation = "review"
    if "approve_with_conditions" in text_l or "approve with conditions" in text_l:
        recommendation = "approve_with_conditions"
    elif "approve" in text_l:
        recommendation = "approve"
    elif "reject" in text_l:
        recommendation = "reject"

    memo = CreditMemo(
        tenant_id=g.tenant.id,
        deal_id=deal.id,
        borrower_id=deal.borrower_id,
        title=f"AI Memo {deal.code}",
        recommendation=recommendation,
        summary_text=summary,
        ai_generated=True,
        ai_prompt=prompt,
        ai_response_json=ai_result if isinstance(ai_result, dict) else {},
        prepared_by_user_id=getattr(current_user, "id", None),
    )
    db.session.add(memo)
    db.session.flush()
    _maybe_create_initial_pending_approval_for_memo(memo, getattr(current_user, "id", None))
    _maybe_create_backlog_task_for_new_memo_analysis(memo, getattr(current_user, "id", None))
    db.session.commit()

    flash(_("AI credit memo généré."), "success")
    return redirect(url_for("credit.memos"))


@bp.route("/memos/<int:memo_id>/pdf", methods=["GET"])
@login_required
def memo_pdf(memo_id: int):
    _require_tenant()

    memo = CreditMemo.query.filter_by(id=memo_id, tenant_id=g.tenant.id).first()
    if not memo:
        flash(_("Memo invalide."), "warning")
        return redirect(url_for("credit.memos", mode="search"))
    if not _borrower_visible_for_user(g.tenant, current_user.id, memo.borrower):
        flash(_("Borrower out of your UAM scope."), "warning")
        return redirect(url_for("credit.memos", mode="search"))

    html = None
    generated_info = memo.ai_response_json.get("generated_from_template") if isinstance(memo.ai_response_json, dict) else None
    if isinstance(generated_info, dict):
        template_id = _to_int(generated_info.get("template_id"))
        version_no = _to_int(generated_info.get("template_version_no"))
        template = CreditMemoTemplate.query.filter_by(id=template_id, tenant_id=g.tenant.id).first() if template_id else None
        if template and memo.deal_id:
            version = None
            if version_no:
                version = CreditMemoTemplateVersion.query.filter_by(
                    tenant_id=g.tenant.id,
                    template_id=template.id,
                    version_no=version_no,
                ).first()
            if not version and template.published_version_no:
                version = CreditMemoTemplateVersion.query.filter_by(
                    tenant_id=g.tenant.id,
                    template_id=template.id,
                    version_no=template.published_version_no,
                ).first()
            if version:
                definition = _sanitize_memo_template_definition(version.definition_json or _default_memo_template_definition())
                payload = _memo_preview_context(g.tenant.id, memo.deal_id)
                html = _render_memo_template_html(template.name, definition, payload)

    if not html:
        summary_plain = _html_to_text(str(memo.summary_text or ""))
        summary_html = html_escape(summary_plain, quote=True).replace("\n", "<br>")
        html = (
            "<!doctype html><html><head><meta charset='utf-8'><title>"
            + html_escape(str(memo.title or _("Credit Memo")), quote=True)
            + "</title><style>body{font-family:Arial,sans-serif;padding:28px;color:#102a43;}"
            "h1{font-size:24px;margin:0 0 10px 0;color:#0b4f6c;}"
            ".meta{color:#627d98;margin-bottom:16px;}"
            ".memo-section{margin:0 0 14px 0;padding:12px;border:1px solid #d9e2ec;border-radius:8px;background:#fff;}"
            ".memo-section h3{margin:0 0 8px 0;font-size:16px;color:#0b4f6c;}"
            "</style></head><body>"
            + f"<h1>{html_escape(str(memo.title or _('Credit Memo')), quote=True)}</h1>"
            + "<section class='memo-section'>"
            + f"<h3>{html_escape(str(_('Recommendation')), quote=True)}</h3>"
            + f"<div>{html_escape(str(memo.recommendation or 'review'), quote=True)}</div>"
            + "</section>"
            + "<section class='memo-section'>"
            + f"<h3>{html_escape(str(_('Executive Summary')), quote=True)}</h3>"
            + f"<div>{summary_html}</div>"
            + "</section>"
            + "</body></html>"
        )

    return _memo_template_export_response(memo.title or _("Credit Memo"), html, "pdf")


@bp.route("/help/chat", methods=["POST"])
@login_required
def help_chat():
    _require_tenant()

    payload = request.get_json(silent=True) or {}
    message = (payload.get("message") or "").strip()
    if not message:
        return jsonify({"ok": False, "error": _("Message vide.")}), 400

    text = message.lower()
    credit_url = url_for("credit.overview")

    if any(k in text for k in ["borrower", "contrepart", "counterparty", "client", "rating"]):
        reply = _(
            "Borrowers: enregistrez secteur, pays et rating pour alimenter le filtrage UAM et le workflow d'approbation."
        )
    elif any(k in text for k in ["deal", "intake", "demande", "montant"]):
        reply = _(
            "Deals: créez la demande avec purpose, montant et statut, puis rattachez facility, états financiers et memo."
        )
    elif any(k in text for k in ["facilit", "tenor", "rate", "tranche"]):
        reply = _(
            "Facilities: gérez type, montant approuvé, tenor et taux pour structurer la transaction avant décision."
        )
    elif any(k in text for k in ["statement", "financial", "spreading", "ebitda", "ratio"]):
        reply = _(
            "Financials & Ratios: importez ou saisissez les états, puis vérifiez DSCR, leverage et liquidité pour le risk view."
        )
    elif any(k in text for k in ["memo", "credit memo", "template", "committee"]):
        reply = _(
            "Credit Memo: générez le memo (manuel, IA ou template publié) avec recommandation et pièces justificatives."
        )
    elif any(k in text for k in ["approval", "workflow", "approb", "esign", "backlog", "task"]):
        reply = _(
            "Approvals & Workflow: suivez les étapes, décisions, approbateurs et la tâche courante; e-sign disponible sur les décisions pending."
        )
    else:
        reply = _(
            "Je peux aider sur Borrowers, Deals, Facilities, Financials, Ratios, Credit Memo, Approvals, Workflow et Backlog."
        )

    reply = f"{reply} {_('Ouvrez aussi le module Credit')}: {credit_url}"
    suggestions = [
        _("Comment créer un deal ?"),
        _("Comment structurer une facility ?"),
        _("Comment générer un credit memo ?"),
        _("Comment suivre le workflow d'approbation ?"),
    ]
    return jsonify({"ok": True, "reply": reply, "suggestions": suggestions})


@bp.route("/approvals", methods=["GET", "POST"])
@login_required
def approvals():
    _require_tenant()
    _seed_default_approval_workflow(g.tenant.id)
    memos = CreditMemo.query.filter_by(tenant_id=g.tenant.id).order_by(CreditMemo.updated_at.desc()).all()
    memos = [m for m in memos if _borrower_visible_for_user(g.tenant, current_user.id, m.borrower)]
    workflow_steps = _workflow_steps_ordered(g.tenant.id)

    can_submit = _can_record_approval_decisions()

    if request.method == "POST":
        if not can_submit:
            flash(_("You do not have permission to record approval decisions."), "warning")
            return redirect(url_for("credit.approvals"))

        memo_id = int(request.form.get("memo_id") or 0)
        memo = CreditMemo.query.filter_by(id=memo_id, tenant_id=g.tenant.id).first()
        if not memo:
            flash(_("Memo invalide."), "warning")
            return redirect(url_for("credit.approvals"))
        if not _borrower_visible_for_user(g.tenant, current_user.id, memo.borrower):
            flash(_("Borrower out of your UAM scope."), "warning")
            return redirect(url_for("credit.approvals"))

        workflow_step_id = _to_int(request.form.get("workflow_step_id"))
        if not workflow_step_id:
            flash(_("Workflow step is required."), "warning")
            return redirect(url_for("credit.approvals", mode="add"))

        workflow_step = None
        if workflow_step_id:
            workflow_step = CreditApprovalWorkflowStep.query.filter_by(
                id=workflow_step_id,
                tenant_id=g.tenant.id,
            ).first()
            if not workflow_step:
                flash(_("Workflow step invalide."), "warning")
                return redirect(url_for("credit.approvals"))

        expected_step, workflow_state_message = _expected_workflow_step_for_memo(g.tenant.id, memo.id, workflow_steps)
        if workflow_state_message and expected_step is None:
            flash(workflow_state_message, "warning")
            return redirect(url_for("credit.approvals", mode="add"))
        if expected_step and workflow_step and expected_step.id != workflow_step.id:
            flash(
                _(
                    "Invalid workflow order. Expected step: {step}",
                    step=expected_step.step_name or expected_step.stage,
                ),
                "warning",
            )
            return redirect(url_for("credit.approvals", mode="add"))

        decision = (request.form.get("decision") or "pending").strip()
        stage = workflow_step.stage if workflow_step else (request.form.get("stage") or "analyst_review").strip()

        analyst_group_id = workflow_step.group_id if workflow_step else None
        analyst_function_id = workflow_step.function_id if workflow_step else None
        analyst_function = None
        if workflow_step and workflow_step.function_ref:
            analyst_function = workflow_step.function_ref.code
        elif workflow_step and workflow_step.function_name:
            analyst_function = workflow_step.function_name

        approval = CreditApproval(
            tenant_id=g.tenant.id,
            memo_id=memo.id,
            stage=stage,
            decision=decision,
            comments=(request.form.get("comments") or "").strip() or None,
            workflow_step_id=workflow_step.id if workflow_step else None,
            analyst_group_id=analyst_group_id,
            analyst_function_id=analyst_function_id,
            analyst_function=analyst_function,
            actor_user_id=getattr(current_user, "id", None),
            decided_at=datetime.utcnow() if decision != "pending" else None,
        )
        db.session.add(approval)
        if approval.decision == "approved":
            _sync_entity_approval_dates_for_memo(memo, approval.decided_at)
        _maybe_create_backlog_task_for_pending_approval(approval)
        db.session.commit()
        flash(_("Décision d'approbation enregistrée."), "success")
        return redirect(url_for("credit.approvals"))

    rows = CreditApproval.query.filter_by(tenant_id=g.tenant.id).order_by(CreditApproval.created_at.desc()).all()
    rows = [a for a in rows if _borrower_visible_for_user(g.tenant, current_user.id, a.memo.borrower if a.memo else None)]
    memo_ids_for_rows = sorted({int(a.memo_id) for a in rows if a.memo_id})
    memo_logs_by_id = _approval_logs_for_memos(g.tenant.id, memo_ids_for_rows)
    expected_step_by_memo: dict[int, int] = {}
    workflow_state_by_memo: dict[int, str] = {}
    for memo in memos:
        step, msg = _expected_workflow_step_for_memo(g.tenant.id, memo.id, workflow_steps)
        if step:
            expected_step_by_memo[memo.id] = step.id
        if msg:
            workflow_state_by_memo[memo.id] = msg

    return render_template(
        "credit/approvals.html",
        tenant=g.tenant,
        approvals=rows,
        memos=memos,
        workflow_steps=workflow_steps,
        stage_options=_approval_stage_options(),
        can_submit=can_submit,
        expected_step_by_memo=expected_step_by_memo,
        workflow_state_by_memo=workflow_state_by_memo,
        memo_logs_by_id=memo_logs_by_id,
    )


@bp.route("/approvals/export.csv")
@login_required
def approvals_export_csv():
    _require_tenant()

    rows = CreditApproval.query.filter_by(tenant_id=g.tenant.id).order_by(CreditApproval.created_at.desc()).all()
    rows = [a for a in rows if _borrower_visible_for_user(g.tenant, current_user.id, a.memo.borrower if a.memo else None)]

    memo_ids = sorted({int(a.memo_id) for a in rows if a.memo_id})
    memo_logs_by_id = _approval_logs_for_memos(g.tenant.id, memo_ids)

    buffer = io.StringIO()
    writer = csv.writer(buffer)
    writer.writerow(
        [
            _("Memo"),
            _("Stage"),
            _("Group"),
            _("Function"),
            _("Decision"),
            _("Comments"),
            _("Date"),
            _("Analyst"),
            _("Approvals"),
        ]
    )

    for row in rows:
        memo_logs = memo_logs_by_id.get(int(row.memo_id or 0), [])
        history_text = " | ".join(
            [
                f"{item.get('stage', '-')}: {item.get('decision', '-')}; {item.get('actor', '-')}; {item.get('date', '-')}"
                for item in memo_logs
            ]
        )
        writer.writerow(
            [
                row.memo.title if row.memo else "-",
                row.workflow_step.step_name if row.workflow_step else _display_approval_stage(str(row.stage or "")),
                row.analyst_group.name if row.analyst_group else "-",
                row.analyst_function_ref.label if row.analyst_function_ref else (row.analyst_function or "-"),
                _display_approval_decision(str(row.decision or "pending")),
                row.comments or "-",
                (row.decided_at or row.created_at).strftime("%d/%m/%Y %H:%M") if (row.decided_at or row.created_at) else "-",
                row.actor_user.email if row.actor_user else _("Unknown approver"),
                history_text or "-",
            ]
        )

    response = make_response(buffer.getvalue())
    response.headers["Content-Type"] = "text/csv; charset=utf-8"
    response.headers["Content-Disposition"] = "attachment; filename=credit_approvals.csv"
    return response


@bp.route("/approval-workflow", methods=["GET", "POST"])
@login_required
def approval_workflow():
    _require_tenant()
    if not _can_manage_credit_backoffice():
        flash(_("Backoffice role required to manage workflow."), "warning")
        return redirect(url_for("credit.approvals"))

    _seed_default_analyst_functions(g.tenant.id)
    _seed_default_approval_workflow(g.tenant.id)
    _seed_credit_references()

    if request.method == "POST":
        action = (request.form.get("action") or "").strip()

        if action == "create_group":
            name = (request.form.get("name") or "").strip()
            description = (request.form.get("description") or "").strip() or None
            if not name:
                flash(_("Nom du groupe requis."), "warning")
                return redirect(url_for("credit.approval_workflow"))

            group = CreditAnalystGroup(tenant_id=g.tenant.id, name=name, description=description)
            db.session.add(group)
            try:
                db.session.commit()
                flash(_("Groupe analyste créé."), "success")
            except IntegrityError:
                db.session.rollback()
                flash(_("Nom du groupe déjà utilisé."), "warning")
            return redirect(url_for("credit.approval_workflow"))

        if action == "create_function":
            code = (request.form.get("code") or "").strip().lower().replace(" ", "_")
            label = (request.form.get("label") or "").strip()
            if not code or not label:
                flash(_("Code et libellé de fonction requis."), "warning")
                return redirect(url_for("credit.approval_workflow"))

            db.session.add(CreditAnalystFunction(tenant_id=g.tenant.id, code=code, label=label))
            try:
                db.session.commit()
                flash(_("Fonction analyste créée."), "success")
            except IntegrityError:
                db.session.rollback()
                flash(_("Code fonction déjà utilisé."), "warning")
            return redirect(url_for("credit.approval_workflow"))

        if action == "delete_function":
            function_id = _to_int(request.form.get("function_id"))
            function_row = (
                CreditAnalystFunction.query.filter_by(id=function_id, tenant_id=g.tenant.id).first()
                if function_id
                else None
            )
            if not function_row:
                flash(_("Fonction analyste invalide."), "warning")
                return redirect(url_for("credit.approval_workflow"))

            CreditAnalystGroupMember.query.filter_by(function_id=function_row.id).update(
                {CreditAnalystGroupMember.function_id: None},
                synchronize_session=False,
            )
            CreditApprovalWorkflowStep.query.filter_by(tenant_id=g.tenant.id, function_id=function_row.id).update(
                {
                    CreditApprovalWorkflowStep.function_id: None,
                    CreditApprovalWorkflowStep.function_name: None,
                },
                synchronize_session=False,
            )
            CreditApproval.query.filter_by(tenant_id=g.tenant.id, analyst_function_id=function_row.id).update(
                {CreditApproval.analyst_function_id: None},
                synchronize_session=False,
            )
            CreditFinancialStatement.query.filter_by(tenant_id=g.tenant.id, analyst_function_id=function_row.id).update(
                {CreditFinancialStatement.analyst_function_id: None},
                synchronize_session=False,
            )
            db.session.delete(function_row)
            db.session.commit()
            flash(_("Fonction analyste supprimée."), "success")
            return redirect(url_for("credit.approval_workflow"))

        if action == "delete_group":
            group_id = _to_int(request.form.get("group_id"))
            group = CreditAnalystGroup.query.filter_by(id=group_id, tenant_id=g.tenant.id).first() if group_id else None
            if not group:
                flash(_("Groupe analyste invalide."), "warning")
                return redirect(url_for("credit.approval_workflow"))

            CreditApprovalWorkflowStep.query.filter_by(tenant_id=g.tenant.id, group_id=group.id).update(
                {CreditApprovalWorkflowStep.group_id: None},
                synchronize_session=False,
            )
            CreditApproval.query.filter_by(tenant_id=g.tenant.id, analyst_group_id=group.id).update(
                {CreditApproval.analyst_group_id: None},
                synchronize_session=False,
            )
            db.session.delete(group)
            db.session.commit()
            flash(_("Groupe analyste supprimé."), "success")
            return redirect(url_for("credit.approval_workflow"))

        if action == "add_member":
            group_id = _to_int(request.form.get("group_id"))
            user_id = _to_int(request.form.get("user_id"))
            function_id = _to_int(request.form.get("function_id"))

            group = CreditAnalystGroup.query.filter_by(id=group_id, tenant_id=g.tenant.id).first() if group_id else None
            user = User.query.filter_by(id=user_id, tenant_id=g.tenant.id).first() if user_id else None
            function_row = (
                CreditAnalystFunction.query.filter_by(id=function_id, tenant_id=g.tenant.id).first()
                if function_id
                else None
            )
            if not group or not user or not function_row:
                flash(_("Membre analyste invalide."), "warning")
                return redirect(url_for("credit.approval_workflow"))

            db.session.add(
                CreditAnalystGroupMember(
                    group_id=group.id,
                    user_id=user.id,
                    function_id=function_row.id,
                    function_name=function_row.code,
                )
            )
            try:
                db.session.commit()
                flash(_("Membre ajouté au groupe."), "success")
            except IntegrityError:
                db.session.rollback()
                flash(_("Membre/fonction déjà présent dans ce groupe."), "warning")
            return redirect(url_for("credit.approval_workflow"))

        if action == "remove_member":
            member_id = _to_int(request.form.get("member_id"))
            member = (
                CreditAnalystGroupMember.query.join(CreditAnalystGroup)
                .filter(
                    CreditAnalystGroupMember.id == member_id,
                    CreditAnalystGroup.tenant_id == g.tenant.id,
                )
                .first()
            )
            if not member:
                flash(_("Membre analyste invalide."), "warning")
                return redirect(url_for("credit.approval_workflow"))

            db.session.delete(member)
            db.session.commit()
            flash(_("Membre retiré du groupe."), "success")
            return redirect(url_for("credit.approval_workflow"))

        if action == "add_step":
            stage = (request.form.get("stage") or "").strip() or "analyst_review"
            step_name = (request.form.get("step_name") or "").strip() or stage
            step_order = _to_int(request.form.get("step_order"))
            group_id = _to_int(request.form.get("group_id"))
            function_id = _to_int(request.form.get("function_id"))
            sla_days = _to_int(request.form.get("sla_days"))
            is_required = (request.form.get("is_required") or "").lower() in ("on", "1", "true", "yes")

            if step_order is None:
                top_step = (
                    CreditApprovalWorkflowStep.query.filter_by(tenant_id=g.tenant.id)
                    .order_by(CreditApprovalWorkflowStep.step_order.desc())
                    .first()
                )
                step_order = (top_step.step_order + 1) if top_step else 1

            group = CreditAnalystGroup.query.filter_by(id=group_id, tenant_id=g.tenant.id).first() if group_id else None
            if group_id and not group:
                flash(_("Groupe analyste invalide."), "warning")
                return redirect(url_for("credit.approval_workflow"))

            function_row = (
                CreditAnalystFunction.query.filter_by(id=function_id, tenant_id=g.tenant.id).first()
                if function_id
                else None
            )
            if function_id and not function_row:
                flash(_("Fonction analyste invalide."), "warning")
                return redirect(url_for("credit.approval_workflow"))

            db.session.add(
                CreditApprovalWorkflowStep(
                    tenant_id=g.tenant.id,
                    step_order=step_order,
                    stage=stage,
                    step_name=step_name,
                    group_id=getattr(group, "id", None),
                    function_id=getattr(function_row, "id", None),
                    function_name=getattr(function_row, "code", None),
                    sla_days=sla_days,
                    is_required=is_required,
                )
            )
            db.session.commit()
            flash(_("Étape workflow ajoutée."), "success")
            return redirect(url_for("credit.approval_workflow"))

        if action == "delete_step":
            step_id = _to_int(request.form.get("step_id"))
            step = CreditApprovalWorkflowStep.query.filter_by(id=step_id, tenant_id=g.tenant.id).first() if step_id else None
            if not step:
                flash(_("Étape workflow invalide."), "warning")
                return redirect(url_for("credit.approval_workflow"))

            db.session.delete(step)
            db.session.commit()
            flash(_("Étape workflow supprimée."), "success")
            return redirect(url_for("credit.approval_workflow"))

        flash(_("Action workflow inconnue."), "warning")
        return redirect(url_for("credit.approval_workflow"))

    users = User.query.filter_by(tenant_id=g.tenant.id).order_by(User.email.asc()).all()
    groups = CreditAnalystGroup.query.filter_by(tenant_id=g.tenant.id).order_by(CreditAnalystGroup.name.asc()).all()
    functions = CreditAnalystFunction.query.filter_by(tenant_id=g.tenant.id).order_by(CreditAnalystFunction.label.asc()).all()
    steps = (
        CreditApprovalWorkflowStep.query.filter_by(tenant_id=g.tenant.id)
        .order_by(CreditApprovalWorkflowStep.step_order.asc(), CreditApprovalWorkflowStep.id.asc())
        .all()
    )
    return render_template(
        "credit/approval_workflow.html",
        tenant=g.tenant,
        users=users,
        groups=groups,
        functions=functions,
        steps=steps,
        stage_options=_approval_stage_options(),
    )


@bp.route("/approval-uam", methods=["GET", "POST"])
@login_required
def approval_uam():
    _require_tenant()
    if not _can_manage_credit_backoffice():
        flash(_("Backoffice role required to manage workflow."), "warning")
        return redirect(url_for("credit.approvals"))

    _seed_credit_references()

    if request.method == "POST":
        action = (request.form.get("action") or "").strip().lower()

        def _parse_ids(name: str) -> list[int]:
            out: list[int] = []
            for raw in request.form.getlist(name):
                try:
                    iv = int(raw)
                except Exception:
                    continue
                if iv > 0:
                    out.append(iv)
            return sorted(set(out))

        if action == "save_scope":
            target_type = (request.form.get("target_type") or "").strip().lower()
            target_id = _to_int(request.form.get("target_id"))
            if target_type not in {"user", "group"} or not target_id:
                flash(_("Invalid UAM target."), "warning")
                return redirect(url_for("credit.approval_uam"))

            if target_type == "user":
                row_exists = User.query.filter_by(id=target_id, tenant_id=g.tenant.id).first() is not None
            else:
                row_exists = CreditAnalystGroup.query.filter_by(id=target_id, tenant_id=g.tenant.id).first() is not None

            if not row_exists:
                flash(_("Invalid UAM target."), "warning")
                return redirect(url_for("credit.approval_uam"))

            _save_credit_assignment_scope(
                g.tenant,
                target_type,
                int(target_id),
                _parse_ids("sector_ids"),
                _parse_ids("country_ids"),
                _parse_ids("rating_ids"),
            )
            db.session.commit()
            flash(_("Credit UAM scope updated."), "success")
            return redirect(url_for("credit.approval_uam"))

        if action == "clone_scope":
            src_raw = str(request.form.get("source_ref") or "").strip().lower()
            dst_raw = str(request.form.get("target_ref") or "").strip().lower()

            def _parse_ref(raw: str) -> tuple[str, int] | None:
                if ":" not in raw:
                    return None
                t, rid = raw.split(":", 1)
                t = str(t or "").strip().lower()
                if t not in {"user", "group"}:
                    return None
                try:
                    iv = int(rid)
                except Exception:
                    return None
                if iv <= 0:
                    return None
                return t, iv

            src = _parse_ref(src_raw)
            dst = _parse_ref(dst_raw)
            if not src or not dst:
                flash(_("Invalid scope clone request."), "warning")
                return redirect(url_for("credit.approval_uam"))

            src_type, src_id = src
            dst_type, dst_id = dst
            if src_type == dst_type and src_id == dst_id:
                flash(_("Source and target must be different."), "warning")
                return redirect(url_for("credit.approval_uam"))

            src_scopes = _credit_assignment_scopes(g.tenant)
            src_scope = src_scopes.get("users", {}).get(str(src_id), {}) if src_type == "user" else src_scopes.get("groups", {}).get(str(src_id), {})
            if not isinstance(src_scope, dict) or not src_scope:
                flash(_("Source scope is empty."), "warning")
                return redirect(url_for("credit.approval_uam"))

            _save_credit_assignment_scope(
                g.tenant,
                dst_type,
                dst_id,
                [int(v) for v in (src_scope.get("sector_ids") or []) if int(v) > 0],
                [int(v) for v in (src_scope.get("country_ids") or []) if int(v) > 0],
                [int(v) for v in (src_scope.get("rating_ids") or []) if int(v) > 0],
            )
            db.session.commit()
            flash(_("Credit UAM scope cloned."), "success")
            return redirect(url_for("credit.approval_uam"))

        if action == "clear_scope":
            target_type = (request.form.get("target_type") or "").strip().lower()
            target_id = _to_int(request.form.get("target_id"))
            if target_type not in {"user", "group"} or not target_id:
                flash(_("Invalid UAM target."), "warning")
                return redirect(url_for("credit.approval_uam"))

            _clear_credit_assignment_scope(g.tenant, target_type, int(target_id))
            db.session.commit()
            flash(_("Credit UAM scope reset."), "success")
            return redirect(url_for("credit.approval_uam"))

        flash(_("Unknown UAM action."), "warning")
        return redirect(url_for("credit.approval_uam"))

    users = User.query.filter_by(tenant_id=g.tenant.id).order_by(User.email.asc()).all()
    groups = CreditAnalystGroup.query.filter_by(tenant_id=g.tenant.id).order_by(CreditAnalystGroup.name.asc()).all()
    countries = CreditCountry.query.order_by(CreditCountry.name.asc()).all()
    sectors = CreditSector.query.order_by(CreditSector.name.asc()).all()
    ratings = CreditRating.query.order_by(CreditRating.rank_order.asc()).all()
    assignment_scopes = _credit_assignment_scopes(g.tenant)
    group_by_id = {int(grp.id): grp for grp in groups}
    sector_by_id = {int(s.id): s.display_name(getattr(g, "lang", DEFAULT_LANG)) for s in sectors}
    country_by_id = {int(c.id): c.display_name(getattr(g, "lang", DEFAULT_LANG)) for c in countries}
    rating_by_id = {int(r.id): r.display_label(getattr(g, "lang", DEFAULT_LANG)) for r in ratings}

    def _title_from_ids(values: list[int], label_map: dict[int, str]) -> str:
        ids = [int(v) for v in (values or []) if int(v) > 0]
        if not ids:
            return _("All")
        names = [str(label_map.get(i) or i) for i in ids]
        return ", ".join(names)

    user_scope_titles: dict[str, dict[str, str]] = {}
    group_scope_titles: dict[str, dict[str, str]] = {}
    for u in users:
        scope = assignment_scopes.get("users", {}).get(str(int(u.id)), {})
        user_scope_titles[str(int(u.id))] = {
            "sectors": _title_from_ids(scope.get("sector_ids") if isinstance(scope, dict) else [], sector_by_id),
            "countries": _title_from_ids(scope.get("country_ids") if isinstance(scope, dict) else [], country_by_id),
            "ratings": _title_from_ids(scope.get("rating_ids") if isinstance(scope, dict) else [], rating_by_id),
        }
    for grp in groups:
        scope = assignment_scopes.get("groups", {}).get(str(int(grp.id)), {})
        group_scope_titles[str(int(grp.id))] = {
            "sectors": _title_from_ids(scope.get("sector_ids") if isinstance(scope, dict) else [], sector_by_id),
            "countries": _title_from_ids(scope.get("country_ids") if isinstance(scope, dict) else [], country_by_id),
            "ratings": _title_from_ids(scope.get("rating_ids") if isinstance(scope, dict) else [], rating_by_id),
        }

    effective_user_scopes: list[dict[str, object]] = []
    for usr in users:
        group_ids, function_codes_unused = _credit_user_group_scope(g.tenant.id, int(usr.id))
        direct_scope = assignment_scopes.get("users", {}).get(str(int(usr.id)), {})
        group_scope_rows = [
            assignment_scopes.get("groups", {}).get(str(int(gid)), {})
            for gid in group_ids
            if assignment_scopes.get("groups", {}).get(str(int(gid)), {})
        ]
        combined = []
        if isinstance(direct_scope, dict) and direct_scope:
            combined.append(direct_scope)
        combined.extend([row for row in group_scope_rows if isinstance(row, dict) and row])
        counts = _scope_counts_union(combined)
        eff_sector_names: set[str] = set()
        eff_country_names: set[str] = set()
        eff_rating_names: set[str] = set()
        for sc in combined:
            if not isinstance(sc, dict):
                continue
            for iv in [int(v) for v in (sc.get("sector_ids") or []) if int(v) > 0]:
                eff_sector_names.add(str(sector_by_id.get(iv) or iv))
            for iv in [int(v) for v in (sc.get("country_ids") or []) if int(v) > 0]:
                eff_country_names.add(str(country_by_id.get(iv) or iv))
            for iv in [int(v) for v in (sc.get("rating_ids") or []) if int(v) > 0]:
                eff_rating_names.add(str(rating_by_id.get(iv) or iv))

        effective_user_scopes.append(
            {
                "user": usr,
                "direct_scope": direct_scope if isinstance(direct_scope, dict) else {},
                "group_scope_count": len(group_scope_rows),
                "group_names": [str(group_by_id.get(int(gid)).name) for gid in group_ids if group_by_id.get(int(gid))],
                "effective_sector_count": int(counts.get("sector_count", 0)),
                "effective_country_count": int(counts.get("country_count", 0)),
                "effective_rating_count": int(counts.get("rating_count", 0)),
                "effective_sector_title": ", ".join(sorted(eff_sector_names)) if eff_sector_names else _("All"),
                "effective_country_title": ", ".join(sorted(eff_country_names)) if eff_country_names else _("All"),
                "effective_rating_title": ", ".join(sorted(eff_rating_names)) if eff_rating_names else _("All"),
            }
        )

    return render_template(
        "credit/approval_uam.html",
        tenant=g.tenant,
        users=users,
        groups=groups,
        countries=countries,
        sectors=sectors,
        ratings=ratings,
        assignment_scopes=assignment_scopes,
        user_scope_titles=user_scope_titles,
        group_scope_titles=group_scope_titles,
        effective_user_scopes=effective_user_scopes,
    )


@bp.route("/backlog", methods=["GET", "POST"])
@login_required
def backlog():
    _require_tenant()
    _seed_default_analyst_functions(g.tenant.id)
    _seed_default_approval_workflow(g.tenant.id)

    is_backoffice_admin = _can_manage_credit_backoffice()
    can_create_task = _can_create_credit_task()
    group_ids, function_codes = _credit_user_group_scope(g.tenant.id, current_user.id)

    def _redirect_backlog() -> object:
        scope_arg = (request.form.get("scope") or request.args.get("scope") or "my").strip().lower()
        status_arg = (request.form.get("status") or request.args.get("status") or "").strip().lower()
        borrower_arg = _to_int(request.form.get("borrower_id") or request.args.get("borrower_id"))
        params: dict[str, object] = {"mode": "search", "scope": scope_arg}
        if status_arg:
            params["status"] = status_arg
        if borrower_arg:
            params["borrower_id"] = borrower_arg
        return redirect(url_for("credit.backlog", **params))

    if request.method == "POST":
        action = (request.form.get("action") or "").strip()

        if action == "create_task":
            if not can_create_task:
                flash(_("You do not have permission to create backlog tasks."), "warning")
                return redirect(url_for("credit.backlog"))

            title = (request.form.get("title") or "").strip()
            if not title:
                flash(_("Task title is required."), "warning")
                return redirect(url_for("credit.backlog"))

            memo_id = _to_int(request.form.get("memo_id"))
            deal_id = _to_int(request.form.get("deal_id"))
            borrower_id = _to_int(request.form.get("borrower_id"))
            workflow_step_id = _to_int(request.form.get("workflow_step_id"))
            assigned_user_id = _to_int(request.form.get("assigned_user_id"))
            assigned_group_id = _to_int(request.form.get("assigned_group_id"))
            due_date = _parse_iso_date(request.form.get("due_date"))

            memo = CreditMemo.query.filter_by(id=memo_id, tenant_id=g.tenant.id).first() if memo_id else None
            deal = CreditDeal.query.filter_by(id=deal_id, tenant_id=g.tenant.id).first() if deal_id else None
            borrower = CreditBorrower.query.filter_by(id=borrower_id, tenant_id=g.tenant.id).first() if borrower_id else None
            workflow_step = (
                CreditApprovalWorkflowStep.query.filter_by(id=workflow_step_id, tenant_id=g.tenant.id).first()
                if workflow_step_id
                else None
            )
            assigned_user = User.query.filter_by(id=assigned_user_id, tenant_id=g.tenant.id).first() if assigned_user_id else None
            assigned_group = (
                CreditAnalystGroup.query.filter_by(id=assigned_group_id, tenant_id=g.tenant.id).first()
                if assigned_group_id
                else None
            )

            if memo_id and not memo:
                flash(_("Memo invalide."), "warning")
                return redirect(url_for("credit.backlog"))
            if deal_id and not deal:
                flash(_("Deal invalide."), "warning")
                return redirect(url_for("credit.backlog"))
            if borrower_id and not borrower:
                flash(_("Borrower invalide."), "warning")
                return redirect(url_for("credit.backlog"))
            if workflow_step_id and not workflow_step:
                flash(_("Workflow step invalide."), "warning")
                return redirect(url_for("credit.backlog"))
            if assigned_user_id and not assigned_user:
                flash(_("User invalide."), "warning")
                return redirect(url_for("credit.backlog"))
            if assigned_group_id and not assigned_group:
                flash(_("Groupe analyste invalide."), "warning")
                return redirect(url_for("credit.backlog"))

            task = CreditBacklogTask(
                tenant_id=g.tenant.id,
                memo_id=getattr(memo, "id", None),
                deal_id=getattr(deal, "id", None),
                borrower_id=getattr(borrower, "id", None),
                workflow_step_id=getattr(workflow_step, "id", None),
                title=title,
                description=(request.form.get("description") or "").strip() or None,
                status=(request.form.get("status") or "todo").strip() or "todo",
                priority=(request.form.get("priority") or "normal").strip() or "normal",
                due_date=due_date,
                assigned_user_id=getattr(assigned_user, "id", None),
                assigned_group_id=getattr(assigned_group, "id", None),
                created_by_user_id=current_user.id,
            )
            db.session.add(task)
            db.session.commit()
            flash(_("Backlog task created."), "success")
            return redirect(url_for("credit.backlog"))

        if action == "set_status":
            task_id = _to_int(request.form.get("task_id"))
            task = CreditBacklogTask.query.filter_by(id=task_id, tenant_id=g.tenant.id).first() if task_id else None
            if not task:
                flash(_("Task invalide."), "warning")
                return redirect(url_for("credit.backlog"))

            can_update = is_backoffice_admin
            if not can_update and task.assigned_user_id == current_user.id:
                can_update = True
            if not can_update and task.created_by_user_id == current_user.id:
                can_update = True
            if not can_update and task.assigned_group_id and task.assigned_group_id in group_ids:
                can_update = True
            if not can_update:
                flash(_("You do not have permission to update this task."), "warning")
                return redirect(url_for("credit.backlog"))

            next_status = (request.form.get("status") or "").strip().lower()
            if next_status not in {"todo", "in_progress", "done", "cancelled"}:
                flash(_("Invalid task status."), "warning")
                return redirect(url_for("credit.backlog"))

            task.status = next_status
            task.completed_at = datetime.utcnow() if next_status == "done" else None
            db.session.commit()
            flash(_("Task status updated."), "success")
            return redirect(url_for("credit.backlog"))

        if action == "approve_esign":
            approval_id = _to_int(request.form.get("approval_id"))
            approval = (
                CreditApproval.query.filter_by(id=approval_id, tenant_id=g.tenant.id, decision="pending").first()
                if approval_id
                else None
            )
            if not approval or not approval.memo:
                flash(_("Approval invalide."), "warning")
                return _redirect_backlog()

            signature_value = (request.form.get("signature_value") or "").strip().lower()
            expected_signature = str(getattr(current_user, "email", "") or "").strip().lower()
            if not signature_value or signature_value != expected_signature:
                flash(_("Invalid electronic signature. Please type your email to sign."), "warning")
                return _redirect_backlog()

            workflow_steps = _workflow_steps_ordered(g.tenant.id)
            expected_step, workflow_msg = _expected_workflow_step_for_memo(g.tenant.id, approval.memo_id, workflow_steps)
            if workflow_msg and expected_step is None:
                flash(workflow_msg, "warning")
                return _redirect_backlog()
            if expected_step and approval.workflow_step_id and expected_step.id != approval.workflow_step_id:
                flash(_("You are not the expected approver for the current workflow step."), "warning")
                return _redirect_backlog()

            workflow_step = approval.workflow_step
            if not workflow_step and approval.workflow_step_id:
                workflow_step = CreditApprovalWorkflowStep.query.filter_by(
                    id=approval.workflow_step_id,
                    tenant_id=g.tenant.id,
                ).first()

            borrower = approval.memo.borrower if approval.memo else None
            if not _user_can_sign_pending_approval(g.tenant, current_user.id, workflow_step, borrower):
                flash(_("You are not allowed to sign this approval based on workflow/UAM scope."), "warning")
                return _redirect_backlog()

            approval.decision = "approved"
            approval.actor_user_id = current_user.id
            approval.decided_at = datetime.utcnow()
            signed_line = _("E-signature by {email} on {date}", email=expected_signature, date=datetime.utcnow().strftime("%Y-%m-%d %H:%M"))
            approval.comments = f"{(approval.comments or '').strip()}\n{signed_line}".strip()

            open_tasks = (
                CreditBacklogTask.query.filter_by(
                    tenant_id=g.tenant.id,
                    memo_id=approval.memo_id,
                    workflow_step_id=approval.workflow_step_id,
                )
                .filter(CreditBacklogTask.status.in_(["todo", "in_progress"]))
                .all()
            )
            for task in open_tasks:
                task.status = "done"
                task.completed_at = datetime.utcnow()

            _sync_entity_approval_dates_for_memo(approval.memo, approval.decided_at)

            db.session.commit()
            flash(_("Approval signed and approved."), "success")
            return _redirect_backlog()

        flash(_("Unknown backlog action."), "warning")
        return redirect(url_for("credit.backlog"))

    scope = (request.args.get("scope") or "my").strip().lower()
    status_filter = (request.args.get("status") or "").strip().lower()
    selected_borrower_id = _to_int(request.args.get("borrower_id"))

    borrowers = CreditBorrower.query.filter_by(tenant_id=g.tenant.id).order_by(CreditBorrower.name.asc()).all()
    borrowers = [b for b in borrowers if _borrower_visible_for_user(g.tenant, current_user.id, b)]
    borrower_ids = {b.id for b in borrowers}
    if selected_borrower_id and selected_borrower_id not in borrower_ids:
        selected_borrower_id = None
        flash(_("Borrower invalide."), "warning")

    task_query = CreditBacklogTask.query.filter_by(tenant_id=g.tenant.id)
    if status_filter in {"todo", "in_progress", "done", "cancelled"}:
        task_query = task_query.filter(CreditBacklogTask.status == status_filter)
    if selected_borrower_id:
        task_query = task_query.filter(CreditBacklogTask.borrower_id == selected_borrower_id)

    own_scope_filter = or_(
        CreditBacklogTask.created_by_user_id == current_user.id,
        CreditBacklogTask.assigned_user_id == current_user.id,
        CreditBacklogTask.assigned_group_id.in_(group_ids) if group_ids else false(),
    )

    if is_backoffice_admin and scope == "all":
        pass
    elif is_backoffice_admin and scope == "open":
        task_query = task_query.filter(CreditBacklogTask.status.in_(["todo", "in_progress"]))
    else:
        task_query = task_query.filter(own_scope_filter)

    tasks = task_query.order_by(CreditBacklogTask.created_at.desc()).all()

    pending_approval_q = CreditApproval.query.filter_by(tenant_id=g.tenant.id, decision="pending")
    if selected_borrower_id:
        pending_approval_q = pending_approval_q.join(CreditMemo, CreditApproval.memo_id == CreditMemo.id).filter(
            CreditMemo.borrower_id == selected_borrower_id
        )
    strict_pending_approval_q = pending_approval_q
    if not (is_backoffice_admin or _has_credit_role("credit_approver")):
        strict_pending_approval_q = strict_pending_approval_q.filter(
            or_(
                CreditApproval.actor_user_id == current_user.id,
                CreditApproval.analyst_group_id.in_(group_ids) if group_ids else false(),
                CreditApproval.analyst_function.in_(function_codes) if function_codes else false(),
            )
        )
    pending_approvals_relaxed_scope = False
    pending_approvals = strict_pending_approval_q.order_by(CreditApproval.created_at.desc()).limit(120).all()
    pending_approvals = [a for a in pending_approvals if _borrower_visible_for_user(g.tenant, current_user.id, a.memo.borrower if a.memo else None)][:60]
    if not pending_approvals:
        relaxed_rows = pending_approval_q.order_by(CreditApproval.created_at.desc()).limit(120).all()
        relaxed_rows = [
            a
            for a in relaxed_rows
            if _borrower_visible_for_user(g.tenant, current_user.id, a.memo.borrower if a.memo else None)
        ][:60]
        if relaxed_rows:
            pending_approvals = relaxed_rows
            pending_approvals_relaxed_scope = True
    workflow_steps = _workflow_steps_ordered(g.tenant.id)

    can_esign_by_approval: dict[int, bool] = {}
    expected_step_name_by_approval: dict[int, str] = {}
    for approval in pending_approvals:
        memo = approval.memo
        if not memo:
            can_esign_by_approval[int(approval.id)] = False
            continue

        expected_step, _workflow_note = _expected_workflow_step_for_memo(g.tenant.id, memo.id, workflow_steps)
        expected_step_name_by_approval[int(approval.id)] = (
            expected_step.step_name if expected_step else _("No expected step")
        )
        same_step = bool(expected_step and approval.workflow_step_id and expected_step.id == approval.workflow_step_id)
        approval_step = approval.workflow_step
        if not approval_step and approval.workflow_step_id:
            approval_step = CreditApprovalWorkflowStep.query.filter_by(
                id=approval.workflow_step_id,
                tenant_id=g.tenant.id,
            ).first()
        can_sign = same_step and _user_can_sign_pending_approval(
            g.tenant,
            current_user.id,
            approval_step,
            memo.borrower if memo else None,
        )
        can_esign_by_approval[int(approval.id)] = bool(can_sign)

    users = User.query.filter_by(tenant_id=g.tenant.id).order_by(User.email.asc()).all()
    groups = CreditAnalystGroup.query.filter_by(tenant_id=g.tenant.id).order_by(CreditAnalystGroup.name.asc()).all()
    memos = CreditMemo.query.filter_by(tenant_id=g.tenant.id).order_by(CreditMemo.updated_at.desc()).all()
    memos = [m for m in memos if _borrower_visible_for_user(g.tenant, current_user.id, m.borrower)]
    deals = CreditDeal.query.filter_by(tenant_id=g.tenant.id).order_by(CreditDeal.updated_at.desc()).all()
    deals = [d for d in deals if _borrower_visible_for_user(g.tenant, current_user.id, d.borrower)]
    workflow_steps = (
        CreditApprovalWorkflowStep.query.filter_by(tenant_id=g.tenant.id)
        .order_by(CreditApprovalWorkflowStep.step_order.asc())
        .all()
    )

    return render_template(
        "credit/backlog.html",
        tenant=g.tenant,
        tasks=tasks,
        pending_approvals=pending_approvals,
        users=users,
        groups=groups,
        memos=memos,
        deals=deals,
        borrowers=borrowers,
        workflow_steps=workflow_steps,
        can_create_task=can_create_task,
        is_backoffice_admin=is_backoffice_admin,
        scope=scope,
        status_filter=status_filter,
        selected_borrower_id=selected_borrower_id,
        can_esign_by_approval=can_esign_by_approval,
        expected_step_name_by_approval=expected_step_name_by_approval,
        pending_approvals_relaxed_scope=pending_approvals_relaxed_scope,
    )


_CREDIT_DOCS_ROOT_NAME = "__credit_documents__"
_CREDIT_DOCS_STORAGE_PREFIX = "credit_docs"


def _credit_docs_safe_next_url() -> str | None:
    nxt = request.form.get("next") or request.args.get("next")
    if not nxt:
        return None
    nxt = str(nxt)
    if nxt.startswith("/") and "://" not in nxt and "\\" not in nxt:
        return nxt
    return None


def _credit_docs_redirect_back(default_endpoint: str = "credit.documents", **kwargs):
    nxt = _credit_docs_safe_next_url()
    if nxt:
        return redirect(nxt)
    return redirect(url_for(default_endpoint, **kwargs))


def _credit_docs_root_folder(tenant_id: int) -> FileFolder:
    root = FileFolder.query.filter_by(tenant_id=tenant_id, parent_id=None, name=_CREDIT_DOCS_ROOT_NAME).first()
    if root:
        return root

    root = FileFolder(tenant_id=tenant_id, parent_id=None, name=_CREDIT_DOCS_ROOT_NAME)
    db.session.add(root)
    db.session.commit()
    return root


def _credit_docs_descendant_ids(tenant_id: int, root_id: int) -> set[int]:
    out: set[int] = {root_id}
    stack = [root_id]
    while stack:
        fid = stack.pop()
        children = FileFolder.query.filter_by(tenant_id=tenant_id, parent_id=fid).all()
        for child in children:
            if child.id not in out:
                out.add(child.id)
                stack.append(child.id)
    return out


def _credit_docs_folder_rel_path(root_folder: FileFolder, folder: FileFolder | None) -> str:
    target = folder or root_folder
    chain: list[str] = []
    cur = target
    while cur is not None and cur.id != root_folder.id:
        chain.append(f"f_{cur.id}")
        cur = cur.parent

    if cur is None:
        return _CREDIT_DOCS_STORAGE_PREFIX

    chain.reverse()
    if chain:
        return _CREDIT_DOCS_STORAGE_PREFIX + "/" + "/".join(chain)
    return _CREDIT_DOCS_STORAGE_PREFIX


def _credit_docs_folder_or_none(tenant_id: int, root_folder: FileFolder, raw_folder_id) -> FileFolder | None:
    if raw_folder_id in (None, "", 0, "0"):
        return root_folder

    try:
        folder_id = int(raw_folder_id)
    except Exception:
        return None

    allowed = _credit_docs_descendant_ids(tenant_id, root_folder.id)
    if folder_id not in allowed:
        return None
    return FileFolder.query.filter_by(id=folder_id, tenant_id=tenant_id).first()


def _credit_docs_build_tree(tenant_id: int, root_folder: FileFolder) -> dict:
    allowed = _credit_docs_descendant_ids(tenant_id, root_folder.id)
    folders = FileFolder.query.filter(FileFolder.tenant_id == tenant_id, FileFolder.id.in_(allowed)).all()
    files = (
        FileAsset.query.filter(
            FileAsset.tenant_id == tenant_id,
            FileAsset.folder_id.in_(allowed),
            FileAsset.storage_path.like(f"{_CREDIT_DOCS_STORAGE_PREFIX}/%"),
        )
        .order_by(FileAsset.created_at.desc())
        .all()
    )

    f_by_id: dict[int, dict] = {}
    roots: list[dict] = []
    for folder in folders:
        if folder.id == root_folder.id:
            continue
        f_by_id[folder.id] = {"folder": folder, "children": [], "files": []}

    for folder in folders:
        if folder.id == root_folder.id:
            continue
        node = f_by_id[folder.id]
        if folder.parent_id == root_folder.id:
            roots.append(node)
        elif folder.parent_id in f_by_id:
            f_by_id[folder.parent_id]["children"].append(node)

    root_files: list[FileAsset] = []
    for asset in files:
        if asset.folder_id == root_folder.id:
            root_files.append(asset)
        elif asset.folder_id in f_by_id:
            f_by_id[asset.folder_id]["files"].append(asset)

    return {"roots": roots, "root_files": root_files, "allowed_folder_ids": allowed}


def _credit_docs_asset_or_404(file_id: int, tenant_id: int, allowed_folder_ids: set[int]) -> FileAsset:
    asset = FileAsset.query.filter_by(id=file_id, tenant_id=tenant_id).first_or_404()
    if asset.folder_id not in allowed_folder_ids:
        abort(404)
    if not str(asset.storage_path or "").startswith(f"{_CREDIT_DOCS_STORAGE_PREFIX}/"):
        abort(404)
    return asset


def _credit_docs_folder_or_404(folder_id: int, tenant_id: int, root_folder: FileFolder) -> FileFolder:
    folder = FileFolder.query.filter_by(id=folder_id, tenant_id=tenant_id).first_or_404()
    allowed = _credit_docs_descendant_ids(tenant_id, root_folder.id)
    if folder.id not in allowed:
        abort(404)
    return folder


def _credit_docs_create_row_from_asset(asset: FileAsset) -> None:
    borrower_id = _to_int(request.form.get("borrower_id"))
    deal_id = _to_int(request.form.get("deal_id"))
    memo_id = _to_int(request.form.get("memo_id"))

    borrower = CreditBorrower.query.filter_by(id=borrower_id, tenant_id=asset.tenant_id).first() if borrower_id else None
    deal = CreditDeal.query.filter_by(id=deal_id, tenant_id=asset.tenant_id).first() if deal_id else None
    memo = CreditMemo.query.filter_by(id=memo_id, tenant_id=asset.tenant_id).first() if memo_id else None

    title = (request.form.get("display_name") or "").strip() or asset.name or (asset.original_filename or "")
    row = CreditDocument(
        tenant_id=asset.tenant_id,
        borrower_id=borrower.id if borrower else None,
        deal_id=deal.id if deal else None,
        memo_id=memo.id if memo else None,
        title=title or _("Document"),
        doc_type=(request.form.get("doc_type") or "supporting").strip(),
        file_path=asset.storage_path,
        uploaded_by_user_id=getattr(current_user, "id", None),
    )
    db.session.add(row)


@bp.route("/documents", methods=["GET", "POST"])
@login_required
def documents():
    _require_tenant()
    root_folder = _credit_docs_root_folder(g.tenant.id)

    borrowers = CreditBorrower.query.filter_by(tenant_id=g.tenant.id).order_by(CreditBorrower.name.asc()).all()
    deals = CreditDeal.query.filter_by(tenant_id=g.tenant.id).order_by(CreditDeal.code.asc()).all()
    memos = CreditMemo.query.filter_by(tenant_id=g.tenant.id).order_by(CreditMemo.updated_at.desc()).all()

    # Backward-compatible manual metadata insert.
    if request.method == "POST":
        row = CreditDocument(
            tenant_id=g.tenant.id,
            borrower_id=_to_int(request.form.get("borrower_id")),
            deal_id=_to_int(request.form.get("deal_id")),
            memo_id=_to_int(request.form.get("memo_id")),
            title=(request.form.get("title") or "").strip(),
            doc_type=(request.form.get("doc_type") or "supporting").strip(),
            file_path=(request.form.get("file_path") or "").strip() or None,
            uploaded_by_user_id=getattr(current_user, "id", None),
        )
        if not row.title:
            flash(_("Titre document requis."), "warning")
            return _credit_docs_redirect_back()
        db.session.add(row)
        db.session.commit()
        flash(_("Document ajouté."), "success")
        return _credit_docs_redirect_back()

    tree_data = _credit_docs_build_tree(g.tenant.id, root_folder)
    current_folder = _credit_docs_folder_or_none(g.tenant.id, root_folder, request.args.get("folder"))
    if not current_folder:
        flash(_("Pasta inválida."), "warning")
        current_folder = root_folder

    child_folders = (
        FileFolder.query.filter_by(tenant_id=g.tenant.id, parent_id=current_folder.id)
        .order_by(FileFolder.name.asc())
        .all()
    )
    child_files = (
        FileAsset.query.filter(
            FileAsset.tenant_id == g.tenant.id,
            FileAsset.folder_id == current_folder.id,
            FileAsset.storage_path.like(f"{_CREDIT_DOCS_STORAGE_PREFIX}/%"),
        )
        .order_by(FileAsset.created_at.desc())
        .all()
    )

    breadcrumb: list[FileFolder] = []
    breadcrumb_ids: list[int] = []
    cur = current_folder
    while cur is not None and cur.id != root_folder.id:
        breadcrumb.append(cur)
        breadcrumb_ids.append(cur.id)
        cur = cur.parent
    breadcrumb.reverse()
    breadcrumb_ids.reverse()

    folders = (
        FileFolder.query.filter(
            FileFolder.tenant_id == g.tenant.id,
            FileFolder.id.in_(tree_data["allowed_folder_ids"]),
            FileFolder.id != root_folder.id,
        )
        .order_by(FileFolder.name.asc())
        .all()
    )

    rows = CreditDocument.query.filter_by(tenant_id=g.tenant.id).order_by(CreditDocument.created_at.desc()).limit(50).all()
    return render_template(
        "credit/documents.html",
        tenant=g.tenant,
        tree={"roots": tree_data["roots"]},
        folders=folders,
        current_folder=(None if current_folder.id == root_folder.id else current_folder),
        child_folders=child_folders,
        child_files=child_files,
        breadcrumb=breadcrumb,
        breadcrumb_ids=set(breadcrumb_ids),
        borrowers=borrowers,
        deals=deals,
        memos=memos,
        documents=rows,
    )


@bp.route("/documents/folders", methods=["POST"])
@login_required
def documents_create_folder():
    _require_tenant()
    root_folder = _credit_docs_root_folder(g.tenant.id)

    name = (request.form.get("name") or "").strip()
    if not name:
        flash(_("Nome da pasta é obrigatório."), "warning")
        return _credit_docs_redirect_back()

    parent = _credit_docs_folder_or_none(g.tenant.id, root_folder, request.form.get("parent_id"))
    if not parent:
        flash(_("Pasta inválida."), "warning")
        return _credit_docs_redirect_back()

    folder = FileFolder(tenant_id=g.tenant.id, name=name, parent_id=parent.id)
    db.session.add(folder)
    db.session.commit()

    import os
    from ...services.file_storage_service import ensure_tenant_root

    base = ensure_tenant_root(g.tenant.id)
    rel = _credit_docs_folder_rel_path(root_folder, folder)
    os.makedirs(os.path.join(base, rel), exist_ok=True)

    flash(_("Pasta criada."), "success")
    return _credit_docs_redirect_back(folder=("" if parent.id == root_folder.id else parent.id))


@bp.route("/documents/upload", methods=["POST"])
@login_required
def documents_upload():
    _require_tenant()
    root_folder = _credit_docs_root_folder(g.tenant.id)

    f = request.files.get("file")
    display_name = (request.form.get("display_name") or "").strip()
    folder = _credit_docs_folder_or_none(g.tenant.id, root_folder, request.form.get("folder_id"))
    if not folder:
        flash(_("Pasta inválida."), "warning")
        return _credit_docs_redirect_back()
    if not f:
        flash(_("Nenhum arquivo enviado."), "warning")
        return _credit_docs_redirect_back(folder=("" if folder.id == root_folder.id else folder.id))

    from ...services.file_storage_service import store_upload
    from ...services.file_introspect_service import infer_schema_for_asset

    folder_rel = _credit_docs_folder_rel_path(root_folder, folder)
    stored = store_upload(g.tenant.id, f, folder_rel=folder_rel)

    asset = FileAsset(
        tenant_id=g.tenant.id,
        folder_id=folder.id,
        name=display_name or stored.get("original_filename") or "document",
        source_type="upload",
        storage_path=stored["storage_path"],
        file_format=stored["file_format"],
        original_filename=stored.get("original_filename"),
        size_bytes=stored.get("size_bytes"),
        sha256=stored.get("sha256"),
    )
    asset.schema_json = infer_schema_for_asset(asset)
    db.session.add(asset)
    db.session.flush()
    _credit_docs_create_row_from_asset(asset)
    db.session.commit()

    flash(_("Document ajouté."), "success")
    return _credit_docs_redirect_back(folder=("" if folder.id == root_folder.id else folder.id))


@bp.route("/documents/from_url", methods=["POST"])
@login_required
def documents_from_url():
    _require_tenant()
    root_folder = _credit_docs_root_folder(g.tenant.id)

    url = (request.form.get("url") or "").strip()
    if not url:
        flash(_("URL é obrigatória."), "warning")
        return _credit_docs_redirect_back()

    filename = (request.form.get("filename") or "").strip()
    display_name = (request.form.get("display_name") or "").strip()
    folder = _credit_docs_folder_or_none(g.tenant.id, root_folder, request.form.get("folder_id"))
    if not folder:
        flash(_("Pasta inválida."), "warning")
        return _credit_docs_redirect_back()

    from ...services.file_storage_service import download_from_url
    from ...services.file_introspect_service import infer_schema_for_asset

    folder_rel = _credit_docs_folder_rel_path(root_folder, folder)
    stored = download_from_url(g.tenant.id, url, filename_hint=filename, folder_rel=folder_rel)

    asset = FileAsset(
        tenant_id=g.tenant.id,
        folder_id=folder.id,
        name=display_name or stored.get("original_filename") or filename or "document",
        source_type="url",
        storage_path=stored["storage_path"],
        file_format=stored["file_format"],
        original_filename=stored.get("original_filename"),
        size_bytes=stored.get("size_bytes"),
        sha256=stored.get("sha256"),
    )
    asset.schema_json = infer_schema_for_asset(asset)
    db.session.add(asset)
    db.session.flush()
    _credit_docs_create_row_from_asset(asset)
    db.session.commit()

    flash(_("Document ajouté."), "success")
    return _credit_docs_redirect_back(folder=("" if folder.id == root_folder.id else folder.id))


@bp.route("/documents/from_s3", methods=["POST"])
@login_required
def documents_from_s3():
    _require_tenant()
    root_folder = _credit_docs_root_folder(g.tenant.id)

    bucket = (request.form.get("bucket") or "").strip()
    key = (request.form.get("key") or "").strip()
    if not bucket or not key:
        flash(_("Bucket e key são obrigatórios."), "warning")
        return _credit_docs_redirect_back()

    filename = (request.form.get("filename") or "").strip()
    region = (request.form.get("region") or "").strip() or None
    access_key_id = (request.form.get("access_key_id") or "").strip() or None
    secret_access_key = (request.form.get("secret_access_key") or "").strip() or None
    session_token = (request.form.get("session_token") or "").strip() or None
    display_name = (request.form.get("display_name") or "").strip()

    folder = _credit_docs_folder_or_none(g.tenant.id, root_folder, request.form.get("folder_id"))
    if not folder:
        flash(_("Pasta inválida."), "warning")
        return _credit_docs_redirect_back()

    from ...services.file_storage_service import download_from_s3
    from ...services.file_introspect_service import infer_schema_for_asset

    folder_rel = _credit_docs_folder_rel_path(root_folder, folder)
    stored = download_from_s3(
        g.tenant.id,
        bucket=bucket,
        key=key,
        filename_hint=filename,
        region=region,
        folder_rel=folder_rel,
        access_key_id=access_key_id,
        secret_access_key=secret_access_key,
        session_token=session_token,
    )

    asset = FileAsset(
        tenant_id=g.tenant.id,
        folder_id=folder.id,
        name=display_name or stored.get("original_filename") or filename or key.split("/")[-1] or "document",
        source_type="s3",
        storage_path=stored["storage_path"],
        file_format=stored["file_format"],
        original_filename=stored.get("original_filename"),
        size_bytes=stored.get("size_bytes"),
        sha256=stored.get("sha256"),
    )
    asset.schema_json = infer_schema_for_asset(asset)
    db.session.add(asset)
    db.session.flush()
    _credit_docs_create_row_from_asset(asset)
    db.session.commit()

    flash(_("Document ajouté."), "success")
    return _credit_docs_redirect_back(folder=("" if folder.id == root_folder.id else folder.id))


@bp.route("/documents/files/<int:file_id>/download", methods=["GET"])
@login_required
def documents_download(file_id: int):
    _require_tenant()
    root_folder = _credit_docs_root_folder(g.tenant.id)
    allowed = _credit_docs_descendant_ids(g.tenant.id, root_folder.id)
    asset = _credit_docs_asset_or_404(file_id, g.tenant.id, allowed)

    from ...services.file_storage_service import resolve_abs_path

    abs_path = resolve_abs_path(g.tenant.id, asset.storage_path)
    return send_file(abs_path, as_attachment=True, download_name=asset.original_filename or asset.name)


@bp.route("/documents/files/<int:file_id>/delete", methods=["POST"])
@login_required
def documents_delete(file_id: int):
    _require_tenant()
    root_folder = _credit_docs_root_folder(g.tenant.id)
    allowed = _credit_docs_descendant_ids(g.tenant.id, root_folder.id)
    asset = _credit_docs_asset_or_404(file_id, g.tenant.id, allowed)

    from ...services.file_storage_service import delete_storage_path

    try:
        delete_storage_path(g.tenant.id, asset.storage_path)
    except Exception:
        pass
    CreditDocument.query.filter_by(tenant_id=g.tenant.id, file_path=asset.storage_path).delete(synchronize_session=False)
    db.session.delete(asset)
    db.session.commit()

    flash(_("Arquivo removido."), "success")
    return _credit_docs_redirect_back()


@bp.route("/documents/folders/<int:folder_id>/delete", methods=["POST"])
@login_required
def documents_folders_delete(folder_id: int):
    _require_tenant()
    root_folder = _credit_docs_root_folder(g.tenant.id)
    folder = _credit_docs_folder_or_404(folder_id, g.tenant.id, root_folder)
    if folder.id == root_folder.id:
        flash(_("Movimento inválido."), "warning")
        return _credit_docs_redirect_back()

    folder_rel = _credit_docs_folder_rel_path(root_folder, folder)
    descendants = _credit_docs_descendant_ids(g.tenant.id, folder.id)

    from ...services.file_storage_service import delete_storage_path, delete_folder_tree

    assets = FileAsset.query.filter(
        FileAsset.tenant_id == g.tenant.id,
        FileAsset.folder_id.in_(descendants),
        FileAsset.storage_path.like(f"{_CREDIT_DOCS_STORAGE_PREFIX}/%"),
    ).all()
    for asset in assets:
        try:
            delete_storage_path(g.tenant.id, asset.storage_path)
        except Exception:
            pass
        CreditDocument.query.filter_by(tenant_id=g.tenant.id, file_path=asset.storage_path).delete(synchronize_session=False)
        db.session.delete(asset)

    for sub in FileFolder.query.filter(
        FileFolder.tenant_id == g.tenant.id,
        FileFolder.id.in_(descendants),
        FileFolder.id != folder.id,
    ).all():
        db.session.delete(sub)
    db.session.delete(folder)
    db.session.commit()

    try:
        delete_folder_tree(g.tenant.id, folder_rel)
    except Exception:
        pass

    flash(_("Pasta removida."), "success")
    return _credit_docs_redirect_back()


@bp.route("/documents/files/<int:file_id>/rename", methods=["POST"])
@login_required
def documents_rename(file_id: int):
    _require_tenant()
    root_folder = _credit_docs_root_folder(g.tenant.id)
    allowed = _credit_docs_descendant_ids(g.tenant.id, root_folder.id)
    asset = _credit_docs_asset_or_404(file_id, g.tenant.id, allowed)

    payload = request.json if request.is_json else request.form
    name = str((payload or {}).get("name") or "").strip()
    if not name:
        msg = _("Nome é obrigatório.")
        if request.is_json:
            return jsonify({"ok": False, "error": msg}), 400
        flash(msg, "warning")
        return _credit_docs_redirect_back()

    asset.name = name
    db.session.commit()
    if request.is_json:
        return jsonify({"ok": True})
    flash(_("Arquivo renomeado."), "success")
    return _credit_docs_redirect_back()


@bp.route("/documents/folders/<int:folder_id>/rename", methods=["POST"])
@login_required
def documents_folders_rename(folder_id: int):
    _require_tenant()
    root_folder = _credit_docs_root_folder(g.tenant.id)
    folder = _credit_docs_folder_or_404(folder_id, g.tenant.id, root_folder)
    if folder.id == root_folder.id:
        msg = _("Movimento inválido.")
        if request.is_json:
            return jsonify({"ok": False, "error": msg}), 400
        flash(msg, "warning")
        return _credit_docs_redirect_back()

    payload = request.json if request.is_json else request.form
    name = str((payload or {}).get("name") or "").strip()
    if not name:
        msg = _("Nome é obrigatório.")
        if request.is_json:
            return jsonify({"ok": False, "error": msg}), 400
        flash(msg, "warning")
        return _credit_docs_redirect_back()

    folder.name = name
    db.session.commit()
    if request.is_json:
        return jsonify({"ok": True})
    flash(_("Pasta renomeada."), "success")
    return _credit_docs_redirect_back(folder=folder.id)


@bp.route("/documents/files/<int:file_id>/move", methods=["POST"])
@login_required
def documents_move(file_id: int):
    _require_tenant()
    root_folder = _credit_docs_root_folder(g.tenant.id)
    allowed = _credit_docs_descendant_ids(g.tenant.id, root_folder.id)
    asset = _credit_docs_asset_or_404(file_id, g.tenant.id, allowed)

    payload = request.json if request.is_json else request.form
    new_folder = _credit_docs_folder_or_none(g.tenant.id, root_folder, (payload or {}).get("folder_id"))
    if not new_folder:
        msg = _("Pasta inválida.")
        if request.is_json:
            return jsonify({"ok": False, "error": msg}), 400
        flash(msg, "warning")
        return _credit_docs_redirect_back()

    import os
    import shutil
    from ...services.file_storage_service import ensure_tenant_root

    old_rel = asset.storage_path
    old_abs = os.path.join(ensure_tenant_root(g.tenant.id), old_rel)
    filename = os.path.basename(old_rel)
    new_dir_rel = _credit_docs_folder_rel_path(root_folder, new_folder)
    new_rel = f"{new_dir_rel}/{filename}" if new_dir_rel else filename
    new_abs = os.path.join(ensure_tenant_root(g.tenant.id), new_rel)
    os.makedirs(os.path.dirname(new_abs), exist_ok=True)

    try:
        if os.path.exists(old_abs):
            shutil.move(old_abs, new_abs)
    except Exception:
        pass

    asset.folder_id = new_folder.id
    asset.storage_path = new_rel
    for row in CreditDocument.query.filter_by(tenant_id=g.tenant.id, file_path=old_rel).all():
        row.file_path = new_rel
    db.session.commit()

    if request.is_json:
        return jsonify({"ok": True})
    flash(_("Arquivo movido."), "success")
    return _credit_docs_redirect_back(folder=("" if new_folder.id == root_folder.id else new_folder.id))


@bp.route("/documents/folders/<int:folder_id>/move", methods=["POST"])
@login_required
def documents_folders_move(folder_id: int):
    _require_tenant()
    root_folder = _credit_docs_root_folder(g.tenant.id)
    folder = _credit_docs_folder_or_404(folder_id, g.tenant.id, root_folder)
    if folder.id == root_folder.id:
        msg = _("Movimento inválido.")
        if request.is_json:
            return jsonify({"ok": False, "error": msg}), 400
        flash(msg, "warning")
        return _credit_docs_redirect_back()

    payload = request.json if request.is_json else request.form
    raw_parent = (payload or {}).get("parent_id")
    new_parent = _credit_docs_folder_or_none(g.tenant.id, root_folder, raw_parent)
    if not new_parent:
        msg = _("Pasta inválida.")
        if request.is_json:
            return jsonify({"ok": False, "error": msg}), 400
        flash(msg, "warning")
        return _credit_docs_redirect_back(folder=folder.id)

    bad = _credit_docs_descendant_ids(g.tenant.id, folder.id)
    bad.add(folder.id)
    if new_parent.id in bad:
        msg = _("Movimento inválido.")
        if request.is_json:
            return jsonify({"ok": False, "error": msg}), 400
        flash(msg, "warning")
        return _credit_docs_redirect_back(folder=folder.id)

    import os
    import shutil
    from ...services.file_storage_service import ensure_tenant_root

    old_rel = _credit_docs_folder_rel_path(root_folder, folder)
    folder.parent_id = new_parent.id
    folder.parent = new_parent
    db.session.flush()
    new_rel = _credit_docs_folder_rel_path(root_folder, folder)

    tenant_root = ensure_tenant_root(g.tenant.id)
    old_abs = os.path.join(tenant_root, old_rel)
    new_abs = os.path.join(tenant_root, new_rel)
    os.makedirs(os.path.dirname(new_abs), exist_ok=True)
    try:
        if os.path.isdir(old_abs):
            shutil.move(old_abs, new_abs)
        else:
            os.makedirs(new_abs, exist_ok=True)
    except Exception:
        os.makedirs(new_abs, exist_ok=True)

    prefix = old_rel + "/"
    assets = FileAsset.query.filter(
        FileAsset.tenant_id == g.tenant.id,
        FileAsset.storage_path.like(prefix + "%"),
        FileAsset.folder_id.in_(_credit_docs_descendant_ids(g.tenant.id, folder.id)),
    ).all()
    for asset in assets:
        old_path = asset.storage_path
        asset.storage_path = new_rel + asset.storage_path[len(old_rel):]
        for row in CreditDocument.query.filter_by(tenant_id=g.tenant.id, file_path=old_path).all():
            row.file_path = asset.storage_path

    db.session.commit()

    if request.is_json:
        return jsonify({"ok": True})
    flash(_("Pasta movida."), "success")
    return _credit_docs_redirect_back(folder=folder.id)


def _standard_reports(tenant_id: int, filters: dict | None = None) -> dict:
    active_filters = filters or _credit_filters_from_request()
    where = _credit_filter_predicates(tenant_id, active_filters)
    deal_where = where["deal"]
    approval_where = where["approval"]
    ratio_where = where["ratio"]

    pipeline_rows = (
        db.session.query(
            CreditDeal.status.label("status"),
            func.count(CreditDeal.id).label("deal_count"),
            func.coalesce(func.sum(CreditDeal.requested_amount), 0).label("amount"),
        )
        .filter(*deal_where)
        .group_by(CreditDeal.status)
        .order_by(CreditDeal.status.asc())
        .all()
    )

    top_exposures = (
        db.session.query(
            CreditDeal.code.label("deal_code"),
            CreditBorrower.name.label("borrower"),
            CreditDeal.requested_amount.label("requested_amount"),
            CreditDeal.status.label("status"),
        )
        .join(CreditBorrower, CreditBorrower.id == CreditDeal.borrower_id)
        .filter(*deal_where)
        .order_by(CreditDeal.requested_amount.desc())
        .limit(20)
        .all()
    )

    approval_queue = (
        db.session.query(
            CreditMemo.title.label("memo"),
            CreditApproval.stage.label("stage"),
            CreditApproval.decision.label("decision"),
            CreditApproval.created_at.label("created_at"),
        )
        .join(CreditMemo, CreditMemo.id == CreditApproval.memo_id)
        .filter(*approval_where)
        .order_by(CreditApproval.created_at.desc())
        .limit(30)
        .all()
    )

    collateral_rows = []
    deals = CreditDeal.query.filter(*deal_where).all()
    for deal in deals:
        collaterals = CreditCollateral.query.filter_by(tenant_id=tenant_id, deal_id=deal.id).all()
        net_collateral = Decimal("0")
        for c in collaterals:
            mv = Decimal(c.market_value or 0)
            haircut = Decimal(c.haircut_pct or 0)
            net_collateral += mv * (Decimal("1") - (haircut / Decimal("100")))
        requested = Decimal(deal.requested_amount or 0)
        coverage = (net_collateral / requested) if requested else Decimal("0")
        collateral_rows.append(
            {
                "deal_code": deal.code,
                "requested_amount": float(requested),
                "net_collateral": float(net_collateral),
                "coverage": float(coverage),
            }
        )

    ratio_watchlist = []
    latest_by_borrower: dict[int, CreditRatioSnapshot] = {}
    for snap in CreditRatioSnapshot.query.filter(*ratio_where).order_by(CreditRatioSnapshot.created_at.desc()).all():
        if snap.borrower_id not in latest_by_borrower:
            latest_by_borrower[snap.borrower_id] = snap
    for borrower_id, snap in latest_by_borrower.items():
        dscr = Decimal(snap.dscr or 0)
        leverage = Decimal(snap.leverage or 0)
        if dscr < Decimal("1.10") or leverage > Decimal("3.50"):
            borrower = CreditBorrower.query.filter_by(id=borrower_id, tenant_id=tenant_id).first()
            ratio_watchlist.append(
                {
                    "borrower": borrower.name if borrower else str(borrower_id),
                    "dscr": float(dscr),
                    "leverage": float(leverage),
                    "liquidity": float(Decimal(snap.liquidity or 0)),
                    "risk_grade": snap.risk_grade or "",
                }
            )

    approval_decision_rows = (
        db.session.query(CreditApproval.decision, func.count(CreditApproval.id))
        .filter(*approval_where)
        .group_by(CreditApproval.decision)
        .order_by(CreditApproval.decision.asc())
        .all()
    )

    pipeline_data = [
        {"status": r.status or "", "deal_count": int(r.deal_count or 0), "amount": float(r.amount or 0)}
        for r in pipeline_rows
    ]
    exposures_data = [
        {
            "deal_code": r.deal_code,
            "borrower": r.borrower,
            "requested_amount": float(r.requested_amount or 0),
            "status": r.status,
        }
        for r in top_exposures
    ]

    return {
        "pipeline": [
            row for row in pipeline_data
        ],
        "exposures": [
            row for row in exposures_data
        ],
        "approvals": [
            {
                "memo": r.memo,
                "stage": r.stage,
                "decision": r.decision,
                "created_at": r.created_at.isoformat() if r.created_at else "",
            }
            for r in approval_queue
        ],
        "collateral_coverage": collateral_rows,
        "risk_watchlist": ratio_watchlist,
        "charts": {
            "pipeline": {
                "labels": [row["status"] for row in pipeline_data],
                "amounts": [row["amount"] for row in pipeline_data],
                "counts": [row["deal_count"] for row in pipeline_data],
            },
            "approval_decisions": {
                "labels": [str(row[0] or "unknown") for row in approval_decision_rows],
                "counts": [int(row[1] or 0) for row in approval_decision_rows],
            },
            "top_exposures": {
                "labels": [row["deal_code"] for row in exposures_data[:8]],
                "amounts": [row["requested_amount"] for row in exposures_data[:8]],
            },
        },
    }


@bp.route("/reports")
@login_required
def reports():
    _require_tenant()
    filters = _credit_filters_from_request()
    filter_options = _credit_filter_options(g.tenant.id)
    filter_labels = _credit_filter_label_maps(filter_options)
    active_filter_tags = _credit_active_filter_tags(filters, filter_options, filter_labels)
    reports_data = _standard_reports(g.tenant.id, filters=filters)
    filter_query_string = _credit_filters_query_string(filters)
    return render_template(
        "credit/reports.html",
        tenant=g.tenant,
        reports=reports_data,
        filters=filters,
        filter_options=filter_options,
        filter_labels=filter_labels,
        active_filter_tags=active_filter_tags,
        filter_query_string=filter_query_string,
    )


@bp.route("/reports/<string:slug>.csv")
@login_required
def reports_csv(slug: str):
    _require_tenant()
    filters = _credit_filters_from_request()
    reports_data = _standard_reports(g.tenant.id, filters=filters)
    rows = reports_data.get(slug)
    if not isinstance(rows, list):
        abort(404)

    buffer = io.StringIO()
    if rows:
        headers = list(rows[0].keys())
    else:
        headers = ["empty"]
    writer = csv.DictWriter(buffer, fieldnames=headers)
    writer.writeheader()
    for row in rows:
        writer.writerow(row)

    response = make_response(buffer.getvalue())
    response.headers["Content-Type"] = "text/csv; charset=utf-8"
    response.headers["Content-Disposition"] = f"attachment; filename=credit_report_{slug}.csv"
    return response
