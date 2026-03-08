#!/usr/bin/env bash
set -euo pipefail

# Safe local migration helper.
# It handles the common local SQLite case where alembic_version exists but is empty,
# causing Alembic to replay init migrations against an already-populated schema.

APP_MODULE="${APP_MODULE:-app}"
PY_BIN="${PY_BIN:-}"
FALLBACK_STAMP_REV="${FALLBACK_STAMP_REV:-20260307_ensure_data_sources_columns}"

if [[ -z "$PY_BIN" ]]; then
  if [[ -x ".venv/bin/python" ]]; then
    PY_BIN=".venv/bin/python"
  elif command -v python3 >/dev/null 2>&1; then
    PY_BIN="$(command -v python3)"
  else
    echo "ERROR: python interpreter not found (.venv/bin/python or python3)."
    exit 1
  fi
fi

run_flask_db() {
  "$PY_BIN" -m flask --app "$APP_MODULE" db "$@"
}

echo "==> Using Python: $PY_BIN"
echo "==> Flask app module: $APP_MODULE"

# First try a normal upgrade.
set +e
OUT="$(run_flask_db upgrade 2>&1)"
RC=$?
set -e

if [[ $RC -eq 0 ]]; then
  echo "$OUT"
  echo "==> Migration upgrade succeeded"
  exit 0
fi

echo "$OUT"

echo "==> Normal upgrade failed, checking known local misalignment pattern..."

if grep -qi "table roles already exists" <<<"$OUT"; then
  echo "==> Detected init replay conflict on existing schema"
  echo "==> Applying safe fallback stamp: $FALLBACK_STAMP_REV"
  run_flask_db stamp "$FALLBACK_STAMP_REV"
  echo "==> Re-running upgrade"
  run_flask_db upgrade
  echo "==> Final migration state"
  run_flask_db current
  echo "==> Safe migration completed"
  exit 0
fi

echo "ERROR: migration failed with an unknown pattern."
echo "Run manually: $PY_BIN -m flask --app $APP_MODULE db current"
exit 1
