import os
from urllib.parse import quote_plus

def _sqlite_db_uri(db_filename: str = "audela.db") -> str:
    """Return a SQLite URI that points to a writable location.

    We deliberately avoid placing the DB next to the source code because many
    deployments mount the code directory read-only (Docker images, PaaS builds,
    etc.). Using an "instance" directory also prevents the common
    "attempt to write a readonly database" SQLite error.
    """
    project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), os.pardir))
    instance_dir = os.path.join(project_root, "instance")
    os.makedirs(instance_dir, exist_ok=True)
    db_path = os.path.join(instance_dir, db_filename)
    # SQLAlchemy expects forward slashes in SQLite URIs.
    db_path = db_path.replace("\\", "/")
    return f"sqlite:///{db_path}"

class Config:
    SECRET_KEY = os.environ.get("SECRET_KEY", "dev-secret-change-me")
    SITE_URL = os.environ.get("SITE_URL", "https://www.audeladedonnees.fr").rstrip("/")
    BRIDGE_CALLBACK_URL = os.environ.get("BRIDGE_CALLBACK_URL", "").strip()

    if os.environ.get("DATABASE_URL"):
        SQLALCHEMY_DATABASE_URI = os.environ["DATABASE_URL"]
    else:
        db_host = os.environ.get("APP_HOST")
        db_user = os.environ.get("APP_USER")
        db_password = os.environ.get("APP_PASSWORD")
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
            SQLALCHEMY_DATABASE_URI = _sqlite_db_uri("audela.db")
            
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

    # Celery (shared async job module)
    CELERY_BROKER_URL = os.environ.get("CELERY_BROKER_URL", REDIS_URL)
    CELERY_RESULT_BACKEND = os.environ.get("CELERY_RESULT_BACKEND", CELERY_BROKER_URL)
    CELERY_DEFAULT_QUEUE = os.environ.get("CELERY_DEFAULT_QUEUE", "default")
    CELERY_TIMEZONE = os.environ.get("CELERY_TIMEZONE", "UTC")
    CELERY_ENABLE_UTC = os.environ.get("CELERY_ENABLE_UTC", "true").lower() == "true"
    CELERY_TASK_IGNORE_RESULT = os.environ.get("CELERY_TASK_IGNORE_RESULT", "false").lower() == "true"
    CELERY_BEAT_SCHEDULE = {}

    # Project notifications job
    PROJECT_NOTIFICATIONS_ENABLED = os.environ.get("PROJECT_NOTIFICATIONS_ENABLED", "true").lower() == "true"
    PROJECT_NOTIFICATIONS_SCAN_MINUTES = int(os.environ.get("PROJECT_NOTIFICATIONS_SCAN_MINUTES", "5"))
    PROJECT_NOTIFICATIONS_COOLDOWN_MINUTES = int(os.environ.get("PROJECT_NOTIFICATIONS_COOLDOWN_MINUTES", "120"))

    # ETL jobs scheduler
    ETL_JOBS_ENABLED = os.environ.get("ETL_JOBS_ENABLED", "true").lower() == "true"
    ETL_JOBS_SCAN_MINUTES = int(os.environ.get("ETL_JOBS_SCAN_MINUTES", "1"))

    # Dev convenience: auto-create tables when using SQLite and no migrations yet.
    # In production you should run Alembic migrations instead.
    AUTO_CREATE_DB = os.environ.get("AUTO_CREATE_DB", "true").lower() == "true"

    # -----------------
    # Optional integrations (read from env)
    # -----------------
    # Bank statement parsing
    MINDEE_API_KEY = os.environ.get("MINDEE_API_KEY", "")
    GOOGLE_VISION_API_KEY = os.environ.get("GOOGLE_VISION_API_KEY", "")
    STATEMENT_PARSER_ENDPOINT = os.environ.get("STATEMENT_PARSER_ENDPOINT", "")
    STATEMENT_PARSER_API_KEY = os.environ.get("STATEMENT_PARSER_API_KEY", "")

    # OpenAI (used by BI/NLQ + optional statement import)
    OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY", "")
    OPENAI_MODEL = os.environ.get("OPENAI_MODEL", "")
    OPENAI_BASE_URL = os.environ.get("OPENAI_BASE_URL", "")

    # SMTP / Email (used by Flask-Mail and ETL notifications)
    MAIL_SERVER = os.environ.get("MAIL_SERVER", "")
    MAIL_PORT = int(os.environ.get("MAIL_PORT", "587"))
    MAIL_USE_TLS = os.environ.get("MAIL_USE_TLS", "true").lower() == "true"
    MAIL_USE_SSL = os.environ.get("MAIL_USE_SSL", "false").lower() == "true"
    MAIL_USERNAME = os.environ.get("MAIL_USERNAME", "")
    MAIL_PASSWORD = os.environ.get("MAIL_PASSWORD", "")
    MAIL_DEFAULT_SENDER = os.environ.get("MAIL_DEFAULT_SENDER", "noreply@audela.com")
    MAIL_SUPPRESS_SEND = os.environ.get("MAIL_SUPPRESS_SEND", "false").lower() == "true"
    MAIL_DEV_MODE = os.environ.get("MAIL_DEV_MODE", "false").lower() == "true"


class DevConfig(Config):
    DEBUG = True
    # Local dev convenience: avoid SMTP dependency and still validate mail flows.
    MAIL_SUPPRESS_SEND = os.environ.get("MAIL_SUPPRESS_SEND", "true").lower() == "true"
    MAIL_DEV_MODE = os.environ.get("MAIL_DEV_MODE", "true").lower() == "true"


class ProdConfig(Config):
    DEBUG = False
    MAIL_SUPPRESS_SEND = os.environ.get("MAIL_SUPPRESS_SEND", "false").lower() == "true"
    MAIL_DEV_MODE = os.environ.get("MAIL_DEV_MODE", "false").lower() == "true"
    SESSION_COOKIE_SAMESITE = "Lax"
    # Enable in production behind TLS
    SESSION_COOKIE_SECURE = os.environ.get("COOKIE_SECURE", "0") == "1"

    # Simple rate limit placeholder (implement with Flask-Limiter later)
    RATELIMIT_DEFAULT = os.environ.get("RATELIMIT_DEFAULT", "200/hour")
