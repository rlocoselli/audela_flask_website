#!/usr/bin/env sh
set -e

: "${FLASK_APP:=app.py}"
: "${GUNICORN_BIND:=0.0.0.0:8000}"
: "${WEB_CONCURRENCY:=3}"
: "${GUNICORN_THREADS:=4}"
: "${GUNICORN_TIMEOUT:=120}"

# Optional: wait for Postgres if DATABASE_URL points to it
if [ -n "${DATABASE_URL:-}" ]; then
  python - <<'PY'
import os, time, socket
from urllib.parse import urlparse

url = os.environ.get("DATABASE_URL", "")
u = urlparse(url)
if u.scheme.startswith("postgres") and u.hostname:
    host = u.hostname
    port = u.port or 5432
    timeout = int(os.environ.get("DB_WAIT_TIMEOUT", "60"))
    deadline = time.time() + timeout
    while True:
        try:
            with socket.create_connection((host, port), timeout=2):
                print(f"DB reachable at {host}:{port}")
                break
        except OSError:
            if time.time() >= deadline:
                print(f"DB not reachable after {timeout}s: {host}:{port}")
                break
            time.sleep(1)
PY
fi

# Run migrations if requested (best effort)
if [ "${RUN_MIGRATIONS:-1}" != "0" ]; then
  (flask --app app db upgrade) || echo "[WARN] Alembic upgrade failed (AUTO_CREATE_DB may still create tables)."
fi

exec gunicorn \
  -b "$GUNICORN_BIND" \
  --workers "$WEB_CONCURRENCY" \
  --threads "$GUNICORN_THREADS" \
  --timeout "$GUNICORN_TIMEOUT" \
  app:app
