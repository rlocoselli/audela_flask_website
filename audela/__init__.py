from __future__ import annotations

import logging
import os
import sys
from urllib.parse import urlencode, urlsplit, urlunsplit

from flask import Flask
from flask import g, request, session, redirect
from flask import url_for
from jinja2 import ChoiceLoader, FileSystemLoader
from sqlalchemy import inspect, text

from .config import DevConfig, ProdConfig
from .extensions import csrf, db, login_manager, migrate, mail
from .models.core import User
from .i18n import DEFAULT_LANG, SUPPORTED_LANGS, TRANSLATIONS, best_lang_from_accept_language, normalize_lang, tr


def _configured_site_parts(app: Flask):
    site_url = str(app.config.get("SITE_URL") or "").strip().rstrip("/")
    if not site_url:
        return None

    parts = urlsplit(site_url)
    if not parts.scheme or not parts.netloc:
        return None
    return parts


def _canonical_request_url(app: Flask, include_query_params: list[str] | tuple[str, ...] | None = None) -> str:
    site_parts = _configured_site_parts(app)
    scheme = site_parts.scheme if site_parts else request.scheme
    netloc = site_parts.netloc if site_parts else request.host

    allowed_params = {str(key).strip() for key in (include_query_params or []) if str(key).strip()}
    query_items: list[tuple[str, str]] = []
    if allowed_params:
        for key in sorted(allowed_params):
            for value in request.args.getlist(key):
                if value:
                    query_items.append((key, value))

    query = urlencode(query_items, doseq=True)
    return urlunsplit((scheme, netloc, request.path or "/", query, ""))


def _is_flask_db_command() -> bool:
    """Return True when running a Flask-Migrate command via Flask CLI."""
    argv = [str(a).lower() for a in sys.argv]
    if not argv:
        return False

    executable = os.path.basename(argv[0])
    is_flask_cli = executable == "flask" or executable.startswith("flask")
    return is_flask_cli and "db" in argv[1:]


def _skip_startup_db_guards() -> bool:
    """Allow migration/maintenance commands to initialize the app without DB guard checks."""
    if _is_flask_db_command():
        return True
    return str(os.environ.get("SKIP_ALEMBIC_HEAD_CHECK", "")).lower() in {"1", "true", "yes", "on"}


def _configure_logging() -> None:
    level_name = os.environ.get("LOG_LEVEL", "INFO").upper()
    level = getattr(logging, level_name, logging.INFO)

    root_logger = logging.getLogger()
    if not root_logger.handlers:
        handler = logging.StreamHandler(sys.stdout)
        handler.setFormatter(
            logging.Formatter(
                "ts=%(asctime)s level=%(levelname)s logger=%(name)s msg=%(message)s"
            )
        )
        root_logger.addHandler(handler)
    root_logger.setLevel(level)


def _assert_required_schema_on_startup(app: Flask) -> None:
    """Fail fast in production when DB schema is behind code expectations."""
    if _skip_startup_db_guards():
        return

    if str(os.environ.get("FLASK_ENV", "development")).lower() != "production":
        return

    with app.app_context():
        engine = db.engine
        insp = inspect(engine)

        if not insp.has_table("data_sources"):
            raise RuntimeError(
                "Database schema check failed: missing table 'data_sources'. "
                "Run migrations before starting production: 'flask db upgrade'."
            )

        cols = {c.get("name") for c in insp.get_columns("data_sources")}
        required = {"id", "tenant_id", "type", "name", "created_at", "config_encrypted", "policy_json", "base_url", "method"}
        missing = sorted(str(c) for c in required if c not in cols)
        if missing:
            raise RuntimeError(
                "Database schema check failed for 'data_sources'. Missing columns: "
                + ", ".join(missing)
                + ". Run migrations before starting production: 'flask db upgrade'."
            )


