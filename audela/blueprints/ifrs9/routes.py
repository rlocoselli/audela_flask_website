from __future__ import annotations

from datetime import date
from decimal import Decimal, InvalidOperation

from flask import abort, flash, g, redirect, render_template, request, url_for
from flask_login import current_user, login_required
from sqlalchemy.orm.attributes import flag_modified

from ...extensions import db
from ...i18n import DEFAULT_LANG, tr
from ...models.core import Tenant
from ...models.finance import FinanceCompany
from ...models.finance_ext import FinanceGLAccount, FinanceLedgerLine, FinanceLedgerVoucher
from ...services.subscription_service import SubscriptionService
from ...tenancy import get_current_tenant_id
from . import bp


def _(msgid: str, **kwargs):
    return tr(msgid, getattr(g, "lang", DEFAULT_LANG), **kwargs)


def _require_tenant() -> None:
    if not current_user.is_authenticated:
        abort(401)
    if not getattr(g, "tenant", None) or current_user.tenant_id != g.tenant.id:
        abort(403)


def _has_ifrs9_access(tenant: Tenant | None) -> bool:
    if not tenant:
        return False
    return SubscriptionService.check_feature_access(tenant.id, "ifrs9")


def _to_decimal(raw: str | None, fallback: Decimal) -> Decimal:
    if raw is None:
        return fallback
    value = (raw or "").strip().replace(",", ".")
    if not value:
        return fallback
    try:
        return Decimal(value)
    except (InvalidOperation, ValueError):
        return fallback


def _default_ifrs9_config() -> dict:
    return {
        "company_id": None,
        "expense_gl_account_id": None,
        "provision_gl_account_id": None,
        "default_pd": "0.03",
        "default_lgd": "0.45",
        "default_ead": "250000",
        "stage": "stage1",
    }


def _load_ifrs9_config(tenant: Tenant) -> dict:
    settings = tenant.settings_json if isinstance(tenant.settings_json, dict) else {}
    raw = settings.get("ifrs9") if isinstance(settings.get("ifrs9"), dict) else {}
    cfg = _default_ifrs9_config()
    cfg.update(raw)
    return cfg


def _save_ifrs9_config(tenant: Tenant, cfg: dict) -> None:
    settings = dict(tenant.settings_json) if isinstance(tenant.settings_json, dict) else {}
    settings["ifrs9"] = cfg
    tenant.settings_json = settings
    flag_modified(tenant, "settings_json")


def _compute_ecl(pd_ratio: Decimal, lgd_ratio: Decimal, ead_amount: Decimal, stage: str) -> Decimal:
    stage_multipliers = {
        "stage1": Decimal("1.00"),
        "stage2": Decimal("1.50"),
        "stage3": Decimal("2.00"),
    }
    multiplier = stage_multipliers.get(stage, Decimal("1.00"))
    value = ead_amount * pd_ratio * lgd_ratio * multiplier
    return value.quantize(Decimal("0.01"))


def _company_and_accounts_scope(tenant_id: int, company_id: int | None) -> tuple[list[FinanceCompany], list[FinanceGLAccount]]:
    companies = (
        FinanceCompany.query.filter_by(tenant_id=tenant_id)
        .order_by(FinanceCompany.name.asc())
        .all()
    )
    if not company_id:
        return companies, []
    accounts = (
        FinanceGLAccount.query.filter_by(tenant_id=tenant_id, company_id=company_id)
        .order_by(FinanceGLAccount.code.asc())
        .all()
    )
    return companies, accounts


