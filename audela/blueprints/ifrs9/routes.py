from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal, InvalidOperation

from flask import abort, flash, g, redirect, render_template, request, url_for
from flask_login import current_user, login_required
from sqlalchemy.orm.attributes import flag_modified

from ...extensions import db
from ...i18n import DEFAULT_LANG, tr
from ...models.core import Tenant
from ...models.finance import FinanceCompany
from ...models.finance_ext import FinanceGLAccount, FinanceLedgerLine, FinanceLedgerVoucher
from ...models.finance_invoices import FinanceInvoice, FinanceSetting
from ...services.subscription_service import SubscriptionService
from ...tenancy import enforce_subscription_access_or_redirect, get_current_tenant_id
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
        "ead_source": "manual",
        "stage_mode": "manual",
        "scenario_base_weight": "0.60",
        "scenario_upside_weight": "0.20",
        "scenario_downside_weight": "0.20",
        "scenario_base_multiplier": "1.00",
        "scenario_upside_multiplier": "0.80",
        "scenario_downside_multiplier": "1.30",
        "sicr_stage2_dpd": 30,
        "sicr_stage3_dpd": 90,
        "stage": "stage1",
    }


def _normalize_ifrs9_config(raw_cfg: dict | None) -> dict:
    cfg = _default_ifrs9_config()
    if isinstance(raw_cfg, dict):
        cfg.update(raw_cfg)

    stage = str(cfg.get("stage") or "stage1").strip().lower()
    if stage not in {"stage1", "stage2", "stage3"}:
        stage = "stage1"
    cfg["stage"] = stage

    ead_source = str(cfg.get("ead_source") or "manual").strip().lower()
    cfg["ead_source"] = ead_source if ead_source in {"manual", "finance"} else "manual"

    stage_mode = str(cfg.get("stage_mode") or "manual").strip().lower()
    cfg["stage_mode"] = stage_mode if stage_mode in {"manual", "auto"} else "manual"

    def _dflt_decimal(key: str, fallback: str, min_v: Decimal | None = None, max_v: Decimal | None = None) -> str:
        v = _to_decimal(str(cfg.get(key) or ""), Decimal(fallback))
        if min_v is not None and v < min_v:
            v = min_v
        if max_v is not None and v > max_v:
            v = max_v
        return str(v)

    cfg["default_pd"] = _dflt_decimal("default_pd", "0.03", Decimal("0"), Decimal("1"))
    cfg["default_lgd"] = _dflt_decimal("default_lgd", "0.45", Decimal("0"), Decimal("1"))
    cfg["default_ead"] = _dflt_decimal("default_ead", "250000", Decimal("0"), None)

    cfg["scenario_base_weight"] = _dflt_decimal("scenario_base_weight", "0.60", Decimal("0"), None)
    cfg["scenario_upside_weight"] = _dflt_decimal("scenario_upside_weight", "0.20", Decimal("0"), None)
    cfg["scenario_downside_weight"] = _dflt_decimal("scenario_downside_weight", "0.20", Decimal("0"), None)
    cfg["scenario_base_multiplier"] = _dflt_decimal("scenario_base_multiplier", "1.00", Decimal("0"), None)
    cfg["scenario_upside_multiplier"] = _dflt_decimal("scenario_upside_multiplier", "0.80", Decimal("0"), None)
    cfg["scenario_downside_multiplier"] = _dflt_decimal("scenario_downside_multiplier", "1.30", Decimal("0"), None)

    w_base = _to_decimal(cfg["scenario_base_weight"], Decimal("0.60"))
    w_up = _to_decimal(cfg["scenario_upside_weight"], Decimal("0.20"))
    w_down = _to_decimal(cfg["scenario_downside_weight"], Decimal("0.20"))
    total = w_base + w_up + w_down
    if total <= 0:
        w_base, w_up, w_down = Decimal("0.60"), Decimal("0.20"), Decimal("0.20")
        total = Decimal("1.00")

    cfg["scenario_base_weight"] = str((w_base / total).quantize(Decimal("0.0001")))
    cfg["scenario_upside_weight"] = str((w_up / total).quantize(Decimal("0.0001")))
    cfg["scenario_downside_weight"] = str((w_down / total).quantize(Decimal("0.0001")))

    try:
        stage2 = max(1, int(cfg.get("sicr_stage2_dpd") or 30))
    except Exception:
        stage2 = 30
    try:
        stage3 = int(cfg.get("sicr_stage3_dpd") or 90)
    except Exception:
        stage3 = 90
    if stage3 <= stage2:
        stage3 = stage2 + 60
    cfg["sicr_stage2_dpd"] = stage2
    cfg["sicr_stage3_dpd"] = stage3

    return cfg


