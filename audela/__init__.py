from __future__ import annotations

import os

from flask import Flask

from .config import DevConfig, ProdConfig
from .extensions import csrf, db, login_manager, migrate
from .models.core import User


def create_app() -> Flask:
    # This repository keeps `templates/` and `static/` at the project root (sibling of the `audela/` package).
    # Using absolute paths avoids TemplateNotFound issues when the working directory changes (gunicorn, tests, etc.).
    package_dir = os.path.dirname(__file__)
    project_root = os.path.abspath(os.path.join(package_dir, ".."))
    template_dir = os.path.join(project_root, "templates")
    static_dir = os.path.join(project_root, "static")

    app = Flask(__name__, static_folder=static_dir, template_folder=template_dir)

    env = os.environ.get("FLASK_ENV", "development").lower()
    app.config.from_object(DevConfig if env != "production" else ProdConfig)

    # Extensions
    db.init_app(app)
    migrate.init_app(app, db)
    login_manager.init_app(app)
    csrf.init_app(app)

    login_manager.login_view = "auth.login"

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

    app.register_blueprint(public_bp)
    app.register_blueprint(auth_bp)
    app.register_blueprint(portal_bp)

    # DEV: ensure core tables exist (use Alembic migrations in production)
    if app.config.get("AUTO_CREATE_DB", False):
        with app.app_context():
            db.create_all()

    return app
