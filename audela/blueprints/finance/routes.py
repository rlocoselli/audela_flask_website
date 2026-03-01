from __future__ import annotations

import logging
import time
import uuid
import os
import random
import csv
from collections import defaultdict
from datetime import date, datetime, timedelta
from io import BytesIO
from decimal import Decimal
import requests
from pathlib import Path

from flask import abort, flash, g, redirect, render_template, request, session, url_for, current_app, jsonify, send_file
from flask_login import current_user, login_required
from werkzeug.utils import secure_filename
from sqlalchemy.orm import joinedload
from sqlalchemy import func, or_
from sqlalchemy.exc import SQLAlchemyError

from ...extensions import db
from ...i18n import DEFAULT_LANG, tr
from ...models.core import Tenant
from ...models.finance import FinanceAccount, FinanceCompany, FinanceTransaction
from ...models.finance_ref import FinanceCurrency, FinanceCounterparty, FinanceStatementImport
from ...models.finance_invoices import FinanceInvoice, FinanceInvoiceLine, FinanceSetting
from ...models.finance_ext import (
    FinanceBankAccountLink,
    FinanceBankConnection,
    FinanceCategory,
    FinanceCategoryRule,
    FinanceGLAccount,
    FinanceLedgerVoucher,
    FinanceLedgerLine,
    FinanceAccountingPeriod,
    FinanceLiability,
    FinanceInvestment,
    FinanceRecurringTransaction,
    FinanceProduct,
)
from ...security import require_roles
from ...services.bank_bridge import BridgeClient, BridgeError
from ...services.bank_statement import import_bank_statement, StatementImportError
from ...services.openai_statement import parse_bank_statement_pdf_via_openai, OpenAIStatementError
from ...services.openai_quick_entry import parse_quick_entry_text_via_openai, OpenAIQuickEntryError
from ...services.finance_service import (
    compute_basic_risk,
    compute_risk_metrics,
    compute_cashflow,
    compute_opening_balance,
    compute_interest_rate_gaps,
    compute_liquidity,
    compute_nii,
    compute_starting_cash,
    parse_transactions_csv,
    parse_transactions_csv_mapped,
    normalize_counterparty_label,
    # Legacy: kept for compatibility, but PDF imports now use audela.services.bank_statement
    parse_bank_statement_pdf_local,
    parse_bank_statement_pdf_via_api,
)

from ...services.einvoice_service import build_invoice_export_zip, compute_totals
from ...services.einvoice_service import build_invoice_pdf_bytes
from ...services.finance_projection import project_cash_balance, build_ui_alerts
from ...services.regulation_exports import export_fec_csv, export_it_ledger_csv
from ...services.einvoice_service import build_invoice_export_zip, compute_totals
from ...services.finance_projection import project_cash_balance, build_ui_alerts, compute_starting_cash as proj_starting_cash
from ...services.regulation_exports import export_fec_csv, export_it_ledger_csv
from ...services.email_service import EmailService
from ...services.subscription_service import SubscriptionService
from ...tenancy import get_current_tenant_id, get_user_module_access, get_user_menu_access

from . import bp


finance_logger = logging.getLogger("audela.finance")
_INVEST_LOOKUP_CACHE: dict[str, tuple[float, list[dict]]] = {}
_INVEST_LOOKUP_CACHE_TTL_S = int(os.environ.get("INVEST_LOOKUP_CACHE_TTL_S", "60"))
_INVEST_HISTORY_CACHE: dict[str, tuple[float, list[dict]]] = {}
_INVEST_HISTORY_CACHE_TTL_S = int(os.environ.get("INVEST_HISTORY_CACHE_TTL_S", "300"))


def _finance_context() -> dict:
    return {
        "tenant_id": getattr(getattr(g, "tenant", None), "id", None),
        "user_id": getattr(current_user, "id", None) if getattr(current_user, "is_authenticated", False) else None,
        "endpoint": request.endpoint,
        "path": request.path,
        "method": request.method,
        "request_id": getattr(g, "finance_request_id", None),
    }


@bp.before_app_request
def _finance_log_request_start() -> None:
    if not (request.endpoint and request.endpoint.startswith("finance.")):
        return
    g.finance_request_started = time.perf_counter()
    g.finance_request_id = request.headers.get("X-Request-Id") or uuid.uuid4().hex[:12]
    ctx = _finance_context()
    finance_logger.info(
        "event=finance.request.start request_id=%s tenant_id=%s user_id=%s endpoint=%s method=%s path=%s",
        ctx["request_id"],
        ctx["tenant_id"],
        ctx["user_id"],
        ctx["endpoint"],
        ctx["method"],
        ctx["path"],
    )


@bp.after_app_request
def _finance_log_request_end(response):
    if not (request.endpoint and request.endpoint.startswith("finance.")):
        return response
    started = getattr(g, "finance_request_started", None)
    duration_ms = ((time.perf_counter() - started) * 1000.0) if started is not None else 0.0
    ctx = _finance_context()
    msg = (
        "event=finance.request.end request_id=%s tenant_id=%s user_id=%s endpoint=%s method=%s "
        "path=%s status=%s duration_ms=%.2f"
    )
    args = (
        ctx["request_id"],
        ctx["tenant_id"],
        ctx["user_id"],
        ctx["endpoint"],
        ctx["method"],
        ctx["path"],
        response.status_code,
        duration_ms,
    )
    if response.status_code >= 500:
        finance_logger.error(msg, *args)
    elif response.status_code >= 400:
        finance_logger.warning(msg, *args)
    else:
        finance_logger.info(msg, *args)
    return response


@bp.teardown_request
def _finance_log_exception(exc) -> None:
    if exc is None:
        return
    if not (request.endpoint and request.endpoint.startswith("finance.")):
        return
    ctx = _finance_context()
    finance_logger.exception(
        "event=finance.request.exception request_id=%s tenant_id=%s user_id=%s endpoint=%s method=%s path=%s err=%s",
        ctx["request_id"],
        ctx["tenant_id"],
        ctx["user_id"],
        ctx["endpoint"],
        ctx["method"],
        ctx["path"],
        str(exc),
    )


def _(msgid: str, **kwargs):
    return tr(msgid, getattr(g, "lang", DEFAULT_LANG), **kwargs)


def _require_tenant() -> None:
    if not current_user.is_authenticated:
        abort(401)
    if not getattr(g, "tenant", None) or current_user.tenant_id != g.tenant.id:
        abort(403)


@bp.app_context_processor
def _finance_layout_context():
    tenant = getattr(g, "tenant", None)
    module_access = get_user_module_access(tenant, getattr(current_user, "id", None))
    finance_menu_access = get_user_menu_access(tenant, getattr(current_user, "id", None), "finance")
    if not tenant or not getattr(tenant, "subscription", None):
        return {"transaction_usage": None, "module_access": module_access, "finance_menu_access": finance_menu_access}

    _, current_count, max_limit = SubscriptionService.check_limit(tenant.id, "transactions")
    return {
        "module_access": module_access,
        "finance_menu_access": finance_menu_access,
        "transaction_usage": {
            "current": int(current_count),
            "max": int(max_limit),
            "max_label": "∞" if int(max_limit) == -1 else str(int(max_limit)),
            "is_unlimited": int(max_limit) == -1,
        }
    }


@bp.before_app_request
def _load_tenant_into_g() -> None:
    """Ensure g.tenant is available even if user enters finance pages directly."""
    # The portal blueprint already does this, but keeping here makes finance self-contained.
    tenant_id = get_current_tenant_id()
    if getattr(g, "tenant", None) is None:
        g.tenant = None
        if tenant_id:
            tenant = Tenant.query.get(tenant_id)
            if tenant:
                g.tenant = tenant

    if (
        request.endpoint
        and request.endpoint.startswith("finance.")
        and current_user.is_authenticated
        and getattr(g, "tenant", None)
        and current_user.tenant_id == g.tenant.id
    ):
        access = get_user_module_access(g.tenant, current_user.id)
        if not access.get("finance", True):
            flash(_("Acesso Finance desativado para seu usuário."), "warning")
            return redirect(url_for("tenant.dashboard"))

        finance_menu_access = get_user_menu_access(g.tenant, current_user.id, "finance")
        endpoint_menu_key = {
            "finance.dashboard": "dashboard",
            "finance.accounts_list": "accounts",
            "finance.account_view": "accounts",
            "finance.transactions_list": "transactions",
            "finance.transaction_new": "transactions",
            "finance.transaction_edit": "transactions",
            "finance.quick_entry": "transactions",
            "finance.reports_transactions": "reports",
            "finance.reports_statistics": "stats",
            "finance.reports_accounting": "accounting",
            "finance.pivot_page": "pivot",
            "finance.invoices_list": "invoices",
            "finance.invoice_view": "invoices",
            "finance.alerts_page": "alerts",
            "finance.regulation_page": "regulation",
            "finance.liabilities_list": "liabilities",
            "finance.investments_list": "investments",
            "finance.recurring_list": "recurring",
            "finance.cashflow": "cashflow",
            "finance.nii": "nii",
            "finance.gaps": "gaps",
            "finance.liquidity": "liquidity",
            "finance.risk": "risk",
            "finance.settings_categories": "settings",
            "finance.settings_gl": "settings",
            "finance.counterparties_settings": "settings",
            "finance.master_data_import": "imports",
            "finance.help_page": "help",
        }
        menu_key = endpoint_menu_key.get(request.endpoint)
        if menu_key and not finance_menu_access.get(menu_key, True):
            flash(_("Accès menu Finance désactivé pour votre utilisateur."), "warning")
            return redirect(url_for("finance.dashboard"))


def _get_company() -> FinanceCompany:
    """Get the selected company for the current tenant.

    If none exists yet, creates a default company for MVP convenience.
    """
    _require_tenant()

    ensure_default_currencies()

    company_id = session.get("finance_company_id")
    if company_id:
        comp = FinanceCompany.query.filter_by(id=company_id, tenant_id=g.tenant.id).first()
        if comp:
            ensure_default_categories(comp)
            ensure_default_gl_accounts(comp)
            return comp

    comp = FinanceCompany.query.filter_by(tenant_id=g.tenant.id).order_by(FinanceCompany.id.asc()).first()
    if comp:
        session["finance_company_id"] = comp.id
        ensure_default_categories(comp)
        ensure_default_gl_accounts(comp)
        return comp

    # Create a default company (safe MVP behavior)
    slug = "default"
    if FinanceCompany.query.filter_by(tenant_id=g.tenant.id, slug=slug).first():
        slug = f"default-{g.tenant.id}"

    comp = FinanceCompany(
        tenant_id=g.tenant.id,
        slug=slug,
        name=_("Minha empresa"),
        base_currency="EUR",
    )
    db.session.add(comp)
    db.session.commit()
    session["finance_company_id"] = comp.id
    ensure_default_categories(comp)
    ensure_default_gl_accounts(comp)
    return comp


def _transaction_quota_info() -> tuple[bool, int, int, int]:
    """Return transaction quota status for current tenant.

    Returns:
        (allowed_now, remaining_slots, current_count, max_limit)
    """
    can_add, current_count, max_limit = SubscriptionService.check_limit(g.tenant.id, "transactions")
    if max_limit == -1:
        return True, 10**9, current_count, max_limit
    remaining = max(0, int(max_limit) - int(current_count))
    return bool(can_add), remaining, int(current_count), int(max_limit)


def _ensure_transaction_quota(required: int = 1) -> bool:
    allowed, remaining, current_count, max_limit = _transaction_quota_info()
    if allowed and remaining >= int(required):
        return True
    if max_limit == -1:
        return True
    flash(
        _("Limite de transações do plano atingida ({current}/{max}).", current=current_count, max=max_limit),
        "error",
    )
    return False


def _get_fin_setting(company: FinanceCompany, key: str, default: dict) -> dict:
    s = FinanceSetting.query.filter_by(
        tenant_id=g.tenant.id,
        company_id=company.id,
        key=key,
    ).first()
    return (s.value_json if s and isinstance(s.value_json, dict) else default)


def _set_fin_setting(company: FinanceCompany, key: str, value: dict) -> None:
    s = FinanceSetting.query.filter_by(
        tenant_id=g.tenant.id,
        company_id=company.id,
        key=key,
    ).first()
    if not s:
        s = FinanceSetting(tenant_id=g.tenant.id, company_id=company.id, key=key, value_json=value)
        db.session.add(s)
    else:
        s.value_json = value
    db.session.commit()


_INVOICE_TEMPLATE_SETTING_KEY = "invoice_template"
_INVOICE_TEMPLATE_LANGS = ["fr", "en", "pt", "es", "it", "de"]
_GL_AUTO_RULES_SETTING_KEY = "gl_auto_rules"


def _invoice_lang_label(code: str) -> str:
    labels = {
        "fr": "Français",
        "en": "English",
        "pt": "Português",
        "es": "Español",
        "it": "Italiano",
        "de": "Deutsch",
    }
    return labels.get(code, code.upper())


def _default_invoice_template_settings(company: FinanceCompany) -> dict:
    localized_defaults = {
        "fr": {
            "email_subject_template": "Facture {invoice_number} - {company_name}",
            "email_body_template": (
                "Bonjour {client_name},\n\n"
                "Veuillez trouver en pièce jointe la facture {invoice_number} d'un montant de {total} {currency}.\n"
                "Date d'émission : {issue_date}."
                "{due_line}\n\n"
                "Cordialement,\n"
                "{sender_name}"
            ),
        },
        "en": {
            "email_subject_template": "Invoice {invoice_number} - {company_name}",
            "email_body_template": (
                "Hello {client_name},\n\n"
                "Please find attached invoice {invoice_number} for {total} {currency}.\n"
                "Issue date: {issue_date}."
                "{due_line}\n\n"
                "Best regards,\n"
                "{sender_name}"
            ),
        },
        "pt": {
            "email_subject_template": "Fatura {invoice_number} - {company_name}",
            "email_body_template": (
                "Olá {client_name},\n\n"
                "Segue em anexo a fatura {invoice_number} no valor de {total} {currency}.\n"
                "Data de emissão: {issue_date}."
                "{due_line}\n\n"
                "Atenciosamente,\n"
                "{sender_name}"
            ),
        },
        "es": {
            "email_subject_template": "Factura {invoice_number} - {company_name}",
            "email_body_template": (
                "Hola {client_name},\n\n"
                "Adjunto encontrará la factura {invoice_number} por un importe de {total} {currency}.\n"
                "Fecha de emisión: {issue_date}."
                "{due_line}\n\n"
                "Saludos cordiales,\n"
                "{sender_name}"
            ),
        },
        "it": {
            "email_subject_template": "Fattura {invoice_number} - {company_name}",
            "email_body_template": (
                "Ciao {client_name},\n\n"
                "In allegato trovi la fattura {invoice_number} per un importo di {total} {currency}.\n"
                "Data di emissione: {issue_date}."
                "{due_line}\n\n"
                "Cordiali saluti,\n"
                "{sender_name}"
            ),
        },
        "de": {
            "email_subject_template": "Rechnung {invoice_number} - {company_name}",
            "email_body_template": (
                "Hallo {client_name},\n\n"
                "Im Anhang finden Sie die Rechnung {invoice_number} über {total} {currency}.\n"
                "Ausstellungsdatum: {issue_date}."
                "{due_line}\n\n"
                "Mit freundlichen Grüßen,\n"
                "{sender_name}"
            ),
        },
    }

    defaults = {
        "logo_url": "",
        "email_subject_template": localized_defaults["fr"]["email_subject_template"],
        "email_body_template": localized_defaults["fr"]["email_body_template"],
        "sender_name": company.name or "",
    }
    defaults["localized_templates"] = {
        lang: {
            "email_subject_template": localized_defaults.get(lang, localized_defaults["fr"])["email_subject_template"],
            "email_body_template": localized_defaults.get(lang, localized_defaults["fr"])["email_body_template"],
        }
        for lang in _INVOICE_TEMPLATE_LANGS
    }
    return defaults


def _get_invoice_template_settings(company: FinanceCompany) -> dict:
    defaults = _default_invoice_template_settings(company)
    value = _get_fin_setting(company, _INVOICE_TEMPLATE_SETTING_KEY, defaults)
    settings = defaults.copy()
    settings.update(value if isinstance(value, dict) else {})
    localized_templates = settings.get("localized_templates")
    if not isinstance(localized_templates, dict):
        localized_templates = {}
    normalized_localized: dict = {}
    for lang in _INVOICE_TEMPLATE_LANGS:
        row = localized_templates.get(lang)
        if not isinstance(row, dict):
            row = {}
        lang_defaults = defaults.get("localized_templates", {}).get(lang, {})
        normalized_localized[lang] = {
            "email_subject_template": str(row.get("email_subject_template") or lang_defaults.get("email_subject_template") or defaults["email_subject_template"]),
            "email_body_template": str(row.get("email_body_template") or lang_defaults.get("email_body_template") or defaults["email_body_template"]),
        }
    settings["localized_templates"] = normalized_localized
    return settings


def _invoice_template_lang(settings: dict, requested_lang: str | None = None) -> str:
    lang = (requested_lang or getattr(g, "lang", "fr") or "fr").strip().lower()
    if lang not in _INVOICE_TEMPLATE_LANGS:
        lang = "fr"
    return lang


def _invoice_template_texts(settings: dict, lang: str) -> tuple[str, str]:
    localized_templates = settings.get("localized_templates") if isinstance(settings.get("localized_templates"), dict) else {}
    row = localized_templates.get(lang) if isinstance(localized_templates.get(lang), dict) else {}
    subject = str(row.get("email_subject_template") or settings.get("email_subject_template") or "")
    body = str(row.get("email_body_template") or settings.get("email_body_template") or "")
    return subject, body


def _build_invoice_mail_tokens(inv: FinanceInvoice, company: FinanceCompany, lang: str = "fr") -> dict:
    due_str = inv.due_date.isoformat() if inv.due_date else ""
    total_str = f"{Decimal(str(inv.total_gross or 0)).quantize(Decimal('0.01'))}"
    client_name = inv.counterparty.name if inv.counterparty else "Client"
    due_line_labels = {
        "fr": "Échéance",
        "en": "Due date",
        "pt": "Vencimento",
        "es": "Vencimiento",
        "it": "Scadenza",
        "de": "Fällig am",
    }
    due_line_label = due_line_labels.get(lang, due_line_labels["fr"])
    return {
        "invoice_number": inv.invoice_number,
        "company_name": company.name,
        "client_name": client_name,
        "currency": inv.currency,
        "total": total_str,
        "issue_date": inv.issue_date.isoformat() if inv.issue_date else "",
        "due_date": due_str,
        "due_line": f"\n{due_line_label}: {due_str}." if due_str else "",
        "sender_name": company.name,
    }


def _render_invoice_text_template(template_text: str, tokens: dict) -> str:
    if not template_text:
        return ""
    try:
        return template_text.format(**tokens)
    except Exception:
        rendered = template_text
        for key, value in tokens.items():
            rendered = rendered.replace("{" + key + "}", str(value))
        return rendered


def _save_finance_logo_upload(tenant_id: int, company_id: int, file_storage) -> str | None:
    if not file_storage or not getattr(file_storage, "filename", None):
        return None
    filename = secure_filename(file_storage.filename or "")
    if not filename:
        return None
    ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
    if ext not in {"png", "jpg", "jpeg", "webp", "gif"}:
        raise ValueError("Unsupported logo format")

    rel_dir = os.path.join("uploads", "finance_logos", f"tenant_{int(tenant_id)}", f"company_{int(company_id)}")
    abs_dir = os.path.join(current_app.static_folder, rel_dir)
    os.makedirs(abs_dir, exist_ok=True)
    new_name = f"logo_{uuid.uuid4().hex}.{ext}"
    abs_path = os.path.join(abs_dir, new_name)
    file_storage.save(abs_path)
    rel_path = os.path.join(rel_dir, new_name).replace("\\", "/")
    return "/static/" + rel_path


def _resolve_logo_static_path(logo_url: str | None) -> str | None:
    if not logo_url:
        return None
    value = str(logo_url).strip()
    if not value.startswith("/static/"):
        return None
    rel = value[len("/static/"):].strip("/")
    if not rel:
        return None
    abs_path = Path(current_app.static_folder) / rel
    if abs_path.exists() and abs_path.is_file():
        return str(abs_path)
    return None


def _q_accounts(company: FinanceCompany):
    return FinanceAccount.query.filter_by(tenant_id=g.tenant.id, company_id=company.id)


def _q_txns(company: FinanceCompany):
    return FinanceTransaction.query.filter_by(tenant_id=g.tenant.id, company_id=company.id)


# -----------------
# Reference data (currencies / counterparties)
# -----------------

_DEF_CURRENCIES = [
    ('EUR', 'Euro', '€'),
    ('USD', 'US Dollar', '$'),
    ('GBP', 'Pound sterling', '£'),
    ('CHF', 'Swiss franc', 'CHF'),
    ('BRL', 'Real brasileiro', 'R$'),
    ('CAD', 'Canadian dollar', 'CA$'),
    ('JPY', 'Yen', '¥'),
]


def ensure_default_currencies() -> None:
    """Insert a minimal currency catalog if the table is empty."""
    if FinanceCurrency.query.count() > 0:
        return
    for code, name, sym in _DEF_CURRENCIES:
        db.session.add(FinanceCurrency(code=code, name=name, symbol=sym, decimals=2))
    db.session.commit()


def get_currencies():
    ensure_default_currencies()
    return FinanceCurrency.query.order_by(FinanceCurrency.code.asc()).all()


def get_counterparties(company: FinanceCompany):
    return (
        FinanceCounterparty.query
        .filter_by(tenant_id=g.tenant.id)
        .filter((FinanceCounterparty.company_id == None) | (FinanceCounterparty.company_id == company.id))
        .order_by(FinanceCounterparty.name.asc())
        .all()
    )


# -----------------
# Reference data (categories / accounting)
# -----------------

_DEF_CATEGORIES = [
    ("sales", "Ventes", ["vente", "sales", "invoice", "facture", "client", "paiement", "carte"]),
    ("payroll", "Salaires", ["salaire", "paie", "payroll", "salary"]),
    ("rent", "Loyer", ["loyer", "rent"]),
    ("tax", "Taxes", ["tax", "tva", "impot", "urssaf", "vat"]),
    ("fees", "Frais bancaires", ["frais", "commission", "fee", "charges", "cotisation"]),
    ("loan", "Prêts", ["pret", "loan", "credit", "emprunt"]),
    ("capex", "Investissements", ["capex", "equipment", "materiel", "immobilisation"]),
    ("transfer", "Virements", ["virement", "transfer", "interne"]),
    ("other", "Autre", []),
]


def ensure_default_categories(company: FinanceCompany) -> None:
    existing = FinanceCategory.query.filter_by(tenant_id=g.tenant.id, company_id=company.id).count()
    if existing > 0:
        return

    for idx, (code, name, keywords) in enumerate(_DEF_CATEGORIES):
        cat = FinanceCategory(tenant_id=g.tenant.id, company_id=company.id, code=code, name=name)
        db.session.add(cat)
        db.session.flush()
        if keywords:
            db.session.add(
                FinanceCategoryRule(
                    tenant_id=g.tenant.id,
                    company_id=company.id,
                    category_id=cat.id,
                    direction="any",
                    keywords=",".join(keywords),
                    priority=10 + idx,
                )
            )
    db.session.commit()


def get_categories(company: FinanceCompany):
    ensure_default_categories(company)
    return FinanceCategory.query.filter_by(tenant_id=g.tenant.id, company_id=company.id).order_by(FinanceCategory.name.asc()).all()


_DEF_GL = [
    ("512", "Banque", "asset"),
    ("411", "Clients", "asset"),
    ("401", "Fournisseurs", "liability"),
    ("706", "Ventes", "income"),
    ("601", "Achats", "expense"),
    ("613", "Loyer", "expense"),
    ("641", "Salaires", "expense"),
    ("627", "Frais bancaires", "expense"),
    ("445", "Taxes", "liability"),
]


def ensure_default_gl_accounts(company: FinanceCompany) -> None:
    existing = FinanceGLAccount.query.filter_by(tenant_id=g.tenant.id, company_id=company.id).count()
    if existing > 0:
        return
    for idx, (code, name, typ) in enumerate(_DEF_GL, start=1):
        db.session.add(
            FinanceGLAccount(
                tenant_id=g.tenant.id,
                company_id=company.id,
                code=code,
                name=name,
                kind=typ,
                parent_id=None,
                sort_order=idx,
            )
        )
    db.session.commit()


def get_gl_accounts(company: FinanceCompany):
    ensure_default_gl_accounts(company)
    return (
        FinanceGLAccount.query
        .filter_by(tenant_id=g.tenant.id, company_id=company.id)
        .order_by(FinanceGLAccount.sort_order.asc(), FinanceGLAccount.code.asc(), FinanceGLAccount.id.asc())
        .all()
    )


def _gl_children_map(gl_accounts: list[FinanceGLAccount]) -> dict[int | None, list[FinanceGLAccount]]:
    by_parent: dict[int | None, list[FinanceGLAccount]] = {}
    for gl in gl_accounts:
        by_parent.setdefault(gl.parent_id, []).append(gl)
    for key in by_parent:
        by_parent[key].sort(key=lambda x: (int(x.sort_order or 0), str(x.code or ""), int(x.id or 0)))
    return by_parent


def _flatten_gl_accounts(gl_accounts: list[FinanceGLAccount]) -> list[tuple[FinanceGLAccount, int]]:
    by_parent = _gl_children_map(gl_accounts)
    out: list[tuple[FinanceGLAccount, int]] = []

    def walk(parent_id: int | None, depth: int) -> None:
        for node in by_parent.get(parent_id, []):
            out.append((node, depth))
            walk(node.id, depth + 1)

    walk(None, 0)
    return out


def _leaf_gl_ids(gl_accounts: list[FinanceGLAccount]) -> set[int]:
    parent_ids = {int(gl.parent_id) for gl in gl_accounts if gl.parent_id is not None}
    return {int(gl.id) for gl in gl_accounts if int(gl.id) not in parent_ids}


def get_postable_gl_accounts(company: FinanceCompany) -> list[FinanceGLAccount]:
    all_gl = get_gl_accounts(company)
    leaves = _leaf_gl_ids(all_gl)
    flattened = _flatten_gl_accounts(all_gl)
    return [gl for gl, _depth in flattened if gl.id in leaves]


def _is_leaf_gl_account(gl_id: int | None, company: FinanceCompany) -> bool:
    if not gl_id:
        return False
    cnt = (
        FinanceGLAccount.query
        .filter_by(tenant_id=g.tenant.id, company_id=company.id, parent_id=int(gl_id))
        .count()
    )
    return cnt == 0


def _is_descendant_gl_account(candidate_parent_id: int, node_id: int, company: FinanceCompany) -> bool:
    cur = FinanceGLAccount.query.filter_by(id=candidate_parent_id, tenant_id=g.tenant.id, company_id=company.id).first()
    seen: set[int] = set()
    while cur is not None and cur.id not in seen:
        if int(cur.id) == int(node_id):
            return True
        seen.add(int(cur.id))
        if cur.parent_id is None:
            break
        cur = FinanceGLAccount.query.filter_by(id=cur.parent_id, tenant_id=g.tenant.id, company_id=company.id).first()
    return False


def apply_category_rules(
    company: FinanceCompany,
    *,
    description: str,
    counterparty_id: int | None,
    amount: float,
    counterparty_name: str | None = None,
) -> int | None:
    direction = "inflow" if amount > 0 else "outflow" if amount < 0 else "any"
    desc_l = (description or "").lower()
    counterparty_name_l = (counterparty_name or "").strip().lower()
    cp_name_by_id: dict[int, str] = {}
    if counterparty_name_l:
        cp_name_by_id = {
            int(cp.id): (cp.name or "").strip().lower()
            for cp in get_counterparties(company)
            if cp.id and (cp.name or "").strip()
        }
    rules = (
        FinanceCategoryRule.query
        .filter_by(tenant_id=g.tenant.id, company_id=company.id)
        .order_by(FinanceCategoryRule.priority.asc())
        .all()
    )
    for r in rules:
        if r.direction and r.direction != "any" and r.direction != direction:
            continue
        if r.counterparty_id:
            if counterparty_id:
                if r.counterparty_id != counterparty_id:
                    continue
            elif counterparty_name_l:
                if cp_name_by_id.get(int(r.counterparty_id)) != counterparty_name_l:
                    continue
            else:
                continue
        if r.min_amount is not None and abs(amount) < float(r.min_amount):
            continue
        if r.max_amount is not None and abs(amount) > float(r.max_amount):
            continue
        if r.keywords:
            kws = [k.strip().lower() for k in r.keywords.split(",") if k.strip()]
            if kws and not any(k in desc_l for k in kws):
                continue
        return r.category_id
    return None


def _normalize_gl_auto_rules(value: dict) -> list[dict]:
    raw_rules = value.get("rules") if isinstance(value, dict) else []
    if not isinstance(raw_rules, list):
        return []

    normalized: list[dict] = []
    for row in raw_rules:
        if not isinstance(row, dict):
            continue
        try:
            gl_account_id = int(row.get("gl_account_id") or 0)
        except Exception:
            gl_account_id = 0
        if gl_account_id <= 0:
            continue

        def _to_int(v):
            try:
                iv = int(v)
                return iv if iv > 0 else None
            except Exception:
                return None

        def _to_float(v):
            if v in (None, ""):
                return None
            try:
                return float(v)
            except Exception:
                return None

        rule_id = str(row.get("id") or "").strip() or uuid.uuid4().hex[:12]
        direction = str(row.get("direction") or "any").strip().lower()
        if direction not in {"any", "inflow", "outflow"}:
            direction = "any"

        normalized.append(
            {
                "id": rule_id,
                "name": str(row.get("name") or "").strip(),
                "priority": int(row.get("priority") or 100),
                "direction": direction,
                "keywords": str(row.get("keywords") or "").strip(),
                "counterparty_id": _to_int(row.get("counterparty_id")),
                "category_id": _to_int(row.get("category_id")),
                "min_amount": _to_float(row.get("min_amount")),
                "max_amount": _to_float(row.get("max_amount")),
                "gl_account_id": gl_account_id,
            }
        )

    normalized.sort(key=lambda r: int(r.get("priority") or 100))
    return normalized


def _get_gl_auto_rules(company: FinanceCompany) -> list[dict]:
    raw = _get_fin_setting(company, _GL_AUTO_RULES_SETTING_KEY, {"rules": []})
    return _normalize_gl_auto_rules(raw if isinstance(raw, dict) else {"rules": []})


def _set_gl_auto_rules(company: FinanceCompany, rules: list[dict]) -> None:
    clean = _normalize_gl_auto_rules({"rules": rules})
    _set_fin_setting(company, _GL_AUTO_RULES_SETTING_KEY, {"rules": clean})


def _match_gl_auto_rule(
    rule: dict,
    *,
    description: str,
    counterparty_id: int | None,
    counterparty_name: str | None,
    category_id: int | None,
    amount: float,
    cp_name_by_id: dict[int, str],
) -> bool:
    direction = "inflow" if amount > 0 else "outflow" if amount < 0 else "any"
    if rule.get("direction") not in (None, "", "any") and rule.get("direction") != direction:
        return False

    rule_cp_id = rule.get("counterparty_id")
    if rule_cp_id:
        if counterparty_id:
            if int(rule_cp_id) != int(counterparty_id):
                return False
        elif counterparty_name:
            cp_rule_name = cp_name_by_id.get(int(rule_cp_id), "")
            if cp_rule_name != (counterparty_name or "").strip().lower():
                return False
        else:
            return False

    rule_cat_id = rule.get("category_id")
    if rule_cat_id:
        if not category_id or int(rule_cat_id) != int(category_id):
            return False

    abs_amount = abs(float(amount or 0))
    min_amount = rule.get("min_amount")
    max_amount = rule.get("max_amount")
    if min_amount is not None and abs_amount < float(min_amount):
        return False
    if max_amount is not None and abs_amount > float(max_amount):
        return False

    keywords = [k.strip().lower() for k in str(rule.get("keywords") or "").split(",") if k.strip()]
    if keywords:
        haystack = (description or "").lower()
        if not any(k in haystack for k in keywords):
            return False

    return True