def _default_finance_ifrs9_config() -> dict:
    return {
        "stage_1_max_dpd": 30,
        "stage_2_max_dpd": 90,
        "pd_stage_1": 2.0,
        "pd_stage_2": 10.0,
        "pd_stage_3": 35.0,
        "lgd_stage_1": 40.0,
        "lgd_stage_2": 50.0,
        "lgd_stage_3": 65.0,
        "include_draft_invoices": True,
    }


def _load_ifrs9_config(tenant: Tenant) -> dict:
    settings = tenant.settings_json if isinstance(tenant.settings_json, dict) else {}
    raw = settings.get("ifrs9") if isinstance(settings.get("ifrs9"), dict) else {}
    return _normalize_ifrs9_config(raw)


def _save_ifrs9_config(tenant: Tenant, cfg: dict) -> None:
    settings = dict(tenant.settings_json) if isinstance(tenant.settings_json, dict) else {}
    settings["ifrs9"] = _normalize_ifrs9_config(cfg)
    tenant.settings_json = settings
    flag_modified(tenant, "settings_json")


def _append_ifrs9_model_version(tenant: Tenant, cfg: dict, action: str) -> None:
    settings = dict(tenant.settings_json) if isinstance(tenant.settings_json, dict) else {}
    versions = settings.get("ifrs9_model_versions") if isinstance(settings.get("ifrs9_model_versions"), list) else []
    next_version = int(versions[-1].get("version", 0) or 0) + 1 if versions else 1
    versions.append(
        {
            "version": next_version,
            "saved_at": datetime.utcnow().isoformat(),
            "saved_by": int(getattr(current_user, "id", 0) or 0),
            "action": action,
            "company_id": cfg.get("company_id"),
            "stage": cfg.get("stage"),
            "stage_mode": cfg.get("stage_mode"),
            "ead_source": cfg.get("ead_source"),
            "default_pd": cfg.get("default_pd"),
            "default_lgd": cfg.get("default_lgd"),
            "default_ead": cfg.get("default_ead"),
        }
    )
    settings["ifrs9_model_versions"] = versions[-25:]
    tenant.settings_json = settings
    flag_modified(tenant, "settings_json")


def _append_ifrs9_validation_log(tenant: Tenant, company_id: int, ecl_amount: Decimal, flags: dict) -> None:
    settings = dict(tenant.settings_json) if isinstance(tenant.settings_json, dict) else {}
    logs = settings.get("ifrs9_validation_logs") if isinstance(settings.get("ifrs9_validation_logs"), list) else []
    logs.append(
        {
            "validated_at": datetime.utcnow().isoformat(),
            "validated_by": int(getattr(current_user, "id", 0) or 0),
            "company_id": company_id,
            "ecl_preview": str(ecl_amount),
            "flags": flags,
        }
    )
    settings["ifrs9_validation_logs"] = logs[-50:]
    tenant.settings_json = settings
    flag_modified(tenant, "settings_json")


def _load_finance_ifrs9_config(tenant_id: int, company_id: int) -> dict:
    defaults = _default_finance_ifrs9_config()
    setting = FinanceSetting.query.filter_by(
        tenant_id=tenant_id,
        company_id=company_id,
        key="ifrs9",
    ).first()
    raw = setting.value_json if setting and isinstance(setting.value_json, dict) else {}
    cfg = defaults.copy()
    if isinstance(raw, dict):
        cfg.update(raw)

    try:
        cfg["stage_1_max_dpd"] = max(0, int(cfg.get("stage_1_max_dpd") or defaults["stage_1_max_dpd"]))
    except Exception:
        cfg["stage_1_max_dpd"] = defaults["stage_1_max_dpd"]
    try:
        cfg["stage_2_max_dpd"] = int(cfg.get("stage_2_max_dpd") or defaults["stage_2_max_dpd"])
    except Exception:
        cfg["stage_2_max_dpd"] = defaults["stage_2_max_dpd"]
    if cfg["stage_2_max_dpd"] <= cfg["stage_1_max_dpd"]:
        cfg["stage_2_max_dpd"] = cfg["stage_1_max_dpd"] + 60

    for key in [
        "pd_stage_1", "pd_stage_2", "pd_stage_3",
        "lgd_stage_1", "lgd_stage_2", "lgd_stage_3",
    ]:
        try:
            value = float(cfg.get(key))
        except Exception:
            value = float(defaults[key])
        cfg[key] = max(0.0, min(100.0, value))

    cfg["include_draft_invoices"] = bool(cfg.get("include_draft_invoices", True))
    return cfg


