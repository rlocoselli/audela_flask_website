from datetime import date, datetime

from flask import redirect, render_template, request, session, url_for, flash
from flask_login import current_user

from ...extensions import db
from ...models import Prospect
from ...models import Tenant
from ...services.subscription_service import SubscriptionService

from ...i18n import DEFAULT_LANG, SUPPORTED_LANGS, normalize_lang

from . import bp


@bp.route("/")
def index():
    return render_template("index.html")


@bp.route("/demo/request", methods=["POST"])
def request_demo():
    full_name = (request.form.get("full_name") or "").strip()
    email = (request.form.get("email") or "").strip().lower()
    phone = (request.form.get("phone") or "").strip()
    company = (request.form.get("company") or "").strip()
    solution_interest = (request.form.get("solution_interest") or "").strip()
    message = (request.form.get("message") or "").strip()
    rdv_date_raw = (request.form.get("rdv_date") or "").strip()
    rdv_time_raw = (request.form.get("rdv_time") or "").strip()
    timezone = (request.form.get("timezone") or "Europe/Paris").strip() or "Europe/Paris"

    if not full_name or not email or not rdv_date_raw or not rdv_time_raw:
        flash("Veuillez renseigner nom, email, date et horaire du RDV.", "error")
        return redirect(url_for("public.index") + "#five")

    try:
        rdv_date = datetime.strptime(rdv_date_raw, "%Y-%m-%d").date()
        rdv_time = datetime.strptime(rdv_time_raw, "%H:%M").time()
    except ValueError:
        flash("Format de date/heure invalide.", "error")
        return redirect(url_for("public.index") + "#five")

    if rdv_date < date.today():
        flash("La date de RDV doit être aujourd'hui ou future.", "error")
        return redirect(url_for("public.index") + "#five")

    prospect = Prospect(
        full_name=full_name,
        email=email,
        phone=phone,
        company=company,
        solution_interest=solution_interest,
        message=message,
        rdv_date=rdv_date,
        rdv_time=rdv_time,
        timezone=timezone,
        status="new",
    )
    db.session.add(prospect)
    db.session.commit()

    flash("Merci. Votre demande de démonstration a bien été enregistrée.", "success")
    return redirect(url_for("public.index") + "#five")


@bp.route("/lang/<lang_code>")
def set_language(lang_code: str):
    """Set UI language and redirect back."""
    lang = normalize_lang(lang_code)
    if lang not in SUPPORTED_LANGS:
        lang = DEFAULT_LANG
    session["lang"] = lang

    nxt = request.args.get("next") or request.referrer or url_for("public.index")
    return redirect(nxt)


@bp.route("/projets/mobile")
def projects_mobile():
    return render_template("projects_mobile.html")


@bp.route("/projets/iot")
def projects_iot():
    return render_template("projects_iot.html")


@bp.route("/projets/belegal")
def belegal():
    return render_template("belegal.html")


@bp.route("/projets/gestion-projet")
def projects_management():
    return render_template("projects_management.html")


@bp.route("/bi/metabase")
def metabase():
    return render_template("metabase.html")


@bp.route("/plans")
def plans():
    plans = SubscriptionService.get_available_plans(include_internal=False)
    selected_product = (request.args.get("product") or "").strip().lower()

    def _has_project(plan) -> bool:
        features = plan.features_json if isinstance(plan.features_json, dict) else {}
        return bool(features.get("has_project", False))

    if selected_product == "finance":
        plans = [plan for plan in plans if plan.has_finance]
    elif selected_product == "bi":
        plans = [plan for plan in plans if plan.has_bi]
    elif selected_product == "project":
        plans = [plan for plan in plans if _has_project(plan)]
    else:
        selected_product = None

    current_plan = None
    if current_user.is_authenticated:
        tenant = Tenant.query.get(current_user.tenant_id)
        if tenant and tenant.subscription:
            current_plan = tenant.subscription.plan

    return render_template(
        "plans.html",
        plans=plans,
        current_plan=current_plan,
        selected_product=selected_product,
    )


# -----------------
# Legal pages
# -----------------


@bp.route("/legal/terms")
def legal_terms():
    return render_template("legal/terms.html")


@bp.route("/legal/privacy")
def legal_privacy():
    return render_template("legal/privacy.html")


@bp.route("/legal/cookies")
def legal_cookies():
    return render_template("legal/cookies.html")


@bp.route("/legal/retention")
def legal_retention():
    return render_template("legal/retention.html")


@bp.route("/legal/notice")
def legal_notice():
    return render_template("legal/notice.html")


@bp.route("/left-sidebar")
def left_sidebar():
    return render_template("left-sidebar.html")


@bp.route("/right-sidebar")
def right_sidebar():
    return render_template("right-sidebar.html")


@bp.route("/no-sidebar")
def no_sidebar():
    return render_template("no-sidebar.html")


@bp.route("/elements")
def elements():
    return render_template("elements.html")
