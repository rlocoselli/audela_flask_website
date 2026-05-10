#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

if [[ -x "$ROOT_DIR/.venv/bin/jupyter" ]]; then
  JUPYTER_BIN="$ROOT_DIR/.venv/bin/jupyter"
elif command -v jupyter >/dev/null 2>&1; then
  JUPYTER_BIN="$(command -v jupyter)"
else
  echo "jupyter executable not found. Install with: pip install jupyterlab" >&2
  exit 1
fi

export AUDELA_ORIGIN="${AUDELA_ORIGIN:-http://127.0.0.1:5000}"
export JUPYTER_PORT="${JUPYTER_PORT:-8888}"
export JUPYTER_REQUIRE_TOKEN="${JUPYTER_REQUIRE_TOKEN:-0}"

if [[ -z "${AUDELA_TENANT_ID:-}" ]]; then
  echo "AUDELA_TENANT_ID is required for strict tenant isolation." >&2
  echo "Example: AUDELA_TENANT_ID=12 ./scripts/start_jupyter_embed.sh" >&2
  exit 1
fi

DEFAULT_ROOT="$ROOT_DIR/instance/tenant_files/${AUDELA_TENANT_ID}/projects"
export AUDELA_NOTEBOOK_ROOT="${AUDELA_NOTEBOOK_ROOT:-$DEFAULT_ROOT}"
mkdir -p "$AUDELA_NOTEBOOK_ROOT"

echo "Starting Jupyter Lab for embedding in AUDELA_ORIGIN=$AUDELA_ORIGIN"
echo "Token prompt disabled by default for local embedding (set JUPYTER_REQUIRE_TOKEN=1 to enable)."
echo "Jupyter root dir: $AUDELA_NOTEBOOK_ROOT"
echo "Use this in .env: JUPYTER_EMBED_URL=http://127.0.0.1:${JUPYTER_PORT}/lab"

exec "$JUPYTER_BIN" lab --config "$ROOT_DIR/scripts/jupyter_embed_config.py" --ServerApp.root_dir="$AUDELA_NOTEBOOK_ROOT"
