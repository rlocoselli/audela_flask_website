from __future__ import annotations

from datetime import date, datetime, timedelta
from decimal import Decimal

from flask import abort, flash, g, redirect, render_template, request, session, url_for, current_app, jsonify
from flask_login import current_user, login_required
from werkzeug.utils import secure_filename

from ...extensions import db
from ...i18n import DEFAULT_LANG, tr
from ...models.core import Tenant
from ...models.finance import FinanceAccount, FinanceCompany, FinanceTransaction
from ...models.finance_ref import FinanceCurrency, FinanceCounterparty, FinanceStatementImport
from ...models.finance_ext import (
    FinanceBankAccountLink,
    FinanceBankConnection,
    FinanceCategory,
    FinanceCategoryRule,
    FinanceGLAccount,
    FinanceLedgerVoucher,
    FinanceLedgerLine,
    FinanceLiability,
    FinanceRecurringTransaction,
)
from ...security import require_roles
from ...services.bank_bridge import BridgeClient, BridgeError
from ...services.bank_statement import import_bank_statement, StatementImportError
from ...services.openai_statement import parse_bank_statement_pdf_via_openai, OpenAIStatementError
from ...services.openai_quick_entry import parse_quick_entry_text_via_openai, OpenAIQuickEntryError
from ...services.finance_service import (
    compute_basic_risk,
    compute_cashflow,
    compute_interest_rate_gaps,
    compute_liquidity,
    compute_nii,
    compute_starting_cash,
    parse_transactions_csv,
    # Legacy: kept for compatibility, but PDF imports now use audela.services.bank_statement
    parse_bank_statement_pdf_local,
    parse_bank_statement_pdf_via_api,
)
from ...tenancy import get_current_tenant_id

from . import bp


def _(msgid: str, **kwargs):
    return tr(msgid, getattr(g, "lang", DEFAULT_LANG), **kwargs)


def _require_tenant() -> None:
    if not current_user.is_authenticated:
        abort(401)
    if not getattr(g, "tenant", None) or current_user.tenant_id != g.tenant.id:
        abort(403)


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
    for code, name, typ in _DEF_GL:
        db.session.add(FinanceGLAccount(tenant_id=g.tenant.id, company_id=company.id, code=code, name=name, kind=typ))
    db.session.commit()


def get_gl_accounts(company: FinanceCompany):
    ensure_default_gl_accounts(company)
    return FinanceGLAccount.query.filter_by(tenant_id=g.tenant.id, company_id=company.id).order_by(FinanceGLAccount.code.asc()).all()


def apply_category_rules(company: FinanceCompany, *, description: str, counterparty_id: int | None, amount: float) -> int | None:
    direction = "inflow" if amount > 0 else "outflow" if amount < 0 else "any"
    desc_l = (description or "").lower()
    rules = (
        FinanceCategoryRule.query
        .filter_by(tenant_id=g.tenant.id, company_id=company.id)
        .order_by(FinanceCategoryRule.priority.asc())
        .all()
    )
    for r in rules:
        if r.direction and r.direction != "any" and r.direction != direction:
            continue
        if r.counterparty_id and counterparty_id and r.counterparty_id != counterparty_id:
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