def _assert_alembic_head_on_startup(app: Flask) -> None:
    """Fail fast in production when Alembic revision is not at head."""
    # Allow migration commands to run even when DB is currently behind head.
    if _skip_startup_db_guards():
        return

    if str(os.environ.get("FLASK_ENV", "development")).lower() != "production":
        return

    with app.app_context():
        engine = db.engine
        insp = inspect(engine)
        if not insp.has_table("alembic_version"):
            raise RuntimeError(
                "Database schema check failed: missing table 'alembic_version'. "
                "Run migrations before starting production: 'flask db upgrade'."
            )

        with engine.connect() as conn:
            rows = conn.execute(text("SELECT version_num FROM alembic_version")).fetchall()
        current_revisions = {str(row[0]) for row in rows if row and row[0]}
        if not current_revisions:
            raise RuntimeError(
                "Database schema check failed: 'alembic_version' is empty. "
                "Run migrations before starting production: 'flask db upgrade'."
            )

        try:
            from alembic.config import Config as AlembicConfig
            from alembic.script import ScriptDirectory

            project_root = os.path.abspath(os.path.join(app.root_path, os.pardir))
            alembic_ini = os.path.join(project_root, "migrations", "alembic.ini")
            cfg = AlembicConfig(alembic_ini)
            cfg.set_main_option("script_location", os.path.join(project_root, "migrations"))
            script = ScriptDirectory.from_config(cfg)
            head_revisions = set(script.get_heads())
        except Exception as exc:
            raise RuntimeError(
                "Unable to verify Alembic head revisions in production. "
                "Ensure migrations configuration is available and valid."
            ) from exc

        if current_revisions != head_revisions:
            raise RuntimeError(
                "Database schema is not at Alembic head. "
                f"Current revision(s): {sorted(current_revisions)}; "
                f"Head revision(s): {sorted(head_revisions)}. "
                "Run migrations before starting production: 'flask db upgrade'."
            )


def _seed_subscription_plans_on_startup(app: Flask) -> None:
    """Ensure default subscription plans exist and are normalized in production."""
    if _skip_startup_db_guards():
        return

    if str(os.environ.get("FLASK_ENV", "development")).lower() != "production":
        return

    with app.app_context():
        from .services.subscription_service import SubscriptionService

        SubscriptionService._ensure_default_plans_seeded()


