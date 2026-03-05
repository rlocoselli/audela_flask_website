from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
import csv
import io
import calendar
from urllib.parse import urlencode

from flask import abort, flash, g, jsonify, make_response, redirect, render_template, request, send_file, url_for
from flask_login import current_user, login_required
from sqlalchemy import func
from sqlalchemy.exc import IntegrityError

from ...extensions import db
from ...i18n import DEFAULT_LANG, tr
from ...models.core import Tenant, User
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
        module_access = get_user_module_access(g.tenant, current_user.id)
        if not module_access.get("bi", True):
            flash(_("Accès Audela Credit désactivé pour votre utilisateur."), "warning")
            return redirect(url_for("tenant.dashboard"))

        bi_menu_access = get_user_menu_access(g.tenant, current_user.id, "bi")
        if not bi_menu_access.get("credit_origination", True):
            flash(_("Accès menu Audela Credit désactivé pour votre utilisateur."), "warning")
            return redirect(url_for("tenant.dashboard"))

        if not _credit_feature_enabled(g.tenant):
            flash(_("Le produit Audela Credit n'est pas disponible dans votre plan actuel."), "warning")
            return redirect(url_for("billing.plans", product="credit"))


@bp.app_context_processor
def _credit_layout_context():
    tenant = getattr(g, "tenant", None)
    module_access = get_user_module_access(tenant, getattr(current_user, "id", None))
    bi_menu_access = get_user_menu_access(tenant, getattr(current_user, "id", None), "bi")
    return {
        "module_access": module_access,
        "bi_menu_access": bi_menu_access,
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

    if request.method == "POST":
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

    rows = CreditBorrower.query.filter_by(tenant_id=g.tenant.id).order_by(CreditBorrower.created_at.desc()).all()
    return render_template(
        "credit/borrowers.html",
        tenant=g.tenant,
        borrowers=rows,
        countries=countries,
        sectors=sectors,
        ratings=ratings,
    )


@bp.route("/deals", methods=["GET", "POST"])
@login_required
def deals():
    _require_tenant()
    borrowers = CreditBorrower.query.filter_by(tenant_id=g.tenant.id).order_by(CreditBorrower.name.asc()).all()

    if request.method == "POST":
        borrower_id = int(request.form.get("borrower_id") or 0)
        borrower = CreditBorrower.query.filter_by(id=borrower_id, tenant_id=g.tenant.id).first()
        if not borrower:
            flash(_("Borrower invalide."), "warning")
            return redirect(url_for("credit.deals"))

        deal = CreditDeal(
            tenant_id=g.tenant.id,
            borrower_id=borrower.id,
            code=(request.form.get("code") or "").strip(),
            purpose=(request.form.get("purpose") or "").strip() or None,
            requested_amount=_to_decimal(request.form.get("requested_amount"), "0"),
            status=(request.form.get("status") or "in_review").strip() or "in_review",
        )
        if not deal.code:
            flash(_("Code deal requis."), "warning")
            return redirect(url_for("credit.deals"))
        db.session.add(deal)
        db.session.commit()
        flash(_("Deal ajouté."), "success")
        return redirect(url_for("credit.deals"))

    rows = (
        CreditDeal.query.filter_by(tenant_id=g.tenant.id)
        .order_by(CreditDeal.updated_at.desc())
        .all()
    )
    return render_template("credit/deals.html", tenant=g.tenant, deals=rows, borrowers=borrowers)


@bp.route("/facilities", methods=["GET", "POST"])
@login_required
def facilities():
    _require_tenant()
    _seed_credit_references()
    deals = CreditDeal.query.filter_by(tenant_id=g.tenant.id).order_by(CreditDeal.code.asc()).all()
    facility_types = CreditFacilityType.query.order_by(CreditFacilityType.label.asc()).all()

    if request.method == "POST":
        deal_id = int(request.form.get("deal_id") or 0)
        deal = CreditDeal.query.filter_by(id=deal_id, tenant_id=g.tenant.id).first()
        if not deal:
            flash(_("Deal invalide."), "warning")
            return redirect(url_for("credit.facilities"))

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
        db.session.commit()
        flash(_("Facility ajoutée."), "success")
        return redirect(url_for("credit.facilities"))

    rows = CreditFacility.query.filter_by(tenant_id=g.tenant.id).order_by(CreditFacility.created_at.desc()).all()
    return render_template(
        "credit/facilities.html",
        tenant=g.tenant,
        facilities=rows,
        deals=deals,
        facility_types=facility_types,
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

    rows = CreditCollateral.query.filter_by(tenant_id=g.tenant.id).order_by(CreditCollateral.created_at.desc()).all()
    return render_template(
        "credit/collateral.html",
        tenant=g.tenant,
        collateral=rows,
        borrowers=borrowers,
        deals=deals,
        collateral_types=collateral_types,
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

    rows = CreditGuarantor.query.filter_by(tenant_id=g.tenant.id).order_by(CreditGuarantor.created_at.desc()).all()
    return render_template(
        "credit/guarantors.html",
        tenant=g.tenant,
        guarantors=rows,
        borrowers=borrowers,
        deals=deals,
        guarantee_types=guarantee_types,
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
    borrowers = CreditBorrower.query.filter_by(tenant_id=g.tenant.id).order_by(CreditBorrower.name.asc()).all()
    users = User.query.filter_by(tenant_id=g.tenant.id).order_by(User.email.asc()).all()
    functions = CreditAnalystFunction.query.filter_by(tenant_id=g.tenant.id).order_by(CreditAnalystFunction.label.asc()).all()

    if request.method == "POST":
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

    rows = CreditFinancialStatement.query.filter_by(tenant_id=g.tenant.id).order_by(CreditFinancialStatement.created_at.desc()).all()
    return render_template(
        "credit/financials.html",
        tenant=g.tenant,
        financials=rows,
        borrowers=borrowers,
        users=users,
        functions=functions,
        current_year=date.today().year,
    )


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

    required_cols = {"borrower_id", "period_label", "fiscal_year", "revenue", "ebitda", "total_debt", "cash", "net_income"}
    missing = sorted(required_cols - {str(h).strip() for h in reader.fieldnames})
    if missing:
        flash(_("CSV invalide: colonnes manquantes ({cols}).", cols=", ".join(missing)), "warning")
        return redirect(url_for("credit.financials"))

    imported = 0
    skipped = 0
    file_name = upload.filename or "upload.csv"
    for row in reader:
        borrower_id = _to_int((row.get("borrower_id") or "").strip())
        borrower = CreditBorrower.query.filter_by(id=borrower_id, tenant_id=g.tenant.id).first() if borrower_id else None
        if not borrower:
            skipped += 1
            continue

        try:
            fiscal_year = int((row.get("fiscal_year") or "").strip() or date.today().year)
        except Exception:
            skipped += 1
            continue

        statement = CreditFinancialStatement(
            tenant_id=g.tenant.id,
            borrower_id=borrower.id,
            period_label=(row.get("period_label") or "FY").strip() or "FY",
            fiscal_year=fiscal_year,
            revenue=_to_decimal(row.get("revenue"), "0"),
            ebitda=_to_decimal(row.get("ebitda"), "0"),
            total_debt=_to_decimal(row.get("total_debt"), "0"),
            cash=_to_decimal(row.get("cash"), "0"),
            net_income=_to_decimal(row.get("net_income"), "0"),
            spreading_status=(row.get("spreading_status") or "in_progress").strip() or "in_progress",
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


@bp.route("/ratios")
@login_required
def ratios():
    _require_tenant()
    rows = CreditRatioSnapshot.query.filter_by(tenant_id=g.tenant.id).order_by(CreditRatioSnapshot.snapshot_date.desc()).all()
    return render_template("credit/ratios.html", tenant=g.tenant, ratios=rows)


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


@bp.route("/memos", methods=["GET", "POST"])
@login_required
def memos():
    _require_tenant()
    deals = CreditDeal.query.filter_by(tenant_id=g.tenant.id).order_by(CreditDeal.updated_at.desc()).all()
    borrowers = CreditBorrower.query.filter_by(tenant_id=g.tenant.id).order_by(CreditBorrower.name.asc()).all()

    if request.method == "POST":
        row = CreditMemo(
            tenant_id=g.tenant.id,
            deal_id=int(request.form.get("deal_id") or 0) or None,
            borrower_id=int(request.form.get("borrower_id") or 0) or None,
            title=(request.form.get("title") or "").strip() or _("Credit Memo"),
            recommendation=(request.form.get("recommendation") or "review").strip(),
            summary_text=(request.form.get("summary_text") or "").strip(),
            prepared_by_user_id=getattr(current_user, "id", None),
        )
        if not row.summary_text:
            flash(_("Le résumé du memo est requis."), "warning")
            return redirect(url_for("credit.memos"))
        db.session.add(row)
        db.session.commit()
        flash(_("Credit memo créé."), "success")
        return redirect(url_for("credit.memos"))

    rows = CreditMemo.query.filter_by(tenant_id=g.tenant.id).order_by(CreditMemo.updated_at.desc()).all()
    return render_template("credit/memos.html", tenant=g.tenant, memos=rows, deals=deals, borrowers=borrowers)


@bp.route("/memos/ai-draft", methods=["POST"])
@login_required
def memos_ai_draft():
    _require_tenant()

    deal_id = int(request.form.get("deal_id") or 0)
    deal = CreditDeal.query.filter_by(id=deal_id, tenant_id=g.tenant.id).first()
    if not deal:
        flash(_("Deal invalide pour IA."), "warning")
        return redirect(url_for("credit.memos"))

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
    db.session.commit()

    flash(_("AI credit memo généré."), "success")
    return redirect(url_for("credit.memos"))


@bp.route("/approvals", methods=["GET", "POST"])
@login_required
def approvals():
    _require_tenant()
    _seed_default_approval_workflow(g.tenant.id)
    memos = CreditMemo.query.filter_by(tenant_id=g.tenant.id).order_by(CreditMemo.updated_at.desc()).all()
    workflow_steps = (
        CreditApprovalWorkflowStep.query.filter_by(tenant_id=g.tenant.id)
        .order_by(CreditApprovalWorkflowStep.step_order.asc(), CreditApprovalWorkflowStep.id.asc())
        .all()
    )

    if request.method == "POST":
        memo_id = int(request.form.get("memo_id") or 0)
        memo = CreditMemo.query.filter_by(id=memo_id, tenant_id=g.tenant.id).first()
        if not memo:
            flash(_("Memo invalide."), "warning")
            return redirect(url_for("credit.approvals"))

        workflow_step_id = _to_int(request.form.get("workflow_step_id"))
        workflow_step = None
        if workflow_step_id:
            workflow_step = CreditApprovalWorkflowStep.query.filter_by(
                id=workflow_step_id,
                tenant_id=g.tenant.id,
            ).first()
            if not workflow_step:
                flash(_("Workflow step invalide."), "warning")
                return redirect(url_for("credit.approvals"))

        decision = (request.form.get("decision") or "pending").strip()
        stage = (request.form.get("stage") or "analyst_review").strip()
        if workflow_step:
            stage = workflow_step.stage

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
        db.session.commit()
        flash(_("Décision d'approbation enregistrée."), "success")
        return redirect(url_for("credit.approvals"))

    rows = CreditApproval.query.filter_by(tenant_id=g.tenant.id).order_by(CreditApproval.created_at.desc()).all()
    return render_template(
        "credit/approvals.html",
        tenant=g.tenant,
        approvals=rows,
        memos=memos,
        workflow_steps=workflow_steps,
        stage_options=_approval_stage_options(),
    )


@bp.route("/approval-workflow", methods=["GET", "POST"])
@login_required
def approval_workflow():
    _require_tenant()
    _seed_default_analyst_functions(g.tenant.id)
    _seed_default_approval_workflow(g.tenant.id)

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