def _save_finance_ifrs9_config(tenant_id: int, company_id: int, cfg: dict) -> None:
    setting = FinanceSetting.query.filter_by(
        tenant_id=tenant_id,
        company_id=company_id,
        key="ifrs9",
    ).first()
    if not setting:
        setting = FinanceSetting(
            tenant_id=tenant_id,
            company_id=company_id,
            key="ifrs9",
            value_json=cfg,
        )
        db.session.add(setting)
    else:
        setting.value_json = cfg


def _stage_suffix(stage: str) -> str:
    return {
        "stage1": "1",
        "stage2": "2",
        "stage3": "3",
    }.get(stage, "1")


def _finance_ead_snapshot(
    tenant_id: int,
    company_id: int,
    include_draft_invoices: bool,
    sicr_stage2_dpd: int,
    sicr_stage3_dpd: int,
) -> dict:
    statuses = ["sent"]
    if include_draft_invoices:
        statuses.append("draft")

    invoices = (
        FinanceInvoice.query.filter_by(tenant_id=tenant_id, company_id=company_id)
        .filter(FinanceInvoice.invoice_type == "sale")
        .filter(FinanceInvoice.status.in_(statuses))
        .all()
    )

    total = Decimal("0.00")
    stage1_ead = Decimal("0.00")
    stage2_ead = Decimal("0.00")
    stage3_ead = Decimal("0.00")
    overdue = 0
    overdue_amount = Decimal("0.00")
    today = date.today()
    for inv in invoices:
        gross = Decimal(str(inv.total_gross or 0))
        if gross <= 0:
            continue
        total += gross
        due = inv.due_date or inv.issue_date
        dpd = max(0, (today - due).days) if due else 0
        if dpd > 0:
            overdue += 1
            overdue_amount += gross

        if dpd >= int(sicr_stage3_dpd):
            stage3_ead += gross
        elif dpd >= int(sicr_stage2_dpd):
            stage2_ead += gross
        else:
            stage1_ead += gross

    suggested_stage = "stage1"
    if stage3_ead > 0:
        suggested_stage = "stage3"
    elif stage2_ead > 0:
        suggested_stage = "stage2"

    overdue_share = Decimal("0.00")
    if total > 0:
        overdue_share = (overdue_amount / total).quantize(Decimal("0.0001"))

    return {
        "ead_total": total.quantize(Decimal("0.01")),
        "invoice_count": len(invoices),
        "overdue_count": overdue,
        "overdue_amount": overdue_amount.quantize(Decimal("0.01")),
        "overdue_share": overdue_share,
        "stage1_ead": stage1_ead.quantize(Decimal("0.01")),
        "stage2_ead": stage2_ead.quantize(Decimal("0.01")),
        "stage3_ead": stage3_ead.quantize(Decimal("0.01")),
        "suggested_stage": suggested_stage,
        "include_draft_invoices": include_draft_invoices,
    }


def _compute_ecl(
    pd_ratio: Decimal,
    lgd_ratio: Decimal,
    ead_amount: Decimal,
    stage: str,
    cfg: dict,
) -> tuple[Decimal, list[dict]]:
    stage_multipliers = {
        "stage1": Decimal("1.00"),
        "stage2": Decimal("1.50"),
        "stage3": Decimal("2.00"),
    }
    multiplier = stage_multipliers.get(stage, Decimal("1.00"))
    scenarios = [
        {
            "name": "base",
            "weight": _to_decimal(str(cfg.get("scenario_base_weight") or "0.60"), Decimal("0.60")),
            "multiplier": _to_decimal(str(cfg.get("scenario_base_multiplier") or "1.00"), Decimal("1.00")),
        },
        {
            "name": "upside",
            "weight": _to_decimal(str(cfg.get("scenario_upside_weight") or "0.20"), Decimal("0.20")),
            "multiplier": _to_decimal(str(cfg.get("scenario_upside_multiplier") or "0.80"), Decimal("0.80")),
        },
        {
            "name": "downside",
            "weight": _to_decimal(str(cfg.get("scenario_downside_weight") or "0.20"), Decimal("0.20")),
            "multiplier": _to_decimal(str(cfg.get("scenario_downside_multiplier") or "1.30"), Decimal("1.30")),
        },
    ]

    breakdown = []
    total = Decimal("0.00")
    for sc in scenarios:
        ecl = ead_amount * pd_ratio * lgd_ratio * multiplier * max(Decimal("0"), sc["multiplier"])
        weighted = ecl * max(Decimal("0"), sc["weight"])
        total += weighted
        breakdown.append(
            {
                "name": sc["name"],
                "weight": sc["weight"],
                "multiplier": sc["multiplier"],
                "ecl": ecl.quantize(Decimal("0.01")),
                "weighted_ecl": weighted.quantize(Decimal("0.01")),
            }
        )

    return total.quantize(Decimal("0.01")), breakdown