def select_gl_account_by_rules(company: FinanceCompany, txn: FinanceTransaction, rules: list[dict] | None = None) -> int | None:
    current_rules = rules if rules is not None else _get_gl_auto_rules(company)
    if not current_rules:
        return None

    cp_name_by_id: dict[int, str] = {
        int(cp.id): (cp.name or "").strip().lower()
        for cp in get_counterparties(company)
        if cp.id and (cp.name or "").strip()
    }

    for rule in current_rules:
        if _match_gl_auto_rule(
            rule,
            description=(txn.description or ""),
            counterparty_id=txn.counterparty_id,
            counterparty_name=txn.counterparty,
            category_id=txn.category_id,
            amount=float(txn.amount or 0),
            cp_name_by_id=cp_name_by_id,
        ):
            return int(rule.get("gl_account_id") or 0) or None

    return None


def _apply_gl_auto_rules_on_transactions(
    company: FinanceCompany,
    txns: list[FinanceTransaction],
    *,
    only_missing_gl: bool = True,
) -> tuple[int, int]:
    rules = _get_gl_auto_rules(company)
    if not rules:
        return 0, 0

    postable_ids = {int(gl.id) for gl in get_postable_gl_accounts(company)}

    scanned = 0
    updated = 0
    for txn in txns:
        scanned += 1
        if txn.ledger_voucher_id:
            continue
        if only_missing_gl and txn.gl_account_id:
            continue
        gl_id = select_gl_account_by_rules(company, txn, rules)
        if not gl_id:
            continue
        if int(gl_id) not in postable_ids:
            continue
        if txn.gl_account_id == int(gl_id):
            continue
        txn.gl_account_id = int(gl_id)
        updated += 1

    return updated, scanned



@bp.route("/")
@login_required
@require_roles("tenant_admin", "creator", "viewer")
def dashboard():
    company = _get_company()
    accounts = _q_accounts(company).order_by(FinanceAccount.name.asc()).all()
    txns_12m = (
        _q_txns(company)
        .filter(FinanceTransaction.txn_date >= (date.today() - timedelta(days=365)))
        .all()
    )
    liabilities = FinanceLiability.query.filter_by(tenant_id=g.tenant.id, company_id=company.id).all()
    investments = _safe_get_investments(company)

    cash = compute_starting_cash(accounts)
    nii = compute_nii(accounts, horizon_days=365)
    liquidity = compute_liquidity(accounts, horizon_days=30)
    investment_liquid_sources = _compute_investment_liquid_sources(investments)
    liquidity = _with_investment_liquidity(liquidity, investment_liquid_sources)

    def _n(v) -> float:
        try:
            return float(v or 0)
        except Exception:
            return 0.0

    operating_exclusion_tokens = {
        "loan", "emprunt", "prêt", "juros", "interest", "tax", "impot", "tva", "amort", "depreci"
    }
    op_inflows = 0.0
    op_outflows = 0.0
    for t in txns_12m:
        category_text = (getattr(t, "category", None) or "").lower()
        if any(tok in category_text for tok in operating_exclusion_tokens):
            continue
        amt = _n(getattr(t, "amount", 0))
        if amt >= 0:
            op_inflows += amt
        else:
            op_outflows += abs(amt)
    ebitda_12m = op_inflows - op_outflows

    debt_from_liabilities = sum(
        _n(li.outstanding_amount if li.outstanding_amount is not None else li.principal_amount)
        for li in liabilities
    )
    debt_from_accounts = sum(
        abs(_n(a.balance))
        for a in accounts
        if (a.side or "").lower() == "liability" and (a.account_type or "").lower() in {"loan", "credit_line", "payable"}
    )
    debt_total = debt_from_liabilities if debt_from_liabilities > 0 else debt_from_accounts
    leverage_ratio = (debt_total / ebitda_12m) if ebitda_12m > 0 else None

    assets_total = sum(
        abs(_n(a.balance))
        for a in accounts
        if (a.side or "").lower() == "asset"
    )
    liabilities_total = sum(
        abs(_n(a.balance))
        for a in accounts
        if (a.side or "").lower() == "liability"
    )
    equity_total = sum(
        abs(_n(a.balance))
        for a in accounts
        if (a.side or "").lower() == "equity"
    )

    debt_to_assets_ratio = (debt_total / assets_total) if assets_total > 0 else None
    debt_to_equity_ratio = (debt_total / equity_total) if equity_total > 0 else None
    debt_to_capital_ratio = (debt_total / (debt_total + equity_total)) if (debt_total + equity_total) > 0 else None

    net_debt = max(0.0, debt_total - max(0.0, _n(cash)))
    net_debt_to_ebitda = (net_debt / ebitda_12m) if ebitda_12m > 0 else None

    expense_by_category: dict[str, float] = {}
    start_6m = date.today() - timedelta(days=183)
    monthly_flows: dict[str, dict[str, float]] = {}
    for t in txns_12m:
        amt = _n(getattr(t, "amount", 0))
        if amt < 0:
            cat_name = (getattr(getattr(t, "category_ref", None), "name", None) or getattr(t, "category", None) or "Sem categoria")
            expense_by_category[cat_name] = expense_by_category.get(cat_name, 0.0) + abs(amt)

        if t.txn_date >= start_6m:
            mkey = t.txn_date.strftime("%Y-%m")
            bucket = monthly_flows.setdefault(mkey, {"in": 0.0, "out": 0.0})
            if amt >= 0:
                bucket["in"] += amt
            else:
                bucket["out"] += abs(amt)

    top_expense_categories = [
        {"name": nm, "value": val}
        for nm, val in sorted(expense_by_category.items(), key=lambda x: x[1], reverse=True)[:8]
    ]

    month_cursor = date(start_6m.year, start_6m.month, 1)
    end_month = date(date.today().year, date.today().month, 1)
    cashflow_labels: list[str] = []
    cashflow_in: list[float] = []
    cashflow_out: list[float] = []
    while month_cursor <= end_month:
        key = month_cursor.strftime("%Y-%m")
        cashflow_labels.append(key)
        row = monthly_flows.get(key, {"in": 0.0, "out": 0.0})
        cashflow_in.append(float(row.get("in", 0.0)))
        cashflow_out.append(float(row.get("out", 0.0)))
        if month_cursor.month == 12:
            month_cursor = date(month_cursor.year + 1, 1, 1)
        else:
            month_cursor = date(month_cursor.year, month_cursor.month + 1, 1)

    inflows_6m = sum(cashflow_in)
    outflows_6m = sum(cashflow_out)
    net_6m = inflows_6m - outflows_6m

    flow_trend_label = _("Stable")
    flow_trend_pct = None
    if len(cashflow_in) >= 6 and len(cashflow_out) >= 6:
        prev_net = sum(cashflow_in[-6:-3]) - sum(cashflow_out[-6:-3])
        last_net = sum(cashflow_in[-3:]) - sum(cashflow_out[-3:])
        if prev_net != 0:
            flow_trend_pct = ((last_net - prev_net) / abs(prev_net)) * 100.0
        if last_net > prev_net + 0.01:
            flow_trend_label = _("Hausse")
        elif last_net < prev_net - 0.01:
            flow_trend_label = _("Baisse")

    # Small, friendly KPIs
    kpis = {
        "cash": cash,
        "nii_12m": nii["nii_total"],
        "liq_ratio": liquidity["liquidity_ratio"],
        "net_liq": liquidity["net_liquidity"],
        "ebitda_12m": ebitda_12m,
        "debt_total": debt_total,
        "leverage_ratio": leverage_ratio,
        "debt_to_assets_ratio": debt_to_assets_ratio,
        "debt_to_equity_ratio": debt_to_equity_ratio,
        "debt_to_capital_ratio": debt_to_capital_ratio,
        "net_debt": net_debt,
        "net_debt_to_ebitda": net_debt_to_ebitda,
        "assets_total": assets_total,
        "liabilities_total": liabilities_total,
        "equity_total": equity_total,
        "inflows_6m": inflows_6m,
        "outflows_6m": outflows_6m,
        "net_6m": net_6m,
        "flow_trend_label": flow_trend_label,
        "flow_trend_pct": flow_trend_pct,
    }

    return render_template(
        "finance/dashboard.html",
        tenant=g.tenant,
        company=company,
        kpis=kpis,
        accounts=accounts,
        top_expense_categories=top_expense_categories,
        cashflow_simple={
            "labels": cashflow_labels,
            "inflows": cashflow_in,
            "outflows": cashflow_out,
        },
    )


# -----------------
# Companies (multi-company within tenant)
# -----------------


@bp.route("/companies", methods=["GET", "POST"])
@login_required
@require_roles("tenant_admin", "creator")
def companies():
    _require_tenant()

    if request.method == "POST":
        name = (request.form.get("name") or "").strip()
        slug = (request.form.get("slug") or "").strip().lower()
        base_currency = (request.form.get("base_currency") or "EUR").strip().upper()
        if not FinanceCurrency.query.get(base_currency):
            flash(_("Moeda inválida."), "error")
            return redirect(url_for("finance.companies"))
        country = (request.form.get("country") or "").strip() or None

        if not name or not slug:
            flash(_("Preencha todos os campos."), "error")
            return redirect(url_for("finance.companies"))

        if FinanceCompany.query.filter_by(tenant_id=g.tenant.id, slug=slug).first():
            flash(_("Slug já existe."), "error")
            return redirect(url_for("finance.companies"))

        comp = FinanceCompany(
            tenant_id=g.tenant.id,
            name=name,
            slug=slug,
            base_currency=base_currency,
            country=country,
        )
        db.session.add(comp)
        db.session.commit()
        session["finance_company_id"] = comp.id
        flash(_("Empresa criada."), "success")
        return redirect(url_for("finance.dashboard"))

    selected = None
    if session.get("finance_company_id"):
        selected = FinanceCompany.query.filter_by(id=session.get("finance_company_id"), tenant_id=g.tenant.id).first()

    companies = FinanceCompany.query.filter_by(tenant_id=g.tenant.id).order_by(FinanceCompany.name.asc()).all()
    return render_template(
        "finance/companies.html",
        tenant=g.tenant,
        company=selected,
        companies=companies,
        currencies=get_currencies(),
    )


@bp.route("/companies/select/<int:company_id>")
@login_required
@require_roles("tenant_admin", "creator", "viewer")
def company_select(company_id: int):
    _require_tenant()
    comp = FinanceCompany.query.filter_by(id=company_id, tenant_id=g.tenant.id).first_or_404()
    session["finance_company_id"] = comp.id
    flash(_("Empresa selecionada."), "success")
    return redirect(url_for("finance.dashboard"))


# -----------------
# Accounts
# -----------------


@bp.route("/accounts")
@login_required
@require_roles("tenant_admin", "creator", "viewer")
def accounts_list():
    company = _get_company()
    accounts = _q_accounts(company).order_by(FinanceAccount.account_type.asc(), FinanceAccount.name.asc()).all()
    return render_template(
        "finance/accounts_list.html",
        tenant=g.tenant,
        company=company,
        accounts=accounts,
    )


@bp.route("/accounts/new", methods=["GET", "POST"])
@login_required
@require_roles("tenant_admin", "creator")
def account_new():
    company = _get_company()
    if request.method == "POST":
        name = (request.form.get("name") or "").strip()
        account_type = (request.form.get("account_type") or "bank").strip()
        side = (request.form.get("side") or "asset").strip()
        currency = (request.form.get("currency") or company.base_currency or "EUR").strip().upper()
        if not FinanceCurrency.query.get(currency):
            flash(_("Moeda inválida."), "error")
            return redirect(url_for("finance.account_new"))

        balance = (request.form.get("balance") or "0").strip().replace(",", ".")
        limit_amount = (request.form.get("limit_amount") or "").strip().replace(",", ".")
        is_interest_bearing = bool(request.form.get("is_interest_bearing"))
        annual_rate = (request.form.get("annual_rate") or "").strip().replace(",", ".")
        rate_type = (request.form.get("rate_type") or "fixed").strip()
        repricing_date = (request.form.get("repricing_date") or "").strip()
        maturity_date = (request.form.get("maturity_date") or "").strip()

        # Counterparty from directory
        counterparty_id = int(request.form.get("counterparty_id") or 0)
        counterparty_name = (request.form.get("counterparty_name") or "").strip()
        counterparty_kind = (request.form.get("counterparty_kind") or "other").strip()

        gl_account_id = int(request.form.get("gl_account_id") or 0) or None
        if gl_account_id:
            ok_gl = FinanceGLAccount.query.filter_by(
                id=gl_account_id,
                tenant_id=g.tenant.id,
                company_id=company.id,
            ).first()
            if not ok_gl:
                flash(_("Conta contábil inválida."), "error")
                return redirect(url_for("finance.account_new"))
            if not _is_leaf_gl_account(ok_gl.id, company):
                flash(_("Somente contas contábeis de nível mais baixo podem receber transações."), "error")
                return redirect(url_for("finance.account_new"))

        cp_obj = None
        if counterparty_id:
            cp_obj = FinanceCounterparty.query.filter_by(id=counterparty_id, tenant_id=g.tenant.id).first()
        if not cp_obj and counterparty_name:
            cp_obj = FinanceCounterparty(tenant_id=g.tenant.id, company_id=company.id, name=counterparty_name, kind=counterparty_kind)
            db.session.add(cp_obj)
            db.session.flush()

        cp_id = cp_obj.id if cp_obj else None

        notes = (request.form.get("notes") or "").strip() or None

        if not name:
            flash(_("Nome é obrigatório."), "error")
            return redirect(url_for("finance.account_new"))

        def _parse_date(s: str):
            if not s:
                return None
            try:
                return datetime.strptime(s, "%Y-%m-%d").date()
            except Exception:
                return None

        acc = FinanceAccount(
            tenant_id=g.tenant.id,
            company_id=company.id,
            name=name,
            account_type=account_type,
            side=side,
            currency=currency,
            balance=Decimal(balance or "0"),
            limit_amount=Decimal(limit_amount) if limit_amount else None,
            is_interest_bearing=is_interest_bearing,
            annual_rate=Decimal(annual_rate) if annual_rate else None,
            rate_type=rate_type,
            repricing_date=_parse_date(repricing_date),
            maturity_date=_parse_date(maturity_date),
            counterparty_id=cp_id,
            counterparty=None,
            gl_account_id=gl_account_id,
            notes=notes,
        )
        db.session.add(acc)
        db.session.commit()
        flash(_("Conta criada."), "success")
        return redirect(url_for("finance.accounts_list"))

    return render_template(
        "finance/account_form.html",
        tenant=g.tenant,
        company=company,
        account=None,
        currencies=get_currencies(),
        counterparties=get_counterparties(company),
        gl_accounts=get_gl_accounts(company),
    )


@bp.route("/accounts/<int:account_id>")
@login_required
@require_roles("tenant_admin", "creator", "viewer")
def account_view(account_id: int):
    company = _get_company()
    acc = FinanceAccount.query.filter_by(id=account_id, tenant_id=g.tenant.id, company_id=company.id).first_or_404()
    page = request.args.get("page", 1, type=int)
    per_page = request.args.get("per_page", 25, type=int)
    per_page = min(max(per_page, 10), 200)

    pagination = (
        FinanceTransaction.query
        .filter_by(tenant_id=g.tenant.id, company_id=company.id, account_id=acc.id)
        .order_by(FinanceTransaction.txn_date.desc(), FinanceTransaction.id.desc())
        .paginate(page=page, per_page=per_page, error_out=False)
    )
    return render_template(
        "finance/account_view.html",
        tenant=g.tenant,
        company=company,
        account=acc,
        txns=pagination.items,
        pagination=pagination,
        per_page=per_page,
    )


@bp.route("/accounts/<int:account_id>/edit", methods=["GET", "POST"])
@login_required
@require_roles("tenant_admin", "creator")
def account_edit(account_id: int):
    company = _get_company()
    acc = FinanceAccount.query.filter_by(id=account_id, tenant_id=g.tenant.id, company_id=company.id).first_or_404()

    if request.method == "POST":
        acc.name = (request.form.get("name") or acc.name).strip()
        acc.account_type = (request.form.get("account_type") or acc.account_type).strip()
        acc.side = (request.form.get("side") or acc.side).strip()
        new_ccy = (request.form.get("currency") or acc.currency).strip().upper()
        if not FinanceCurrency.query.get(new_ccy):
            flash(_("Moeda inválida."), "error")
            return redirect(url_for("finance.account_edit", account_id=acc.id))
        acc.currency = new_ccy

        def _num(s: str, default: Decimal | None = None):
            s = (s or "").strip().replace(",", ".")
            if not s:
                return default
            try:
                return Decimal(s)
            except Exception:
                return default

        acc.balance = _num(request.form.get("balance"), Decimal("0"))
        acc.limit_amount = _num(request.form.get("limit_amount"), None)
        acc.is_interest_bearing = bool(request.form.get("is_interest_bearing"))
        acc.annual_rate = _num(request.form.get("annual_rate"), None)
        acc.rate_type = (request.form.get("rate_type") or acc.rate_type).strip()

        def _parse_date(s: str):
            s = (s or "").strip()
            if not s:
                return None
            try:
                return datetime.strptime(s, "%Y-%m-%d").date()
            except Exception:
                return None

        acc.repricing_date = _parse_date(request.form.get("repricing_date"))
        acc.maturity_date = _parse_date(request.form.get("maturity_date"))

        counterparty_id = int(request.form.get("counterparty_id") or 0)
        counterparty_name = (request.form.get("counterparty_name") or "").strip()
        counterparty_kind = (request.form.get("counterparty_kind") or "other").strip()

        cp_obj = None
        if counterparty_id:
            cp_obj = FinanceCounterparty.query.filter_by(id=counterparty_id, tenant_id=g.tenant.id).first()
        if not cp_obj and counterparty_name:
            cp_obj = FinanceCounterparty(tenant_id=g.tenant.id, company_id=company.id, name=counterparty_name, kind=counterparty_kind)
            db.session.add(cp_obj)
            db.session.flush()

        acc.counterparty_id = cp_obj.id if cp_obj else None
        acc.counterparty = None
        acc.notes = (request.form.get("notes") or "").strip() or None

        db.session.commit()
        flash(_("Conta atualizada."), "success")
        return redirect(url_for("finance.account_view", account_id=acc.id))

    return render_template(
        "finance/account_form.html",
        tenant=g.tenant,
        company=company,
        account=acc,
        currencies=get_currencies(),
        counterparties=get_counterparties(company),
        gl_accounts=get_gl_accounts(company),
    )


@bp.route("/accounts/<int:account_id>/delete", methods=["POST"])
@login_required
@require_roles("tenant_admin", "creator")
def account_delete(account_id: int):
    company = _get_company()
    acc = FinanceAccount.query.filter_by(id=account_id, tenant_id=g.tenant.id, company_id=company.id).first_or_404()
    db.session.delete(acc)
    db.session.commit()
    flash(_("Conta removida."), "success")
    return redirect(url_for("finance.accounts_list"))


# -----------------
# Transactions
# -----------------


@bp.route("/transactions/new", methods=["GET", "POST"])
@login_required
@require_roles("tenant_admin", "creator")
def transaction_new():
    company = _get_company()
    account_id = int(request.args.get("account_id") or request.form.get("account_id") or 0)
    acc = None
    if account_id:
        acc = FinanceAccount.query.filter_by(id=account_id, tenant_id=g.tenant.id, company_id=company.id).first()

    if request.method == "POST":
        if not account_id or not acc:
            flash(_("Selecione uma conta."), "error")
            return redirect(url_for("finance.accounts_list"))

        txn_date = (request.form.get("txn_date") or "").strip() or date.today().isoformat()
        amount = (request.form.get("amount") or "0").strip().replace(",", ".")
        description = (request.form.get("description") or "").strip() or None
        category = (request.form.get("category") or "").strip() or None
        counterparty_id = int(request.form.get("counterparty_id") or 0)
        counterparty_name = (request.form.get("counterparty_name") or "").strip()
        counterparty_kind = (request.form.get("counterparty_kind") or "other").strip()
        counterparty_text = (request.form.get("counterparty") or "").strip()

        cp_obj = None
        if counterparty_id:
            cp_obj = FinanceCounterparty.query.filter_by(id=counterparty_id, tenant_id=g.tenant.id).first()
        if not cp_obj and counterparty_name:
            cp_obj = FinanceCounterparty(tenant_id=g.tenant.id, company_id=company.id, name=counterparty_name, kind=counterparty_kind)
            db.session.add(cp_obj)
            db.session.flush()

        cp_id = cp_obj.id if cp_obj else None
        legacy_cp = None
        reference = (request.form.get("reference") or "").strip() or None

        try:
            d = datetime.strptime(txn_date, "%Y-%m-%d").date()
            amt = Decimal(amount)
        except Exception:
            flash(_("Dados inválidos."), "error")
            return redirect(url_for("finance.transaction_new", account_id=account_id))

        if not _ensure_transaction_quota(1):
            return redirect(url_for("finance.account_view", account_id=acc.id))

        t = FinanceTransaction(
            tenant_id=g.tenant.id,
            company_id=company.id,
            account_id=acc.id,
            txn_date=d,
            amount=amt,
            description=description,
            category=category,
            counterparty_id=cp_id,
            counterparty=legacy_cp,
            reference=reference,
        )
        db.session.add(t)
        db.session.commit()
        flash(_("Transação criada."), "success")
        return redirect(url_for("finance.account_view", account_id=acc.id))

    accounts = _q_accounts(company).order_by(FinanceAccount.name.asc()).all()
    return render_template(
        "finance/transaction_form.html",
        tenant=g.tenant,
        company=company,
        accounts=accounts,
        selected_account=acc,
        txn=None,
        counterparties=get_counterparties(company),
    )


@bp.route("/transactions/<int:txn_id>/delete", methods=["POST"])
@login_required
@require_roles("tenant_admin", "creator")
def transaction_delete(txn_id: int):
    company = _get_company()
    txn = FinanceTransaction.query.filter_by(id=txn_id, tenant_id=g.tenant.id, company_id=company.id).first_or_404()
    account_id = txn.account_id
    next_url = (request.form.get("next") or "").strip()
    db.session.delete(txn)
    db.session.commit()
    flash(_("Transação removida."), "success")
    if next_url.startswith("/") and not next_url.startswith("//"):
        return redirect(next_url)
    return redirect(url_for("finance.account_view", account_id=account_id))


@bp.route("/transactions/<int:txn_id>/edit", methods=["GET", "POST"])
@login_required
@require_roles("tenant_admin", "creator")
def transaction_edit(txn_id: int):
    company = _get_company()
    txn = FinanceTransaction.query.filter_by(id=txn_id, tenant_id=g.tenant.id, company_id=company.id).first_or_404()

    if request.method == "POST":
        account_id = int(request.form.get("account_id") or 0)
        acc = FinanceAccount.query.filter_by(id=account_id, tenant_id=g.tenant.id, company_id=company.id).first()
        if not account_id or not acc:
            flash(_("Selecione uma conta."), "error")
            return redirect(url_for("finance.transaction_edit", txn_id=txn.id))

        txn_date = (request.form.get("txn_date") or "").strip() or date.today().isoformat()
        amount = (request.form.get("amount") or "0").strip().replace(",", ".")
        description = (request.form.get("description") or "").strip() or None
        category = (request.form.get("category") or "").strip() or None
        counterparty_id = int(request.form.get("counterparty_id") or 0)
        counterparty_name = (request.form.get("counterparty_name") or "").strip()
        counterparty_kind = (request.form.get("counterparty_kind") or "other").strip()
        reference = (request.form.get("reference") or "").strip() or None

        cp_obj = None
        if counterparty_id:
            cp_obj = FinanceCounterparty.query.filter_by(id=counterparty_id, tenant_id=g.tenant.id).first()
        if not cp_obj and counterparty_name:
            cp_obj = FinanceCounterparty(tenant_id=g.tenant.id, company_id=company.id, name=counterparty_name, kind=counterparty_kind)
            db.session.add(cp_obj)
            db.session.flush()

        try:
            d = datetime.strptime(txn_date, "%Y-%m-%d").date()
            amt = Decimal(amount)
        except Exception:
            flash(_("Dados inválidos."), "error")
            return redirect(url_for("finance.transaction_edit", txn_id=txn.id))

        txn.account_id = acc.id
        txn.txn_date = d
        txn.amount = amt
        txn.description = description
        txn.category = category
        txn.counterparty_id = (cp_obj.id if cp_obj else None)
        txn.counterparty = None
        txn.reference = reference
        db.session.commit()
        flash(_("Transação atualizada."), "success")

        next_url = (request.form.get("next") or "").strip()
        if next_url.startswith("/") and not next_url.startswith("//"):
            return redirect(next_url)
        return redirect(url_for("finance.transactions_list"))

    accounts = _q_accounts(company).order_by(FinanceAccount.name.asc()).all()
    return render_template(
        "finance/transaction_form.html",
        tenant=g.tenant,
        company=company,
        accounts=accounts,
        selected_account=FinanceAccount.query.filter_by(id=txn.account_id, tenant_id=g.tenant.id, company_id=company.id).first(),
        txn=txn,
        counterparties=get_counterparties(company),
    )


@bp.route("/transactions/<int:txn_id>/set-category", methods=["POST"])
@login_required
@require_roles("tenant_admin", "creator")
def transaction_set_category(txn_id: int):
    company = _get_company()
    txn = FinanceTransaction.query.filter_by(id=txn_id, tenant_id=g.tenant.id, company_id=company.id).first_or_404()

    next_url = (request.form.get("next") or "").strip()
    if txn.ledger_voucher_id:
        flash(_("Impossible de modifier la catégorie d'une transaction déjà comptabilisée."), "error")
        if next_url.startswith("/") and not next_url.startswith("//"):
            return redirect(next_url)
        return redirect(url_for("finance.reports_transactions"))

    category_raw = (request.form.get("category_id") or "").strip()
    category_id = int(category_raw) if category_raw.isdigit() else None

    category_obj = None
    if category_id:
        category_obj = FinanceCategory.query.filter_by(
            id=category_id,
            tenant_id=g.tenant.id,
            company_id=company.id,
        ).first()
        if not category_obj:
            flash(_("Categoria inválida."), "error")
            if next_url.startswith("/") and not next_url.startswith("//"):
                return redirect(next_url)
            return redirect(url_for("finance.reports_transactions"))

    txn.category_id = category_obj.id if category_obj else None
    txn.category = category_obj.name if category_obj else None
    if category_obj and category_obj.default_gl_account_id:
        txn.gl_account_id = category_obj.default_gl_account_id
    db.session.commit()

    flash(_("Categoria da transação atualizada."), "success")
    if next_url.startswith("/") and not next_url.startswith("//"):
        return redirect(next_url)
    return redirect(url_for("finance.reports_transactions"))


@bp.route("/transactions/import", methods=["POST"])
@login_required
@require_roles("tenant_admin", "creator")
def transactions_import():
    company = _get_company()
    account_id = int(request.form.get("account_id") or 0)
    acc = FinanceAccount.query.filter_by(id=account_id, tenant_id=g.tenant.id, company_id=company.id).first()
    if not acc:
        flash(_("Selecione uma conta."), "error")
        return redirect(url_for("finance.accounts_list"))

    f = request.files.get("file")
    if not f:
        flash(_("Selecione um arquivo."), "error")
        return redirect(url_for("finance.account_view", account_id=acc.id))

    try:
        text = f.read().decode("utf-8", errors="ignore")
    except Exception:
        flash(_("Falha ao ler arquivo."), "error")
        return redirect(url_for("finance.account_view", account_id=acc.id))

    rows = parse_transactions_csv(text)
    if not rows:
        flash(_("Nenhuma linha válida encontrada."), "error")
        return redirect(url_for("finance.account_view", account_id=acc.id))

    allowed, remaining, current_count, max_limit = _transaction_quota_info()
    if not allowed or remaining <= 0:
        flash(_("Limite de transações do plano atingida ({current}/{max}).", current=current_count, max=max_limit), "error")
        return redirect(url_for("finance.account_view", account_id=acc.id))

    # Map counterparty names to directory entries (auto-create when needed)
    existing = { (cp.name or "").strip().lower(): cp for cp in get_counterparties(company) if (cp.name or "").strip() }

    n = 0
    for r in rows[:remaining]:
        cp_name = (r.get("counterparty") or "").strip()
        cp_obj = None
        if cp_name:
            key = cp_name.lower()
            cp_obj = existing.get(key)
            if not cp_obj:
                cp_obj = FinanceCounterparty(tenant_id=g.tenant.id, company_id=company.id, name=cp_name, kind="other")
                db.session.add(cp_obj)
                db.session.flush()
                existing[key] = cp_obj

        db.session.add(
            FinanceTransaction(
                tenant_id=g.tenant.id,
                company_id=company.id,
                account_id=acc.id,
                txn_date=r["txn_date"],
                amount=r["amount"],
                description=r.get("description"),
                category=r.get("category"),
                counterparty_id=cp_obj.id if cp_obj else None,
                counterparty=None if cp_obj else (cp_name or None),
                reference=r.get("reference"),
            )
        )
        n += 1

    db.session.commit()
    flash(_("Importação concluída: {n} linhas.", n=n), "success")
    if len(rows) > remaining:
        flash(_("Importação limitada pelo plano: {n} linhas não importadas.", n=(len(rows) - remaining)), "warning")
    return redirect(url_for("finance.account_view", account_id=acc.id))


@bp.route("/transactions", methods=["GET"])
@login_required
@require_roles("tenant_admin", "creator", "viewer")
def transactions_list():
    """List transactions with pagination and advanced filters."""
    company = _get_company()
    
    # Get filter parameters
    page = request.args.get("page", 1, type=int)
    per_page = request.args.get("per_page", 50, type=int)
    per_page = min(per_page, 500)  # Max 500 per page
    
    account_id = request.args.get("account_id", type=int)
    category_id = request.args.get("category_id", type=int)
    counterparty_id = request.args.get("counterparty_id", type=int)
    txn_type = request.args.get("type")  # "inflow" or "outflow"
    start_date = request.args.get("start_date")
    end_date = request.args.get("end_date")
    
    # Build query
    query = _q_txns(company).options(
        joinedload(FinanceTransaction.account),
        joinedload(FinanceTransaction.category_ref),
        joinedload(FinanceTransaction.counterparty_ref)
    )
    
    # Apply filters
    if account_id:
        query = query.filter(FinanceTransaction.account_id == account_id)
    
    if category_id:
        query = query.filter(FinanceTransaction.category_id == category_id)
    
    if counterparty_id:
        query = query.filter(FinanceTransaction.counterparty_id == counterparty_id)
    
    if txn_type == "inflow":
        query = query.filter(FinanceTransaction.amount >= 0)
    elif txn_type == "outflow":
        query = query.filter(FinanceTransaction.amount < 0)
    
    if start_date:
        try:
            sd = datetime.strptime(start_date, "%Y-%m-%d").date()
            query = query.filter(FinanceTransaction.txn_date >= sd)
        except Exception:
            pass
    
    if end_date:
        try:
            ed = datetime.strptime(end_date, "%Y-%m-%d").date()
            query = query.filter(FinanceTransaction.txn_date <= ed)
        except Exception:
            pass
    
    # Order and paginate
    pagination = query.order_by(FinanceTransaction.txn_date.desc(), FinanceTransaction.id.desc()).paginate(
        page=page, per_page=per_page, error_out=False
    )
    
    # Get filter options
    accounts = _q_accounts(company).order_by(FinanceAccount.name).all()
    categories = FinanceCategory.query.filter_by(tenant_id=g.tenant.id, company_id=company.id).order_by(FinanceCategory.name).all()
    counterparties = FinanceCounterparty.query.filter_by(tenant_id=g.tenant.id, company_id=company.id).order_by(FinanceCounterparty.name).all()
    
    return render_template(
        "finance/transactions_list.html",
        tenant=g.tenant,
        company=company,
        pagination=pagination,
        accounts=accounts,
        categories=categories,
        counterparties=counterparties,
        account_id=account_id,
        category_id=category_id,
        counterparty_id=counterparty_id,
        txn_type=txn_type,
        start_date=start_date,
        end_date=end_date,
        per_page=per_page,
    )


