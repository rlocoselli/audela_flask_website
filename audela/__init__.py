from __future__ import annotations

import os

from flask import Flask
from flask import g, request, session

from .config import DevConfig, ProdConfig
from .extensions import csrf, db, login_manager, migrate
from .models.core import User
from .i18n import DEFAULT_LANG, SUPPORTED_LANGS, TRANSLATIONS, best_lang_from_accept_language, normalize_lang, tr


def create_app() -> Flask:
    # This repository keeps `templates/` and `static/` at the project root (sibling of the `audela/` package).
    # Using absolute paths avoids TemplateNotFound issues when the working directory changes (gunicorn, tests, etc.).
    package_dir = os.path.dirname(__file__)
    project_root = os.path.abspath(os.path.join(package_dir, ".."))
    template_dir = os.path.join(project_root, "templates")
    static_dir = os.path.join(project_root, "static")

    app = Flask(__name__, static_folder=static_dir, template_folder=template_dir)

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

    app.register_blueprint(public_bp)
    app.register_blueprint(auth_bp)
    app.register_blueprint(portal_bp)
    app.register_blueprint(etl_bp)
    app.register_blueprint(finance_bp)
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
            except Exception:
                # Best effort only; schema issues will surface in logs/errors.
                pass

    return app
