from __future__ import annotations

import logging
import os
import sys

from flask import Flask
from flask import g, request, session, redirect
from jinja2 import ChoiceLoader, FileSystemLoader
from sqlalchemy import inspect

from .config import DevConfig, ProdConfig
from .extensions import csrf, db, login_manager, migrate, mail
from .models.core import User
from .i18n import DEFAULT_LANG, SUPPORTED_LANGS, TRANSLATIONS, best_lang_from_accept_language, normalize_lang, tr


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

    _assert_required_schema_on_startup(app)

    login_manager.login_view = "auth.login"

    # -----------------
    # i18n (dictionary-based)
    # -----------------
    @app.before_request
    def _set_language() -> None:  # noqa: ANN001
        # Order: explicit session -> browser header -> default
        sess_lang = normalize_lang(session.get("lang")) if session.get("lang") else None
        g.lang = sess_lang or best_lang_from_accept_language(request.headers.get("Accept-Language"))

    @app.context_processor
    def _inject_i18n() -> dict:  # noqa: ANN001
        def _(msgid: str, **kwargs):
            return tr(msgid, getattr(g, "lang", DEFAULT_LANG), **kwargs)

        _lang = getattr(g, "lang", DEFAULT_LANG)
        _merged = {}
        # JS translations: include fallbacks to reduce mixed-language UI
        _merged.update(TRANSLATIONS.get("pt", {}))
        _merged.update(TRANSLATIONS.get("en", {}))
        _merged.update(TRANSLATIONS.get(_lang, {}))

        return {
            "_": _,
            "current_lang": _lang,
            "supported_langs": SUPPORTED_LANGS,
            "lang_label": lambda code: SUPPORTED_LANGS.get(code, SUPPORTED_LANGS[DEFAULT_LANG]).label,
            "request": request,
            "i18n_strings": _merged,
            "tenant": getattr(g, "tenant", None),

        }


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