# -----------------
# Help and settings
# -----------------


@bp.route("/help")
@login_required
@require_roles("tenant_admin", "creator", "viewer")
def help_page():
    company = _get_company()
    return render_template("finance/help.html", tenant=g.tenant, company=company)


@bp.route("/help/chat", methods=["POST"])
@login_required
@require_roles("tenant_admin", "creator", "viewer")
def help_chat():
    _get_company()
    data = request.get_json(silent=True) or {}
    message = (data.get("message") or "").strip()
    if not message:
        return jsonify({"ok": False, "error": _("Mensagem vazia.")}), 400

    text = message.lower()
    help_url = url_for("finance.help_page")

    if any(k in text for k in ["cashflow", "caixa", "tresor", "trésor", "tesorer", "treasury"]):
        reply = _(
            "Cashflow: entradas são positivas, saídas negativas. Você pode filtrar por conta, categoria e período na lista de transações."
        )
    elif any(k in text for k in ["liquidez", "liquidity", "liquidit", "liquidit", "liquidità"]):
        reply = _(
            "Liquidez: a visão estima caixa disponível por horizonte de tempo com base em contas, passivos e vencimentos informados."
        )
    elif any(k in text for k in ["gap", "gaps"]):
        reply = _(
            "GAP: mostra entradas menos saídas por bucket de tempo e também o acumulado para analisar pressão de liquidez."
        )
    elif any(k in text for k in ["nii", "juros", "interest", "intérêt", "interes", "interesse"]):
        reply = _(
            "NII: estima receita de juros menos custo de juros usando saldo, annual_rate e período."
        )
    elif any(k in text for k in ["recon", "reconc", "reconcil", "conciliation"]):
        reply = _(
            "Reconciliação: importe o extrato bancário, faça o match com transações e revise divergências antes de concluir."
        )
    elif any(k in text for k in ["plano", "conta", "chart of accounts", "coa", "gl", "ledger"]):
        reply = _(
            "Plano de contas: use a hierarquia por arrastar e soltar. Apenas contas de nível mais baixo aceitam lançamentos."
        )
    elif any(k in text for k in ["fatura", "invoice", "facture", "fattura", "factura"]):
        reply = _(
            "E-faturas: crie a fatura, valide os campos obrigatórios e exporte conforme o formato suportado."
        )
    else:
        reply = _(
            "Posso ajudar com Cashflow, Liquidez, GAP, NII, Reconciliação, Plano de contas e E-faturas."
        )

    reply = f"{reply} {_('Veja também a página de ajuda completa')}: {help_url}"
    suggestions = [
        _("Como funciona o cashflow?"),
        _("Como interpretar a liquidez?"),
        _("Como fazer reconciliação bancária?"),
        _("Onde configuro o plano de contas?"),
    ]
    return jsonify({"ok": True, "reply": reply, "suggestions": suggestions})


@bp.route("/settings/currencies", methods=["GET", "POST"])
@login_required
@require_roles("tenant_admin", "creator")
def currencies_settings():
    company = _get_company()
    ensure_default_currencies()

    if request.method == "POST":
        code = (request.form.get("code") or "").strip().upper()
        name = (request.form.get("name") or "").strip() or None
        symbol = (request.form.get("symbol") or "").strip() or None
        decimals = int(request.form.get("decimals") or 2)

        if not code:
            flash(_("Código é obrigatório."), "error")
            return redirect(url_for("finance.currencies_settings"))

        if FinanceCurrency.query.get(code):
            flash(_("Moeda já existe."), "error")
            return redirect(url_for("finance.currencies_settings"))

        db.session.add(FinanceCurrency(code=code, name=name, symbol=symbol, decimals=decimals))
        db.session.commit()
        flash(_("Moeda adicionada."), "success")
        return redirect(url_for("finance.currencies_settings"))

    currencies = FinanceCurrency.query.order_by(FinanceCurrency.code.asc()).all()
    return render_template(
        "finance/settings_currencies.html",
        tenant=g.tenant,
        company=company,
        currencies=currencies,
    )


@bp.route("/settings/counterparties", methods=["GET", "POST"])
@login_required
@require_roles("tenant_admin", "creator")
def counterparties_settings():
    company = _get_company()

    if request.method == "POST":
        name = (request.form.get("name") or "").strip()
        kind = (request.form.get("kind") or "other").strip()
        default_currency = (request.form.get("default_currency") or "").strip().upper() or None

        if not name:
            flash(_("Nome é obrigatório."), "error")
            return redirect(url_for("finance.counterparties_settings"))

        if default_currency and not FinanceCurrency.query.get(default_currency):
            flash(_("Moeda inválida."), "error")
            return redirect(url_for("finance.counterparties_settings"))

        # Avoid duplicates within company scope
        if FinanceCounterparty.query.filter_by(tenant_id=g.tenant.id, company_id=company.id, name=name).first():
            flash(_("Contraparte já existe."), "error")
            return redirect(url_for("finance.counterparties_settings"))

        db.session.add(
            FinanceCounterparty(
                tenant_id=g.tenant.id,
                company_id=company.id,
                name=name,
                kind=kind,
                default_currency=default_currency,
            )
        )
        db.session.commit()
        flash(_("Contraparte adicionada."), "success")
        return redirect(url_for("finance.counterparties_settings"))

    counterparties = get_counterparties(company)
    currencies = get_currencies()
    return render_template(
        "finance/settings_counterparties.html",
        tenant=g.tenant,
        company=company,
        counterparties=counterparties,
        currencies=currencies,
    )


@bp.route("/settings/counterparties/<int:cp_id>/delete", methods=["POST"])
@login_required
@require_roles("tenant_admin", "creator")
def counterparty_delete(cp_id: int):
    company = _get_company()
    cp = FinanceCounterparty.query.filter_by(id=cp_id, tenant_id=g.tenant.id).first_or_404()
    # Optional: only allow deleting company-scoped records
    if cp.company_id not in (None, company.id):
        abort(403)
    db.session.delete(cp)
    db.session.commit()
    flash(_("Contraparte removida."), "success")
    return redirect(url_for("finance.counterparties_settings"))


# -----------------
# Bank statement PDF import
# -----------------


@bp.route("/accounts/<int:account_id>/import-statement", methods=["GET", "POST"])
@login_required
@require_roles("tenant_admin", "creator")
def statement_import(account_id: int):
    company = _get_company()
    acc = FinanceAccount.query.filter_by(id=account_id, tenant_id=g.tenant.id, company_id=company.id).first_or_404()
    csv_setting_key = f"csv_import_mapping_account_{acc.id}"
    csv_mapping_preset = {}
    csv_setting = FinanceSetting.query.filter_by(
        tenant_id=g.tenant.id,
        company_id=company.id,
        key=csv_setting_key,
    ).first()
    if csv_setting and isinstance(csv_setting.value_json, dict):
        csv_mapping_preset = csv_setting.value_json

    if request.method == "POST":
        import_mode = (request.form.get("import_mode") or "pdf").strip().lower()
        provider = "openai"
        bank = (request.form.get("bank") or "auto").strip().lower()
        bank_hint = None if bank in ("", "auto", "detect") else bank

        f = request.files.get("file")
        if not f:
            flash(_("Selecione um arquivo."), "error")
            return redirect(url_for("finance.statement_import", account_id=acc.id))

        filename = secure_filename(f.filename or ("transactions.csv" if import_mode == "csv" else "statement.pdf"))
        file_bytes = f.read() or b""
        if not file_bytes:
            flash(_("Falha ao ler arquivo."), "error")
            return redirect(url_for("finance.statement_import", account_id=acc.id))

        rows: list[dict] = []
        payload: dict = {"provider": provider, "bank_hint": bank_hint or "auto", "import_mode": import_mode}

        if import_mode == "csv":
            csv_delimiter = (request.form.get("csv_delimiter") or "auto").strip().lower()
            csv_date_format = (request.form.get("csv_date_format") or "auto").strip().lower()
            save_csv_mapping = (request.form.get("save_csv_mapping") or "").strip() in ("1", "true", "on", "yes")
            mapping = {
                "date": (request.form.get("map_date") or "").strip(),
                "amount": (request.form.get("map_amount") or "").strip(),
                "description": (request.form.get("map_description") or "").strip(),
                "category": (request.form.get("map_category") or "").strip(),
                "counterparty": (request.form.get("map_counterparty") or "").strip(),
                "reference": (request.form.get("map_reference") or "").strip(),
            }
            if not mapping["date"] or not mapping["amount"]:
                flash(_("Mapeie ao menos as colunas de data e valor."), "error")
                return redirect(url_for("finance.statement_import", account_id=acc.id))
            try:
                text = file_bytes.decode("utf-8")
            except UnicodeDecodeError:
                text = file_bytes.decode("latin-1", errors="ignore")
            rows = parse_transactions_csv_mapped(
                text,
                mapping,
                delimiter=csv_delimiter,
                date_format=csv_date_format,
            )
            payload["csv_mapping"] = mapping
            payload["csv_delimiter"] = csv_delimiter
            payload["csv_date_format"] = csv_date_format
            payload["provider"] = "csv"
            provider = "csv"

            if save_csv_mapping:
                preset_payload = {
                    "mapping": mapping,
                    "delimiter": csv_delimiter,
                    "date_format": csv_date_format,
                }
                if not csv_setting:
                    csv_setting = FinanceSetting(
                        tenant_id=g.tenant.id,
                        company_id=company.id,
                        key=csv_setting_key,
                        value_json=preset_payload,
                    )
                    db.session.add(csv_setting)
                else:
                    csv_setting.value_json = preset_payload
                db.session.commit()
        else:
            pdf_bytes = file_bytes
            gv_key = (current_app.config.get("GOOGLE_VISION_API_KEY") or "").strip() or None
            try:
                bank_detected, parsed_rows, meta = parse_bank_statement_pdf_via_openai(
                    pdf_bytes,
                    filename=filename,
                    default_currency=(acc.currency or company.base_currency or "EUR"),
                    bank_hint=bank_hint,
                    google_vision_api_key=gv_key,
                    max_pages=10,
                )
                payload["bank_detected"] = bank_detected
                payload["meta"] = meta
                rows = parsed_rows
            except OpenAIStatementError as j:
                # Missing key, timeout, schema errors, or OpenAI failure.
                current_app.logger.warning("OpenAI statement parse failed: %s", str(j))
                msg = (str(j) or "").strip()
                if len(msg) > 260:
                    msg = msg[:260] + "…"
                # Show the underlying error message to the user (truncated).
                flash(_("Falha ao importar via OpenAI: {msg}", msg=msg), "error")
                return redirect(url_for("finance.statement_import", account_id=acc.id))
            except StatementImportError:
                flash(_("Falha ao extrair texto do PDF. Tente OCR ou um PDF com texto."), "error")
                return redirect(url_for("finance.statement_import", account_id=acc.id))
            except Exception as e:
                payload["openai_error"] = str(e)[:250]
                msg = (str(e) or "").strip()
                if len(msg) > 260:
                    msg = msg[:260] + "…"
                flash(_("Falha ao importar via OpenAI: {msg}", msg=msg), "error")
                return redirect(url_for("finance.statement_import", account_id=acc.id))

        if not rows:
            flash(_("Nenhuma linha válida encontrada."), "error")
            return redirect(url_for("finance.statement_import", account_id=acc.id))

        # Dedupe existing transactions in date range
        min_d = min(r["txn_date"] for r in rows)
        max_d = max(r["txn_date"] for r in rows)
        existing = (
            FinanceTransaction.query
            .filter_by(tenant_id=g.tenant.id, company_id=company.id, account_id=acc.id)
            .filter(FinanceTransaction.txn_date >= min_d)
            .filter(FinanceTransaction.txn_date <= max_d)
            .all()
        )
        existing_sigs = set(
            (e.txn_date, str(e.amount), (e.description or "").strip(), (e.reference or "").strip())
            for e in existing
        )

        # Map counterparties and categories
        cp_map = {(cp.name or "").strip().lower(): cp for cp in get_counterparties(company) if (cp.name or "").strip()}
        cats = get_categories(company)
        cat_by_name = {(c.name or "").strip().lower(): c for c in cats if (c.name or "").strip()}

        created = 0
        skipped = 0
        allowed, remaining, current_count, max_limit = _transaction_quota_info()
        if not allowed or remaining <= 0:
            flash(_("Limite de transações do plano atingida ({current}/{max}).", current=current_count, max=max_limit), "error")
            return redirect(url_for("finance.account_view", account_id=acc.id))

        for r in rows:
            if created >= remaining:
                break
            sig = (r["txn_date"], str(r["amount"]), (r.get("description") or "").strip(), (r.get("reference") or "").strip())
            if sig in existing_sigs:
                skipped += 1
                continue

            cp_name = (r.get("counterparty") or "").strip()
            cp_obj = None
            if cp_name:
                k = cp_name.lower()
                cp_obj = cp_map.get(k)
                if not cp_obj:
                    cp_obj = FinanceCounterparty(tenant_id=g.tenant.id, company_id=company.id, name=cp_name, kind="other")
                    db.session.add(cp_obj)
                    db.session.flush()
                    cp_map[k] = cp_obj

            # Category mapping (statement category string OR rules)
            cat_obj = None
            cat_name = (r.get("category") or "").strip()
            if cat_name:
                cat_obj = cat_by_name.get(cat_name.lower())
                if not cat_obj:
                    cat_obj = FinanceCategory(tenant_id=g.tenant.id, company_id=company.id, code=None, name=cat_name)
                    db.session.add(cat_obj)
                    db.session.flush()
                    cat_by_name[cat_name.lower()] = cat_obj
            if not cat_obj:
                cat_id = apply_category_rules(
                    company,
                    description=r.get("description") or "",
                    counterparty_id=cp_obj.id if cp_obj else None,
                    amount=float(r["amount"]),
                    counterparty_name=cp_name,
                )
                if cat_id:
                    cat_obj = FinanceCategory.query.filter_by(id=cat_id, tenant_id=g.tenant.id, company_id=company.id).first()

            gl_account_id = None
            if cat_obj and cat_obj.default_gl_account_id:
                gl_account_id = cat_obj.default_gl_account_id

            txn_preview = FinanceTransaction(
                tenant_id=g.tenant.id,
                company_id=company.id,
                account_id=acc.id,
                txn_date=r["txn_date"],
                amount=r["amount"],
                description=r.get("description"),
                category=r.get("category") or (cat_obj.name if cat_obj else None),
                category_id=cat_obj.id if cat_obj else None,
                gl_account_id=gl_account_id,
                counterparty_id=cp_obj.id if cp_obj else None,
                counterparty=None if cp_obj else (cp_name or None),
                reference=r.get("reference"),
            )
            if txn_preview.gl_account_id is None:
                txn_preview.gl_account_id = select_gl_account_by_rules(company, txn_preview)

            db.session.add(txn_preview)
            created += 1
            existing_sigs.add(sig)

        # Track import
        imp = FinanceStatementImport(
            tenant_id=g.tenant.id,
            company_id=company.id,
            account_id=acc.id,
            filename=filename,
            provider=provider,
            imported_rows=created,
            skipped_rows=skipped,
            payload_json=payload,
        )
        db.session.add(imp)
        db.session.commit()

        flash(_("Importação concluída: {n} linhas.", n=created), "success")
        if created >= remaining and (len(rows) - skipped) > created:
            flash(_("Importação limitada pelo plano de transações."), "warning")
        if skipped:
            flash(_("Linhas ignoradas (duplicadas): {n}.", n=skipped), "info")
        return redirect(url_for("finance.account_view", account_id=acc.id))

    return render_template(
        "finance/statement_import.html",
        tenant=g.tenant,
        company=company,
        account=acc,
        csv_mapping_preset=csv_mapping_preset,
    )



# -----------------
# Master data CSV imports (products, counterparties, financings, investments, accounts)
# -----------------


def _master_import_entities() -> dict:
    return {
        "products": {
            "label": "Produits",
            "fields": [
                {"key": "code", "label": "Code", "required": False, "sample": "PRD-001"},
                {"key": "name", "label": "Nom", "required": True, "sample": "Conseil mensuel"},
                {"key": "description", "label": "Description", "required": False, "sample": "Abonnement support"},
                {"key": "product_type", "label": "Type produit", "required": False, "sample": "service"},
                {"key": "unit_price", "label": "Prix unitaire", "required": False, "sample": "1200.00"},
                {"key": "currency_code", "label": "Devise", "required": False, "sample": "EUR"},
                {"key": "vat_rate", "label": "TVA %", "required": False, "sample": "20"},
                {"key": "status", "label": "Statut", "required": False, "sample": "active"},
                {"key": "notes", "label": "Notes", "required": False, "sample": ""},
            ],
        },
        "counterparties": {
            "label": "Contreparties",
            "fields": [
                {"key": "name", "label": "Nom", "required": True, "sample": "Client Alpha"},
                {"key": "kind", "label": "Type", "required": False, "sample": "customer"},
                {"key": "email", "label": "Email", "required": False, "sample": "finance@alpha.com"},
                {"key": "phone", "label": "Téléphone", "required": False, "sample": "+33 1 00 00 00 00"},
                {"key": "vat_number", "label": "TVA", "required": False, "sample": "FR12345678901"},
                {"key": "tax_id", "label": "Tax ID", "required": False, "sample": "123456789"},
                {"key": "address_line1", "label": "Adresse 1", "required": False, "sample": "1 rue de Paris"},
                {"key": "address_line2", "label": "Adresse 2", "required": False, "sample": ""},
                {"key": "postal_code", "label": "Code postal", "required": False, "sample": "75001"},
                {"key": "city", "label": "Ville", "required": False, "sample": "Paris"},
                {"key": "state", "label": "Région", "required": False, "sample": "Île-de-France"},
                {"key": "country_code", "label": "Pays", "required": False, "sample": "FR"},
                {"key": "sdi_code", "label": "SDI", "required": False, "sample": "0000000"},
                {"key": "pec_email", "label": "PEC email", "required": False, "sample": ""},
            ],
        },
        "financings": {
            "label": "Financements",
            "fields": [
                {"key": "name", "label": "Nom", "required": True, "sample": "Prêt BPI 2026"},
                {"key": "lender", "label": "Prêteur", "required": False, "sample": "Banque X"},
                {"key": "currency_code", "label": "Devise", "required": False, "sample": "EUR"},
                {"key": "principal_amount", "label": "Principal", "required": False, "sample": "100000"},
                {"key": "outstanding_amount", "label": "Encours", "required": False, "sample": "92000"},
                {"key": "interest_rate", "label": "Taux %", "required": False, "sample": "3.25"},
                {"key": "start_date", "label": "Date début", "required": False, "sample": "2026-01-15"},
                {"key": "maturity_date", "label": "Date échéance", "required": False, "sample": "2031-01-15"},
                {"key": "payment_frequency", "label": "Fréquence", "required": False, "sample": "monthly"},
                {"key": "installment_amount", "label": "Mensualité", "required": False, "sample": "1800"},
                {"key": "next_payment_date", "label": "Prochain paiement", "required": False, "sample": "2026-04-15"},
                {"key": "notes", "label": "Notes", "required": False, "sample": ""},
            ],
        },
        "investments": {
            "label": "Investissements",
            "fields": [
                {"key": "name", "label": "Nom", "required": True, "sample": "ETF World"},
                {"key": "provider", "label": "Provider", "required": False, "sample": "stock_exchange"},
                {"key": "instrument_code", "label": "Code instrument", "required": False, "sample": "EWLD.PA"},
                {"key": "account_name", "label": "Compte", "required": False, "sample": "Banque principale"},
                {"key": "currency_code", "label": "Devise", "required": False, "sample": "EUR"},
                {"key": "invested_amount", "label": "Montant investi", "required": False, "sample": "5000"},
                {"key": "current_value", "label": "Valeur actuelle", "required": False, "sample": "5200"},
                {"key": "started_on", "label": "Date début", "required": False, "sample": "2026-02-01"},
                {"key": "status", "label": "Statut", "required": False, "sample": "active"},
                {"key": "notes", "label": "Notes", "required": False, "sample": ""},
            ],
        },
        "accounts": {
            "label": "Comptes (loan/deposit/credit line)",
            "fields": [
                {"key": "name", "label": "Nom", "required": True, "sample": "Ligne de crédit A"},
                {"key": "account_type", "label": "Type compte", "required": False, "sample": "credit_line"},
                {"key": "side", "label": "Side", "required": False, "sample": "liability"},
                {"key": "currency", "label": "Devise", "required": False, "sample": "EUR"},
                {"key": "balance", "label": "Solde", "required": False, "sample": "0"},
                {"key": "limit_amount", "label": "Limite", "required": False, "sample": "20000"},
                {"key": "counterparty", "label": "Contrepartie", "required": False, "sample": "Banque X"},
                {"key": "iban", "label": "IBAN", "required": False, "sample": ""},
                {"key": "bic", "label": "BIC", "required": False, "sample": ""},
                {"key": "is_interest_bearing", "label": "Porte intérêt", "required": False, "sample": "true"},
                {"key": "annual_rate", "label": "Taux annuel", "required": False, "sample": "0.035"},
                {"key": "rate_type", "label": "Type taux", "required": False, "sample": "fixed"},
                {"key": "repricing_date", "label": "Date repricing", "required": False, "sample": ""},
                {"key": "maturity_date", "label": "Date échéance", "required": False, "sample": "2030-12-31"},
                {"key": "notes", "label": "Notes", "required": False, "sample": ""},
            ],
        },
    }


def _master_import_setting_key(entity: str) -> str:
    return f"master_import_template_{entity}"


def _master_import_value(row: dict, mapping: dict, key: str) -> str:
    col = str(mapping.get(key) or "").strip()
    if not col:
        return ""
    return str(row.get(col) or "").strip()


def _parse_csv_rows(file_bytes: bytes, delimiter_mode: str = "auto") -> tuple[list[str], list[dict], str]:
    try:
        text = file_bytes.decode("utf-8")
    except UnicodeDecodeError:
        text = file_bytes.decode("latin-1", errors="ignore")

    sample = text[:4096]
    delimiter_map = {
        "comma": ",",
        "semicolon": ";",
        "tab": "\t",
        "pipe": "|",
    }
    if delimiter_mode == "auto":
        try:
            sniff = csv.Sniffer().sniff(sample, delimiters=",;\t|")
            delimiter = sniff.delimiter
        except Exception:
            delimiter = ","
    else:
        delimiter = delimiter_map.get(delimiter_mode, ",")

    reader = csv.DictReader(text.splitlines(), delimiter=delimiter)
    headers = [str(h or "").strip() for h in (reader.fieldnames or []) if str(h or "").strip()]
    rows: list[dict] = []
    for row in reader:
        normalized = {str(k or "").strip(): str(v or "").strip() for k, v in row.items() if str(k or "").strip()}
        if any(v for v in normalized.values()):
            rows.append(normalized)
    return headers, rows, delimiter


def _parse_decimal_safe(value: str | None) -> Decimal | None:
    raw = (value or "").strip()
    if not raw:
        return None
    return Decimal(raw.replace(",", "."))


def _parse_date_safe(value: str | None) -> date | None:
    raw = (value or "").strip()
    if not raw:
        return None
    return date.fromisoformat(raw)


def _parse_bool_safe(value: str | None) -> bool | None:
    raw = (value or "").strip().lower()
    if not raw:
        return None
    if raw in {"1", "true", "yes", "y", "on", "oui", "vrai"}:
        return True
    if raw in {"0", "false", "no", "n", "off", "non", "faux"}:
        return False
    return None


def _import_master_data_row(entity: str, company: FinanceCompany, row: dict, mapping: dict) -> str:
    if entity == "products":
        name = _master_import_value(row, mapping, "name")
        code = _master_import_value(row, mapping, "code")
        if not name:
            raise ValueError("missing name")
        product = None
        if code:
            product = (
                FinanceProduct.query
                .filter_by(tenant_id=g.tenant.id, company_id=company.id, code=code)
                .first()
            )
        if not product:
            product = (
                FinanceProduct.query
                .filter_by(tenant_id=g.tenant.id, company_id=company.id, name=name)
                .first()
            )
        created = product is None
        if created:
            product = FinanceProduct(
                tenant_id=g.tenant.id,
                company_id=company.id,
                name=name,
                unit_price=Decimal("0"),
                currency_code=company.base_currency or "EUR",
            )
            db.session.add(product)

        product.code = code or product.code
        product.name = name
        product.description = _master_import_value(row, mapping, "description") or product.description
        product.product_type = (_master_import_value(row, mapping, "product_type") or product.product_type or "service").lower()
        product.currency_code = (_master_import_value(row, mapping, "currency_code") or product.currency_code or company.base_currency or "EUR").upper()
        product.status = (_master_import_value(row, mapping, "status") or product.status or "active").lower()
        product.notes = _master_import_value(row, mapping, "notes") or product.notes
        up = _parse_decimal_safe(_master_import_value(row, mapping, "unit_price"))
        if up is not None:
            product.unit_price = up
        vat = _parse_decimal_safe(_master_import_value(row, mapping, "vat_rate"))
        if vat is not None:
            product.vat_rate = vat
            product.vat_applies = vat > 0
        return "created" if created else "updated"

    if entity == "counterparties":
        name = _master_import_value(row, mapping, "name")
        if not name:
            raise ValueError("missing name")
        cp = (
            FinanceCounterparty.query
            .filter_by(tenant_id=g.tenant.id, company_id=company.id)
            .filter(func.lower(FinanceCounterparty.name) == name.lower())
            .first()
        )
        created = cp is None
        if created:
            cp = FinanceCounterparty(tenant_id=g.tenant.id, company_id=company.id, name=name, kind="other")
            db.session.add(cp)

        cp.name = name
        cp.kind = (_master_import_value(row, mapping, "kind") or cp.kind or "other").lower()
        cp.email = _master_import_value(row, mapping, "email") or cp.email
        cp.phone = _master_import_value(row, mapping, "phone") or cp.phone
        cp.vat_number = _master_import_value(row, mapping, "vat_number") or cp.vat_number
        cp.tax_id = _master_import_value(row, mapping, "tax_id") or cp.tax_id
        cp.address_line1 = _master_import_value(row, mapping, "address_line1") or cp.address_line1
        cp.address_line2 = _master_import_value(row, mapping, "address_line2") or cp.address_line2
        cp.postal_code = _master_import_value(row, mapping, "postal_code") or cp.postal_code
        cp.city = _master_import_value(row, mapping, "city") or cp.city
        cp.state = _master_import_value(row, mapping, "state") or cp.state
        cc = (_master_import_value(row, mapping, "country_code") or cp.country_code or "").upper()
        cp.country_code = cc[:2] if cc else cp.country_code
        cp.sdi_code = _master_import_value(row, mapping, "sdi_code") or cp.sdi_code
        cp.pec_email = _master_import_value(row, mapping, "pec_email") or cp.pec_email
        return "created" if created else "updated"

    if entity == "financings":
        name = _master_import_value(row, mapping, "name")
        if not name:
            raise ValueError("missing name")
        liability = (
            FinanceLiability.query
            .filter_by(tenant_id=g.tenant.id, company_id=company.id)
            .filter(func.lower(FinanceLiability.name) == name.lower())
            .first()
        )
        created = liability is None
        if created:
            liability = FinanceLiability(tenant_id=g.tenant.id, company_id=company.id, name=name)
            db.session.add(liability)

        lender = _find_or_create_counterparty(company, _master_import_value(row, mapping, "lender"))
        liability.name = name
        liability.lender_counterparty_id = lender.id if lender else liability.lender_counterparty_id
        liability.currency_code = (_master_import_value(row, mapping, "currency_code") or liability.currency_code or company.base_currency or "EUR").upper()
        liability.notes = _master_import_value(row, mapping, "notes") or liability.notes
        freq = (_master_import_value(row, mapping, "payment_frequency") or liability.payment_frequency or "monthly").lower()
        liability.payment_frequency = freq if freq in {"monthly", "quarterly", "yearly", "other"} else "monthly"

        principal = _parse_decimal_safe(_master_import_value(row, mapping, "principal_amount"))
        if principal is not None:
            liability.principal_amount = principal
        outstanding = _parse_decimal_safe(_master_import_value(row, mapping, "outstanding_amount"))
        if outstanding is not None:
            liability.outstanding_amount = outstanding
        rate = _parse_decimal_safe(_master_import_value(row, mapping, "interest_rate"))
        if rate is not None:
            liability.interest_rate = rate
        installment = _parse_decimal_safe(_master_import_value(row, mapping, "installment_amount"))
        if installment is not None:
            liability.installment_amount = installment

        start_dt = _parse_date_safe(_master_import_value(row, mapping, "start_date"))
        if start_dt is not None:
            liability.start_date = start_dt
        maturity_dt = _parse_date_safe(_master_import_value(row, mapping, "maturity_date"))
        if maturity_dt is not None:
            liability.maturity_date = maturity_dt
        next_pay_dt = _parse_date_safe(_master_import_value(row, mapping, "next_payment_date"))
        if next_pay_dt is not None:
            liability.next_payment_date = next_pay_dt
        return "created" if created else "updated"

    if entity == "investments":
        name = _master_import_value(row, mapping, "name")
        if not name:
            raise ValueError("missing name")
        if not _investments_table_available(company):
            raise ValueError("investments table unavailable")

        instrument_code = _master_import_value(row, mapping, "instrument_code")
        investment = (
            FinanceInvestment.query
            .filter_by(tenant_id=g.tenant.id, company_id=company.id)
            .filter(func.lower(FinanceInvestment.name) == name.lower())
            .first()
        )
        if not investment and instrument_code:
            investment = (
                FinanceInvestment.query
                .filter_by(tenant_id=g.tenant.id, company_id=company.id, instrument_code=instrument_code)
                .first()
            )

        created = investment is None
        if created:
            investment = FinanceInvestment(
                tenant_id=g.tenant.id,
                company_id=company.id,
                name=name,
                provider="stock_exchange",
                invested_amount=Decimal("0"),
                status="active",
            )
            db.session.add(investment)

        account_name = _master_import_value(row, mapping, "account_name")
        if account_name:
            acc = (
                FinanceAccount.query
                .filter_by(tenant_id=g.tenant.id, company_id=company.id)
                .filter(func.lower(FinanceAccount.name) == account_name.lower())
                .first()
            )
            if not acc:
                raise ValueError(f"account not found: {account_name}")
            investment.account_id = acc.id

        investment.name = name
        investment.instrument_code = instrument_code or investment.instrument_code
        provider = (_master_import_value(row, mapping, "provider") or investment.provider or "stock_exchange").lower()
        investment.provider = provider if provider in {"edf", "stock_exchange"} else "stock_exchange"
        investment.currency_code = (_master_import_value(row, mapping, "currency_code") or investment.currency_code or company.base_currency or "EUR").upper()
        investment.notes = _master_import_value(row, mapping, "notes") or investment.notes
        status = (_master_import_value(row, mapping, "status") or investment.status or "active").lower()
        investment.status = status if status in {"active", "closed"} else "active"

        invested = _parse_decimal_safe(_master_import_value(row, mapping, "invested_amount"))
        if invested is not None:
            investment.invested_amount = abs(invested)
        current_val = _parse_decimal_safe(_master_import_value(row, mapping, "current_value"))
        if current_val is not None:
            investment.current_value = current_val
        started = _parse_date_safe(_master_import_value(row, mapping, "started_on"))
        if started is not None:
            investment.started_on = started

        return "created" if created else "updated"

    if entity == "accounts":
        name = _master_import_value(row, mapping, "name")
        if not name:
            raise ValueError("missing name")
        account = (
            FinanceAccount.query
            .filter_by(tenant_id=g.tenant.id, company_id=company.id)
            .filter(func.lower(FinanceAccount.name) == name.lower())
            .first()
        )
        created = account is None
        if created:
            account = FinanceAccount(
                tenant_id=g.tenant.id,
                company_id=company.id,
                name=name,
                account_type="bank",
                side="asset",
                currency=company.base_currency or "EUR",
                balance=Decimal("0"),
            )
            db.session.add(account)

        account.name = name
        acc_type = (_master_import_value(row, mapping, "account_type") or account.account_type or "bank").lower()
        if acc_type not in {"cash", "bank", "loan", "deposit", "receivable", "payable", "credit_line", "other"}:
            acc_type = "other"
        account.account_type = acc_type

        side = (_master_import_value(row, mapping, "side") or account.side or "asset").lower()
        account.side = side if side in {"asset", "liability"} else "asset"
        account.currency = (_master_import_value(row, mapping, "currency") or account.currency or company.base_currency or "EUR").upper()
        account.notes = _master_import_value(row, mapping, "notes") or account.notes
        account.iban = _master_import_value(row, mapping, "iban") or account.iban
        account.bic = _master_import_value(row, mapping, "bic") or account.bic

        cp_name = _master_import_value(row, mapping, "counterparty")
        cp = _find_or_create_counterparty(company, cp_name)
        if cp:
            account.counterparty_id = cp.id

        bal = _parse_decimal_safe(_master_import_value(row, mapping, "balance"))
        if bal is not None:
            account.balance = bal
        lim = _parse_decimal_safe(_master_import_value(row, mapping, "limit_amount"))
        if lim is not None:
            account.limit_amount = lim
        annual_rate = _parse_decimal_safe(_master_import_value(row, mapping, "annual_rate"))
        if annual_rate is not None:
            account.annual_rate = annual_rate

        has_interest = _parse_bool_safe(_master_import_value(row, mapping, "is_interest_bearing"))
        if has_interest is not None:
            account.is_interest_bearing = has_interest

        rate_type = (_master_import_value(row, mapping, "rate_type") or account.rate_type or "fixed").lower()
        account.rate_type = rate_type if rate_type in {"fixed", "float"} else "fixed"

        repricing_date = _parse_date_safe(_master_import_value(row, mapping, "repricing_date"))
        if repricing_date is not None:
            account.repricing_date = repricing_date
        maturity_date = _parse_date_safe(_master_import_value(row, mapping, "maturity_date"))
        if maturity_date is not None:
            account.maturity_date = maturity_date

        return "created" if created else "updated"

    raise ValueError("unsupported entity")