def create_app() -> Flask:
    _configure_logging()

    # This repository keeps `templates/` and `static/` at the project root (sibling of the `audela/` package).
    # Using absolute paths avoids TemplateNotFound issues when the working directory changes (gunicorn, tests, etc.).
    package_dir = os.path.dirname(__file__)
    project_root = os.path.abspath(os.path.join(package_dir, ".."))
    template_dir = os.path.join(project_root, "templates")
    package_template_dir = os.path.join(package_dir, "templates")
    static_dir = os.path.join(project_root, "static")

    app = Flask(__name__, static_folder=static_dir, template_folder=template_dir)
    app.jinja_loader = ChoiceLoader(
        [
            FileSystemLoader(template_dir),
            FileSystemLoader(package_template_dir),
        ]
    )

    # Ensure instance folder exists (SQLite, uploads, etc.)
    try:
        os.makedirs(os.path.join(project_root, "instance"), exist_ok=True)
    except Exception:
        # If filesystem is read-only, the app can still run if DATABASE_URL points elsewhere.
        pass

    # Tenant file storage (uploads + cached URL/S3 files)
    app.config.setdefault(
        "TENANT_FILE_ROOT",
        os.environ.get("TENANT_FILE_ROOT", os.path.join(project_root, "instance", "tenant_files")),
    )
    # Default upload limit: 50 MB (can be overridden by env var MAX_CONTENT_LENGTH)
    try:
        app.config.setdefault(
            "MAX_CONTENT_LENGTH",
            int(os.environ.get("MAX_CONTENT_LENGTH", str(50 * 1024 * 1024))),
        )
    except Exception:
        pass

    env = os.environ.get("FLASK_ENV", "development").lower()
    app.config.from_object(DevConfig if env != "production" else ProdConfig)

    # Extensions
    db.init_app(app)
    migrate.init_app(app, db)
    login_manager.init_app(app)
    csrf.init_app(app)
    mail.init_app(app)

    _assert_alembic_head_on_startup(app)
    _assert_required_schema_on_startup(app)
    _seed_subscription_plans_on_startup(app)

    login_manager.login_view = "auth.login"

    # -----------------
    # i18n (dictionary-based)
    # -----------------
    @app.before_request
    def _set_language() -> None:  # noqa: ANN001
        # Order: explicit session -> browser header -> default
        sess_lang = normalize_lang(session.get("lang")) if session.get("lang") else None
        g.lang = sess_lang or best_lang_from_accept_language(request.headers.get("Accept-Language"))

    @app.before_request
    def _redirect_public_canonical_host():  # noqa: ANN001
        if request.method not in {"GET", "HEAD"}:
            return None
        if str(os.environ.get("FLASK_ENV", "development")).lower() != "production":
            return None
        if request.blueprint != "public":
            return None

        site_parts = _configured_site_parts(app)
        if not site_parts:
            return None

        current_scheme = request.headers.get("X-Forwarded-Proto", request.scheme).split(",", 1)[0].strip().lower()
        current_netloc = request.host.lower()
        target_netloc = site_parts.netloc.lower()
        if current_scheme == site_parts.scheme.lower() and current_netloc == target_netloc:
            return None

        return redirect(
            urlunsplit(
                (
                    site_parts.scheme,
                    site_parts.netloc,
                    request.path or "/",
                    request.query_string.decode("utf-8") if request.query_string else "",
                    "",
                )
            ),
            code=301,
        )

    @app.context_processor
    def _inject_i18n() -> dict:  # noqa: ANN001
        def _(msgid: str, **kwargs):
            return tr(msgid, getattr(g, "lang", DEFAULT_LANG), **kwargs)

        _lang = getattr(g, "lang", DEFAULT_LANG)
        _merged = {}
        # JS translations baseline: use English first so missing keys do not
        # unexpectedly display Portuguese when UI language is English.
        _merged.update(TRANSLATIONS.get("en", {}))
        _merged.update(TRANSLATIONS.get(_lang, {}))
        if _lang == "pt":
            _merged.update(TRANSLATIONS.get("pt", {}))

        app_release = str(app.config.get("APP_RELEASE", "dev"))
        site_parts = _configured_site_parts(app)

        def static_asset_url(filename: str) -> str:
            return url_for("static", filename=filename, v=app_release)

        def canonical_url(include_query_params: list[str] | tuple[str, ...] | None = None) -> str:
            return _canonical_request_url(app, include_query_params=include_query_params)

        site_root_url = urlunsplit(
            (
                site_parts.scheme,
                site_parts.netloc,
                "/",
                "",
                "",
            )
        ) if site_parts else request.url_root

        return {
            "_": _,
            "current_lang": _lang,
            "supported_langs": SUPPORTED_LANGS,
            "lang_label": lambda code: SUPPORTED_LANGS.get(code, SUPPORTED_LANGS[DEFAULT_LANG]).label,
            "request": request,
            "i18n_strings": _merged,
            "tenant": getattr(g, "tenant", None),
            "app_release": app_release,
            "static_asset_url": static_asset_url,
            "canonical_url": canonical_url,
            "site_root_url": site_root_url,

        }

    @app.after_request
    def _set_release_header(response):  # noqa: ANN001
        response.headers.setdefault("X-App-Release", str(app.config.get("APP_RELEASE", "dev")))
        return response


    @login_manager.user_loader
    def load_user(user_id: str):
        try:
            return User.query.get(int(user_id))
        except Exception:
            return None

    # Blueprints
    from .blueprints.public import bp as public_bp
    from .blueprints.auth import bp as auth_bp
    from .blueprints.portal import bp as portal_bp
    from .blueprints.etl import bp as etl_bp
    from .blueprints.finance import bp as finance_bp
    from .blueprints.project import bp as project_bp
    from .blueprints.credit import bp as credit_bp
    from .blueprints.ifrs9 import bp as ifrs9_bp
    from .blueprints.finance.finance_master_data import finance_master_bp
    from .blueprints.tenant import bp as tenant_bp
    from .blueprints.billing import bp as billing_bp
    from .blueprints.admin import bp as admin_bp

    app.register_blueprint(public_bp)
    app.register_blueprint(auth_bp)
    app.register_blueprint(portal_bp)
    app.register_blueprint(etl_bp)
    app.register_blueprint(finance_bp)
    app.register_blueprint(project_bp)
    app.register_blueprint(credit_bp)
    app.register_blueprint(ifrs9_bp)
    app.register_blueprint(finance_master_bp)
    app.register_blueprint(tenant_bp)
    app.register_blueprint(billing_bp)
    app.register_blueprint(admin_bp)

    # Legacy compatibility: previous links may still use /portal/*.
    @app.route("/portal", methods=["GET"])
    def _legacy_portal_root_redirect():  # noqa: ANN001
        return redirect("/app", code=302)

    @app.route("/portal/<path:subpath>", methods=["GET"])
    def _legacy_portal_redirect(subpath: str):  # noqa: ANN001
        qs = request.query_string.decode("utf-8") if request.query_string else ""
        target = f"/app/{subpath}"
        if qs:
            target = f"{target}?{qs}"
        return redirect(target, code=302)

    # Finance CLI Commands
    from .commands import init_finance_cli, init_celery_cli, init_admin_cli
    init_finance_cli(app)
    init_celery_cli(app)
    init_admin_cli(app)

    # Finance Auto-balance Updates (SQLAlchemy Event Listeners)
    from .services.bank_configuration_service import initialize_balance_updates
    with app.app_context():
        initialize_balance_updates()
    # DEV: ensure core tables exist (use Alembic migrations in production)
    if app.config.get("AUTO_CREATE_DB", False):
        with app.app_context():
            db.create_all()

            # SQLite dev convenience: add new columns without requiring a manual DB reset.
            # (In production, use Alembic migrations.)
            try:
                from sqlalchemy import text

                uri = str(app.config.get("SQLALCHEMY_DATABASE_URI") or "")
                if uri.startswith("sqlite"):
                    engine = db.get_engine()
                    with engine.begin() as conn:
                        cols = [
                            row[1]
                            for row in conn.execute(text("PRAGMA table_info(finance_transactions);"))
                        ]
                        if "gl_account_id" not in cols:
                            conn.execute(text("ALTER TABLE finance_transactions ADD COLUMN gl_account_id INTEGER"))
                            conn.execute(
                                text(
                                    "CREATE INDEX IF NOT EXISTS ix_finance_transactions_gl_account_id ON finance_transactions (gl_account_id)"
                                )
                            )

                        gl_cols = [
                            row[1]
                            for row in conn.execute(text("PRAGMA table_info(finance_gl_accounts);"))
                        ]
                        if "parent_id" not in gl_cols:
                            conn.execute(text("ALTER TABLE finance_gl_accounts ADD COLUMN parent_id INTEGER"))
                            conn.execute(
                                text(
                                    "CREATE INDEX IF NOT EXISTS ix_finance_gl_accounts_parent_id ON finance_gl_accounts (parent_id)"
                                )
                            )
                        if "sort_order" not in gl_cols:
                            conn.execute(text("ALTER TABLE finance_gl_accounts ADD COLUMN sort_order INTEGER DEFAULT 0"))
                            conn.execute(
                                text(
                                    "CREATE INDEX IF NOT EXISTS ix_finance_gl_accounts_sort_order ON finance_gl_accounts (sort_order)"
                                )
                            )
            except Exception:
                # Best effort only; schema issues will surface in logs/errors.
                pass

    return app
