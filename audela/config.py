import os
from urllib.parse import quote_plus

class Config:
    SECRET_KEY = os.environ.get("SECRET_KEY", "dev-secret-change-me")

    if os.environ.get("DATABASE_URL"):
        SQLALCHEMY_DATABASE_URI = os.environ["DATABASE_URL"]
    else:
        db_host = os.environ.get("HOST")
        db_user = os.environ.get("USER")
        db_password = os.environ.get("PASSWORD")
        db_name = os.environ.get("DB_NAME", "audela")
        db_port = os.environ.get("DB_PORT", "5432")

        if all([db_host, db_user, db_password]):
            SQLALCHEMY_DATABASE_URI = (
                "postgresql+psycopg2://"
                f"{quote_plus(db_user)}:{quote_plus(db_password)}"
                f"@{db_host}:{db_port}/{quote_plus(db_name)}"
            )
        else:
            # local dev fallback
            SQLALCHEMY_DATABASE_URI = "sqlite:///audela.db"    
            
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    # Security / session
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = "Lax"
    # Set True behind HTTPS
    SESSION_COOKIE_SECURE = os.environ.get("SESSION_COOKIE_SECURE", "false").lower() == "true"

    # Multi-tenancy (Model 1 default)
    TENANCY_MODEL = os.environ.get("TENANCY_MODEL", "shared_db_tenant_id")
    # How we resolve the current tenant in Model 1:
    # - "path": /t/<tenant_slug>/... (recommended for simplicity)
    # - "subdomain": <tenant>.yourdomain.com
    TENANT_RESOLUTION = os.environ.get("TENANT_RESOLUTION", "path")

    # BI runtime limits (MVP defaults)
    QUERY_TIMEOUT_SECONDS = int(os.environ.get("QUERY_TIMEOUT_SECONDS", "30"))
    QUERY_MAX_ROWS = int(os.environ.get("QUERY_MAX_ROWS", "5000"))

    # Result cache
    REDIS_URL = os.environ.get("REDIS_URL", "redis://localhost:6379/0")
    CACHE_TTL_SECONDS = int(os.environ.get("CACHE_TTL_SECONDS", "300"))

    # Dev convenience: auto-create tables when using SQLite and no migrations yet.
    # In production you should run Alembic migrations instead.
    AUTO_CREATE_DB = os.environ.get("AUTO_CREATE_DB", "true").lower() == "true"


class DevConfig(Config):
    DEBUG = True


class ProdConfig(Config):
    DEBUG = False
    SESSION_COOKIE_SAMESITE = "Lax"
    # Enable in production behind TLS
    SESSION_COOKIE_SECURE = os.environ.get("COOKIE_SECURE", "0") == "1"

    # Simple rate limit placeholder (implement with Flask-Limiter later)
    RATELIMIT_DEFAULT = os.environ.get("RATELIMIT_DEFAULT", "200/hour")