@bp.route("/imports/master-data", methods=["GET", "POST"])
@login_required
@require_roles("tenant_admin", "creator")
def master_data_import():
    company = _get_company()
    entities = _master_import_entities()
    entity = (request.values.get("entity") or "products").strip().lower()
    if entity not in entities:
        entity = "products"

    default_mapping = {f["key"]: f["key"] for f in entities[entity]["fields"]}
    setting = _get_fin_setting(company, _master_import_setting_key(entity), {"mapping": default_mapping, "delimiter": "auto"})
    mapping_preset = setting.get("mapping") if isinstance(setting.get("mapping"), dict) else default_mapping
    delimiter_preset = str(setting.get("delimiter") or "auto").strip().lower()
    if delimiter_preset not in {"auto", "comma", "semicolon", "tab", "pipe"}:
        delimiter_preset = "auto"

    result = None

    if request.method == "POST":
        fields = entities[entity]["fields"]
        mapping = {f["key"]: (request.form.get(f"map_{f['key']}") or "").strip() for f in fields}
        delimiter_mode = (request.form.get("csv_delimiter") or "auto").strip().lower()
        save_template = (request.form.get("save_template") or "").strip() in {"1", "true", "on", "yes"}
        file_obj = request.files.get("file")

        missing_required = [f["label"] for f in fields if f.get("required") and not mapping.get(f["key"])]
        if missing_required:
            flash(_("Mapeamento obrigatório ausente: {fields}", fields=", ".join(missing_required)), "error")
            return redirect(url_for("finance.master_data_import", entity=entity))

        if not file_obj:
            flash(_("Selecione um arquivo CSV."), "error")
            return redirect(url_for("finance.master_data_import", entity=entity))

        filename = secure_filename(file_obj.filename or "master_data.csv")
        file_bytes = file_obj.read() or b""
        if not file_bytes:
            flash(_("Arquivo vazio."), "error")
            return redirect(url_for("finance.master_data_import", entity=entity))

        try:
            headers, rows, detected_delimiter = _parse_csv_rows(file_bytes, delimiter_mode=delimiter_mode)
        except Exception as e:
            flash(_("Falha ao ler CSV: {msg}", msg=str(e)), "error")
            return redirect(url_for("finance.master_data_import", entity=entity))

        if save_template:
            _set_fin_setting(
                company,
                _master_import_setting_key(entity),
                {
                    "mapping": mapping,
                    "delimiter": delimiter_mode,
                },
            )

        created = 0
        updated = 0
        skipped = 0
        errors: list[str] = []

        for idx, row in enumerate(rows, start=2):
            try:
                action = _import_master_data_row(entity, company, row, mapping)
                if action == "created":
                    created += 1
                elif action == "updated":
                    updated += 1
                else:
                    skipped += 1
            except Exception as e:
                skipped += 1
                if len(errors) < 30:
                    errors.append(f"L{idx}: {str(e)}")

        db.session.commit()

        result = {
            "filename": filename,
            "headers": headers,
            "rows": len(rows),
            "created": created,
            "updated": updated,
            "skipped": skipped,
            "delimiter": detected_delimiter,
            "errors": errors,
        }

        flash(
            _(
                "Import concluído ({entity}): {created} criados, {updated} atualizados, {skipped} ignorados.",
                entity=entities[entity]["label"],
                created=created,
                updated=updated,
                skipped=skipped,
            ),
            "success" if not errors else "warning",
        )

        mapping_preset = mapping
        delimiter_preset = delimiter_mode

    return render_template(
        "finance/master_data_import.html",
        tenant=g.tenant,
        company=company,
        active="imports",
        entities=entities,
        entity=entity,
        entity_config=entities[entity],
        mapping_preset=mapping_preset,
        delimiter_preset=delimiter_preset,
        result=result,
    )


@bp.route("/imports/master-data/template.csv")
@login_required
@require_roles("tenant_admin", "creator")
def master_data_import_template_csv():
    company = _get_company()
    entities = _master_import_entities()
    entity = (request.args.get("entity") or "products").strip().lower()
    if entity not in entities:
        entity = "products"

    fields = entities[entity]["fields"]
    output = []
    header = [f["key"] for f in fields]
    sample = [f.get("sample") or "" for f in fields]
    output.append(header)
    output.append(sample)

    delimiter = ","
    sio = []
    for row in output:
        escaped = []
        for val in row:
            cell = str(val or "")
            if any(ch in cell for ch in ["\n", "\r", ",", '"']):
                cell = '"' + cell.replace('"', '""') + '"'
            escaped.append(cell)
        sio.append(delimiter.join(escaped))
    content = "\n".join(sio)

    filename = f"master_import_template_{entity}_{company.slug}.csv"
    return send_file(
        BytesIO(content.encode("utf-8")),
        mimetype="text/csv",
        as_attachment=True,
        download_name=filename,
    )



# -----------------
# Reports
# -----------------


def _next_liability_cashflow_date(d: date, freq: str) -> date:
    f = (freq or "monthly").strip().lower()
    if f == "yearly":
        return _add_months(d, 12)
    if f == "quarterly":
        return _add_months(d, 3)
    if f == "other":
        # Fallback for MVP when custom schedule is not modeled
        return _add_months(d, 1)
    return _add_months(d, 1)


def _build_financing_cashflow_events(
    liabilities: list[FinanceLiability],
    *,
    start: date,
    end: date,
) -> list[tuple[date, Decimal, str]]:
    """Build synthetic cashflow events from financing registry.

    Rules (MVP):
    - principal drawdown on start_date => inflow
    - installment schedule from next_payment_date => outflow
    - bullet repayment on maturity_date when no installments => outflow outstanding
    """
    events: list[tuple[date, Decimal, str]] = []

    for l in liabilities:
        principal = Decimal(str(l.principal_amount or 0))
        outstanding = Decimal(str(l.outstanding_amount or 0))
        installment = Decimal(str(l.installment_amount or 0))

        if l.start_date and principal > 0 and start <= l.start_date <= end:
            events.append((l.start_date, abs(principal), "financing"))

        has_schedule = bool(l.next_payment_date and installment > 0)
        if has_schedule:
            d = l.next_payment_date
            while d and d <= end:
                if l.maturity_date and d > l.maturity_date:
                    break
                if d >= start:
                    events.append((d, -abs(installment), "financing"))
                d = _next_liability_cashflow_date(d, l.payment_frequency or "monthly")

        if (not has_schedule) and l.maturity_date and outstanding > 0 and start <= l.maturity_date <= end:
            events.append((l.maturity_date, -abs(outstanding), "financing"))

    return events


@bp.route("/cashflow")
@login_required
@require_roles("tenant_admin", "creator", "viewer")
def cashflow():
    company = _get_company()
    accounts = _q_accounts(company).all()
    txns = _q_txns(company).all()
    liabilities = FinanceLiability.query.filter_by(tenant_id=g.tenant.id, company_id=company.id).all()

    # default horizon: 90 days ahead
    try:
        start = datetime.strptime((request.args.get("start") or ""), "%Y-%m-%d").date()
    except Exception:
        start = date.today()

    try:
        end = datetime.strptime((request.args.get("end") or ""), "%Y-%m-%d").date()
    except Exception:
        end = start + timedelta(days=90)

    starting_arg = request.args.get("starting")
    if starting_arg:
        starting = Decimal(str(starting_arg))
    else:
        current_balance = compute_starting_cash(accounts)
        starting = compute_opening_balance(txns, start=start, as_of=date.today(), current_balance=current_balance)
    financing_events = _build_financing_cashflow_events(liabilities, start=start, end=end)
    series = compute_cashflow(
        txns,
        start=start,
        end=end,
        starting_balance=starting,
        extra_events=financing_events,
    )

    chart = [
        {
            "day": p.day.isoformat(),
            "inflow": float(p.inflow),
            "outflow": float(p.outflow),
            "balance": float(p.balance),
            "net": float(p.net),
        }
        for p in series
    ]

    return render_template(
        "finance/cashflow.html",
        tenant=g.tenant,
        company=company,
        start=start,
        end=end,
        starting=starting,
        series=series,
        chart=chart,
    )


@bp.route("/nii")
@login_required
@require_roles("tenant_admin", "creator", "viewer")
def nii():
    company = _get_company()
    accounts = _q_accounts(company).all()
    horizon = int(request.args.get("days") or 365)
    res = compute_nii(accounts, horizon_days=horizon)
    return render_template(
        "finance/nii.html",
        tenant=g.tenant,
        company=company,
        horizon=horizon,
        rows=res["rows"],
        total=res["nii_total"],
    )


@bp.route("/gaps")
@login_required
@require_roles("tenant_admin", "creator", "viewer")
def gaps():
    company = _get_company()
    accounts = _q_accounts(company).all()
    as_of = date.today()
    res = compute_interest_rate_gaps(accounts, as_of=as_of)

    chart = [
        {
            "bucket": r["bucket"],
            "assets": float(r["assets"]),
            "liabilities": float(r["liabilities"]),
            "gap": float(r["gap"]),
        }
        for r in res["rows"]
    ]

    return render_template(
        "finance/gaps.html",
        tenant=g.tenant,
        company=company,
        as_of=as_of,
        rows=res["rows"],
        chart=chart,
    )


@bp.route("/liquidity")
@login_required
@require_roles("tenant_admin", "creator", "viewer")
def liquidity():
    company = _get_company()
    accounts = _q_accounts(company).all()
    investments = _safe_get_investments(company)
    horizon = int(request.args.get("days") or 30)
    res = compute_liquidity(accounts, horizon_days=horizon)
    res = _with_investment_liquidity(res, _compute_investment_liquid_sources(investments))
    return render_template(
        "finance/liquidity.html",
        tenant=g.tenant,
        company=company,
        horizon=horizon,
        res=res,
    )


@bp.route("/pivot")
@login_required
@require_roles("tenant_admin", "creator", "viewer")
def pivot_page():
    company = _get_company()
    return render_template(
        "finance/pivot.html",
        tenant=g.tenant,
        company=company,
        active="pivot",
    )


@bp.route("/pivot/data")
@login_required
@require_roles("tenant_admin", "creator", "viewer")
def pivot_data():
    company = _get_company()
    source = request.args.get('source', 'transactions')
    rows = []
    
    if source == 'invoices':
        # Get invoice data
        invoices = FinanceInvoice.query.options(
            joinedload(FinanceInvoice.counterparty),
            joinedload(FinanceInvoice.settlement_account)
        ).filter_by(tenant_id=g.tenant.id, company_id=company.id).all()
        
        for inv in invoices:
            net_amount = float(inv.total_net or 0)
            tax_amount = float(inv.total_tax or 0)
            gross_amount = float(inv.total_gross or 0)
            
            rows.append({
                "month": inv.issue_date.strftime("%Y-%m") if inv.issue_date else "",
                "account": inv.settlement_account.name if inv.settlement_account else "",
                "category": "",
                "counterparty": inv.counterparty.name if inv.counterparty else "",
                "type": "sale" if inv.invoice_type == "sale" else "purchase",
                "invoice_type": "sale" if inv.invoice_type == "sale" else "purchase",
                "amount": gross_amount,
                "inflow": gross_amount if inv.invoice_type == "sale" else 0.0,
                "outflow": gross_amount if inv.invoice_type == "purchase" else 0.0,
            })
    else:
        # Get transaction data (default)
        txns = (
            _q_txns(company)
            .options(joinedload(FinanceTransaction.account), joinedload(FinanceTransaction.category_ref), joinedload(FinanceTransaction.counterparty_ref))
            .all()
        )
        for t in txns:
            amount = Decimal(str(t.amount or 0))
            rows.append({
                "month": t.txn_date.strftime("%Y-%m"),
                "account": t.account.name if t.account else "",
                "category": (t.category_ref.name if t.category_ref else (t.category or "")),
                "counterparty": (t.counterparty_ref.name if t.counterparty_ref else (t.counterparty or "")),
                "type": "inflow" if amount >= 0 else "outflow",
                "invoice_type": "",
                "amount": float(amount),
                "inflow": float(amount) if amount >= 0 else 0.0,
                "outflow": float(-amount) if amount < 0 else 0.0,
            })
    
    return jsonify(rows)



@bp.route("/risk")
@login_required
@require_roles("tenant_admin", "creator", "viewer")
def risk():
    company = _get_company()
    accounts = _q_accounts(company).all()
    horizon_raw = (request.args.get("horizon") or "90").strip()
    if horizon_raw not in {"30", "90", "180", "365", "0"}:
        horizon_raw = "90"
    horizon_days = int(horizon_raw)

    transactions_q = (
        FinanceTransaction.query
        .options(joinedload(FinanceTransaction.account), joinedload(FinanceTransaction.counterparty_ref))
        .filter_by(tenant_id=g.tenant.id, company_id=company.id)
    )
    if horizon_days > 0:
        transactions_q = transactions_q.filter(FinanceTransaction.txn_date >= (date.today() - timedelta(days=horizon_days)))
    transactions = transactions_q.all()
    liabilities = FinanceLiability.query.filter_by(tenant_id=g.tenant.id, company_id=company.id).all()
    
    # Use new robust risk metrics (LCR, NSFR, concentration)
    res = compute_risk_metrics(accounts, transactions=transactions, liabilities=liabilities)

    # Convert all Decimal values to float for Jinja2 template compatibility
    def convert_decimals(obj):
        """Recursively convert Decimal values to float."""
        if isinstance(obj, Decimal):
            return float(obj)
        elif isinstance(obj, dict):
            return {k: convert_decimals(v) for k, v in obj.items()}
        elif isinstance(obj, (list, tuple)):
            return [convert_decimals(item) for item in obj]
        return obj
    
    res = convert_decimals(res)
    
    # Prepare chart data for currency exposure
    ccy_chart = [{"name": r["currency"], "value": r["exposure"]} for r in res["concentration"]["currency"]]

    return render_template(
        "finance/risk.html",
        tenant=g.tenant,
        company=company,
        res=res,
        ccy_chart=ccy_chart,
        horizon_days=horizon_days,
    )


# -----------------
# Settings: categories & accounting
# -----------------


@bp.route("/settings/categories", methods=["GET", "POST"])
@login_required
@require_roles("tenant_admin", "creator")
def settings_categories():
    company = _get_company()

    if request.method == "POST":
        name = (request.form.get("name") or "").strip()
        code = (request.form.get("code") or "").strip() or None
        kind = (request.form.get("kind") or "expense").strip()
        default_gl = request.form.get("default_gl_account_id") or None
        default_gl_id = int(default_gl) if default_gl and default_gl.isdigit() else None
        if default_gl_id and not _is_leaf_gl_account(default_gl_id, company):
            flash(_("Somente contas contábeis de nível mais baixo podem receber transações."), "error")
            return redirect(url_for("finance.settings_categories"))
        if not name:
            flash(_("Nome é obrigatório."), "error")
            return redirect(url_for("finance.settings_categories"))
        cat = FinanceCategory(
            tenant_id=g.tenant.id,
            company_id=company.id,
            name=name,
            code=code,
            kind=kind,
            default_gl_account_id=default_gl_id,
        )
        db.session.add(cat)
        db.session.commit()
        flash(_("Categoria criada."), "success")
        return redirect(url_for("finance.settings_categories"))

    categories = get_categories(company)
    rules = (
        FinanceCategoryRule.query
        .filter_by(tenant_id=g.tenant.id, company_id=company.id)
        .order_by(FinanceCategoryRule.priority.asc())
        .all()
    )
    gl_accounts = get_postable_gl_accounts(company)
    counterparties = get_counterparties(company)
    gl_auto_rules = _get_gl_auto_rules(company)

    gl_account_map = {int(gl.id): gl for gl in gl_accounts}
    category_map = {int(c.id): c for c in categories}
    counterparty_map = {int(cp.id): cp for cp in counterparties}
    gl_auto_rules_view = []
    for rule in gl_auto_rules:
        gl_obj = gl_account_map.get(int(rule.get("gl_account_id") or 0))
        cat_obj = category_map.get(int(rule.get("category_id") or 0)) if rule.get("category_id") else None
        cp_obj = counterparty_map.get(int(rule.get("counterparty_id") or 0)) if rule.get("counterparty_id") else None
        gl_auto_rules_view.append(
            {
                **rule,
                "gl_account_label": f"{gl_obj.code} · {gl_obj.name}" if gl_obj else "",
                "category_label": cat_obj.name if cat_obj else "",
                "counterparty_label": cp_obj.name if cp_obj else "",
            }
        )

    unassigned_gl_count = (
        FinanceTransaction.query
        .filter_by(tenant_id=g.tenant.id, company_id=company.id)
        .filter(FinanceTransaction.gl_account_id.is_(None))
        .filter(FinanceTransaction.ledger_voucher_id.is_(None))
        .count()
    )

    cp_chart_horizon = (request.args.get("cp_chart_horizon") or "90d").strip().lower()
    cp_start_date = date.today() - timedelta(days=90)
    cp_end_date = date.today()
    if cp_chart_horizon in ("30d", "90d", "180d", "365d"):
        cp_start_date = date.today() - timedelta(days=int(cp_chart_horizon.replace("d", "")))
    elif cp_chart_horizon == "custom":
        try:
            raw_start = (request.args.get("cp_start_date") or "").strip()
            raw_end = (request.args.get("cp_end_date") or "").strip()
            cp_start_date = datetime.strptime(raw_start, "%Y-%m-%d").date()
            cp_end_date = datetime.strptime(raw_end, "%Y-%m-%d").date()
            if cp_start_date > cp_end_date:
                raise ValueError("invalid range")
        except Exception:
            cp_start_date = date.today() - timedelta(days=90)
            cp_end_date = date.today()
            cp_chart_horizon = "90d"

    txns = (
        FinanceTransaction.query
        .options(joinedload(FinanceTransaction.counterparty_ref))
        .filter_by(tenant_id=g.tenant.id, company_id=company.id)
        .filter(FinanceTransaction.txn_date >= cp_start_date)
        .filter(FinanceTransaction.txn_date <= cp_end_date)
        .filter(FinanceTransaction.amount < 0)
        .all()
    )

    cp_totals = defaultdict(float)
    for t in txns:
        cp_name = (
            (t.counterparty_ref.name if getattr(t, "counterparty_ref", None) else None)
            or (t.counterparty or "")
            or str(_("Sem contraparte"))
        )
        cp_totals[cp_name] += abs(float(t.amount or 0))

    cp_debit_chart = [
        {"name": name, "value": round(total, 2)}
        for name, total in sorted(cp_totals.items(), key=lambda x: x[1], reverse=True)[:12]
    ]

    return render_template(
        "finance/settings_categories.html",
        tenant=g.tenant,
        company=company,
        categories=categories,
        rules=rules,
        gl_auto_rules=gl_auto_rules_view,
        gl_accounts=gl_accounts,
        counterparties=counterparties,
        unassigned_gl_count=unassigned_gl_count,
        cp_debit_chart=cp_debit_chart,
        cp_chart_horizon=cp_chart_horizon,
        cp_start_date=cp_start_date,
        cp_end_date=cp_end_date,
    )


@bp.route("/settings/categories/<int:category_id>/delete", methods=["POST"])
@login_required
@require_roles("tenant_admin", "creator")
def category_delete(category_id: int):
    company = _get_company()
    cat = FinanceCategory.query.filter_by(id=category_id, tenant_id=g.tenant.id, company_id=company.id).first_or_404()
    db.session.delete(cat)
    db.session.commit()
    flash(_("Categoria removida."), "success")
    return redirect(url_for("finance.settings_categories"))


@bp.route("/settings/rules", methods=["POST"])
@login_required
@require_roles("tenant_admin", "creator")
def rule_create():
    company = _get_company()
    category_id = request.form.get("category_id")
    direction = (request.form.get("direction") or "any").strip()
    keywords = (request.form.get("keywords") or "").strip() or None
    priority = int(request.form.get("priority") or 50)
    cp_id = request.form.get("counterparty_id")
    cp_id_int = int(cp_id) if cp_id and cp_id.isdigit() else None
    min_amount = request.form.get("min_amount")
    max_amount = request.form.get("max_amount")

    if not category_id or not category_id.isdigit():
        flash(_("Dados inválidos."), "error")
        return redirect(url_for("finance.settings_categories"))

    rule = FinanceCategoryRule(
        tenant_id=g.tenant.id,
        company_id=company.id,
        category_id=int(category_id),
        direction=direction,
        keywords=keywords,
        priority=priority,
        counterparty_id=cp_id_int,
        min_amount=Decimal(str(min_amount)) if min_amount else None,
        max_amount=Decimal(str(max_amount)) if max_amount else None,
    )
    db.session.add(rule)
    db.session.commit()
    flash(_("Regra criada."), "success")
    return redirect(url_for("finance.settings_categories"))


@bp.route("/settings/rules/<int:rule_id>/delete", methods=["POST"])
@login_required
@require_roles("tenant_admin", "creator")
def rule_delete(rule_id: int):
    company = _get_company()
    rule = FinanceCategoryRule.query.filter_by(id=rule_id, tenant_id=g.tenant.id, company_id=company.id).first_or_404()
    db.session.delete(rule)
    db.session.commit()
    flash(_("Regra removida."), "success")
    return redirect(url_for("finance.settings_categories"))


@bp.route("/settings/gl-rules", methods=["POST"])
@login_required
@require_roles("tenant_admin", "creator")
def _parse_gl_rule_form(company: FinanceCompany, form) -> tuple[dict | None, str | None]:
    gl_raw = (form.get("gl_account_id") or "").strip()
    if not gl_raw.isdigit():
        return None, _("Conta contábil inválida.")

    gl_account_id = int(gl_raw)
    if not _is_leaf_gl_account(gl_account_id, company):
        return None, _("Somente contas contábeis de nível mais baixo podem receber transações.")

    postable_ids = {int(gl.id) for gl in get_postable_gl_accounts(company)}
    if gl_account_id not in postable_ids:
        return None, _("Conta contábil inválida.")

    direction = (form.get("direction") or "any").strip().lower()
    if direction not in {"any", "inflow", "outflow"}:
        direction = "any"

    category_raw = (form.get("category_id") or "").strip()
    category_id = int(category_raw) if category_raw.isdigit() else None
    if category_id:
        exists_cat = FinanceCategory.query.filter_by(id=category_id, tenant_id=g.tenant.id, company_id=company.id).first()
        if not exists_cat:
            return None, _("Categoria inválida.")

    cp_raw = (form.get("counterparty_id") or "").strip()
    cp_id = int(cp_raw) if cp_raw.isdigit() else None
    if cp_id:
        exists_cp = FinanceCounterparty.query.filter_by(id=cp_id, tenant_id=g.tenant.id, company_id=company.id).first()
        if not exists_cp:
            return None, _("Contraparte inválida.")

    def _to_dec(v: str | None):
        raw = (v or "").strip()
        if not raw:
            return None
        return float(Decimal(raw.replace(",", ".")))

    try:
        min_amount = _to_dec(form.get("min_amount"))
        max_amount = _to_dec(form.get("max_amount"))
    except Exception:
        return None, _("Montants invalides.")

    if min_amount is not None and max_amount is not None and min_amount > max_amount:
        return None, _("Faixa de valores inválida.")

    name = (form.get("name") or "").strip()
    keywords = (form.get("keywords") or "").strip()
    priority_raw = (form.get("priority") or "100").strip()
    priority = int(priority_raw) if priority_raw.isdigit() else 100

    return {
        "id": uuid.uuid4().hex[:12],
        "name": name,
        "priority": priority,
        "direction": direction,
        "keywords": keywords,
        "counterparty_id": cp_id,
        "category_id": category_id,
        "min_amount": min_amount,
        "max_amount": max_amount,
        "gl_account_id": gl_account_id,
    }, None


@bp.route("/settings/gl-rules", methods=["POST"])
@login_required
@require_roles("tenant_admin", "creator")
def gl_rule_create():
    company = _get_company()
    rules = _get_gl_auto_rules(company)

    new_rule, err = _parse_gl_rule_form(company, request.form)
    if err:
        flash(err, "error")
        return redirect(url_for("finance.settings_categories"))

    rules.append(new_rule)
    _set_gl_auto_rules(company, rules)
    flash(_("Règle comptable automatique créée."), "success")
    return redirect(url_for("finance.settings_categories"))


@bp.route("/settings/gl-rules/preview", methods=["POST"])
@login_required
@require_roles("tenant_admin", "creator")
def gl_rule_preview():
    company = _get_company()

    rule, err = _parse_gl_rule_form(company, request.form)
    if err:
        flash(err, "error")
        return redirect(url_for("finance.settings_categories"))

    txns = (
        FinanceTransaction.query
        .filter_by(tenant_id=g.tenant.id, company_id=company.id)
        .filter(FinanceTransaction.gl_account_id.is_(None))
        .filter(FinanceTransaction.ledger_voucher_id.is_(None))
        .order_by(FinanceTransaction.txn_date.desc())
        .all()
    )

    cp_name_by_id: dict[int, str] = {
        int(cp.id): (cp.name or "").strip().lower()
        for cp in get_counterparties(company)
        if cp.id and (cp.name or "").strip()
    }

    matched: list[FinanceTransaction] = []
    for txn in txns:
        if _match_gl_auto_rule(
            rule,
            description=(txn.description or ""),
            counterparty_id=txn.counterparty_id,
            counterparty_name=txn.counterparty,
            category_id=txn.category_id,
            amount=float(txn.amount or 0),
            cp_name_by_id=cp_name_by_id,
        ):
            matched.append(txn)

    flash(
        _("Prévisualisation: {matched} transaction(s) correspond(ent) sur {scanned} non affectée(s).", matched=len(matched), scanned=len(txns)),
        "info",
    )
    if matched:
        samples = [
            f"{t.txn_date.isoformat()} | {float(t.amount or 0):.2f} | {(t.description or '').strip()[:48]}"
            for t in matched[:5]
        ]
        flash(_("Exemples: {rows}", rows=" ; ".join(samples)), "info")

    return redirect(url_for("finance.settings_categories"))


@bp.route("/settings/gl-rules/<rule_id>/delete", methods=["POST"])
@login_required
@require_roles("tenant_admin", "creator")
def gl_rule_delete(rule_id: str):
    company = _get_company()
    rules = _get_gl_auto_rules(company)
    kept = [r for r in rules if str(r.get("id")) != str(rule_id)]
    if len(kept) == len(rules):
        flash(_("Règle introuvable."), "error")
        return redirect(url_for("finance.settings_categories"))
    _set_gl_auto_rules(company, kept)
    flash(_("Règle comptable supprimée."), "success")
    return redirect(url_for("finance.settings_categories"))


@bp.route("/settings/gl-rules/apply-unassigned", methods=["POST"])
@login_required
@require_roles("tenant_admin", "creator")
def gl_rules_apply_unassigned():
    company = _get_company()
    txns = (
        FinanceTransaction.query
        .filter_by(tenant_id=g.tenant.id, company_id=company.id)
        .filter(FinanceTransaction.gl_account_id.is_(None))
        .filter(FinanceTransaction.ledger_voucher_id.is_(None))
        .all()
    )

    updated, scanned = _apply_gl_auto_rules_on_transactions(company, txns, only_missing_gl=True)
    if updated:
        db.session.commit()

    flash(
        _("Affectation comptable automatique: {updated} transaction(s) mise(s) à jour sur {scanned} analysée(s).", updated=updated, scanned=scanned),
        "success" if updated else "info",
    )
    return redirect(url_for("finance.settings_categories"))


@bp.route("/settings/rules/apply-uncategorized", methods=["POST"])
@login_required
@require_roles("tenant_admin", "creator")
def rules_apply_uncategorized():
    company = _get_company()

    txns = (
        FinanceTransaction.query
        .filter_by(tenant_id=g.tenant.id, company_id=company.id)
        .filter(
            or_(
                FinanceTransaction.category_id.is_(None),
                FinanceTransaction.category_id == 0,
            )
        )
        .all()
    )

    updated = 0
    scanned = 0
    for txn in txns:
        scanned += 1
        cat_id = apply_category_rules(
            company,
            description=txn.description or "",
            counterparty_id=txn.counterparty_id,
            amount=float(txn.amount or 0),
            counterparty_name=txn.counterparty,
        )
        if not cat_id:
            continue
        cat_obj = FinanceCategory.query.filter_by(
            id=cat_id,
            tenant_id=g.tenant.id,
            company_id=company.id,
        ).first()
        if not cat_obj:
            continue

        txn.category_id = cat_obj.id
        txn.category = cat_obj.name
        txn.gl_account_id = cat_obj.default_gl_account_id if cat_obj.default_gl_account_id else txn.gl_account_id
        updated += 1

    if updated:
        db.session.commit()

    flash(
        _("Règles appliquées: {updated} transaction(s) catégorisée(s) sur {scanned} analysée(s).", updated=updated, scanned=scanned),
        "success" if updated else "info",
    )
    return redirect(url_for("finance.settings_categories"))