@bp.route("/")
@login_required
@require_roles("tenant_admin", "creator", "viewer")
def dashboard():
    company = _get_company()
    accounts = _q_accounts(company).order_by(FinanceAccount.name.asc()).all()

    cash = compute_starting_cash(accounts)
    nii = compute_nii(accounts, horizon_days=365)
    liquidity = compute_liquidity(accounts, horizon_days=30)

    # Small, friendly KPIs
    kpis = {
        "cash": cash,
        "nii_12m": nii["nii_total"],
        "liq_ratio": liquidity["liquidity_ratio"],
        "net_liq": liquidity["net_liquidity"],
    }

    return render_template(
        "finance/dashboard.html",
        tenant=g.tenant,
        company=company,
        kpis=kpis,
        accounts=accounts,
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
    txns = (
        FinanceTransaction.query.filter_by(tenant_id=g.tenant.id, company_id=company.id, account_id=acc.id)
        .order_by(FinanceTransaction.txn_date.desc())
        .limit(200)
        .all()
    )
    return render_template("finance/account_view.html", tenant=g.tenant, company=company, account=acc, txns=txns)


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
    db.session.delete(txn)
    db.session.commit()
    flash(_("Transação removida."), "success")
    return redirect(url_for("finance.account_view", account_id=account_id))


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

    # Map counterparty names to directory entries (auto-create when needed)
    existing = { (cp.name or "").strip().lower(): cp for cp in get_counterparties(company) if (cp.name or "").strip() }

    n = 0
    for r in rows:
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
    return redirect(url_for("finance.account_view", account_id=acc.id))


# -----------------
# Help and settings
# -----------------


@bp.route("/help")
@login_required
@require_roles("tenant_admin", "creator", "viewer")
def help_page():
    company = _get_company()
    return render_template("finance/help.html", tenant=g.tenant, company=company)


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

    if request.method == "POST":
        provider = (request.form.get("provider") or "auto").strip()
        bank = (request.form.get("bank") or "auto").strip().lower()
        bank_hint = None if bank in ("", "auto", "detect") else bank

        f = request.files.get("file")
        if not f:
            flash(_("Selecione um arquivo."), "error")
            return redirect(url_for("finance.statement_import", account_id=acc.id))

        filename = secure_filename(f.filename or "statement.pdf")
        pdf_bytes = f.read() or b""
        if not pdf_bytes:
            flash(_("Falha ao ler arquivo."), "error")
            return redirect(url_for("finance.statement_import", account_id=acc.id))

        rows: list[dict] = []
        payload: dict = {"provider": provider, "bank_hint": bank_hint or "auto"}

        # OpenAI Structured Outputs parsing (optional)
        if provider == "openai":
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

        # External parsing API (optional)
        if provider == "api":
            endpoint = (current_app.config.get("STATEMENT_PARSER_ENDPOINT") or "").strip()
            api_key = (current_app.config.get("STATEMENT_PARSER_API_KEY") or "").strip() or None
            payload["endpoint"] = endpoint
            if endpoint:
                try:
                    rows = parse_bank_statement_pdf_via_api(pdf_bytes, filename=filename, endpoint=endpoint, api_key=api_key)
                except Exception as e:
                    payload["api_error"] = str(e)[:250]
                    rows = []
            # fallback to smart local flow
            if not rows:
                provider = "auto"
                payload["fallback"] = "auto"

        # Smart local import flow (with OCR fallbacks if configured)
        if not rows:
            mindee_key = (current_app.config.get("MINDEE_API_KEY") or "").strip() or None
            gv_key = (current_app.config.get("GOOGLE_VISION_API_KEY") or "").strip() or None

            prefer = provider if provider in ("local", "mindee", "google", "tesseract") else "local"
            if provider == "auto":
                prefer = "local"

            bank_detected, parsed, meta = import_bank_statement(
                pdf_bytes,
                prefer=prefer,
                default_currency=(acc.currency or company.base_currency or "EUR"),
                bank_hint=bank_hint,
                mindee_api_key=mindee_key,
                google_vision_api_key=gv_key,
                max_pages=10,
            )
            payload["meta"] = meta
            payload["bank_detected"] = bank_detected
            for p in parsed:
                ref = None
                if p.raw and isinstance(p.raw, dict):
                    ref = p.raw.get("id") or p.raw.get("transaction_id") or p.raw.get("reference")
                rows.append(
                    {
                        "txn_date": p.date,
                        "amount": float(p.amount),
                        "description": p.description,
                        "category": None,
                        "counterparty": p.counterparty,
                        "currency": p.currency,
                        "reference": ref,
                        "balance": p.balance,
                        "raw": p.raw,
                    }
                )

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
        for r in rows:
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
                )
                if cat_id:
                    cat_obj = FinanceCategory.query.filter_by(id=cat_id, tenant_id=g.tenant.id, company_id=company.id).first()

            gl_account_id = None
            if cat_obj and cat_obj.default_gl_account_id:
                gl_account_id = cat_obj.default_gl_account_id

            db.session.add(
                FinanceTransaction(
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
            )
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
        if skipped:
            flash(_("Linhas ignoradas (duplicadas): {n}.", n=skipped), "info")
        return redirect(url_for("finance.account_view", account_id=acc.id))

    return render_template(
        "finance/statement_import.html",
        tenant=g.tenant,
        company=company,
        account=acc,
    )



# -----------------
# Reports
# -----------------


@bp.route("/cashflow")
@login_required
@require_roles("tenant_admin", "creator", "viewer")
def cashflow():
    company = _get_company()
    accounts = _q_accounts(company).all()
    txns = _q_txns(company).all()

    # default horizon: 90 days ahead
    try:
        start = datetime.strptime((request.args.get("start") or ""), "%Y-%m-%d").date()
    except Exception:
        start = date.today()

    try:
        end = datetime.strptime((request.args.get("end") or ""), "%Y-%m-%d").date()
    except Exception:
        end = start + timedelta(days=90)

    starting = Decimal(str(request.args.get("starting") or compute_starting_cash(accounts)))
    series = compute_cashflow(txns, start=start, end=end, starting_balance=starting)

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
    horizon = int(request.args.get("days") or 30)
    res = compute_liquidity(accounts, horizon_days=horizon)
    return render_template(
        "finance/liquidity.html",
        tenant=g.tenant,
        company=company,
        horizon=horizon,
        res=res,
    )


@bp.route("/risk")
@login_required
@require_roles("tenant_admin", "creator", "viewer")
def risk():
    company = _get_company()
    accounts = _q_accounts(company).all()
    res = compute_basic_risk(accounts)

    ccy_chart = [{"name": r["currency"], "value": float(r["exposure"])} for r in res["currency"]]

    return render_template(
        "finance/risk.html",
        tenant=g.tenant,
        company=company,
        res=res,
        ccy_chart=ccy_chart,
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
    gl_accounts = get_gl_accounts(company)
    counterparties = get_counterparties(company)

    return render_template(
        "finance/settings_categories.html",
        tenant=g.tenant,
        company=company,
        categories=categories,
        rules=rules,
        gl_accounts=gl_accounts,
        counterparties=counterparties,
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


@bp.route("/settings/gl", methods=["GET", "POST"])
@login_required
@require_roles("tenant_admin", "creator")
def settings_gl():
    company = _get_company()
    if request.method == "POST":
        code = (request.form.get("code") or "").strip()
        name = (request.form.get("name") or "").strip()
        kind = (request.form.get("kind") or "expense").strip()
        if not code or not name:
            flash(_("Preencha todos os campos."), "error")
            return redirect(url_for("finance.settings_gl"))
        db.session.add(FinanceGLAccount(tenant_id=g.tenant.id, company_id=company.id, code=code, name=name, kind=kind))
        db.session.commit()
        flash(_("Conta contábil criada."), "success")
        return redirect(url_for("finance.settings_gl"))

    gl_accounts = get_gl_accounts(company)
    return render_template(
        "finance/settings_gl.html",
        tenant=g.tenant,
        company=company,
        gl_accounts=gl_accounts,
    )


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

        conn.last_sync_at = datetime.utcnow()
        db.session.commit()
        flash(_("Sincronização concluída: {a} contas, {t} transações.", a=created_accounts, t=created_txns), "success")
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

    gl_accounts = get_gl_accounts(company)
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
    if gl:
        return gl
    # fallback: first asset account
    return FinanceGLAccount.query.filter_by(tenant_id=g.tenant.id, company_id=company.id, kind="asset").first()


@bp.route("/reconciliation/<int:txn_id>/create_voucher", methods=["POST"])
@login_required
@require_roles("tenant_admin", "creator")
def reconcile_create_voucher(txn_id: int):
    company = _get_company()
    txn = FinanceTransaction.query.filter_by(id=txn_id, tenant_id=g.tenant.id, company_id=company.id).first_or_404()

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

    start, end, label = _date_range_from_view(view, year, month)
    base_cur = company.base_currency or "EUR"

    txns = (
        _q_txns(company)
        .filter(FinanceTransaction.txn_date >= start)
        .filter(FinanceTransaction.txn_date < end)
        .order_by(FinanceTransaction.txn_date.desc(), FinanceTransaction.id.desc())
        .all()
    )

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
        cp_name = (t.counterparty_ref.name if getattr(t, "counterparty_ref", None) else None) or (t.counterparty or "—")
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
                "txn_date": t.txn_date,
                "description": t.description,
                "category_name": cat_name,
                "counterparty_name": cp_name,
                "amount_fmt": _fmt_money(Decimal(str(t.amount or 0)), base_cur),
            }
        )

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
        by_counterparty=_top_map(by_cp),
        latest=latest_rows,
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
    for r in items:
        next_d = r.next_run_date
        while next_d and next_d <= target:
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

        # update next_run_date to the first date after target
        if next_d and next_d != r.next_run_date:
            r.next_run_date = next_d

    db.session.commit()
    flash(_(f"{created} transações geradas."), "success")
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