def _recent_ifrs9_postings(tenant_id: int, company_id: int | None) -> tuple[list[dict], Decimal]:
    if not company_id:
        return [], Decimal("0.00")

    vouchers = (
        FinanceLedgerVoucher.query.filter_by(tenant_id=tenant_id, company_id=company_id)
        .filter(FinanceLedgerVoucher.reference.like("IFRS9-%"))
        .order_by(FinanceLedgerVoucher.voucher_date.desc(), FinanceLedgerVoucher.id.desc())
        .limit(10)
        .all()
    )

    rows: list[dict] = []
    posted_total = Decimal("0.00")

    for voucher in vouchers:
        debit_total = sum((Decimal(line.debit or 0) for line in voucher.lines), Decimal("0.00"))
        credit_total = sum((Decimal(line.credit or 0) for line in voucher.lines), Decimal("0.00"))
        amount = max(debit_total, credit_total).quantize(Decimal("0.01"))
        posted_total += amount
        rows.append(
            {
                "id": voucher.id,
                "voucher_date": voucher.voucher_date,
                "reference": voucher.reference or f"IFRS9-{voucher.id}",
                "description": voucher.description or "IFRS9 ECL",
                "amount": amount,
            }
        )

    return rows, posted_total.quantize(Decimal("0.01"))


@bp.before_app_request
def _load_tenant_into_g() -> None:
    tenant_id = get_current_tenant_id()
    if getattr(g, "tenant", None) is None:
        g.tenant = None
        if tenant_id:
            tenant = Tenant.query.get(tenant_id)
            if tenant:
                g.tenant = tenant


