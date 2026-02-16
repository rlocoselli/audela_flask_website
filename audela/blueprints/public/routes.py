from flask import redirect, render_template, request, session, url_for

from ...i18n import DEFAULT_LANG, SUPPORTED_LANGS, normalize_lang

from . import bp


@bp.route("/")
def index():
    return render_template("index.html")


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


@bp.route("/bi/metabase")
def metabase():
    return render_template("metabase.html")


@bp.route("/plans")
def plans():
    return render_template("plans.html")


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