def _build_ifrs9_compliance_flags(
    expense_id: int | None,
    provision_id: int | None,
    ead_source: str,
    finance_snapshot: dict,
    cfg: dict,
) -> dict:
    w_base = _to_decimal(str(cfg.get("scenario_base_weight") or "0"), Decimal("0"))
    w_up = _to_decimal(str(cfg.get("scenario_upside_weight") or "0"), Decimal("0"))
    w_down = _to_decimal(str(cfg.get("scenario_downside_weight") or "0"), Decimal("0"))
    weight_sum = (w_base + w_up + w_down)
    return {
        "accounts_mapped": bool(expense_id and provision_id),
        "ead_source_finance": ead_source == "finance",
        "finance_data_ready": int(finance_snapshot.get("invoice_count") or 0) > 0,
        "staging_thresholds_ordered": int(cfg.get("sicr_stage3_dpd") or 90) > int(cfg.get("sicr_stage2_dpd") or 30),
        "pd_lgd_in_range": all(
            0.0 <= float(cfg.get(k, 0.0)) <= 1.0
            for k in ["default_pd", "default_lgd"]
        ),
        "scenario_weights_valid": abs(float(weight_sum) - 1.0) <= 0.02,
    }


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

    # Keep IFRS9 posting accounts aligned with Chart of Accounts posting rules:
    # if hierarchy exists, only leaf accounts are selectable for debit/credit mapping.
    parent_ids = {
        int(parent_id)
        for (parent_id,) in db.session.query(FinanceGLAccount.parent_id)
        .filter_by(tenant_id=tenant_id, company_id=company_id)
        .filter(FinanceGLAccount.parent_id.isnot(None))
        .all()
    }
    if parent_ids:
        accounts = [acc for acc in accounts if acc.id not in parent_ids]

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

    if (
        request.endpoint
        and request.endpoint.startswith("ifrs9.")
        and current_user.is_authenticated
        and getattr(g, "tenant", None)
        and current_user.tenant_id == g.tenant.id
    ):
        redirect_resp = enforce_subscription_access_or_redirect(current_user.tenant_id)
        if redirect_resp is not None:
            return redirect_resp


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

    if selected_company_id:
        finance_cfg = _load_finance_ifrs9_config(tenant.id, int(selected_company_id))
        stage_for_defaults = str(config.get("stage") or "stage1").strip().lower()
        stage_num = _stage_suffix(stage_for_defaults)
        config["default_pd"] = str(Decimal(str(finance_cfg.get(f"pd_stage_{stage_num}", 3.0))) / Decimal("100"))
        config["default_lgd"] = str(Decimal(str(finance_cfg.get(f"lgd_stage_{stage_num}", 45.0))) / Decimal("100"))

    if request.method == "POST":
        action = (request.form.get("action") or "save_config").strip().lower()

        posted_company_id = request.form.get("company_id", type=int)
        expense_gl_account_id = request.form.get("expense_gl_account_id", type=int)
        provision_gl_account_id = request.form.get("provision_gl_account_id", type=int)
        pd_percent = _to_decimal(request.form.get("pd_percent"), Decimal("3.0"))
        lgd_percent = _to_decimal(request.form.get("lgd_percent"), Decimal("45.0"))
        ead_amount = _to_decimal(request.form.get("ead_amount"), Decimal("250000"))
        ead_source = (request.form.get("ead_source") or "manual").strip().lower()
        if ead_source not in {"manual", "finance"}:
            ead_source = "manual"
        stage_mode = (request.form.get("stage_mode") or "manual").strip().lower()
        if stage_mode not in {"manual", "auto"}:
            stage_mode = "manual"
        stage = (request.form.get("stage") or "stage1").strip().lower()
        if stage not in {"stage1", "stage2", "stage3"}:
            stage = "stage1"

        scenario_base_weight = _to_decimal(request.form.get("scenario_base_weight"), Decimal("0.60"))
        scenario_upside_weight = _to_decimal(request.form.get("scenario_upside_weight"), Decimal("0.20"))
        scenario_downside_weight = _to_decimal(request.form.get("scenario_downside_weight"), Decimal("0.20"))
        scenario_base_multiplier = _to_decimal(request.form.get("scenario_base_multiplier"), Decimal("1.00"))
        scenario_upside_multiplier = _to_decimal(request.form.get("scenario_upside_multiplier"), Decimal("0.80"))
        scenario_downside_multiplier = _to_decimal(request.form.get("scenario_downside_multiplier"), Decimal("1.30"))

        try:
            sicr_stage2_dpd = max(1, int((request.form.get("sicr_stage2_dpd") or "30").strip()))
        except Exception:
            sicr_stage2_dpd = 30
        try:
            sicr_stage3_dpd = int((request.form.get("sicr_stage3_dpd") or "90").strip())
        except Exception:
            sicr_stage3_dpd = 90
        if sicr_stage3_dpd <= sicr_stage2_dpd:
            sicr_stage3_dpd = sicr_stage2_dpd + 60

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

        finance_cfg = _load_finance_ifrs9_config(tenant.id, posted_company_id)
        finance_snapshot = _finance_ead_snapshot(
            tenant.id,
            posted_company_id,
            bool(finance_cfg.get("include_draft_invoices", True)),
            sicr_stage2_dpd,
            sicr_stage3_dpd,
        )
        if stage_mode == "auto" and ead_source == "finance":
            stage = str(finance_snapshot.get("suggested_stage") or stage)
        if ead_source == "finance" and finance_snapshot["ead_total"] > 0:
            ead_amount = finance_snapshot["ead_total"]
        elif ead_source == "finance" and finance_snapshot["ead_total"] <= 0:
            flash(_("Aucune exposition Finance ouverte trouvée: valeur EAD manuelle conservée."), "warning")

        config = _normalize_ifrs9_config({
            "company_id": posted_company_id,
            "expense_gl_account_id": expense_account.id,
            "provision_gl_account_id": provision_account.id,
            "default_pd": str(pd_ratio),
            "default_lgd": str(lgd_ratio),
            "default_ead": str(ead_amount),
            "ead_source": ead_source,
            "stage_mode": stage_mode,
            "scenario_base_weight": str(scenario_base_weight),
            "scenario_upside_weight": str(scenario_upside_weight),
            "scenario_downside_weight": str(scenario_downside_weight),
            "scenario_base_multiplier": str(scenario_base_multiplier),
            "scenario_upside_multiplier": str(scenario_upside_multiplier),
            "scenario_downside_multiplier": str(scenario_downside_multiplier),
            "sicr_stage2_dpd": sicr_stage2_dpd,
            "sicr_stage3_dpd": sicr_stage3_dpd,
            "stage": stage,
        })

        _save_ifrs9_config(tenant, config)
        _append_ifrs9_model_version(tenant, config, action)

        stage_num = _stage_suffix(stage)
        finance_cfg[f"pd_stage_{stage_num}"] = float((pd_ratio * Decimal("100")).quantize(Decimal("0.01")))
        finance_cfg[f"lgd_stage_{stage_num}"] = float((lgd_ratio * Decimal("100")).quantize(Decimal("0.01")))
        _save_finance_ifrs9_config(tenant.id, posted_company_id, finance_cfg)

        ecl_amount, _ = _compute_ecl(pd_ratio, lgd_ratio, ead_amount, stage, config)
        flags = _build_ifrs9_compliance_flags(expense_account.id, provision_account.id, ead_source, finance_snapshot, config)
        _append_ifrs9_validation_log(tenant, posted_company_id, ecl_amount, flags)

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
    ead_source = str(config.get("ead_source") or "manual").strip().lower()
    if ead_source not in {"manual", "finance"}:
        ead_source = "manual"
    stage = str(config.get("stage") or "stage1").lower()
    if stage not in {"stage1", "stage2", "stage3"}:
        stage = "stage1"
    stage_mode = str(config.get("stage_mode") or "manual").strip().lower()
    if stage_mode not in {"manual", "auto"}:
        stage_mode = "manual"

    finance_snapshot = {
        "ead_total": Decimal("0.00"),
        "invoice_count": 0,
        "overdue_count": 0,
        "overdue_amount": Decimal("0.00"),
        "overdue_share": Decimal("0.0000"),
        "stage1_ead": Decimal("0.00"),
        "stage2_ead": Decimal("0.00"),
        "stage3_ead": Decimal("0.00"),
        "suggested_stage": "stage1",
        "include_draft_invoices": True,
    }
    if company_id:
        finance_cfg = _load_finance_ifrs9_config(tenant.id, int(company_id))
        finance_snapshot = _finance_ead_snapshot(
            tenant.id,
            int(company_id),
            bool(finance_cfg.get("include_draft_invoices", True)),
            int(config.get("sicr_stage2_dpd") or 30),
            int(config.get("sicr_stage3_dpd") or 90),
        )
        if stage_mode == "auto" and ead_source == "finance":
            stage = str(finance_snapshot.get("suggested_stage") or stage)
        if ead_source == "finance" and finance_snapshot["ead_total"] > 0:
            ead_amount = finance_snapshot["ead_total"]

    selected_expense_id = config.get("expense_gl_account_id")
    selected_provision_id = config.get("provision_gl_account_id")

    compliance_flags = _build_ifrs9_compliance_flags(
        selected_expense_id,
        selected_provision_id,
        ead_source,
        finance_snapshot,
        config,
    )

    ecl_amount, ecl_scenarios = _compute_ecl(pd_ratio, lgd_ratio, ead_amount, stage, config)

    expense_account = next((a for a in gl_accounts if a.id == selected_expense_id), None)
    provision_account = next((a for a in gl_accounts if a.id == selected_provision_id), None)

    selected_company = next((c for c in companies if c.id == company_id), None)
    ifrs9_report_rows, ifrs9_posted_total = _recent_ifrs9_postings(tenant.id, company_id)
    settings = tenant.settings_json if isinstance(tenant.settings_json, dict) else {}
    model_versions = settings.get("ifrs9_model_versions") if isinstance(settings.get("ifrs9_model_versions"), list) else []
    validation_logs = settings.get("ifrs9_validation_logs") if isinstance(settings.get("ifrs9_validation_logs"), list) else []

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
        ead_source=ead_source,
        stage_mode=stage_mode,
        scenario_base_weight=_to_decimal(str(config.get("scenario_base_weight") or "0.60"), Decimal("0.60")),
        scenario_upside_weight=_to_decimal(str(config.get("scenario_upside_weight") or "0.20"), Decimal("0.20")),
        scenario_downside_weight=_to_decimal(str(config.get("scenario_downside_weight") or "0.20"), Decimal("0.20")),
        scenario_base_multiplier=_to_decimal(str(config.get("scenario_base_multiplier") or "1.00"), Decimal("1.00")),
        scenario_upside_multiplier=_to_decimal(str(config.get("scenario_upside_multiplier") or "0.80"), Decimal("0.80")),
        scenario_downside_multiplier=_to_decimal(str(config.get("scenario_downside_multiplier") or "1.30"), Decimal("1.30")),
        sicr_stage2_dpd=int(config.get("sicr_stage2_dpd") or 30),
        sicr_stage3_dpd=int(config.get("sicr_stage3_dpd") or 90),
        finance_ead_total=finance_snapshot["ead_total"],
        finance_invoice_count=finance_snapshot["invoice_count"],
        finance_overdue_count=finance_snapshot["overdue_count"],
        finance_overdue_share=finance_snapshot["overdue_share"],
        finance_stage1_ead=finance_snapshot["stage1_ead"],
        finance_stage2_ead=finance_snapshot["stage2_ead"],
        finance_stage3_ead=finance_snapshot["stage3_ead"],
        finance_suggested_stage=finance_snapshot["suggested_stage"],
        finance_include_draft_invoices=finance_snapshot["include_draft_invoices"],
        ifrs9_compliance_flags=compliance_flags,
        ecl_scenarios=ecl_scenarios,
        ifrs9_model_versions=list(reversed(model_versions[-5:])),
        ifrs9_validation_logs=list(reversed(validation_logs[-10:])),
        stage=stage,
        ecl_amount=ecl_amount,
        expense_account=expense_account,
        provision_account=provision_account,
        ifrs9_report_rows=ifrs9_report_rows,
        ifrs9_posted_total=ifrs9_posted_total,
        ifrs9_postings_count=len(ifrs9_report_rows),
    )