@bp.route("", methods=["GET", "POST"])
@bp.route("/", methods=["GET", "POST"])
@login_required
def overview():
    _require_tenant()
    if not _has_ifrs9_access(g.tenant):
        flash(_("Le module IFRS9 n'est pas disponible dans votre plan actuel. Activez un plan IFRS9 depuis la page des plans."), "warning")
        return redirect(url_for("billing.plans", product="ifrs9"))

    tenant: Tenant = g.tenant
    config = _load_ifrs9_config(tenant)

    selected_company_id = request.args.get("company_id", type=int)
    if not selected_company_id:
        selected_company_id = config.get("company_id")
    if not selected_company_id:
        selected_company_id = None

    if request.method == "POST":
        action = (request.form.get("action") or "save_config").strip().lower()

        posted_company_id = request.form.get("company_id", type=int)
        expense_gl_account_id = request.form.get("expense_gl_account_id", type=int)
        provision_gl_account_id = request.form.get("provision_gl_account_id", type=int)
        pd_percent = _to_decimal(request.form.get("pd_percent"), Decimal("3.0"))
        lgd_percent = _to_decimal(request.form.get("lgd_percent"), Decimal("45.0"))
        ead_amount = _to_decimal(request.form.get("ead_amount"), Decimal("250000"))
        stage = (request.form.get("stage") or "stage1").strip().lower()
        if stage not in {"stage1", "stage2", "stage3"}:
            stage = "stage1"

        pd_ratio = max(Decimal("0"), min(Decimal("1"), pd_percent / Decimal("100")))
        lgd_ratio = max(Decimal("0"), min(Decimal("1"), lgd_percent / Decimal("100")))
        ead_amount = max(Decimal("0"), ead_amount)

        if not posted_company_id:
            flash(_("Sélectionnez une société Finance pour IFRS9."), "warning")
            return redirect(url_for("ifrs9.overview"))

        company = FinanceCompany.query.filter_by(id=posted_company_id, tenant_id=tenant.id).first()
        if not company:
            flash(_("La société sélectionnée est invalide."), "warning")
            return redirect(url_for("ifrs9.overview"))

        expense_account = None
        provision_account = None
        if expense_gl_account_id:
            expense_account = FinanceGLAccount.query.filter_by(
                id=expense_gl_account_id,
                tenant_id=tenant.id,
                company_id=posted_company_id,
            ).first()
        if provision_gl_account_id:
            provision_account = FinanceGLAccount.query.filter_by(
                id=provision_gl_account_id,
                tenant_id=tenant.id,
                company_id=posted_company_id,
            ).first()

        if not expense_account or not provision_account:
            flash(_("Sélectionnez les comptes de charge et de provision IFRS9."), "warning")
            return redirect(url_for("ifrs9.overview", company_id=posted_company_id))

        config = {
            "company_id": posted_company_id,
            "expense_gl_account_id": expense_account.id,
            "provision_gl_account_id": provision_account.id,
            "default_pd": str(pd_ratio),
            "default_lgd": str(lgd_ratio),
            "default_ead": str(ead_amount),
            "stage": stage,
        }

        _save_ifrs9_config(tenant, config)

        ecl_amount = _compute_ecl(pd_ratio, lgd_ratio, ead_amount, stage)

        if action == "post_entry":
            voucher = FinanceLedgerVoucher(
                tenant_id=tenant.id,
                company_id=posted_company_id,
                voucher_date=date.today(),
                reference=f"IFRS9-{date.today().isoformat()}",
                description=f"IFRS9 ECL {stage.upper()}",
            )
            db.session.add(voucher)
            db.session.flush()

            db.session.add(
                FinanceLedgerLine(
                    tenant_id=tenant.id,
                    company_id=posted_company_id,
                    voucher_id=voucher.id,
                    gl_account_id=expense_account.id,
                    debit=ecl_amount,
                    credit=Decimal("0.00"),
                    description=f"IFRS9 charge ECL {stage.upper()}",
                )
            )
            db.session.add(
                FinanceLedgerLine(
                    tenant_id=tenant.id,
                    company_id=posted_company_id,
                    voucher_id=voucher.id,
                    gl_account_id=provision_account.id,
                    debit=Decimal("0.00"),
                    credit=ecl_amount,
                    description=f"IFRS9 provision ECL {stage.upper()}",
                )
            )
            db.session.commit()
            flash(
                _(
                    "Écriture IFRS9 comptabilisée ({amount}) avec référence {reference}.",
                    amount=str(ecl_amount),
                    reference=voucher.reference or "IFRS9",
                ),
                "success",
            )
        else:
            db.session.commit()
            flash(_("Configuration IFRS9 enregistrée."), "success")

        return redirect(url_for("ifrs9.overview", company_id=posted_company_id))

    company_id = selected_company_id if isinstance(selected_company_id, int) else config.get("company_id")
    companies, gl_accounts = _company_and_accounts_scope(tenant.id, company_id)

    if not company_id and companies:
        company_id = companies[0].id
        companies, gl_accounts = _company_and_accounts_scope(tenant.id, company_id)

    pd_ratio = _to_decimal(str(config.get("default_pd") or "0.03"), Decimal("0.03"))
    lgd_ratio = _to_decimal(str(config.get("default_lgd") or "0.45"), Decimal("0.45"))
    ead_amount = _to_decimal(str(config.get("default_ead") or "250000"), Decimal("250000"))
    stage = str(config.get("stage") or "stage1").lower()
    if stage not in {"stage1", "stage2", "stage3"}:
        stage = "stage1"

    ecl_amount = _compute_ecl(pd_ratio, lgd_ratio, ead_amount, stage)

    selected_expense_id = config.get("expense_gl_account_id")
    selected_provision_id = config.get("provision_gl_account_id")

    expense_account = next((a for a in gl_accounts if a.id == selected_expense_id), None)
    provision_account = next((a for a in gl_accounts if a.id == selected_provision_id), None)

    selected_company = next((c for c in companies if c.id == company_id), None)
    ifrs9_report_rows, ifrs9_posted_total = _recent_ifrs9_postings(tenant.id, company_id)

    return render_template(
        "ifrs9/overview.html",
        tenant=tenant,
        title="AUDELA IFRS9",
        companies=companies,
        gl_accounts=gl_accounts,
        selected_company=selected_company,
        selected_company_id=company_id,
        selected_expense_id=selected_expense_id,
        selected_provision_id=selected_provision_id,
        pd_percent=(pd_ratio * Decimal("100")).quantize(Decimal("0.01")),
        lgd_percent=(lgd_ratio * Decimal("100")).quantize(Decimal("0.01")),
        ead_amount=ead_amount.quantize(Decimal("0.01")),
        stage=stage,
        ecl_amount=ecl_amount,
        expense_account=expense_account,
        provision_account=provision_account,
        ifrs9_report_rows=ifrs9_report_rows,
        ifrs9_posted_total=ifrs9_posted_total,
        ifrs9_postings_count=len(ifrs9_report_rows),
    )