@bp.route("/settings/rules/recategorize-period", methods=["POST"])
@login_required
@require_roles("tenant_admin", "creator")
def rules_recategorize_period():
    company = _get_company()

    horizon = (request.form.get("horizon") or "90d").strip().lower()
    today = date.today()
    end_date = today
    start_date = today - timedelta(days=90)

    if horizon in ("30d", "90d", "180d", "365d"):
        days = int(horizon.replace("d", ""))
        start_date = today - timedelta(days=days)
    elif horizon == "custom":
        raw_start = (request.form.get("start_date") or "").strip()
        raw_end = (request.form.get("end_date") or "").strip()
        try:
            start_date = datetime.strptime(raw_start, "%Y-%m-%d").date()
            end_date = datetime.strptime(raw_end, "%Y-%m-%d").date()
        except Exception:
            flash(_("Période invalide."), "error")
            return redirect(url_for("finance.settings_categories"))
        if start_date > end_date:
            flash(_("Période invalide."), "error")
            return redirect(url_for("finance.settings_categories"))

    txns = (
        FinanceTransaction.query
        .filter_by(tenant_id=g.tenant.id, company_id=company.id)
        .filter(FinanceTransaction.txn_date >= start_date)
        .filter(FinanceTransaction.txn_date <= end_date)
        .all()
    )

    updated = 0
    scanned = 0
    for txn in txns:
        scanned += 1
        cat_id = apply_category_rules(
            company,
            description=txn.description or "",
            counterparty_id=txn.counterparty_id,
            amount=float(txn.amount or 0),
            counterparty_name=txn.counterparty,
        )
        if not cat_id:
            continue
        if txn.category_id == cat_id:
            continue
        cat_obj = FinanceCategory.query.filter_by(
            id=cat_id,
            tenant_id=g.tenant.id,
            company_id=company.id,
        ).first()
        if not cat_obj:
            continue
        txn.category_id = cat_obj.id
        txn.category = cat_obj.name
        txn.gl_account_id = cat_obj.default_gl_account_id if cat_obj.default_gl_account_id else txn.gl_account_id
        updated += 1

    if updated:
        db.session.commit()

    flash(
        _("Recatégorisation exécutée: {updated} transaction(s) mise(s) à jour sur {scanned} analysée(s).", updated=updated, scanned=scanned),
        "success" if updated else "info",
    )
    return redirect(url_for("finance.settings_categories"))


@bp.route("/settings/gl", methods=["GET", "POST"])
@login_required
@require_roles("tenant_admin", "creator")
def settings_gl():
    company = _get_company()
    if request.method == "POST":
        code = (request.form.get("code") or "").strip()
        name = (request.form.get("name") or "").strip()
        kind = (request.form.get("kind") or "expense").strip()
        parent_raw = request.form.get("parent_gl_id") or ""
        parent_id = int(parent_raw) if parent_raw.isdigit() else None
        if not code or not name:
            flash(_("Preencha todos os campos."), "error")
            return redirect(url_for("finance.settings_gl"))
        if parent_id:
            parent = FinanceGLAccount.query.filter_by(id=parent_id, tenant_id=g.tenant.id, company_id=company.id).first()
            if not parent:
                flash(_("Conta contábil inválida."), "error")
                return redirect(url_for("finance.settings_gl"))
        else:
            parent = None

        max_sort = (
            db.session.query(func.max(FinanceGLAccount.sort_order))
            .filter_by(tenant_id=g.tenant.id, company_id=company.id, parent_id=(parent.id if parent else None))
            .scalar()
        )
        db.session.add(
            FinanceGLAccount(
                tenant_id=g.tenant.id,
                company_id=company.id,
                code=code,
                name=name,
                kind=kind,
                parent_id=(parent.id if parent else None),
                sort_order=int(max_sort or 0) + 1,
            )
        )
        db.session.commit()
        flash(_("Conta contábil criada."), "success")
        return redirect(url_for("finance.settings_gl"))

    gl_accounts = get_gl_accounts(company)
    gl_flat = _flatten_gl_accounts(gl_accounts)
    gl_leaf_ids = _leaf_gl_ids(gl_accounts)
    return render_template(
        "finance/settings_gl.html",
        tenant=g.tenant,
        company=company,
        gl_accounts=gl_accounts,
        gl_flat=gl_flat,
        gl_leaf_ids=gl_leaf_ids,
    )


@bp.route("/settings/gl/move", methods=["POST"])
@login_required
@require_roles("tenant_admin", "creator")
def gl_move():
    company = _get_company()
    payload = request.get_json(silent=True) or {}

    try:
        dragged_id = int(payload.get("dragged_id") or 0)
    except Exception:
        dragged_id = 0

    parent_raw = payload.get("parent_id")
    try:
        parent_id = int(parent_raw) if parent_raw not in (None, "", 0, "0") else None
    except Exception:
        parent_id = None

    if not dragged_id:
        return jsonify({"error": _("Conta contábil inválida.")}), 400

    node = FinanceGLAccount.query.filter_by(id=dragged_id, tenant_id=g.tenant.id, company_id=company.id).first()
    if not node:
        return jsonify({"error": _("Conta contábil inválida.")}), 404

    parent = None
    if parent_id is not None:
        parent = FinanceGLAccount.query.filter_by(id=parent_id, tenant_id=g.tenant.id, company_id=company.id).first()
        if not parent:
            return jsonify({"error": _("Conta contábil inválida.")}), 404
        if int(parent.id) == int(node.id) or _is_descendant_gl_account(int(parent.id), int(node.id), company):
            return jsonify({"error": _("Hierarquia inválida.")}), 400

    max_sort = (
        db.session.query(func.max(FinanceGLAccount.sort_order))
        .filter_by(tenant_id=g.tenant.id, company_id=company.id, parent_id=(parent.id if parent else None))
        .scalar()
    )
    node.parent_id = parent.id if parent else None
    node.sort_order = int(max_sort or 0) + 1
    db.session.commit()

    return jsonify({"ok": True})


@bp.route("/settings/gl/<int:gl_id>/delete", methods=["POST"])
@login_required
@require_roles("tenant_admin", "creator")
def gl_delete(gl_id: int):
    company = _get_company()
    gl = FinanceGLAccount.query.filter_by(id=gl_id, tenant_id=g.tenant.id, company_id=company.id).first_or_404()
    db.session.delete(gl)
    db.session.commit()
    flash(_("Conta contábil removida."), "success")
    return redirect(url_for("finance.settings_gl"))


# -----------------
# Banking API (PSD2) – Bridge
# -----------------


@bp.route("/banks", methods=["GET"])
@login_required
@require_roles("tenant_admin", "creator", "viewer")
def banks():
    company = _get_company()
    bridge = BridgeClient()
    connections = (
        FinanceBankConnection.query
        .filter_by(tenant_id=g.tenant.id, company_id=company.id)
        .order_by(FinanceBankConnection.created_at.desc())
        .all()
    )
    return render_template(
        "finance/banks.html",
        tenant=g.tenant,
        company=company,
        bridge_configured=bridge.is_configured(),
        connections=connections,
    )


@bp.route("/banks/connect", methods=["POST"])
@login_required
@require_roles("tenant_admin", "creator")
def banks_connect():
    company = _get_company()
    bridge = BridgeClient()
    if not bridge.is_configured():
        flash(_("API bancária não configurada."), "error")
        return redirect(url_for("finance.banks"))

    # One Bridge user per (tenant, app user) – keep stable
    external_user_id = f"t{g.tenant.id}:u{current_user.id}"
    try:
        bridge.create_user(external_user_id=external_user_id, email=getattr(current_user, "email", None))
        bearer, _exp = bridge.get_user_token(external_user_id=external_user_id)
        callback = url_for("finance.banks_callback", _external=True)
        sess = bridge.create_connect_session(
            bearer=bearer,
            user_email=getattr(current_user, "email", "user@audela.local"),
            callback_url=callback,
            context=f"company:{company.id}",
        )
        connect_url = sess.get("redirect_url") or sess.get("url") or sess.get("connect_url")
        if not connect_url:
            raise BridgeError(f"Connect session missing url: {sess}")
        session["bridge_external_user_id"] = external_user_id
        session["bridge_company_id"] = company.id
        return redirect(connect_url)
    except BridgeError as e:
        flash(_("Falha ao iniciar conexão bancária: {err}", err=str(e)[:180]), "error")
        return redirect(url_for("finance.banks"))


@bp.route("/banks/callback")
@login_required
@require_roles("tenant_admin", "creator")
def banks_callback():
    company = _get_company()

    # Bridge sends item_id in query params (can vary depending on flow)
    item_id = (request.args.get("item_id") or request.args.get("item_uuid") or request.args.get("id") or "").strip()
    if not item_id:
        flash(_("Callback inválido (item_id ausente)."), "error")
        return redirect(url_for("finance.banks"))

    external_user_id = session.get("bridge_external_user_id")
    if not external_user_id:
        # still accept: derive from user
        external_user_id = f"t{g.tenant.id}:u{current_user.id}"

    conn = FinanceBankConnection(
        tenant_id=g.tenant.id,
        company_id=company.id,
        provider="bridge",
        label=_(("Conexão bancária")),
        status="connected",
        external_user_id=external_user_id,
        item_id=item_id,
    )
    db.session.add(conn)
    db.session.commit()

    flash(_("Banco conectado. Sincronize para importar contas e transações."), "success")
    return redirect(url_for("finance.banks"))


def _dedupe_sig(txn_date, amount, description, reference):
    return (txn_date, str(amount), (description or "").strip(), (reference or "").strip())


@bp.route("/banks/<int:conn_id>/sync", methods=["POST"])
@login_required
@require_roles("tenant_admin", "creator")
def banks_sync(conn_id: int):
    company = _get_company()
    conn = FinanceBankConnection.query.filter_by(id=conn_id, tenant_id=g.tenant.id, company_id=company.id).first_or_404()

    if conn.provider != "bridge":
        flash(_("Provedor não suportado."), "error")
        return redirect(url_for("finance.banks"))

    bridge = BridgeClient()
    if not bridge.is_configured():
        flash(_("API bancária não configurada."), "error")
        return redirect(url_for("finance.banks"))

    try:
        allowed, remaining, current_count, max_limit = _transaction_quota_info()
        if not allowed or remaining <= 0:
            flash(_("Limite de transações do plano atingida ({current}/{max}).", current=current_count, max=max_limit), "error")
            return redirect(url_for("finance.banks"))

        bearer, _exp = bridge.get_user_token(external_user_id=conn.external_user_id)
        accounts = bridge.list_accounts(bearer=bearer, item_id=conn.item_id)

        # existing txns signature set for dedupe (last 120 days)
        date_from = (date.today() - timedelta(days=120)).isoformat()
        existing = (
            FinanceTransaction.query
            .filter_by(tenant_id=g.tenant.id, company_id=company.id)
            .filter(FinanceTransaction.txn_date >= date.today() - timedelta(days=120))
            .all()
        )
        existing_sigs = set(_dedupe_sig(t.txn_date, t.amount, t.description, t.reference) for t in existing)

        cp_map = {(cp.name or "").strip().lower(): cp for cp in get_counterparties(company) if (cp.name or "").strip()}

        created_accounts = 0
        created_txns = 0

        for a in accounts:
            provider_account_id = str(a.get("id") or a.get("uuid") or "").strip()
            if not provider_account_id:
                continue

            link = FinanceBankAccountLink.query.filter_by(
                tenant_id=g.tenant.id,
                company_id=company.id,
                connection_id=conn.id,
                provider_account_id=provider_account_id,
            ).first()

            ccy = (a.get("currency_code") or a.get("currency") or company.base_currency or "EUR").strip().upper()
            name = (a.get("name") or a.get("iban") or a.get("bank_name") or f"Bank {provider_account_id}").strip()

            if not link:
                link = FinanceBankAccountLink(
                    tenant_id=g.tenant.id,
                    company_id=company.id,
                    connection_id=conn.id,
                    provider_account_id=provider_account_id,
                    provider_account_name=name,
                    currency_code=ccy,
                )
                db.session.add(link)
                db.session.flush()

            # Ensure there is a FinanceAccount mapped
            if not link.finance_account_id:
                fa = FinanceAccount(
                    tenant_id=g.tenant.id,
                    company_id=company.id,
                    name=name,
                    account_type="bank",
                    currency=ccy,
                    balance=float(a.get("balance") or 0),
                )
                db.session.add(fa)
                db.session.flush()
                link.finance_account_id = fa.id
                created_accounts += 1

            # Sync transactions for this account
            txns = bridge.list_transactions(bearer=bearer, account_id=provider_account_id, date_from=date_from)
            for t in txns:
                if created_txns >= remaining:
                    break
                d = t.get("date") or t.get("booking_date") or t.get("value_date")
                if not d:
                    continue
                try:
                    txn_date = datetime.fromisoformat(d[:10]).date()
                except Exception:
                    continue
                amt = t.get("amount")
                try:
                    amount = float(amt)
                except Exception:
                    continue
                desc = (t.get("label") or t.get("description") or t.get("name") or "").strip()
                ref = str(t.get("id") or t.get("uuid") or t.get("transaction_id") or "").strip() or None
                sig = _dedupe_sig(txn_date, amount, desc, ref or "")
                if sig in existing_sigs:
                    continue

                cp_name = (t.get("counterparty") or t.get("merchant_name") or t.get("merchant") or "").strip()
                cp_obj = None
                if cp_name:
                    k = cp_name.lower()
                    cp_obj = cp_map.get(k)
                    if not cp_obj:
                        cp_obj = FinanceCounterparty(tenant_id=g.tenant.id, company_id=company.id, name=cp_name, kind="other")
                        db.session.add(cp_obj)
                        db.session.flush()
                        cp_map[k] = cp_obj

                cat_id = apply_category_rules(company, description=desc, counterparty_id=cp_obj.id if cp_obj else None, amount=amount)
                cat_obj = FinanceCategory.query.filter_by(id=cat_id, tenant_id=g.tenant.id, company_id=company.id).first() if cat_id else None
                gl_account_id = cat_obj.default_gl_account_id if cat_obj and cat_obj.default_gl_account_id else None
                if gl_account_id and not _is_leaf_gl_account(gl_account_id, company):
                    gl_account_id = None

                db.session.add(
                    FinanceTransaction(
                        tenant_id=g.tenant.id,
                        company_id=company.id,
                        account_id=link.finance_account_id,
                        txn_date=txn_date,
                        amount=amount,
                        description=desc,
                        category=cat_obj.name if cat_obj else None,
                        category_id=cat_obj.id if cat_obj else None,
                        gl_account_id=gl_account_id,
                        counterparty_id=cp_obj.id if cp_obj else None,
                        counterparty=None if cp_obj else (cp_name or None),
                        reference=ref,
                        source="bridge",
                    )
                )
                created_txns += 1
                existing_sigs.add(sig)

            if created_txns >= remaining:
                break

        conn.last_sync_at = datetime.utcnow()
        db.session.commit()
        flash(_("Sincronização concluída: {a} contas, {t} transações.", a=created_accounts, t=created_txns), "success")
        if created_txns >= remaining:
            flash(_("Sincronização limitada pelo plano de transações."), "warning")
    except BridgeError as e:
        flash(_("Falha na sincronização: {err}", err=str(e)[:180]), "error")

    return redirect(url_for("finance.banks"))


# -----------------
# Reconciliation
# -----------------


@bp.route("/reconciliation")
@login_required
@require_roles("tenant_admin", "creator", "viewer")
def reconciliation():
    company = _get_company()

    txns = (
        FinanceTransaction.query
        .filter_by(tenant_id=g.tenant.id, company_id=company.id)
        .filter(FinanceTransaction.txn_date >= date.today() - timedelta(days=90))
        .order_by(FinanceTransaction.txn_date.desc())
        .limit(300)
        .all()
    )

    gl_accounts = get_postable_gl_accounts(company)
    categories = get_categories(company)

    return render_template(
        "finance/reconciliation.html",
        tenant=g.tenant,
        company=company,
        txns=txns,
        gl_accounts=gl_accounts,
        categories=categories,
    )


def _get_bank_gl(company: FinanceCompany) -> FinanceGLAccount | None:
    # Prefer explicit bank GL code 512 if present
    gl = FinanceGLAccount.query.filter_by(tenant_id=g.tenant.id, company_id=company.id, code="512").first()
    if gl and _is_leaf_gl_account(gl.id, company):
        return gl
    # fallback: first asset account
    for candidate in (
        FinanceGLAccount.query
        .filter_by(tenant_id=g.tenant.id, company_id=company.id, kind="asset")
        .order_by(FinanceGLAccount.sort_order.asc(), FinanceGLAccount.code.asc())
        .all()
    ):
        if _is_leaf_gl_account(candidate.id, company):
            return candidate
    return None


@bp.route("/reconciliation/<int:txn_id>/create_voucher", methods=["POST"])
@login_required
@require_roles("tenant_admin", "creator")
def reconcile_create_voucher(txn_id: int):
    company = _get_company()
    txn = FinanceTransaction.query.filter_by(id=txn_id, tenant_id=g.tenant.id, company_id=company.id).first_or_404()

    if _is_period_closed(company, txn.txn_date):
        flash(_("Período contábil fechado para a data da transação. Reabra o período para lançar."), "danger")
        return redirect(url_for("finance.reconciliation"))

    if txn.ledger_voucher_id:
        flash(_("Transação já conciliada."), "info")
        return redirect(url_for("finance.reconciliation"))

    # Choose GL account
    gl_id = request.form.get("gl_account_id")
    gl_account = None
    if gl_id and gl_id.isdigit():
        gl_account = FinanceGLAccount.query.filter_by(id=int(gl_id), tenant_id=g.tenant.id, company_id=company.id).first()

    # If not provided, try category default
    if not gl_account and txn.category_id:
        cat = FinanceCategory.query.filter_by(id=txn.category_id, tenant_id=g.tenant.id, company_id=company.id).first()
        if cat and cat.default_gl_account_id:
            gl_account = FinanceGLAccount.query.filter_by(id=cat.default_gl_account_id, tenant_id=g.tenant.id, company_id=company.id).first()

    if not gl_account:
        flash(_("Selecione uma conta contábil."), "error")
        return redirect(url_for("finance.reconciliation"))

    if not _is_leaf_gl_account(gl_account.id, company):
        flash(_("Somente contas contábeis de nível mais baixo podem receber transações."), "error")
        return redirect(url_for("finance.reconciliation"))

    bank_gl = _get_bank_gl(company)
    if not bank_gl:
        flash(_("Crie uma conta contábil de banco (ex: 512)."), "error")
        return redirect(url_for("finance.reconciliation"))

    v = FinanceLedgerVoucher(
        tenant_id=g.tenant.id,
        company_id=company.id,
        voucher_date=txn.txn_date,
        reference=str(txn.id),
        description=txn.description,
    )
    db.session.add(v)
    db.session.flush()

    amount = abs(Decimal(str(txn.amount)))

    # Basic double-entry: bank vs selected GL
    if txn.amount >= 0:
        # money in: bank debit, income/other credit
        db.session.add(FinanceLedgerLine(tenant_id=g.tenant.id, company_id=company.id, voucher_id=v.id, gl_account_id=bank_gl.id, txn_id=txn.id, debit=amount, credit=0, description=txn.description, counterparty_id=txn.counterparty_id))
        db.session.add(FinanceLedgerLine(tenant_id=g.tenant.id, company_id=company.id, voucher_id=v.id, gl_account_id=gl_account.id, txn_id=txn.id, debit=0, credit=amount, description=txn.description, counterparty_id=txn.counterparty_id))
    else:
        # money out: bank credit, expense/other debit
        db.session.add(FinanceLedgerLine(tenant_id=g.tenant.id, company_id=company.id, voucher_id=v.id, gl_account_id=gl_account.id, txn_id=txn.id, debit=amount, credit=0, description=txn.description, counterparty_id=txn.counterparty_id))
        db.session.add(FinanceLedgerLine(tenant_id=g.tenant.id, company_id=company.id, voucher_id=v.id, gl_account_id=bank_gl.id, txn_id=txn.id, debit=0, credit=amount, description=txn.description, counterparty_id=txn.counterparty_id))

    txn.ledger_voucher_id = v.id
    txn.gl_account_id = gl_account.id

    db.session.commit()
    flash(_("Conciliado."), "success")
    return redirect(url_for("finance.reconciliation"))


# -----------------
# Reports (transactions)
# -----------------


def _fmt_money(value: Decimal | None, currency: str | None) -> str:
    try:
        v = Decimal(str(value or 0))
    except Exception:
        v = Decimal("0")
    cur = (currency or "").strip() or "EUR"
    # Keep simple formatting (no locale dependency)
    return f"{v.quantize(Decimal('0.01'))} {cur}"


def _date_range_from_view(view: str, year: int, month: int) -> tuple[date, date, str]:
    if view == "year":
        start = date(year, 1, 1)
        end = date(year + 1, 1, 1)
        label = str(year)
        return start, end, label
    # default month
    start = date(year, month, 1)
    if month == 12:
        end = date(year + 1, 1, 1)
    else:
        end = date(year, month + 1, 1)
    label = f"{year}-{month:02d}"
    return start, end, label


@bp.route("/reports/transactions")
@login_required
@require_roles("tenant_admin", "creator", "viewer")
def reports_transactions():
    company = _get_company()
    view = (request.args.get("view") or "month").strip().lower()
    if view not in ("month", "year"):
        view = "month"

    today = date.today()
    try:
        year = int(request.args.get("year") or today.year)
    except Exception:
        year = today.year
    try:
        month = int(request.args.get("month") or today.month)
    except Exception:
        month = today.month
    month = max(1, min(12, month))
    cp_page = request.args.get("cp_page", type=int) or 1
    cp_per_page = request.args.get("cp_per_page", type=int) or 20
    cp_per_page = max(10, min(100, cp_per_page))

    start, end, label = _date_range_from_view(view, year, month)
    base_cur = company.base_currency or "EUR"

    txns = (
        _q_txns(company)
        .filter(FinanceTransaction.txn_date >= start)
        .filter(FinanceTransaction.txn_date < end)
        .order_by(FinanceTransaction.txn_date.desc(), FinanceTransaction.id.desc())
        .all()
    )
    categories = get_categories(company)
    can_edit_categories = current_user.has_role("tenant_admin") or current_user.has_role("creator")

    inflow = Decimal("0")
    outflow = Decimal("0")
    net = Decimal("0")
    by_cat: dict[str, Decimal] = {}
    by_cp: dict[str, Decimal] = {}

    latest = []
    for t in txns:
        amt = Decimal(str(t.amount or 0))
        net += amt
        if amt >= 0:
            inflow += amt
        else:
            outflow += abs(amt)

        cat_name = (t.category_ref.name if getattr(t, "category_ref", None) else None) or (t.category or "Sem categoria")
        cp_name_raw = (t.counterparty_ref.name if getattr(t, "counterparty_ref", None) else None) or (t.counterparty or t.description or "—")
        cp_name = normalize_counterparty_label(cp_name_raw)
        by_cat[cat_name] = by_cat.get(cat_name, Decimal("0")) + amt
        by_cp[cp_name] = by_cp.get(cp_name, Decimal("0")) + amt

    def _top_map(d: dict[str, Decimal]):
        items = sorted(d.items(), key=lambda kv: abs(kv[1]), reverse=True)[:10]
        return [{"name": k, "net": v, "net_fmt": _fmt_money(v, base_cur)} for k, v in items]

    latest_rows = []
    for t in txns[:25]:
        cat_name = (t.category_ref.name if getattr(t, "category_ref", None) else None) or (t.category or "Sem categoria")
        cp_name = (t.counterparty_ref.name if getattr(t, "counterparty_ref", None) else None) or (t.counterparty or "—")
        latest_rows.append(
            {
                "id": t.id,
                "txn_date": t.txn_date,
                "description": t.description,
                "category_name": cat_name,
                "category_id": t.category_id,
                "counterparty_name": cp_name,
                "amount_fmt": _fmt_money(Decimal(str(t.amount or 0)), base_cur),
                "is_locked": bool(t.ledger_voucher_id),
            }
        )

    cp_items = sorted(by_cp.items(), key=lambda kv: abs(kv[1]), reverse=True)
    cp_total = len(cp_items)
    cp_pages = max(1, ((cp_total - 1) // cp_per_page) + 1) if cp_total else 1
    cp_page = max(1, min(cp_page, cp_pages))
    cp_start = (cp_page - 1) * cp_per_page
    cp_end = cp_start + cp_per_page
    by_counterparty_rows = [
        {"name": k, "net": v, "net_fmt": _fmt_money(v, base_cur)}
        for k, v in cp_items[cp_start:cp_end]
    ]

    years = list(range(today.year - 5, today.year + 1))

    return render_template(
        "finance/reports_transactions.html",
        tenant=g.tenant,
        company=company,
        view=view,
        year=year,
        month=month,
        years=years,
        period_label=label,
        kpis={
            "inflow_fmt": _fmt_money(inflow, base_cur),
            "outflow_fmt": _fmt_money(outflow, base_cur),
            "net_fmt": _fmt_money(net, base_cur),
            "count": len(txns),
        },
        by_category=_top_map(by_cat),
        by_counterparty=by_counterparty_rows,
        cp_page=cp_page,
        cp_pages=cp_pages,
        cp_total=cp_total,
        cp_per_page=cp_per_page,
        categories=categories,
        can_edit_categories=can_edit_categories,
        current_path=request.full_path if request.query_string else request.path,
        latest=latest_rows,
    )


@bp.route("/reports/statistics")
@login_required
@require_roles("tenant_admin", "creator", "viewer")
def reports_statistics():
    company = _get_company()
    base_cur = company.base_currency or "EUR"
    granularity = (request.args.get("granularity") or "month").strip().lower()
    if granularity not in {"month", "quarter"}:
        granularity = "month"

    today = date.today()
    default_start = today - timedelta(days=365)
    try:
        start = datetime.strptime((request.args.get("start") or default_start.isoformat()), "%Y-%m-%d").date()
    except Exception:
        start = default_start
    try:
        end = datetime.strptime((request.args.get("end") or today.isoformat()), "%Y-%m-%d").date()
    except Exception:
        end = today
    if end < start:
        start, end = end, start

    txns = (
        _q_txns(company)
        .filter(FinanceTransaction.txn_date >= start)
        .filter(FinanceTransaction.txn_date <= end)
        .order_by(FinanceTransaction.txn_date.asc(), FinanceTransaction.id.asc())
        .all()
    )

    expense_rows: list[dict] = []
    income_values: list[Decimal] = []
    by_category_expense: dict[str, dict] = {}
    period_expenses: dict[str, Decimal] = {}
    period_income: dict[str, Decimal] = {}
    by_category_period: dict[str, dict[str, Decimal]] = {}

    def _period_key(d: date) -> str:
        if granularity == "quarter":
            q = ((d.month - 1) // 3) + 1
            return f"{d.year}-Q{q}"
        return d.strftime("%Y-%m")

    def _period_start(d: date) -> date:
        if granularity == "quarter":
            sm = ((d.month - 1) // 3) * 3 + 1
            return date(d.year, sm, 1)
        return date(d.year, d.month, 1)

    def _next_period_start(d: date) -> date:
        step = 3 if granularity == "quarter" else 1
        y = d.year
        m = d.month + step
        while m > 12:
            y += 1
            m -= 12
        return date(y, m, 1)

    for t in txns:
        amt = Decimal(str(t.amount or 0))
        cat_name = (t.category_ref.name if getattr(t, "category_ref", None) else None) or (t.category or "Sem categoria")
        if amt < 0:
            exp_amt = abs(amt)
            pkey = _period_key(t.txn_date)
            expense_rows.append(
                {
                    "txn_date": t.txn_date,
                    "description": t.description or "",
                    "category": cat_name,
                    "amount": exp_amt,
                }
            )
            bucket = by_category_expense.setdefault(cat_name, {"count": 0, "total": Decimal("0")})
            bucket["count"] += 1
            bucket["total"] += exp_amt
            period_expenses[pkey] = period_expenses.get(pkey, Decimal("0")) + exp_amt
            cat_period = by_category_period.setdefault(cat_name, {})
            cat_period[pkey] = cat_period.get(pkey, Decimal("0")) + exp_amt
        elif amt > 0:
            income_values.append(amt)
            pkey = _period_key(t.txn_date)
            period_income[pkey] = period_income.get(pkey, Decimal("0")) + amt

    category_avg_rows = []
    for cat, stats in by_category_expense.items():
        count = int(stats["count"] or 0)
        total = Decimal(str(stats["total"] or 0))
        avg = (total / Decimal(str(count))) if count > 0 else Decimal("0")
        category_avg_rows.append(
            {
                "name": cat,
                "count": count,
                "total": total,
                "avg": avg,
                "total_fmt": _fmt_money(total, base_cur),
                "avg_fmt": _fmt_money(avg, base_cur),
            }
        )
    category_avg_rows.sort(key=lambda x: x["avg"], reverse=True)

    month_cursor = _period_start(start)
    end_month = _period_start(end)
    expense_trend_labels: list[str] = []
    expense_trend_values: list[float] = []
    while month_cursor <= end_month:
        key = _period_key(month_cursor)
        expense_trend_labels.append(key)
        expense_trend_values.append(float(period_expenses.get(key, Decimal("0"))))
        month_cursor = _next_period_start(month_cursor)

    trend_label = _("Stable")
    trend_slope = 0.0
    trend_change_pct = None
    n_vals = len(expense_trend_values)
    if n_vals >= 2:
        mean_x = (n_vals - 1) / 2.0
        mean_y = sum(expense_trend_values) / n_vals
        denom = sum((i - mean_x) ** 2 for i in range(n_vals))
        if denom > 0:
            trend_slope = sum((i - mean_x) * (expense_trend_values[i] - mean_y) for i in range(n_vals)) / denom
        if trend_slope > 0.01:
            trend_label = _("Hausse")
        elif trend_slope < -0.01:
            trend_label = _("Baisse")
    if n_vals >= 6:
        prev_avg = sum(expense_trend_values[-6:-3]) / 3.0
        last_avg = sum(expense_trend_values[-3:]) / 3.0
        if prev_avg > 0:
            trend_change_pct = ((last_avg - prev_avg) / prev_avg) * 100.0

    monthly_changes: list[float] = []
    for i in range(1, len(expense_trend_values)):
        prev_v = expense_trend_values[i - 1]
        cur_v = expense_trend_values[i]
        if prev_v > 0:
            monthly_changes.append((cur_v - prev_v) / prev_v)

    monthly_volatility_pct = 0.0
    if len(monthly_changes) >= 2:
        ch_mean = sum(monthly_changes) / len(monthly_changes)
        ch_var = sum((x - ch_mean) ** 2 for x in monthly_changes) / len(monthly_changes)
        monthly_volatility_pct = (ch_var ** 0.5) * 100.0

    outlier_rows = []
    z_values: list[float] = []
    gauss_mean = 0.0
    gauss_std = 0.0
    if len(expense_rows) >= 3:
        values = [float(r["amount"]) for r in expense_rows]
        gauss_mean = sum(values) / len(values)
        variance = sum((v - gauss_mean) ** 2 for v in values) / len(values)
        gauss_std = variance ** 0.5
        if gauss_std > 0:
            for r in expense_rows:
                z = (float(r["amount"]) - gauss_mean) / gauss_std
                z_values.append(z)
                if abs(z) >= 2.0:
                    outlier_rows.append(
                        {
                            "txn_date": r["txn_date"],
                            "description": r["description"],
                            "category": r["category"],
                            "amount_fmt": _fmt_money(Decimal(str(r["amount"])), base_cur),
                            "zscore": z,
                        }
                    )
    outlier_rows.sort(key=lambda x: abs(x["zscore"]), reverse=True)

    liabilities = (
        FinanceLiability.query
        .filter_by(tenant_id=g.tenant.id, company_id=company.id)
        .order_by(FinanceLiability.outstanding_amount.desc().nullslast(), FinanceLiability.id.desc())
        .limit(10)
        .all()
    )
    liability_rows = []
    total_liabilities = Decimal("0")
    for l in liabilities:
        outstanding = Decimal(str(l.outstanding_amount if l.outstanding_amount is not None else (l.principal_amount or 0)))
        total_liabilities += outstanding
        liability_rows.append(
            {
                "name": l.name,
                "lender": (l.lender.name if getattr(l, "lender", None) else "—"),
                "outstanding": outstanding,
                "outstanding_fmt": _fmt_money(outstanding, l.currency_code or base_cur),
                "maturity_date": l.maturity_date,
            }
        )

    product_rows_raw = (
        db.session.query(
            FinanceInvoiceLine.description,
            func.coalesce(func.sum(FinanceInvoiceLine.quantity), 0),
            func.coalesce(func.sum(FinanceInvoiceLine.gross_amount), 0),
        )
        .join(FinanceInvoice, FinanceInvoice.id == FinanceInvoiceLine.invoice_id)
        .filter(FinanceInvoiceLine.tenant_id == g.tenant.id)
        .filter(FinanceInvoiceLine.company_id == company.id)
        .filter(FinanceInvoice.invoice_type == "sale")
        .filter(FinanceInvoice.status != "void")
        .filter(FinanceInvoice.issue_date >= start)
        .filter(FinanceInvoice.issue_date <= end)
        .group_by(FinanceInvoiceLine.description)
        .order_by(func.coalesce(func.sum(FinanceInvoiceLine.quantity), 0).desc())
        .limit(10)
        .all()
    )
    top_products = []
    for desc, qty, gross in product_rows_raw:
        qty_dec = Decimal(str(qty or 0))
        qty_fmt = format(qty_dec, "f").rstrip("0").rstrip(".") if qty_dec % 1 != 0 else str(int(qty_dec))
        top_products.append(
            {
                "name": desc or "—",
                "quantity": qty_fmt,
                "gross_fmt": _fmt_money(Decimal(str(gross or 0)), base_cur),
            }
        )

    inv_rows = []
    for inv in _safe_get_investments(company):
        invested = Decimal(str(inv.invested_amount or 0))
        if invested <= 0:
            continue
        current_value = Decimal(str(inv.current_value if inv.current_value is not None else (inv.invested_amount or 0)))
        pnl = current_value - invested
        roi_pct = (pnl / invested) * Decimal("100")
        inv_rows.append(
            {
                "name": inv.name,
                "provider": inv.provider,
                "invested_fmt": _fmt_money(invested, inv.currency_code or base_cur),
                "current_fmt": _fmt_money(current_value, inv.currency_code or base_cur),
                "pnl_fmt": _fmt_money(pnl, inv.currency_code or base_cur),
                "roi_pct": float(roi_pct),
            }
        )
    top_investments = sorted(inv_rows, key=lambda x: x["roi_pct"], reverse=True)[:10]

    montecarlo_horizon = 6 if granularity == "month" else 4
    montecarlo_runs = 400
    mc_labels = [f"M+{i}" for i in range(1, montecarlo_horizon + 1)]
    mc_p10 = [0.0] * montecarlo_horizon
    mc_p50 = [0.0] * montecarlo_horizon
    mc_p90 = [0.0] * montecarlo_horizon
    mc_expected_last = 0.0

    base_monthly_expense = 0.0
    non_zero_monthly = [v for v in expense_trend_values if v > 0]
    if non_zero_monthly:
        base_monthly_expense = non_zero_monthly[-1]
    elif expense_trend_values:
        base_monthly_expense = expense_trend_values[-1]

    if base_monthly_expense > 0:
        rng = random.Random(42)
        mu = (sum(monthly_changes) / len(monthly_changes)) if monthly_changes else 0.0
        sigma = ((monthly_volatility_pct / 100.0) if monthly_volatility_pct > 0 else 0.05)
        sigma = max(0.001, min(sigma, 0.8))

        paths: list[list[float]] = []
        for run_idx in range(montecarlo_runs):
            cur = base_monthly_expense
            path = []
            for _step in range(montecarlo_horizon):
                shock = rng.gauss(mu, sigma)
                cur = max(0.0, cur * (1.0 + shock))
                path.append(cur)
            paths.append(path)

        def _pct(sorted_vals: list[float], p: float) -> float:
            if not sorted_vals:
                return 0.0
            idx = int(round((len(sorted_vals) - 1) * p))
            idx = max(0, min(len(sorted_vals) - 1, idx))
            return float(sorted_vals[idx])

        for j in range(montecarlo_horizon):
            col = sorted(path[j] for path in paths)
            mc_p10[j] = _pct(col, 0.10)
            mc_p50[j] = _pct(col, 0.50)
            mc_p90[j] = _pct(col, 0.90)
        mc_expected_last = sum(path[-1] for path in paths) / len(paths)

    top_cats = [r["name"] for r in sorted(category_avg_rows, key=lambda x: x["total"], reverse=True)[:5]]

    def _pearson(xs: list[float], ys: list[float]) -> float:
        if len(xs) != len(ys) or len(xs) < 2:
            return 0.0
        mx = sum(xs) / len(xs)
        my = sum(ys) / len(ys)
        num = sum((x - mx) * (y - my) for x, y in zip(xs, ys))
        denx = sum((x - mx) ** 2 for x in xs)
        deny = sum((y - my) ** 2 for y in ys)
        den = (denx * deny) ** 0.5
        if den <= 0:
            return 0.0
        return max(-1.0, min(1.0, num / den))

    corr_matrix: list[list[float | int]] = []
    corr_top_pair = "—"
    corr_top_value = 0.0
    if len(top_cats) >= 2:
        cat_series: dict[str, list[float]] = {}
        for c in top_cats:
            cat_month = by_category_period.get(c, {})
            cat_series[c] = [float(cat_month.get(m, Decimal("0"))) for m in expense_trend_labels]

        for i, ci in enumerate(top_cats):
            for j, cj in enumerate(top_cats):
                corr = _pearson(cat_series[ci], cat_series[cj])
                corr_matrix.append([i, j, round(corr, 4)])
                if i < j and abs(corr) > abs(corr_top_value):
                    corr_top_value = corr
                    corr_top_pair = f"{ci} ↔ {cj}"

    avg_expense = (
        sum((Decimal(str(r["amount"])) for r in expense_rows), Decimal("0")) / Decimal(str(len(expense_rows)))
        if expense_rows
        else Decimal("0")
    )
    avg_income = (
        sum(income_values, Decimal("0")) / Decimal(str(len(income_values)))
        if income_values
        else Decimal("0")
    )
    total_expense_amount = sum((Decimal(str(r["amount"])) for r in expense_rows), Decimal("0"))
    total_income_amount = sum(income_values, Decimal("0"))
    expense_income_ratio_pct = float((total_expense_amount / total_income_amount) * Decimal("100")) if total_income_amount > 0 else None

    median_expense = Decimal("0")
    if expense_rows:
        sorted_exp = sorted((Decimal(str(r["amount"])) for r in expense_rows))
        n_exp = len(sorted_exp)
        mid = n_exp // 2
        if n_exp % 2 == 1:
            median_expense = sorted_exp[mid]
        else:
            median_expense = (sorted_exp[mid - 1] + sorted_exp[mid]) / Decimal("2")

    return render_template(
        "finance/reports_statistics.html",
        tenant=g.tenant,
        company=company,
        start=start,
        end=end,
        kpis={
            "avg_expense_fmt": _fmt_money(avg_expense, base_cur),
            "avg_income_fmt": _fmt_money(avg_income, base_cur),
            "outliers_count": len(outlier_rows),
            "total_liabilities_fmt": _fmt_money(total_liabilities, base_cur),
            "trend_label": trend_label,
            "trend_change_pct": trend_change_pct,
            "median_expense_fmt": _fmt_money(median_expense, base_cur),
            "expense_income_ratio_pct": expense_income_ratio_pct,
            "monthly_volatility_pct": monthly_volatility_pct,
            "mc_expected_last_fmt": _fmt_money(Decimal(str(mc_expected_last or 0)), base_cur),
            "corr_top_pair": corr_top_pair,
            "corr_top_value": corr_top_value,
            "mc_horizon": montecarlo_horizon,
        },
        category_avg_rows=category_avg_rows,
        liability_rows=liability_rows,
        top_products=top_products,
        top_investments=top_investments,
        outlier_rows=outlier_rows[:20],
        gauss={
            "mean": gauss_mean,
            "std": gauss_std,
            "z_values": z_values,
        },
        trend={
            "labels": expense_trend_labels,
            "values": expense_trend_values,
            "slope": trend_slope,
        },
        montecarlo={
            "labels": mc_labels,
            "p10": mc_p10,
            "p50": mc_p50,
            "p90": mc_p90,
        },
        correlation={
            "labels": top_cats,
            "matrix": corr_matrix,
        },
        category_chart={
            "labels": [r["name"] for r in category_avg_rows[:12]],
            "values": [float(r["avg"]) for r in category_avg_rows[:12]],
        },
        granularity=granularity,
    )


@bp.route("/reports/accounting")
@login_required
@require_roles("tenant_admin", "creator", "viewer")
def reports_accounting():
    company = _get_company()

    today = date.today()
    try:
        start = datetime.strptime((request.args.get("start") or f"{today.year}-01-01"), "%Y-%m-%d").date()
    except Exception:
        start = date(today.year, 1, 1)
    try:
        end = datetime.strptime((request.args.get("end") or today.isoformat()), "%Y-%m-%d").date()
    except Exception:
        end = today

    gl_accounts = get_gl_accounts(company)
    gl_flat = _flatten_gl_accounts(gl_accounts)
    children_map = _gl_children_map(gl_accounts)
    leaf_ids = _leaf_gl_ids(gl_accounts)

    opening_rows = (
        db.session.query(
            FinanceLedgerLine.gl_account_id,
            func.coalesce(func.sum(FinanceLedgerLine.debit), 0),
            func.coalesce(func.sum(FinanceLedgerLine.credit), 0),
        )
        .join(FinanceLedgerVoucher, FinanceLedgerVoucher.id == FinanceLedgerLine.voucher_id)
        .filter(FinanceLedgerLine.tenant_id == g.tenant.id)
        .filter(FinanceLedgerLine.company_id == company.id)
        .filter(FinanceLedgerVoucher.voucher_date < start)
        .group_by(FinanceLedgerLine.gl_account_id)
        .all()
    )

    opening_line_count = (
        db.session.query(func.count(FinanceLedgerLine.id))
        .join(FinanceLedgerVoucher, FinanceLedgerVoucher.id == FinanceLedgerLine.voucher_id)
        .filter(FinanceLedgerLine.tenant_id == g.tenant.id)
        .filter(FinanceLedgerLine.company_id == company.id)
        .filter(FinanceLedgerVoucher.voucher_date < start)
        .scalar()
        or 0
    )

    period_line_count = (
        db.session.query(func.count(FinanceLedgerLine.id))
        .join(FinanceLedgerVoucher, FinanceLedgerVoucher.id == FinanceLedgerLine.voucher_id)
        .filter(FinanceLedgerLine.tenant_id == g.tenant.id)
        .filter(FinanceLedgerLine.company_id == company.id)
        .filter(FinanceLedgerVoucher.voucher_date >= start)
        .filter(FinanceLedgerVoucher.voucher_date <= end)
        .scalar()
        or 0
    )
    period_rows = (
        db.session.query(
            FinanceLedgerLine.gl_account_id,
            func.coalesce(func.sum(FinanceLedgerLine.debit), 0),
            func.coalesce(func.sum(FinanceLedgerLine.credit), 0),
        )
        .join(FinanceLedgerVoucher, FinanceLedgerVoucher.id == FinanceLedgerLine.voucher_id)
        .filter(FinanceLedgerLine.tenant_id == g.tenant.id)
        .filter(FinanceLedgerLine.company_id == company.id)
        .filter(FinanceLedgerVoucher.voucher_date >= start)
        .filter(FinanceLedgerVoucher.voucher_date <= end)
        .group_by(FinanceLedgerLine.gl_account_id)
        .all()
    )

    opening_map = {int(gl_id): (Decimal(str(deb or 0)) - Decimal(str(cred or 0))) for gl_id, deb, cred in opening_rows}
    period_map = {int(gl_id): (Decimal(str(deb or 0)), Decimal(str(cred or 0))) for gl_id, deb, cred in period_rows}

    def _natural_closing(gl_kind: str, opening_amt: Decimal, debit_amt: Decimal, credit_amt: Decimal) -> Decimal:
        signed = opening_amt + debit_amt - credit_amt
        return signed if (gl_kind or "").lower() in {"asset", "expense"} else -signed

    agg_cache: dict[int, dict] = {}

    def _aggregate_gl(gl_id: int) -> dict:
        cached = agg_cache.get(int(gl_id))
        if cached is not None:
            return cached

        gl = next((acc for acc in gl_accounts if int(acc.id) == int(gl_id)), None)
        if gl is None:
            result = {
                "opening": Decimal("0"),
                "debit": Decimal("0"),
                "credit": Decimal("0"),
                "closing": Decimal("0"),
            }
            agg_cache[int(gl_id)] = result
            return result

        direct_opening = opening_map.get(int(gl.id), Decimal("0"))
        direct_debit, direct_credit = period_map.get(int(gl.id), (Decimal("0"), Decimal("0")))

        children = children_map.get(int(gl.id), [])
        if not children:
            result = {
                "opening": direct_opening,
                "debit": direct_debit,
                "credit": direct_credit,
                "closing": _natural_closing(gl.kind or "", direct_opening, direct_debit, direct_credit),
            }
            agg_cache[int(gl.id)] = result
            return result

        opening_total = direct_opening
        debit_total = direct_debit
        credit_total = direct_credit
        closing_total = Decimal("0")

        if direct_opening != 0 or direct_debit != 0 or direct_credit != 0:
            closing_total += _natural_closing(gl.kind or "", direct_opening, direct_debit, direct_credit)

        for child in children:
            sub = _aggregate_gl(int(child.id))
            opening_total += Decimal(str(sub["opening"]))
            debit_total += Decimal(str(sub["debit"]))
            credit_total += Decimal(str(sub["credit"]))
            closing_total += Decimal(str(sub["closing"]))

        result = {
            "opening": opening_total,
            "debit": debit_total,
            "credit": credit_total,
            "closing": closing_total,
        }
        agg_cache[int(gl.id)] = result
        return result

    rows = []
    total_opening = Decimal("0")
    total_debit = Decimal("0")
    total_credit = Decimal("0")
    total_closing = Decimal("0")

    for gl, depth in gl_flat:
        agg = _aggregate_gl(int(gl.id))
        is_group = int(gl.id) not in leaf_ids
        rows.append({
            "gl_id": int(gl.id),
            "code": gl.code,
            "name": gl.name,
            "kind": gl.kind,
            "depth": int(depth),
            "is_group": bool(is_group),
            "opening": agg["opening"],
            "debit": agg["debit"],
            "credit": agg["credit"],
            "closing": agg["closing"],
        })

    for gl in gl_accounts:
        if int(gl.id) not in leaf_ids:
            continue
        leaf = _aggregate_gl(int(gl.id))
        total_opening += Decimal(str(leaf["opening"]))
        total_debit += Decimal(str(leaf["debit"]))
        total_credit += Decimal(str(leaf["credit"]))
        total_closing += Decimal(str(leaf["closing"]))

    investments = _safe_get_investments(company)
    invested_total = Decimal("0")
    current_value_total = Decimal("0")
    for inv in investments:
        if (inv.status or "active").lower() != "active":
            continue
        invested_total += Decimal(str(inv.invested_amount or 0))
        current_value_total += Decimal(str(inv.current_value if inv.current_value is not None else (inv.invested_amount or 0)))

    investment_summary = {
        "invested_total": invested_total,
        "current_value_total": current_value_total,
        "unrealized_result": current_value_total - invested_total,
    }

    detail_gl_id = request.args.get("detail_gl_id", type=int)
    detail_gl = None
    detail_rows = []
    if detail_gl_id:
        detail_gl = next((gl for gl in gl_accounts if int(gl.id) == int(detail_gl_id)), None)
        if detail_gl is not None:
            detail_query = (
                db.session.query(
                    FinanceLedgerVoucher.voucher_date,
                    FinanceLedgerVoucher.reference,
                    FinanceLedgerVoucher.description,
                    FinanceLedgerLine.debit,
                    FinanceLedgerLine.credit,
                    FinanceLedgerLine.description,
                )
                .join(FinanceLedgerVoucher, FinanceLedgerVoucher.id == FinanceLedgerLine.voucher_id)
                .filter(FinanceLedgerLine.tenant_id == g.tenant.id)
                .filter(FinanceLedgerLine.company_id == company.id)
                .filter(FinanceLedgerLine.gl_account_id == detail_gl_id)
                .filter(FinanceLedgerVoucher.voucher_date >= start)
                .filter(FinanceLedgerVoucher.voucher_date <= end)
                .order_by(FinanceLedgerVoucher.voucher_date.desc(), FinanceLedgerLine.id.desc())
                .limit(300)
            )
            for v_date, v_ref, v_desc, ln_debit, ln_credit, ln_desc in detail_query.all():
                detail_rows.append(
                    {
                        "voucher_date": v_date,
                        "voucher_ref": v_ref,
                        "voucher_desc": v_desc,
                        "line_desc": ln_desc,
                        "debit": Decimal(str(ln_debit or 0)),
                        "credit": Decimal(str(ln_credit or 0)),
                    }
                )

    return render_template(
        "finance/reports_accounting.html",
        tenant=g.tenant,
        company=company,
        start=start,
        end=end,
        rows=rows,
        totals={
            "opening": total_opening,
            "debit": total_debit,
            "credit": total_credit,
            "closing": total_closing,
        },
        investment_summary=investment_summary,
        accounting_explain={
            "gl_accounts": len(gl_accounts),
            "gl_groups": len(gl_accounts) - len(leaf_ids),
            "opening_line_count": int(opening_line_count),
            "period_line_count": int(period_line_count),
        },
        detail_gl=detail_gl,
        detail_rows=detail_rows,
        period_state=(
            FinanceAccountingPeriod.query.filter_by(
                tenant_id=g.tenant.id,
                company_id=company.id,
                period_start=start,
                period_end=end,
            ).first()
        ),
    )


def _is_period_closed(company: FinanceCompany, target_date: date) -> bool:
    period = (
        FinanceAccountingPeriod.query
        .filter_by(tenant_id=g.tenant.id, company_id=company.id, is_closed=True)
        .filter(FinanceAccountingPeriod.period_start <= target_date)
        .filter(FinanceAccountingPeriod.period_end >= target_date)
        .first()
    )
    return bool(period)


@bp.route("/reports/accounting/periods")
@login_required
@require_roles("tenant_admin", "creator", "viewer")
def reports_accounting_periods():
    company = _get_company()

    months_back = int(request.args.get("months") or 12)
    months_back = max(3, min(months_back, 36))
    today = date.today()

    periods = []
    for i in range(months_back):
        anchor = date(today.year, today.month, 1) - timedelta(days=31 * i)
        month_start = date(anchor.year, anchor.month, 1)
        next_month = date(anchor.year + 1, 1, 1) if anchor.month == 12 else date(anchor.year, anchor.month + 1, 1)
        month_end = next_month - timedelta(days=1)

        sums = (
            db.session.query(
                func.coalesce(func.sum(FinanceLedgerLine.debit), 0),
                func.coalesce(func.sum(FinanceLedgerLine.credit), 0),
                func.count(FinanceLedgerLine.id),
            )
            .join(FinanceLedgerVoucher, FinanceLedgerVoucher.id == FinanceLedgerLine.voucher_id)
            .filter(FinanceLedgerLine.tenant_id == g.tenant.id)
            .filter(FinanceLedgerLine.company_id == company.id)
            .filter(FinanceLedgerVoucher.voucher_date >= month_start)
            .filter(FinanceLedgerVoucher.voucher_date <= month_end)
            .first()
        )
        period_state = (
            FinanceAccountingPeriod.query
            .filter_by(
                tenant_id=g.tenant.id,
                company_id=company.id,
                period_start=month_start,
                period_end=month_end,
            )
            .first()
        )
        debit = Decimal(str((sums[0] if sums else 0) or 0))
        credit = Decimal(str((sums[1] if sums else 0) or 0))
        line_count = int((sums[2] if sums else 0) or 0)
        periods.append(
            {
                "start": month_start,
                "end": month_end,
                "debit": debit,
                "credit": credit,
                "line_count": line_count,
                "is_closed": bool(period_state and period_state.is_closed),
                "closed_at": (period_state.closed_at if period_state else None),
            }
        )

    periods = sorted(periods, key=lambda r: r["start"], reverse=True)

    return render_template(
        "finance/reports_accounting_periods.html",
        tenant=g.tenant,
        company=company,
        periods=periods,
        months_back=months_back,
    )


@bp.route("/reports/accounting/period/close", methods=["POST"])
@login_required
@require_roles("tenant_admin", "creator")
def close_accounting_period():
    company = _get_company()

    try:
        start = datetime.strptime((request.form.get("start") or "").strip(), "%Y-%m-%d").date()
        end = datetime.strptime((request.form.get("end") or "").strip(), "%Y-%m-%d").date()
    except Exception:
        flash(_("Período inválido."), "danger")
        return redirect(url_for("finance.reports_accounting_periods", company_id=company.id))

    if end < start:
        flash(_("Período inválido."), "danger")
        return redirect(url_for("finance.reports_accounting_periods", company_id=company.id))

    period = (
        FinanceAccountingPeriod.query
        .filter_by(tenant_id=g.tenant.id, company_id=company.id, period_start=start, period_end=end)
        .first()
    )
    if not period:
        period = FinanceAccountingPeriod(
            tenant_id=g.tenant.id,
            company_id=company.id,
            period_start=start,
            period_end=end,
        )
        db.session.add(period)

    period.is_closed = True
    period.closed_at = datetime.utcnow()
    period.closed_by_user_id = getattr(current_user, "id", None)
    period.reopened_at = None
    period.reopened_by_user_id = None
    period.note = (request.form.get("note") or "").strip() or None

    db.session.commit()
    flash(_("Período contábil fechado."), "success")
    return redirect(url_for("finance.reports_accounting_periods", company_id=company.id))


@bp.route("/reports/accounting/period/reopen", methods=["POST"])
@login_required
@require_roles("tenant_admin", "creator")
def reopen_accounting_period():
    company = _get_company()

    try:
        start = datetime.strptime((request.form.get("start") or "").strip(), "%Y-%m-%d").date()
        end = datetime.strptime((request.form.get("end") or "").strip(), "%Y-%m-%d").date()
    except Exception:
        flash(_("Período inválido."), "danger")
        return redirect(url_for("finance.reports_accounting_periods", company_id=company.id))

    period = (
        FinanceAccountingPeriod.query
        .filter_by(tenant_id=g.tenant.id, company_id=company.id, period_start=start, period_end=end)
        .first()
    )
    if not period:
        flash(_("Período não encontrado."), "warning")
        return redirect(url_for("finance.reports_accounting_periods", company_id=company.id))

    period.is_closed = False
    period.reopened_at = datetime.utcnow()
    period.reopened_by_user_id = getattr(current_user, "id", None)
    db.session.commit()

    flash(_("Período contábil reaberto."), "success")
    return redirect(url_for("finance.reports_accounting_periods", company_id=company.id))


@bp.route("/reports/accounting/source")
@login_required
@require_roles("tenant_admin", "creator", "viewer")
def reports_accounting_source():
    company = _get_company()

    gl_id = request.args.get("gl_id", type=int)
    if not gl_id:
        return jsonify({"error": "missing gl_id"}), 400

    today = date.today()
    try:
        start = datetime.strptime((request.args.get("start") or f"{today.year}-01-01"), "%Y-%m-%d").date()
    except Exception:
        start = date(today.year, 1, 1)
    try:
        end = datetime.strptime((request.args.get("end") or today.isoformat()), "%Y-%m-%d").date()
    except Exception:
        end = today

    gl = FinanceGLAccount.query.filter_by(id=gl_id, tenant_id=g.tenant.id, company_id=company.id).first()
    if not gl:
        return jsonify({"error": "gl account not found"}), 404

    descendant_ids: set[int] = set()
    stack: list[int] = [int(gl.id)]
    while stack:
        node_id = stack.pop()
        descendant_ids.add(node_id)
        children = (
            FinanceGLAccount.query
            .filter_by(tenant_id=g.tenant.id, company_id=company.id, parent_id=node_id)
            .all()
        )
        for child in children:
            c_id = int(child.id)
            if c_id not in descendant_ids:
                stack.append(c_id)

    detail_query = (
        db.session.query(
            FinanceLedgerVoucher.voucher_date,
            FinanceLedgerVoucher.reference,
            FinanceLedgerVoucher.description,
            FinanceLedgerLine.debit,
            FinanceLedgerLine.credit,
            FinanceLedgerLine.description,
        )
        .join(FinanceLedgerVoucher, FinanceLedgerVoucher.id == FinanceLedgerLine.voucher_id)
        .filter(FinanceLedgerLine.tenant_id == g.tenant.id)
        .filter(FinanceLedgerLine.company_id == company.id)
        .filter(FinanceLedgerLine.gl_account_id.in_(list(descendant_ids)))
        .filter(FinanceLedgerVoucher.voucher_date >= start)
        .filter(FinanceLedgerVoucher.voucher_date <= end)
        .order_by(FinanceLedgerVoucher.voucher_date.desc(), FinanceLedgerLine.id.desc())
        .limit(300)
    )

    rows = []
    for v_date, v_ref, v_desc, ln_debit, ln_credit, ln_desc in detail_query.all():
        rows.append(
            {
                "voucher_date": v_date.isoformat() if v_date else None,
                "voucher_ref": v_ref,
                "voucher_desc": v_desc,
                "line_desc": ln_desc,
                "debit": float(Decimal(str(ln_debit or 0))),
                "credit": float(Decimal(str(ln_credit or 0))),
            }
        )

    return jsonify(
        {
            "account": {
                "id": int(gl.id),
                "code": gl.code,
                "name": gl.name,
                "kind": gl.kind,
            },
            "start": start.isoformat(),
            "end": end.isoformat(),
            "rows": rows,
        }
    )


# -----------------
# Liabilities / financing
# -----------------


def _find_or_create_counterparty(company: FinanceCompany, name: str | None) -> FinanceCounterparty | None:
    nm = (name or "").strip()
    if not nm:
        return None
    existing = (
        FinanceCounterparty.query
        .filter_by(tenant_id=g.tenant.id)
        .filter(FinanceCounterparty.company_id == company.id)
        .filter(db.func.lower(FinanceCounterparty.name) == nm.lower())
        .first()
    )
    if existing:
        return existing
    cp = FinanceCounterparty(tenant_id=g.tenant.id, company_id=company.id, name=nm, kind="other")
    db.session.add(cp)
    db.session.flush()
    return cp


def _find_or_create_category(company: FinanceCompany, name: str | None, *, direction: str | None = None) -> FinanceCategory | None:
    nm = (name or "").strip()
    if not nm:
        return None
    existing = (
        FinanceCategory.query
        .filter_by(tenant_id=g.tenant.id, company_id=company.id)
        .filter(db.func.lower(FinanceCategory.name) == nm.lower())
        .first()
    )
    if existing:
        return existing
    kind = "expense"
    if direction == "inflow":
        kind = "income"
    cat = FinanceCategory(tenant_id=g.tenant.id, company_id=company.id, name=nm, kind=kind)
    db.session.add(cat)
    db.session.flush()
    return cat


def _compute_investment_liquid_sources(investments: list[FinanceInvestment]) -> Decimal:
    total = Decimal("0")
    for inv in investments:
        if (inv.status or "active").lower() != "active":
            continue
        provider = (inv.provider or "").lower()
        if provider not in {"edf", "stock_exchange"}:
            continue
        total += Decimal(str(inv.current_value if inv.current_value is not None else (inv.invested_amount or 0)))
    return total


def _investments_table_available(company: FinanceCompany) -> bool:
    try:
        (
            FinanceInvestment.query
            .filter_by(tenant_id=g.tenant.id, company_id=company.id)
            .limit(1)
            .all()
        )
        return True
    except SQLAlchemyError as e:
        finance_logger.warning(
            "event=finance.investments.table_unavailable tenant_id=%s company_id=%s err=%s",
            getattr(getattr(g, "tenant", None), "id", None),
            getattr(company, "id", None),
            str(e),
        )
        return False


def _safe_get_investments(company: FinanceCompany) -> list[FinanceInvestment]:
    if not _investments_table_available(company):
        return []
    return (
        FinanceInvestment.query
        .filter_by(tenant_id=g.tenant.id, company_id=company.id)
        .all()
    )


def _with_investment_liquidity(res: dict, investment_sources: Decimal) -> dict:
    out = dict(res)
    base_total_sources = Decimal(str(out.get("total_sources") or 0))
    uses_short_liab = Decimal(str(out.get("uses_short_liab") or 0))
    total_sources = base_total_sources + Decimal(str(investment_sources or 0))
    out["sources_investments"] = Decimal(str(investment_sources or 0))
    out["total_sources"] = total_sources
    out["liquidity_ratio"] = (total_sources / uses_short_liab) if uses_short_liab > 0 else None
    out["net_liquidity"] = total_sources - uses_short_liab
    return out


def _lookup_market_instruments(query: str, provider: str) -> list[dict]:
    q = (query or "").strip()
    p = (provider or "stock_exchange").strip().lower()
    if not q:
        return []

    cache_key = f"{p}:{q.lower()}"
    now_ts = time.time()
    cached = _INVEST_LOOKUP_CACHE.get(cache_key)
    if cached and cached[0] > now_ts:
        return cached[1]

    def _push(rows_list: list[dict], symbol: str, name: str, exchange: str, provider_name: str) -> None:
        sym = (symbol or "").strip()
        nm = (name or "").strip() or sym
        ex = (exchange or "").strip()
        if not sym and not nm:
            return
        key = (sym.lower(), nm.lower())
        seen = {(str(x.get("symbol") or "").lower(), str(x.get("name") or "").lower()) for x in rows_list}
        if key in seen:
            return
        rows_list.append(
            {
                "symbol": sym,
                "name": nm,
                "exchange": ex,
                "provider": provider_name,
            }
        )

    rows: list[dict] = []

    try:
        resp = requests.get(
            "https://query1.finance.yahoo.com/v1/finance/search",
            params={"q": q, "quotesCount": 12, "newsCount": 0},
            headers={"User-Agent": "Mozilla/5.0 AUDELA/1.0"},
            timeout=5,
        )
        resp.raise_for_status()
        payload = resp.json() if resp.content else {}
    except Exception as e:
        finance_logger.warning("event=finance.investments.lookup_failed provider=%s q=%s err=%s", p, q, str(e))
        payload = {}

    for it in (payload.get("quotes") or []):
        symbol = (it.get("symbol") or "").strip()
        short_name = (it.get("shortname") or it.get("longname") or "").strip()
        exch = (it.get("exchange") or "").strip()
        txt = f"{symbol} {short_name}".lower()
        if p == "edf" and "edf" not in txt:
            continue
        _push(rows, symbol, short_name, exch, p)

    # Fallback 2: Financial Modeling Prep demo endpoint (free/demo key)
    if not rows and p != "edf":
        try:
            r2 = requests.get(
                "https://financialmodelingprep.com/api/v3/search",
                params={"query": q, "limit": 10, "apikey": "demo"},
                headers={"User-Agent": "Mozilla/5.0 AUDELA/1.0"},
                timeout=5,
            )
            if r2.ok:
                payload2 = r2.json() if r2.content else []
                for it in (payload2 or []):
                    _push(
                        rows,
                        str(it.get("symbol") or ""),
                        str(it.get("name") or ""),
                        str(it.get("exchangeShortName") or it.get("exchange") or ""),
                        p,
                    )
        except Exception as e:
            finance_logger.warning("event=finance.investments.lookup_fallback_failed provider=%s q=%s err=%s", p, q, str(e))

    # Fallback 3: local quick symbols for common queries
    if not rows:
        local_catalog = [
            ("EDF.PA", "EDF", "EURONEXT"),
            ("TSLA", "Tesla", "NASDAQ"),
            ("AAPL", "Apple", "NASDAQ"),
            ("MSFT", "Microsoft", "NASDAQ"),
            ("AIR.PA", "Airbus", "EURONEXT"),
            ("MC.PA", "LVMH", "EURONEXT"),
        ]
        ql = q.lower()
        for sym, nm, exch in local_catalog:
            txt = f"{sym} {nm}".lower()
            if ql in txt:
                if p == "edf" and "edf" not in txt:
                    continue
                _push(rows, sym, nm, exch, p)

    if p == "edf" and not rows:
        _push(rows, "EDF.PA", "EDF", "EURONEXT", "edf")

    result = rows[:10]
    _INVEST_LOOKUP_CACHE[cache_key] = (now_ts + max(5, _INVEST_LOOKUP_CACHE_TTL_S), result)
    if len(_INVEST_LOOKUP_CACHE) > 500:
        # Keep cache bounded with a lightweight sweep.
        expired = [k for k, (exp, _val) in _INVEST_LOOKUP_CACHE.items() if exp <= now_ts]
        for k in expired[:250]:
            _INVEST_LOOKUP_CACHE.pop(k, None)
    return result


def _history_params(horizon: str) -> tuple[str, str]:
    hz = (horizon or "1y").strip().lower()
    if hz in {"24h", "1d", "day"}:
        return "1d", "5m"
    if hz in {"5y", "5years", "5a"}:
        return "5y", "1wk"
    return "1y", "1d"


def _load_market_history(symbol: str, horizon: str) -> list[dict]:
    sym = (symbol or "").strip()
    if not sym:
        return []

    range_v, interval_v = _history_params(horizon)
    cache_key = f"{sym.upper()}:{range_v}:{interval_v}"
    now_ts = time.time()
    cached = _INVEST_HISTORY_CACHE.get(cache_key)
    if cached and cached[0] > now_ts:
        return cached[1]

    points: list[dict] = []
    try:
        resp = requests.get(
            f"https://query1.finance.yahoo.com/v8/finance/chart/{sym}",
            params={"range": range_v, "interval": interval_v},
            headers={"User-Agent": "Mozilla/5.0 AUDELA/1.0"},
            timeout=8,
        )
        resp.raise_for_status()
        payload = resp.json() if resp.content else {}
        result = ((payload.get("chart") or {}).get("result") or [None])[0] or {}
        timestamps = result.get("timestamp") or []
        quotes = ((result.get("indicators") or {}).get("quote") or [None])[0] or {}
        closes = quotes.get("close") or []

        for ts, close in zip(timestamps, closes):
            if close is None:
                continue
            try:
                points.append(
                    {
                        "t": datetime.utcfromtimestamp(int(ts)).isoformat(),
                        "v": float(close),
                    }
                )
            except Exception:
                continue
    except Exception as e:
        finance_logger.warning("event=finance.investments.history_failed symbol=%s horizon=%s err=%s", sym, horizon, str(e))

    _INVEST_HISTORY_CACHE[cache_key] = (now_ts + max(30, _INVEST_HISTORY_CACHE_TTL_S), points)
    if len(_INVEST_HISTORY_CACHE) > 1000:
        expired = [k for k, (exp, _val) in _INVEST_HISTORY_CACHE.items() if exp <= now_ts]
        for k in expired[:500]:
            _INVEST_HISTORY_CACHE.pop(k, None)
    return points


@bp.route("/investments/lookup", methods=["GET"])
@login_required
@require_roles("tenant_admin", "creator", "viewer")
def investments_lookup():
    _get_company()
    provider = (request.args.get("provider") or "stock_exchange").strip().lower()
    query = (request.args.get("q") or "").strip()
    rows = _lookup_market_instruments(query, provider)
    return jsonify({"items": rows})


@bp.route("/investments")
@login_required
@require_roles("tenant_admin", "creator", "viewer")
def investments_list():
    company = _get_company()
    items = sorted(_safe_get_investments(company), key=lambda x: x.updated_at or datetime.min, reverse=True)

    provider_filter = (request.args.get("provider") or "").strip().lower()
    status_filter = (request.args.get("status") or "").strip().lower()
    search_filter = (request.args.get("q") or "").strip().lower()

    if provider_filter:
        items = [x for x in items if (x.provider or "").lower() == provider_filter]
    if status_filter:
        items = [x for x in items if (x.status or "").lower() == status_filter]
    if search_filter:
        items = [
            x
            for x in items
            if search_filter in (x.name or "").lower()
            or search_filter in (x.instrument_code or "").lower()
        ]

    def _provider_label(provider: str | None) -> str:
        if (provider or "").lower() == "edf":
            return "EDF"
        return _("Bolsa de valores")

    rows = []
    for inv in items:
        invested = Decimal(str(inv.invested_amount or 0))
        current_value = Decimal(str(inv.current_value if inv.current_value is not None else (inv.invested_amount or 0)))
        rows.append(
            {
                "id": inv.id,
                "name": inv.name,
                "provider": inv.provider,
                "provider_label": _provider_label(inv.provider),
                "instrument_code": inv.instrument_code,
                "status": inv.status,
                "status_label": _("Ativo") if (inv.status or "").lower() == "active" else _("Encerrado"),
                "started_on": inv.started_on,
                "currency": inv.currency_code or company.base_currency,
                "invested_fmt": _fmt_money(invested, inv.currency_code or company.base_currency),
                "current_fmt": _fmt_money(current_value, inv.currency_code or company.base_currency),
                "pnl_fmt": _fmt_money(current_value - invested, inv.currency_code or company.base_currency),
            }
        )

    return render_template(
        "finance/investments_list.html",
        tenant=g.tenant,
        company=company,
        items=rows,
        filters={
            "provider": provider_filter,
            "status": status_filter,
            "q": request.args.get("q") or "",
        },
    )


@bp.route("/investments/new", methods=["GET", "POST"])
@login_required
@require_roles("tenant_admin", "creator")
def investment_new():
    company = _get_company()
    if not _investments_table_available(company):
        flash(_("Module Investimentos indisponível: execute as migrações do banco."), "error")
        return redirect(url_for("finance.dashboard"))

    accounts = (
        FinanceAccount.query
        .filter_by(tenant_id=g.tenant.id, company_id=company.id)
        .filter(FinanceAccount.account_type.in_(["cash", "bank"]))
        .order_by(FinanceAccount.name.asc())
        .all()
    )

    if request.method == "POST":
        name = (request.form.get("name") or "").strip()
        provider = (request.form.get("provider") or "stock_exchange").strip().lower()
        instrument_code = (request.form.get("instrument_code") or "").strip() or None
        account_id = int(request.form.get("account_id") or 0)
        currency_code = (request.form.get("currency_code") or "").strip().upper() or None
        invested_amount_raw = (request.form.get("invested_amount") or "0").strip().replace(",", ".")
        current_value_raw = (request.form.get("current_value") or "").strip().replace(",", ".")
        started_on_raw = (request.form.get("started_on") or "").strip()
        notes = (request.form.get("notes") or "").strip() or None

        if not name:
            flash(_("Preencha o nome."), "error")
            return redirect(url_for("finance.investment_new"))

        if provider not in {"edf", "stock_exchange"}:
            provider = "stock_exchange"

        acc = FinanceAccount.query.filter_by(id=account_id, tenant_id=g.tenant.id, company_id=company.id).first() if account_id else None
        if not acc:
            flash(_("Selecione uma conta de caixa/banco para liquidação."), "error")
            return redirect(url_for("finance.investment_new"))

        try:
            invested_amount = abs(Decimal(invested_amount_raw))
            current_value = Decimal(current_value_raw) if current_value_raw else invested_amount
            started_on = date.fromisoformat(started_on_raw) if started_on_raw else date.today()
        except Exception:
            flash(_("Dados inválidos."), "error")
            return redirect(url_for("finance.investment_new"))

        inv = FinanceInvestment(
            tenant_id=g.tenant.id,
            company_id=company.id,
            name=name,
            provider=provider,
            instrument_code=instrument_code,
            account_id=acc.id,
            currency_code=currency_code or acc.currency,
            invested_amount=invested_amount,
            current_value=current_value,
            started_on=started_on,
            status="active",
            notes=notes,
        )
        db.session.add(inv)

        if invested_amount > 0:
            if not _ensure_transaction_quota(1):
                return redirect(url_for("finance.investments_list"))
            db.session.add(
                FinanceTransaction(
                    tenant_id=g.tenant.id,
                    company_id=company.id,
                    account_id=acc.id,
                    txn_date=started_on,
                    amount=-abs(invested_amount),
                    description=f"Investimento inicial: {name}",
                    category="investment_buy",
                    reference=instrument_code,
                )
            )

        db.session.commit()
        flash(_("Investimento criado e refletido no cashflow."), "success")
        return redirect(url_for("finance.investments_list"))

    return render_template(
        "finance/investment_form.html",
        tenant=g.tenant,
        company=company,
        title=_("Novo investimento"),
        accounts=accounts,
        currencies=get_currencies(),
        form={
            "name": "",
            "provider": "stock_exchange",
            "instrument_code": "",
            "account_id": "",
            "currency_code": company.base_currency,
            "invested_amount": "",
            "current_value": "",
            "started_on": date.today().isoformat(),
            "notes": "",
        },
    )


@bp.route("/investments/<int:investment_id>/update", methods=["POST"])
@login_required
@require_roles("tenant_admin", "creator")
def investment_update(investment_id: int):
    company = _get_company()
    if not _investments_table_available(company):
        flash(_("Module Investimentos indisponível: execute as migrações do banco."), "error")
        return redirect(url_for("finance.dashboard"))

    inv = FinanceInvestment.query.filter_by(id=investment_id, tenant_id=g.tenant.id, company_id=company.id).first_or_404()

    current_value_raw = (request.form.get("current_value") or "").strip().replace(",", ".")
    status = (request.form.get("status") or inv.status or "active").strip().lower()
    if status not in {"active", "closed"}:
        status = "active"

    try:
        inv.current_value = Decimal(current_value_raw) if current_value_raw else inv.current_value
    except Exception:
        flash(_("Valor inválido."), "error")
        return redirect(url_for("finance.investments_list"))

    inv.status = status
    db.session.commit()
    flash(_("Investimento atualizado."), "success")
    return redirect(url_for("finance.investments_list"))


@bp.route("/investments/<int:investment_id>/cash_event", methods=["POST"])
@login_required
@require_roles("tenant_admin", "creator")
def investment_cash_event(investment_id: int):
    company = _get_company()
    if not _investments_table_available(company):
        flash(_("Module Investimentos indisponível: execute as migrações do banco."), "error")
        return redirect(url_for("finance.dashboard"))

    inv = FinanceInvestment.query.filter_by(id=investment_id, tenant_id=g.tenant.id, company_id=company.id).first_or_404()

    event_type = (request.form.get("event_type") or "sell").strip().lower()
    amount_raw = (request.form.get("amount") or "0").strip().replace(",", ".")
    txn_date_raw = (request.form.get("txn_date") or date.today().isoformat()).strip()

    try:
        amount = abs(Decimal(amount_raw))
        txn_date = date.fromisoformat(txn_date_raw)
    except Exception:
        flash(_("Dados inválidos."), "error")
        return redirect(url_for("finance.investments_list"))

    if event_type not in {"buy", "sell", "dividend", "fee"}:
        event_type = "sell"

    sign = Decimal("1") if event_type in {"sell", "dividend"} else Decimal("-1")
    txn_amount = sign * amount

    if not inv.account_id:
        flash(_("Defina uma conta no investimento antes de registrar evento de caixa."), "error")
        return redirect(url_for("finance.investments_list"))

    if not _ensure_transaction_quota(1):
        return redirect(url_for("finance.investments_list"))

    db.session.add(
        FinanceTransaction(
            tenant_id=g.tenant.id,
            company_id=company.id,
            account_id=inv.account_id,
            txn_date=txn_date,
            amount=txn_amount,
            description=f"Investimento {event_type}: {inv.name}",
            category=f"investment_{event_type}",
            reference=inv.instrument_code,
        )
    )

    if event_type == "buy":
        inv.invested_amount = Decimal(str(inv.invested_amount or 0)) + amount
    elif event_type == "sell":
        base = Decimal(str(inv.invested_amount or 0))
        inv.invested_amount = max(Decimal("0"), base - amount)

    db.session.commit()
    flash(_("Evento de investimento registrado."), "success")
    return redirect(url_for("finance.investments_list"))


@bp.route("/investments/<int:investment_id>/history", methods=["GET"])
@login_required
@require_roles("tenant_admin", "creator", "viewer")
def investment_history(investment_id: int):
    company = _get_company()
    if not _investments_table_available(company):
        return jsonify({"error": "investments module unavailable", "items": []}), 400

    inv = FinanceInvestment.query.filter_by(id=investment_id, tenant_id=g.tenant.id, company_id=company.id).first_or_404()
    horizon = (request.args.get("horizon") or "1y").strip().lower()
    if horizon not in {"24h", "1y", "5y"}:
        horizon = "1y"

    symbol = (inv.instrument_code or "").strip()
    if not symbol:
        return jsonify(
            {
                "investment_id": inv.id,
                "symbol": "",
                "horizon": horizon,
                "points": [],
                "message": "instrument code missing",
            }
        )

    points = _load_market_history(symbol, horizon)
    return jsonify(
        {
            "investment_id": inv.id,
            "symbol": symbol,
            "horizon": horizon,
            "points": points,
        }
    )


@bp.route("/liabilities")
@login_required
@require_roles("tenant_admin", "creator", "viewer")
def liabilities_list():
    company = _get_company()
    items = (
        FinanceLiability.query
        .filter_by(tenant_id=g.tenant.id, company_id=company.id)
        .order_by(FinanceLiability.updated_at.desc())
        .all()
    )
    rows = []
    for l in items:
        rows.append(
            {
                "id": l.id,
                "name": l.name,
                "currency_code": l.currency_code,
                "maturity_date": l.maturity_date,
                "lender_name": l.lender.name if l.lender else "",
                "outstanding_fmt": _fmt_money(Decimal(str(l.outstanding_amount or 0)), l.currency_code or company.base_currency),
                "rate_fmt": (str(l.interest_rate) if l.interest_rate is not None else ""),
            }
        )
    return render_template(
        "finance/liabilities_list.html",
        tenant=g.tenant,
        company=company,
        liabilities=rows,
    )


@bp.route("/liabilities/new", methods=["GET", "POST"])
@login_required
@require_roles("tenant_admin", "creator")
def liability_new():
    company = _get_company()
    if request.method == "POST":
        name = (request.form.get("name") or "").strip()
        lender_name = (request.form.get("lender") or "").strip()
        currency = (request.form.get("currency") or "").strip().upper() or None
        principal = (request.form.get("principal_amount") or "").strip()
        outstanding = (request.form.get("outstanding_amount") or "").strip()
        rate = (request.form.get("interest_rate") or "").strip()
        start_date = (request.form.get("start_date") or "").strip() or None
        maturity_date = (request.form.get("maturity_date") or "").strip() or None
        freq = (request.form.get("payment_frequency") or "monthly").strip() or "monthly"
        installment = (request.form.get("installment_amount") or "").strip()
        next_pay = (request.form.get("next_payment_date") or "").strip() or None
        notes = (request.form.get("notes") or "").strip() or None

        if not name:
            flash(_("Preencha o nome."), "error")
            return redirect(url_for("finance.liability_new"))

        cp = _find_or_create_counterparty(company, lender_name)

        def _dec(v: str) -> Decimal | None:
            v = (v or "").strip()
            if not v:
                return None
            return Decimal(v.replace(",", "."))

        l = FinanceLiability(
            tenant_id=g.tenant.id,
            company_id=company.id,
            name=name,
            lender_counterparty_id=cp.id if cp else None,
            currency_code=currency,
            principal_amount=_dec(principal),
            outstanding_amount=_dec(outstanding),
            interest_rate=_dec(rate),
            start_date=date.fromisoformat(start_date) if start_date else None,
            maturity_date=date.fromisoformat(maturity_date) if maturity_date else None,
            payment_frequency=freq,
            installment_amount=_dec(installment),
            next_payment_date=date.fromisoformat(next_pay) if next_pay else None,
            notes=notes,
        )
        db.session.add(l)
        db.session.commit()
        flash(_("Financiamento criado."), "success")
        return redirect(url_for("finance.liabilities_list"))

    return render_template(
        "finance/liability_form.html",
        tenant=g.tenant,
        company=company,
        title=_("Novo financiamento"),
        currencies=get_currencies(),
        counterparties=get_counterparties(company),
        form={
            "name": "",
            "lender": "",
            "currency": company.base_currency,
            "principal_amount": "",
            "outstanding_amount": "",
            "interest_rate": "",
            "start_date": "",
            "maturity_date": "",
            "payment_frequency": "monthly",
            "installment_amount": "",
            "next_payment_date": "",
            "notes": "",
        },
    )


@bp.route("/liabilities/<int:liability_id>/edit", methods=["GET", "POST"])
@login_required
@require_roles("tenant_admin", "creator")
def liability_edit(liability_id: int):
    company = _get_company()
    l = FinanceLiability.query.filter_by(id=liability_id, tenant_id=g.tenant.id, company_id=company.id).first_or_404()

    if request.method == "POST":
        name = (request.form.get("name") or "").strip()
        lender_name = (request.form.get("lender") or "").strip()
        currency = (request.form.get("currency") or "").strip().upper() or None
        principal = (request.form.get("principal_amount") or "").strip()
        outstanding = (request.form.get("outstanding_amount") or "").strip()
        rate = (request.form.get("interest_rate") or "").strip()
        start_date = (request.form.get("start_date") or "").strip() or None
        maturity_date = (request.form.get("maturity_date") or "").strip() or None
        freq = (request.form.get("payment_frequency") or "monthly").strip() or "monthly"
        installment = (request.form.get("installment_amount") or "").strip()
        next_pay = (request.form.get("next_payment_date") or "").strip() or None
        notes = (request.form.get("notes") or "").strip() or None

        if not name:
            flash(_("Preencha o nome."), "error")
            return redirect(url_for("finance.liability_edit", liability_id=liability_id))

        cp = _find_or_create_counterparty(company, lender_name)

        def _dec(v: str) -> Decimal | None:
            v = (v or "").strip()
            if not v:
                return None
            return Decimal(v.replace(",", "."))

        l.name = name
        l.lender_counterparty_id = cp.id if cp else None
        l.currency_code = currency
        l.principal_amount = _dec(principal)
        l.outstanding_amount = _dec(outstanding)
        l.interest_rate = _dec(rate)
        l.start_date = date.fromisoformat(start_date) if start_date else None
        l.maturity_date = date.fromisoformat(maturity_date) if maturity_date else None
        l.payment_frequency = freq
        l.installment_amount = _dec(installment)
        l.next_payment_date = date.fromisoformat(next_pay) if next_pay else None
        l.notes = notes
        db.session.commit()
        flash(_("Financiamento atualizado."), "success")
        return redirect(url_for("finance.liabilities_list"))

    return render_template(
        "finance/liability_form.html",
        tenant=g.tenant,
        company=company,
        title=_("Editar financiamento"),
        currencies=get_currencies(),
        counterparties=get_counterparties(company),
        form={
            "name": l.name,
            "lender": l.lender.name if l.lender else "",
            "currency": l.currency_code or company.base_currency,
            "principal_amount": str(l.principal_amount or ""),
            "outstanding_amount": str(l.outstanding_amount or ""),
            "interest_rate": str(l.interest_rate or ""),
            "start_date": l.start_date.isoformat() if l.start_date else "",
            "maturity_date": l.maturity_date.isoformat() if l.maturity_date else "",
            "payment_frequency": l.payment_frequency or "monthly",
            "installment_amount": str(l.installment_amount or ""),
            "next_payment_date": l.next_payment_date.isoformat() if l.next_payment_date else "",
            "notes": l.notes or "",
        },
    )


@bp.route("/liabilities/<int:liability_id>/delete", methods=["POST"])
@login_required
@require_roles("tenant_admin", "creator")
def liability_delete(liability_id: int):
    company = _get_company()
    l = FinanceLiability.query.filter_by(id=liability_id, tenant_id=g.tenant.id, company_id=company.id).first_or_404()
    db.session.delete(l)
    db.session.commit()
    flash(_("Financiamento removido."), "success")
    return redirect(url_for("finance.liabilities_list"))


# -----------------
# Recurring transactions
# -----------------


def _add_months(d: date, months: int) -> date:
    y = d.year + (d.month - 1 + months) // 12
    m = (d.month - 1 + months) % 12 + 1
    # clamp day
    day = d.day
    # days in month
    if m == 12:
        next_month = date(y + 1, 1, 1)
    else:
        next_month = date(y, m + 1, 1)
    last_day = (next_month - timedelta(days=1)).day
    day = min(day, last_day)
    return date(y, m, day)


def _next_date(d: date, freq: str) -> date:
    if freq == "daily":
        return d + timedelta(days=1)
    if freq == "weekly":
        return d + timedelta(days=7)
    if freq == "yearly":
        try:
            return date(d.year + 1, d.month, d.day)
        except Exception:
            # Feb 29 -> Feb 28
            return date(d.year + 1, d.month, 28)
    # monthly default
    return _add_months(d, 1)


@bp.route("/recurring")
@login_required
@require_roles("tenant_admin", "creator", "viewer")
def recurring_list():
    company = _get_company()
    items = (
        FinanceRecurringTransaction.query
        .filter_by(tenant_id=g.tenant.id, company_id=company.id)
        .order_by(FinanceRecurringTransaction.active.desc(), FinanceRecurringTransaction.next_run_date.asc())
        .all()
    )
    rows = []
    for r in items:
        rows.append(
            {
                "id": r.id,
                "name": r.name,
                "account_name": r.account.name if r.account else "",
                "frequency": r.frequency,
                "next_run_date": r.next_run_date,
                "amount_fmt": _fmt_money(Decimal(str(r.amount or 0)), r.currency_code or (r.account.currency if r.account else company.base_currency)),
            }
        )
    return render_template(
        "finance/recurring_list.html",
        tenant=g.tenant,
        company=company,
        items=rows,
    )


def _recurring_form_context(company: FinanceCompany, r: FinanceRecurringTransaction | None = None):
    accounts = _q_accounts(company).order_by(FinanceAccount.name.asc()).all()
    categories = get_categories(company)
    counterparties = get_counterparties(company)
    currencies = get_currencies()

    if r is None:
        today = date.today().isoformat()
        return {
            "accounts": accounts,
            "categories": categories,
            "counterparties": counterparties,
            "currencies": currencies,
            "form": {
                "name": "",
                "account_id": (accounts[0].id if accounts else None),
                "direction": "outflow",
                "amount": "",
                "currency": company.base_currency,
                "frequency": "monthly",
                "next_run_date": today,
                "end_date": "",
                "category": "",
                "counterparty": "",
                "description": "",
                "active": True,
            },
        }

    return {
        "accounts": accounts,
        "categories": categories,
        "counterparties": counterparties,
        "currencies": currencies,
        "form": {
            "name": r.name,
            "account_id": r.account_id,
            "direction": r.direction,
            "amount": str(r.amount),
            "currency": r.currency_code or company.base_currency,
            "frequency": r.frequency,
            "next_run_date": r.next_run_date.isoformat() if r.next_run_date else date.today().isoformat(),
            "end_date": r.end_date.isoformat() if r.end_date else "",
            "category": r.category_ref.name if r.category_ref else "",
            "counterparty": r.counterparty_ref.name if r.counterparty_ref else "",
            "description": r.description or "",
            "active": bool(r.active),
        },
    }


@bp.route("/recurring/new", methods=["GET", "POST"])
@login_required
@require_roles("tenant_admin", "creator")
def recurring_new():
    company = _get_company()
    ctx = _recurring_form_context(company)
    if request.method == "POST":
        try:
            account_id = int(request.form.get("account_id") or 0)
        except Exception:
            account_id = 0
        account = FinanceAccount.query.filter_by(id=account_id, tenant_id=g.tenant.id, company_id=company.id).first()
        if not account:
            flash(_("Conta inválida."), "error")
            return redirect(url_for("finance.recurring_new"))

        name = (request.form.get("name") or "").strip()
        direction = (request.form.get("direction") or "outflow").strip()
        amount_raw = (request.form.get("amount") or "").strip()
        currency = (request.form.get("currency") or "").strip().upper() or None
        frequency = (request.form.get("frequency") or "monthly").strip()
        next_run = (request.form.get("next_run_date") or "").strip()
        end_date = (request.form.get("end_date") or "").strip() or None
        category_name = (request.form.get("category") or "").strip()
        cp_name = (request.form.get("counterparty") or "").strip()
        desc = (request.form.get("description") or "").strip() or None
        active = bool(request.form.get("active"))

        if not name or not amount_raw or not next_run:
            flash(_("Preencha nome, valor e próxima data."), "error")
            return redirect(url_for("finance.recurring_new"))

        cat = _find_or_create_category(company, category_name, direction=direction)
        cp = _find_or_create_counterparty(company, cp_name)

        amount = Decimal(amount_raw.replace(",", "."))

        r = FinanceRecurringTransaction(
            tenant_id=g.tenant.id,
            company_id=company.id,
            name=name,
            account_id=account.id,
            direction=direction if direction in ("inflow", "outflow") else "outflow",
            amount=amount,
            currency_code=currency,
            category_id=cat.id if cat else None,
            counterparty_id=cp.id if cp else None,
            description=desc,
            frequency=frequency if frequency in ("daily", "weekly", "monthly", "yearly") else "monthly",
            next_run_date=date.fromisoformat(next_run),
            end_date=date.fromisoformat(end_date) if end_date else None,
            active=active,
        )
        db.session.add(r)
        db.session.commit()
        flash(_("Recorrência criada."), "success")
        return redirect(url_for("finance.recurring_list"))

    return render_template(
        "finance/recurring_form.html",
        tenant=g.tenant,
        company=company,
        title=_("Nova recorrência"),
        **ctx,
    )


@bp.route("/recurring/<int:recurring_id>/edit", methods=["GET", "POST"])
@login_required
@require_roles("tenant_admin", "creator")
def recurring_edit(recurring_id: int):
    company = _get_company()
    r = FinanceRecurringTransaction.query.filter_by(id=recurring_id, tenant_id=g.tenant.id, company_id=company.id).first_or_404()
    ctx = _recurring_form_context(company, r)

    if request.method == "POST":
        try:
            account_id = int(request.form.get("account_id") or 0)
        except Exception:
            account_id = 0
        account = FinanceAccount.query.filter_by(id=account_id, tenant_id=g.tenant.id, company_id=company.id).first()
        if not account:
            flash(_("Conta inválida."), "error")
            return redirect(url_for("finance.recurring_edit", recurring_id=recurring_id))

        name = (request.form.get("name") or "").strip()
        direction = (request.form.get("direction") or "outflow").strip()
        amount_raw = (request.form.get("amount") or "").strip()
        currency = (request.form.get("currency") or "").strip().upper() or None
        frequency = (request.form.get("frequency") or "monthly").strip()
        next_run = (request.form.get("next_run_date") or "").strip()
        end_date = (request.form.get("end_date") or "").strip() or None
        category_name = (request.form.get("category") or "").strip()
        cp_name = (request.form.get("counterparty") or "").strip()
        desc = (request.form.get("description") or "").strip() or None
        active = bool(request.form.get("active"))

        if not name or not amount_raw or not next_run:
            flash(_("Preencha nome, valor e próxima data."), "error")
            return redirect(url_for("finance.recurring_edit", recurring_id=recurring_id))

        cat = _find_or_create_category(company, category_name, direction=direction)
        cp = _find_or_create_counterparty(company, cp_name)

        amount = Decimal(amount_raw.replace(",", "."))

        r.name = name
        r.account_id = account.id
        r.direction = direction if direction in ("inflow", "outflow") else "outflow"
        r.amount = amount
        r.currency_code = currency
        r.category_id = cat.id if cat else None
        r.counterparty_id = cp.id if cp else None
        r.description = desc
        r.frequency = frequency if frequency in ("daily", "weekly", "monthly", "yearly") else "monthly"
        r.next_run_date = date.fromisoformat(next_run)
        r.end_date = date.fromisoformat(end_date) if end_date else None
        r.active = active

        db.session.commit()
        flash(_("Recorrência atualizada."), "success")
        return redirect(url_for("finance.recurring_list"))

    return render_template(
        "finance/recurring_form.html",
        tenant=g.tenant,
        company=company,
        title=_("Editar recorrência"),
        **ctx,
    )


@bp.route("/recurring/<int:recurring_id>/delete", methods=["POST"])
@login_required
@require_roles("tenant_admin", "creator")
def recurring_delete(recurring_id: int):
    company = _get_company()
    r = FinanceRecurringTransaction.query.filter_by(id=recurring_id, tenant_id=g.tenant.id, company_id=company.id).first_or_404()
    db.session.delete(r)
    db.session.commit()
    flash(_("Recorrência removida."), "success")
    return redirect(url_for("finance.recurring_list"))


@bp.route("/recurring/generate", methods=["POST"])
@login_required
@require_roles("tenant_admin", "creator")
def recurring_generate():
    company = _get_company()
    target = date.today()

    items = (
        FinanceRecurringTransaction.query
        .filter_by(tenant_id=g.tenant.id, company_id=company.id, active=True)
        .order_by(FinanceRecurringTransaction.next_run_date.asc())
        .all()
    )
    created = 0
    allowed, remaining, current_count, max_limit = _transaction_quota_info()
    if not allowed or remaining <= 0:
        flash(_("Limite de transações do plano atingida ({current}/{max}).", current=current_count, max=max_limit), "error")
        return redirect(url_for("finance.recurring_list"))

    for r in items:
        if created >= remaining:
            break
        next_d = r.next_run_date
        while next_d and next_d <= target:
            if created >= remaining:
                break
            if r.end_date and next_d > r.end_date:
                break

            sign = Decimal("1")
            if r.direction == "outflow":
                sign = Decimal("-1")
            amt = sign * Decimal(str(r.amount or 0))

            txn = FinanceTransaction(
                tenant_id=g.tenant.id,
                company_id=company.id,
                account_id=r.account_id,
                txn_date=next_d,
                amount=amt,
                description=r.description or r.name,
                category_id=r.category_id,
                category=(r.category_ref.name if r.category_ref else None),
                counterparty_id=r.counterparty_id,
                counterparty=(r.counterparty_ref.name if r.counterparty_ref else None),
            )
            db.session.add(txn)
            created += 1

            next_d = _next_date(next_d, r.frequency)

        if next_d and next_d != r.next_run_date:
            r.next_run_date = next_d

    db.session.commit()
    flash(_(f"{created} transações geradas."), "success")
    if created >= remaining:
        flash(_("Geração limitada pelo plano de transações."), "warning")
    return redirect(url_for("finance.recurring_list"))


# -----------------
# Quick entry (+ AI parsing)
# -----------------


def _get_default_account(company: FinanceCompany) -> FinanceAccount | None:
    acc = (
        _q_accounts(company)
        .filter(FinanceAccount.account_type == "bank")
        .order_by(FinanceAccount.id.asc())
        .first()
    )
    if acc:
        return acc
    return _q_accounts(company).order_by(FinanceAccount.id.asc()).first()


@bp.route("/quick-entry", methods=["GET", "POST"])
@login_required
@require_roles("tenant_admin", "creator")
def quick_entry():
    company = _get_company()
    accounts = _q_accounts(company).order_by(FinanceAccount.name.asc()).all()
    categories = get_categories(company)
    counterparties = get_counterparties(company)
    default_acc = _get_default_account(company)

    if request.method == "POST":
        try:
            account_id = int(request.form.get("account_id") or (default_acc.id if default_acc else 0))
        except Exception:
            account_id = default_acc.id if default_acc else 0
        account = FinanceAccount.query.filter_by(id=account_id, tenant_id=g.tenant.id, company_id=company.id).first()
        if not account:
            flash(_("Conta inválida."), "error")
            return redirect(url_for("finance.quick_entry"))

        direction = (request.form.get("direction") or "outflow").strip()
        amt_raw = (request.form.get("amount") or "").strip()
        d_raw = (request.form.get("txn_date") or "").strip()
        category_name = (request.form.get("category") or "").strip()
        cp_name = (request.form.get("counterparty") or "").strip()
        desc = (request.form.get("description") or "").strip() or None

        if not amt_raw:
            flash(_("Informe o valor."), "error")
            return redirect(url_for("finance.quick_entry"))

        try:
            amount = Decimal(amt_raw.replace(",", "."))
        except Exception:
            flash(_("Valor inválido."), "error")
            return redirect(url_for("finance.quick_entry"))

        if amount < 0:
            amount = abs(amount)

        sign = Decimal("-1") if direction == "outflow" else Decimal("1")
        signed_amount = sign * amount

        txn_date = date.today()
        if d_raw:
            try:
                txn_date = date.fromisoformat(d_raw)
            except Exception:
                pass

        if not _ensure_transaction_quota(1):
            return redirect(url_for("finance.quick_entry"))

        cat = _find_or_create_category(company, category_name, direction=direction)
        cp = _find_or_create_counterparty(company, cp_name)

        txn = FinanceTransaction(
            tenant_id=g.tenant.id,
            company_id=company.id,
            account_id=account.id,
            txn_date=txn_date,
            amount=signed_amount,
            description=desc,
            category_id=cat.id if cat else None,
            category=cat.name if cat else (category_name or None),
            counterparty_id=cp.id if cp else None,
            counterparty=cp.name if cp else (cp_name or None),
        )

        # If category has a default GL mapping, set it.
        if cat and cat.default_gl_account_id:
            if _is_leaf_gl_account(cat.default_gl_account_id, company):
                txn.gl_account_id = cat.default_gl_account_id

        db.session.add(txn)
        db.session.commit()
        flash(_("Transação registrada."), "success")
        return redirect(url_for("finance.account_view", account_id=account.id))

    return render_template(
        "finance/quick_entry.html",
        tenant=g.tenant,
        company=company,
        accounts=accounts,
        categories=categories,
        counterparties=counterparties,
        default_account_id=(default_acc.id if default_acc else None),
        today=date.today().isoformat(),
    )


@bp.route("/ai/parse-quick-entry", methods=["POST"])
@login_required
@require_roles("tenant_admin", "creator")
def ai_parse_quick_entry():
    company = _get_company()
    data = request.get_json(silent=True) or {}
    text = (data.get("text") or "").strip()
    lang = (data.get("lang") or "").strip() or getattr(g, "lang", DEFAULT_LANG)

    if not text:
        return jsonify({"ok": False, "error": _("Texto vazio.")}), 400

    try:
        parsed = parse_quick_entry_text_via_openai(text, lang=lang, default_currency=company.base_currency or "EUR")
    except OpenAIQuickEntryError as e:
        return jsonify({"ok": False, "error": str(e)}), 400
    except Exception as e:
        return jsonify({"ok": False, "error": f"{str(e)[:200]}"}), 400

    # Ensure minimum fields
    try:
        direction = parsed.get("direction")
        amount = parsed.get("amount")
        if direction not in ("inflow", "outflow"):
            direction = "outflow"
        # amount returned as number
        amount_val = float(amount) if amount is not None else 0
        if amount_val < 0:
            amount_val = abs(amount_val)
    except Exception:
        direction = "outflow"
        amount_val = 0

    resp = {
        "direction": direction,
        "amount": amount_val,
        "currency": parsed.get("currency"),
        "category": parsed.get("category"),
        "counterparty": parsed.get("counterparty"),
        "description": parsed.get("description"),
        "txn_date": parsed.get("txn_date"),
    }
    return jsonify({"ok": True, "parsed": resp})


# -----------------
# Alerts (UI only)
# -----------------


@bp.route("/alerts", methods=["GET", "POST"])
@login_required
@require_roles("tenant_admin", "creator", "viewer")
def alerts_page():
    company = _get_company()
    accounts = _q_accounts(company).all()

    defaults = {
        "granularity": "weekly",
        "threshold": 1000.0,
        "horizon_days": 90,
    }
    settings = _get_fin_setting(company, "alerts", defaults)

    if request.method == "POST":
        granularity = (request.form.get("granularity") or settings.get("granularity") or "weekly").strip().lower()
        if granularity not in ("daily", "weekly", "monthly"):
            granularity = "weekly"
        try:
            threshold = float(request.form.get("threshold") or settings.get("threshold") or 0)
        except Exception:
            threshold = float(settings.get("threshold") or 0)
        try:
            horizon_days = int(request.form.get("horizon_days") or settings.get("horizon_days") or 90)
        except Exception:
            horizon_days = int(settings.get("horizon_days") or 90)
        horizon_days = max(7, min(horizon_days, 365))
        settings = {
            "granularity": granularity,
            "threshold": threshold,
            "horizon_days": horizon_days,
        }
        _set_fin_setting(company, "alerts", settings)
        flash(_("Configuração de alertas atualizada."), "success")
        return redirect(url_for("finance.alerts_page"))

    start = date.today()
    end = start + timedelta(days=int(settings.get("horizon_days") or 90))
    txns = (
        _q_txns(company)
        .filter(FinanceTransaction.txn_date >= start)
        .filter(FinanceTransaction.txn_date <= end)
        .all()
    )
    recurring = FinanceRecurringTransaction.query.filter_by(tenant_id=g.tenant.id, company_id=company.id).all()
    liabilities = FinanceLiability.query.filter_by(tenant_id=g.tenant.id, company_id=company.id).all()
    invoices = FinanceInvoice.query.filter_by(tenant_id=g.tenant.id, company_id=company.id).all()

    current_balance = Decimal(str(compute_starting_cash(accounts)))
    starting = compute_opening_balance(txns, start=start, as_of=date.today(), current_balance=current_balance)
    series = project_cash_balance(
        start=start,
        end=end,
        granularity=settings.get("granularity") or "weekly",
        starting_balance=starting,
        transactions=txns,
        recurring=recurring,
        liabilities=liabilities,
        invoices=invoices,
    )
    ui_alerts = build_ui_alerts(series, low_balance_threshold=Decimal(str(settings.get("threshold") or 0)))

    # simple list for UI
    table = [
        {
            "period": p.period.isoformat(),
            "inflow": float(p.inflow),
            "outflow": float(p.outflow),
            "net": float(p.net),
            "balance": float(p.balance),
        }
        for p in series
    ]

    return render_template(
        "finance/alerts.html",
        tenant=g.tenant,
        company=company,
        active="alerts",
        settings=settings,
        alerts=ui_alerts,
        table=table,
        starting=starting,
        start=start,
        end=end,
    )


# -----------------
# Regulation exports
# -----------------


@bp.route("/regulation")
@login_required
@require_roles("tenant_admin", "creator", "viewer")
def regulation_page():
    company = _get_company()
    return render_template(
        "finance/regulation.html",
        tenant=g.tenant,
        company=company,
        active="regulation",
        today=date.today().isoformat(),
    )


@bp.route("/regulation/export/fec")
@login_required
@require_roles("tenant_admin", "creator", "viewer")
def regulation_export_fec():
    company = _get_company()
    try:
        start = datetime.strptime(request.args.get("start") or "", "%Y-%m-%d").date()
    except Exception:
        start = date(date.today().year, 1, 1)
    try:
        end = datetime.strptime(request.args.get("end") or "", "%Y-%m-%d").date()
    except Exception:
        end = date.today()

    vouchers = (
        FinanceLedgerVoucher.query.filter_by(tenant_id=g.tenant.id, company_id=company.id)
        .filter(FinanceLedgerVoucher.voucher_date >= start)
        .filter(FinanceLedgerVoucher.voucher_date <= end)
        .all()
    )
    voucher_ids = [v.id for v in vouchers]
    lines = []
    if voucher_ids:
        lines = (
            FinanceLedgerLine.query.options(joinedload(FinanceLedgerLine.gl_account))
            .filter_by(tenant_id=g.tenant.id, company_id=company.id)
            .filter(FinanceLedgerLine.voucher_id.in_(voucher_ids))
            .all()
        )

    content = export_fec_csv(vouchers=vouchers, lines=lines, as_of=end)
    filename = f"FEC_{company.slug}_{start.isoformat()}_{end.isoformat()}.csv"
    return send_file(
        BytesIO(content.encode("utf-8")),
        mimetype="text/csv",
        as_attachment=True,
        download_name=filename,
    )


@bp.route("/regulation/export/it-ledger")
@login_required
@require_roles("tenant_admin", "creator", "viewer")
def regulation_export_it_ledger():
    company = _get_company()
    try:
        start = datetime.strptime(request.args.get("start") or "", "%Y-%m-%d").date()
    except Exception:
        start = date(date.today().year, 1, 1)
    try:
        end = datetime.strptime(request.args.get("end") or "", "%Y-%m-%d").date()
    except Exception:
        end = date.today()

    vouchers = (
        FinanceLedgerVoucher.query.filter_by(tenant_id=g.tenant.id, company_id=company.id)
        .filter(FinanceLedgerVoucher.voucher_date >= start)
        .filter(FinanceLedgerVoucher.voucher_date <= end)
        .all()
    )
    voucher_ids = [v.id for v in vouchers]
    lines = []
    if voucher_ids:
        lines = (
            FinanceLedgerLine.query.options(joinedload(FinanceLedgerLine.gl_account))
            .filter_by(tenant_id=g.tenant.id, company_id=company.id)
            .filter(FinanceLedgerLine.voucher_id.in_(voucher_ids))
            .all()
        )

    content = export_it_ledger_csv(vouchers=vouchers, lines=lines)
    filename = f"Ledger_IT_{company.slug}_{start.isoformat()}_{end.isoformat()}.csv"
    return send_file(
        BytesIO(content.encode("utf-8")),
        mimetype="text/csv",
        as_attachment=True,
        download_name=filename,
    )


# -----------------
# E-invoices (PDF + XML)
# -----------------


@bp.route("/invoices")
@login_required
@require_roles("tenant_admin", "creator", "viewer")
def invoices_list():
    company = _get_company()
    invoices = (
        FinanceInvoice.query.options(joinedload(FinanceInvoice.counterparty))
        .filter_by(tenant_id=g.tenant.id, company_id=company.id)
        .order_by(FinanceInvoice.issue_date.desc())
        .all()
    )
    cps = FinanceCounterparty.query.filter_by(tenant_id=g.tenant.id, company_id=company.id).order_by(FinanceCounterparty.name.asc()).all()
    accounts = _q_accounts(company).all()
    return render_template(
        "finance/invoices_list.html",
        tenant=g.tenant,
        company=company,
        active="invoices",
        invoices=invoices,
        counterparties=cps,
        accounts=accounts,
        today=date.today().isoformat(),
    )


@bp.route("/products/lookup")
@login_required
@require_roles("tenant_admin", "creator", "viewer")
def product_lookup():
    company = _get_company()
    name = (request.args.get("name") or "").strip()
    if not name:
        return jsonify({"found": False})

    product = (
        FinanceProduct.query
        .filter_by(tenant_id=g.tenant.id, company_id=company.id)
        .filter(func.lower(FinanceProduct.name) == name.lower())
        .first()
    )
    if not product:
        return jsonify({"found": False})

    return jsonify({
        "found": True,
        "vat_rate": float(product.vat_rate or 0),
        "unit_price": float(product.unit_price or 0),
    })


def _recalc_invoice_totals(inv: FinanceInvoice) -> None:
    totals = compute_totals(inv)
    inv.total_net = totals.net
    inv.total_tax = totals.tax
    inv.total_gross = totals.gross


def _get_or_create_product(company: FinanceCompany, name: str, unit_price: Decimal, vat_rate: Decimal, currency: str) -> FinanceProduct | None:
    product = (
        FinanceProduct.query
        .filter_by(tenant_id=g.tenant.id, company_id=company.id)
        .filter(func.lower(FinanceProduct.name) == name.lower())
        .first()
    )
    if product:
        return product

    if not name:
        return None

    product = FinanceProduct(
        tenant_id=g.tenant.id,
        company_id=company.id,
        name=name,
        description=name,
        product_type="service",
        unit_price=unit_price,
        currency_code=currency,
        vat_rate=vat_rate,
        vat_applies=vat_rate > 0,
        vat_reverse_charge=False,
        status="active",
    )
    db.session.add(product)
    return product


def _parse_lines_from_form(company: FinanceCompany, currency: str) -> list[dict]:
    descs = request.form.getlist("line_description")
    qtys = request.form.getlist("line_quantity")
    prices = request.form.getlist("line_unit_price")
    vats = request.form.getlist("line_vat_rate")
    lines: list[dict] = []
    for i in range(max(len(descs), len(qtys), len(prices), len(vats))):
        desc = (descs[i] if i < len(descs) else "").strip()
        if not desc:
            continue
        try:
            q = Decimal(str(qtys[i] if i < len(qtys) else "1"))
        except Exception:
            q = Decimal("1")
        try:
            up = Decimal(str(prices[i] if i < len(prices) else "0"))
        except Exception:
            up = Decimal("0")
        try:
            vr = Decimal(str(vats[i] if i < len(vats) else "0"))
        except Exception:
            vr = Decimal("0")

        product = _get_or_create_product(company, desc, up, vr, currency)
        if product and product.vat_rate is not None:
            try:
                vr = Decimal(str(product.vat_rate))
            except Exception:
                pass
        net = (q * up).quantize(Decimal("0.01"))
        tax = (net * vr / Decimal("100")).quantize(Decimal("0.01"))
        gross = (net + tax).quantize(Decimal("0.01"))
        lines.append({
            "description": desc,
            "quantity": q,
            "unit_price": up,
            "vat_rate": vr,
            "net_amount": net,
            "tax_amount": tax,
            "gross_amount": gross,
        })
    return lines


@bp.route("/invoices/new", methods=["GET", "POST"])
@login_required
@require_roles("tenant_admin", "creator")
def invoice_new():
    company = _get_company()
    cps = FinanceCounterparty.query.filter_by(tenant_id=g.tenant.id, company_id=company.id).order_by(FinanceCounterparty.name.asc()).all()
    accounts = _q_accounts(company).all()
    products = FinanceProduct.query.filter_by(tenant_id=g.tenant.id, company_id=company.id).order_by(FinanceProduct.name.asc()).all()

    if request.method == "POST":
        invoice_number = (request.form.get("invoice_number") or "").strip()
        invoice_type = (request.form.get("invoice_type") or "sale").strip().lower()
        currency = (request.form.get("currency") or company.base_currency or "EUR").strip().upper()
        status = (request.form.get("status") or "draft").strip().lower()
        try:
            issue_date = datetime.strptime(request.form.get("issue_date") or "", "%Y-%m-%d").date()
        except Exception:
            issue_date = date.today()
        try:
            due_date_str = (request.form.get("due_date") or "").strip()
            due_date = datetime.strptime(due_date_str, "%Y-%m-%d").date() if due_date_str else None
        except Exception:
            due_date = None

        cp_id = request.form.get("counterparty_id")
        settlement_account_id = request.form.get("settlement_account_id")
        notes = (request.form.get("notes") or "").strip() or None

        if not invoice_number:
            flash(_("Número da fatura é obrigatório."), "danger")
            return redirect(url_for("finance.invoice_new"))

        inv = FinanceInvoice(
            tenant_id=g.tenant.id,
            company_id=company.id,
            invoice_number=invoice_number,
            invoice_type=invoice_type if invoice_type in ("sale", "purchase") else "sale",
            status=status if status in ("draft", "sent", "paid", "void") else "draft",
            currency=currency,
            issue_date=issue_date,
            due_date=due_date,
            counterparty_id=int(cp_id) if cp_id else None,
            settlement_account_id=int(settlement_account_id) if settlement_account_id else None,
            notes=notes,
        )

        for ln in _parse_lines_from_form(company, currency):
            inv.lines.append(FinanceInvoiceLine(
                tenant_id=g.tenant.id,
                company_id=company.id,
                **ln,
            ))
        _recalc_invoice_totals(inv)
        db.session.add(inv)
        db.session.commit()
        flash(_("Fatura criada."), "success")
        return redirect(url_for("finance.invoice_view", invoice_id=inv.id))

    return render_template(
        "finance/invoice_form.html",
        tenant=g.tenant,
        company=company,
        active="invoices",
        invoice=None,
        counterparties=cps,
        accounts=accounts,
        products=products,
        today=date.today().isoformat(),
    )


@bp.route("/invoices/<int:invoice_id>")
@login_required
@require_roles("tenant_admin", "creator", "viewer")
def invoice_view(invoice_id: int):
    company = _get_company()
    inv = FinanceInvoice.query.options(joinedload(FinanceInvoice.lines), joinedload(FinanceInvoice.counterparty)).filter_by(
        id=invoice_id, tenant_id=g.tenant.id, company_id=company.id
    ).first_or_404()
    accounts = _q_accounts(company).all()
    template_settings = _get_invoice_template_settings(company)
    selected_lang = _invoice_template_lang(template_settings)
    subject_template, body_template = _invoice_template_texts(template_settings, selected_lang)
    mail_tokens = _build_invoice_mail_tokens(inv, company, selected_lang)
    mail_tokens["sender_name"] = str(template_settings.get("sender_name") or company.name)
    email_subject = _render_invoice_text_template(
        subject_template,
        mail_tokens,
    )
    email_body = _render_invoice_text_template(
        body_template,
        mail_tokens,
    )
    return render_template(
        "finance/invoice_view.html",
        tenant=g.tenant,
        company=company,
        active="invoices",
        invoice=inv,
        accounts=accounts,
        invoice_template_settings=template_settings,
        invoice_template_lang=selected_lang,
        email_subject_default=email_subject,
        email_body_default=email_body,
        today=date.today().isoformat(),
    )


@bp.route("/invoices/<int:invoice_id>/edit", methods=["GET", "POST"])
@login_required
@require_roles("tenant_admin", "creator")
def invoice_edit(invoice_id: int):
    company = _get_company()
    inv = FinanceInvoice.query.options(joinedload(FinanceInvoice.lines)).filter_by(
        id=invoice_id, tenant_id=g.tenant.id, company_id=company.id
    ).first_or_404()
    cps = FinanceCounterparty.query.filter_by(tenant_id=g.tenant.id, company_id=company.id).order_by(FinanceCounterparty.name.asc()).all()
    accounts = _q_accounts(company).all()
    products = FinanceProduct.query.filter_by(tenant_id=g.tenant.id, company_id=company.id).order_by(FinanceProduct.name.asc()).all()

    if request.method == "POST":
        inv.invoice_number = (request.form.get("invoice_number") or inv.invoice_number).strip()
        inv.invoice_type = (request.form.get("invoice_type") or inv.invoice_type).strip().lower()
        inv.status = (request.form.get("status") or inv.status).strip().lower()
        inv.currency = (request.form.get("currency") or inv.currency).strip().upper()
        try:
            inv.issue_date = datetime.strptime(request.form.get("issue_date") or "", "%Y-%m-%d").date()
        except Exception:
            pass
        try:
            due_date_str = (request.form.get("due_date") or "").strip()
            inv.due_date = datetime.strptime(due_date_str, "%Y-%m-%d").date() if due_date_str else None
        except Exception:
            pass
        cp_id = request.form.get("counterparty_id")
        inv.counterparty_id = int(cp_id) if cp_id else None
        settlement_account_id = request.form.get("settlement_account_id")
        inv.settlement_account_id = int(settlement_account_id) if settlement_account_id else None
        inv.notes = (request.form.get("notes") or "").strip() or None

        # replace lines
        inv.lines.clear()
        for ln in _parse_lines_from_form(company, inv.currency):
            inv.lines.append(FinanceInvoiceLine(
                tenant_id=g.tenant.id,
                company_id=company.id,
                **ln,
            ))
        _recalc_invoice_totals(inv)
        db.session.commit()
        flash(_("Fatura atualizada."), "success")
        return redirect(url_for("finance.invoice_view", invoice_id=inv.id))

    return render_template(
        "finance/invoice_form.html",
        tenant=g.tenant,
        company=company,
        active="invoices",
        invoice=inv,
        counterparties=cps,
        accounts=accounts,
        products=products,
        today=date.today().isoformat(),
    )


@bp.route("/invoices/<int:invoice_id>/delete", methods=["POST"])
@login_required
@require_roles("tenant_admin", "creator")
def invoice_delete(invoice_id: int):
    company = _get_company()
    inv = FinanceInvoice.query.filter_by(id=invoice_id, tenant_id=g.tenant.id, company_id=company.id).first_or_404()
    db.session.delete(inv)
    db.session.commit()
    flash(_("Fatura removida."), "success")
    return redirect(url_for("finance.invoices_list"))


@bp.route("/invoices/<int:invoice_id>/mark-paid", methods=["POST"])
@login_required
@require_roles("tenant_admin", "creator")
def invoice_mark_paid(invoice_id: int):
    company = _get_company()
    inv = FinanceInvoice.query.options(joinedload(FinanceInvoice.counterparty)).filter_by(
        id=invoice_id, tenant_id=g.tenant.id, company_id=company.id
    ).first_or_404()

    acc_id = request.form.get("account_id") or inv.settlement_account_id
    if not acc_id:
        flash(_("Selecione a conta de liquidação."), "danger")
        return redirect(url_for("finance.invoice_view", invoice_id=inv.id))
    account = FinanceAccount.query.filter_by(id=int(acc_id), tenant_id=g.tenant.id, company_id=company.id).first()
    if not account:
        flash(_("Conta inválida."), "danger")
        return redirect(url_for("finance.invoice_view", invoice_id=inv.id))

    try:
        pay_date_str = (request.form.get("payment_date") or "").strip()
        pay_date = datetime.strptime(pay_date_str, "%Y-%m-%d").date() if pay_date_str else date.today()
    except Exception:
        pay_date = date.today()

    amount = Decimal(str(inv.total_gross or 0))
    if (inv.invoice_type or "sale").lower() == "purchase":
        amount = -abs(amount)
    else:
        amount = abs(amount)

    if not _ensure_transaction_quota(1):
        return redirect(url_for("finance.invoice_view", invoice_id=inv.id))

    txn = FinanceTransaction(
        tenant_id=g.tenant.id,
        company_id=company.id,
        account_id=account.id,
        txn_date=pay_date,
        amount=amount,
        description=f"Payment for invoice {inv.invoice_number}",
        counterparty_id=inv.counterparty_id,
        reference=inv.invoice_number,
    )
    db.session.add(txn)
    account.balance = (Decimal(str(account.balance or 0)) + amount)
    inv.status = "paid"
    inv.settlement_account_id = account.id
    db.session.commit()
    flash(_("Fatura marcada como paga e transação criada."), "success")
    return redirect(url_for("finance.invoice_view", invoice_id=inv.id))


@bp.route("/invoices/<int:invoice_id>/export")
@login_required
@require_roles("tenant_admin", "creator", "viewer")
def invoice_export(invoice_id: int):
    company = _get_company()
    inv = FinanceInvoice.query.options(joinedload(FinanceInvoice.lines), joinedload(FinanceInvoice.counterparty)).filter_by(
        id=invoice_id, tenant_id=g.tenant.id, company_id=company.id
    ).first_or_404()
    country = (request.args.get("country") or "fr").strip().lower()
    if country not in ("fr", "it"):
        country = "fr"

    template_settings = _get_invoice_template_settings(company)
    logo_path = _resolve_logo_static_path(template_settings.get("logo_url"))
    zip_name, zip_bytes = build_invoice_export_zip(
        inv=inv,
        company=company,
        cp=inv.counterparty,
        country=country,
        logo_path=logo_path,
    )

    return send_file(
        BytesIO(zip_bytes),
        mimetype="application/zip",
        as_attachment=True,
        download_name=zip_name,
    )


@bp.route("/invoices/<int:invoice_id>/pdf")
@login_required
@require_roles("tenant_admin", "creator", "viewer")
def invoice_pdf(invoice_id: int):
    company = _get_company()
    inv = FinanceInvoice.query.options(joinedload(FinanceInvoice.lines), joinedload(FinanceInvoice.counterparty)).filter_by(
        id=invoice_id, tenant_id=g.tenant.id, company_id=company.id
    ).first_or_404()
    template_settings = _get_invoice_template_settings(company)
    logo_path = _resolve_logo_static_path(template_settings.get("logo_url"))
    pdf_bytes = build_invoice_pdf_bytes(inv=inv, company=company, cp=inv.counterparty, logo_path=logo_path)
    return send_file(
        BytesIO(pdf_bytes),
        mimetype="application/pdf",
        as_attachment=True,
        download_name=f"invoice_{inv.invoice_number}.pdf",
    )


@bp.route("/invoices/settings", methods=["GET", "POST"])
@login_required
@require_roles("tenant_admin", "creator")
def invoice_template_settings():
    company = _get_company()
    settings = _get_invoice_template_settings(company)
    selected_lang = _invoice_template_lang(settings, request.values.get("lang"))

    current_subject_template, current_body_template = _invoice_template_texts(settings, selected_lang)

    preview_due_labels = {
        "fr": "Échéance",
        "en": "Due date",
        "pt": "Vencimento",
        "es": "Vencimiento",
        "it": "Scadenza",
        "de": "Fällig am",
    }
    preview_due_label = preview_due_labels.get(selected_lang, "Échéance")

    preview_tokens = {
        "invoice_number": "FAC-2026-001",
        "company_name": company.name,
        "client_name": "Client Démo",
        "currency": company.base_currency or "EUR",
        "total": "1250.00",
        "issue_date": date.today().isoformat(),
        "due_date": (date.today() + timedelta(days=30)).isoformat(),
        "due_line": f"\n{preview_due_label}: {(date.today() + timedelta(days=30)).isoformat()}.",
        "sender_name": str(settings.get("sender_name") or company.name),
    }

    if request.method == "POST":
        selected_lang = _invoice_template_lang(settings, request.form.get("lang"))
        logo_url = (request.form.get("logo_url") or "").strip()
        sender_name = (request.form.get("sender_name") or "").strip()
        email_subject_template = (request.form.get("email_subject_template") or "").strip()
        email_body_template = (request.form.get("email_body_template") or "").strip()

        upload = request.files.get("logo_file")
        if upload and getattr(upload, "filename", ""):
            try:
                uploaded_logo = _save_finance_logo_upload(g.tenant.id, company.id, upload)
                if uploaded_logo:
                    logo_url = uploaded_logo
            except ValueError:
                flash(_("Format de logo non supporté."), "danger")
                return redirect(url_for("finance.invoice_template_settings"))

        localized_templates = settings.get("localized_templates") if isinstance(settings.get("localized_templates"), dict) else {}
        current_row = localized_templates.get(selected_lang) if isinstance(localized_templates.get(selected_lang), dict) else {}
        updated_row = {
            "email_subject_template": email_subject_template or str(current_row.get("email_subject_template") or settings.get("email_subject_template") or _default_invoice_template_settings(company)["email_subject_template"]),
            "email_body_template": email_body_template or str(current_row.get("email_body_template") or settings.get("email_body_template") or _default_invoice_template_settings(company)["email_body_template"]),
        }
        localized_templates[selected_lang] = updated_row

        settings = {
            "logo_url": logo_url,
            "sender_name": sender_name,
            "email_subject_template": str(settings.get("email_subject_template") or _default_invoice_template_settings(company)["email_subject_template"]),
            "email_body_template": str(settings.get("email_body_template") or _default_invoice_template_settings(company)["email_body_template"]),
            "localized_templates": localized_templates,
        }
        _set_fin_setting(company, _INVOICE_TEMPLATE_SETTING_KEY, settings)
        flash(_("Template de facture mis à jour."), "success")
        return redirect(url_for("finance.invoice_template_settings", lang=selected_lang))

    preview_subject = _render_invoice_text_template(current_subject_template, preview_tokens)
    preview_body = _render_invoice_text_template(current_body_template, preview_tokens)

    return render_template(
        "finance/invoice_template_settings.html",
        tenant=g.tenant,
        company=company,
        active="invoices",
        settings=settings,
        selected_lang=selected_lang,
        available_langs=[{"code": lang, "label": _invoice_lang_label(lang)} for lang in _INVOICE_TEMPLATE_LANGS],
        email_subject_template=current_subject_template,
        email_body_template=current_body_template,
        preview_subject=preview_subject,
        preview_body=preview_body,
    )


@bp.route("/invoices/<int:invoice_id>/send-email", methods=["POST"])
@login_required
@require_roles("tenant_admin", "creator")
def invoice_send_email(invoice_id: int):
    company = _get_company()
    inv = FinanceInvoice.query.options(joinedload(FinanceInvoice.lines), joinedload(FinanceInvoice.counterparty)).filter_by(
        id=invoice_id, tenant_id=g.tenant.id, company_id=company.id
    ).first_or_404()

    recipient = (request.form.get("recipient") or "").strip()
    subject = (request.form.get("email_subject") or "").strip()
    body = (request.form.get("email_body") or "").strip()

    if not recipient:
        recipient = (inv.counterparty.email if inv.counterparty else "") or ""

    if not recipient:
        flash(_("Defina um email do cliente para enviar a fatura."), "danger")
        return redirect(url_for("finance.invoice_view", invoice_id=inv.id))

    template_settings = _get_invoice_template_settings(company)
    selected_lang = _invoice_template_lang(template_settings)
    subject_template, body_template = _invoice_template_texts(template_settings, selected_lang)
    tokens = _build_invoice_mail_tokens(inv, company, selected_lang)
    tokens["sender_name"] = str(template_settings.get("sender_name") or company.name)
    if not subject:
        subject = _render_invoice_text_template(subject_template, tokens)
    if not body:
        body = _render_invoice_text_template(body_template, tokens)

    if not subject:
        subject = f"Facture {inv.invoice_number}"

    logo_path = _resolve_logo_static_path(template_settings.get("logo_url"))
    pdf_bytes = build_invoice_pdf_bytes(inv=inv, company=company, cp=inv.counterparty, logo_path=logo_path)
    filename = f"invoice_{inv.invoice_number}.pdf"

    sent = EmailService.send_email(
        to=recipient,
        subject=subject,
        template=None,
        body_text=body,
        attachments=[
            {
                "filename": filename,
                "content_type": "application/pdf",
                "data": pdf_bytes,
            }
        ],
    )

    if sent:
        if inv.status == "draft":
            inv.status = "sent"
            db.session.commit()
        flash(_("Fatura enviada por email com sucesso."), "success")
    else:
        flash(_("Falha ao enviar o email da fatura."), "danger")

    return redirect(url_for("finance.invoice_view", invoice_id=inv.id))
