#!/usr/bin/env bash
set -euo pipefail

# =============================================================================
# Docker deploy installer (used by GitHub Actions)
# =============================================================================
# Calling convention kept compatible with the legacy deploy:
#   ./install.sh HOST USER PASSWORD OPENAI_API_KEY [DB_NAME] [DB_PORT] [DATABASE_URL]
#
# Notes:
# - HOST/USER/PASSWORD/DB_* are treated as DB connection inputs (same as before).
# - If HOST is "localhost" or "127.0.0.1", the app container will connect to the
#   server's host using "host.docker.internal" (mapped to host-gateway).
# - If DATABASE_URL is provided, it wins.
# - This script stops nginx (to free ports 80/443) and disables the legacy
#   systemd service if present.
# =============================================================================

# ---- Site/domain defaults (same spirit as legacy install.sh) ----
DOMAIN="audeladedonnees.fr"
WWW_DOMAIN="www.audeladedonnees.fr"
EMAIL="admin@audeladedonnees.fr"

APP_DIR="/root/audela_flask_website"

DB_HOST_ARG="${1:-}"
DB_USER_ARG="${2:-}"
DB_PASSWORD_ARG="${3:-}"
OPENAI_API_KEY_ARG="${4:-}"
DB_NAME_ARG="${5:-audela}"
DB_PORT_ARG="${6:-5432}"
DATABASE_URL_ARG="${7:-}"

if [[ -z "${DB_HOST_ARG}" || -z "${DB_USER_ARG}" || -z "${DB_PASSWORD_ARG}" ]]; then
  echo "❌ Missing required args. Usage: ./install.sh HOST USER PASSWORD OPENAI_API_KEY [DB_NAME] [DB_PORT] [DATABASE_URL]"
  exit 1
fi

APP_HOSTNAME="${DOMAIN}"
APP_HOSTNAME_WWW="${WWW_DOMAIN}"
GRAFANA_HOSTNAME="grafana.${DOMAIN}"

need_cmd() { command -v "$1" >/dev/null 2>&1; }

rand_hex_64() {
  if need_cmd openssl; then
    openssl rand -hex 32
  else
    python3 - <<'PY'
import secrets
print(secrets.token_hex(32))
PY
  fi
}

install_docker_if_needed() {
  if need_cmd docker && docker compose version >/dev/null 2>&1; then
    echo "✅ Docker + docker compose already installed"
    return
  fi

  echo "🧩 Installing Docker Engine + docker compose plugin"
  apt-get update
  apt-get install -y ca-certificates curl gnupg lsb-release
  install -m 0755 -d /etc/apt/keyrings

  OS_ID="$(. /etc/os-release && echo "$ID")"
  OS_CODENAME="$(. /etc/os-release && echo "$VERSION_CODENAME")"

  # Docker official repo (Ubuntu/Debian supported)
  curl -fsSL "https://download.docker.com/linux/${OS_ID}/gpg" | gpg --dearmor -o /etc/apt/keyrings/docker.gpg
  chmod a+r /etc/apt/keyrings/docker.gpg

  echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] https://download.docker.com/linux/${OS_ID} ${OS_CODENAME} stable"     > /etc/apt/sources.list.d/docker.list

  apt-get update
  apt-get install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin

  systemctl enable docker
  systemctl restart docker
  docker compose version
  echo "✅ Docker installed"
}

free_ports_80_443() {
  # stop nginx if installed, because Traefik binds 80/443
  if systemctl list-unit-files | grep -q '^nginx\.service'; then
    echo "🧹 Stopping/disabling nginx (free 80/443)"
    systemctl stop nginx || true
    systemctl disable nginx || true
  fi

  # stop legacy systemd unit if present
  if systemctl list-unit-files | grep -q '^audela_flask_website\.service'; then
    echo "🧹 Stopping/disabling legacy audela_flask_website systemd service"
    systemctl stop audela_flask_website || true
    systemctl disable audela_flask_website || true
  fi
}

ensure_env_file() {
  cd "${APP_DIR}"

  local env_file="${APP_DIR}/.env"
  local secret_key=""
  local data_key=""

  if [[ -f "${env_file}" ]]; then
    secret_key="$(grep -E '^SECRET_KEY=' "${env_file}" | tail -n1 | cut -d= -f2- || true)"
    data_key="$(grep -E '^DATA_KEY=' "${env_file}" | tail -n1 | cut -d= -f2- || true)"
  fi

  if [[ -z "${secret_key}" ]]; then secret_key="$(rand_hex_64)"; fi
  if [[ -z "${data_key}" ]]; then data_key="$(rand_hex_64)"; fi

  # DB host special-case: if user passed localhost/127.0.0.1, connect to the host from container.
  local db_host_effective="${DB_HOST_ARG}"
  if [[ "${DB_HOST_ARG}" == "localhost" || "${DB_HOST_ARG}" == "127.0.0.1" || "${DB_HOST_ARG}" == "::1" ]]; then
    db_host_effective="host.docker.internal"
  fi

  # Prefer explicit DATABASE_URL when provided
  local database_url_effective="${DATABASE_URL_ARG}"
  if [[ -z "${database_url_effective}" ]]; then
    # Compose a postgres URL like the legacy config would
    database_url_effective="postgresql+psycopg2://${DB_USER_ARG}:${DB_PASSWORD_ARG}@${db_host_effective}:${DB_PORT_ARG}/${DB_NAME_ARG}"
  fi

  echo "🔐 Writing .env for docker compose"
  umask 077
  cat > "${env_file}" <<EOF
# --- Routing ---
APP_HOSTNAME=${APP_HOSTNAME}
APP_HOSTNAME_WWW=${APP_HOSTNAME_WWW}
GRAFANA_HOSTNAME=${GRAFANA_HOSTNAME}

# --- App secrets ---
SECRET_KEY=${secret_key}
DATA_KEY=${data_key}

# --- App config ---
OPENAI_API_KEY=${OPENAI_API_KEY_ARG}
DATABASE_URL=${database_url_effective}
APP_HOST=${db_host_effective}
APP_USER=${DB_USER_ARG}
APP_PASSWORD=${DB_PASSWORD_ARG}
DB_NAME=${DB_NAME_ARG}
DB_PORT=${DB_PORT_ARG}
REDIS_URL=redis://redis:6379/0

# --- Internal Postgres (still started for persistence/monitoring; app may point to external DB) ---
POSTGRES_DB=${DB_NAME_ARG}
POSTGRES_USER=${DB_USER_ARG}
POSTGRES_PASSWORD=${DB_PASSWORD_ARG}

# --- Grafana ---
GRAFANA_ADMIN_USER=admin
GRAFANA_ADMIN_PASSWORD=${DB_PASSWORD_ARG}

# --- Let's Encrypt (Traefik) ---
LETSENCRYPT_EMAIL=${EMAIL}
EOF
  chmod 600 "${env_file}"
}

run_compose() {
  cd "${APP_DIR}"

  if [[ ! -f docker-compose.yml ]]; then
    echo "❌ docker-compose.yml not found in ${APP_DIR}. Did you clone/pull the repo?"
    exit 1
  fi

  echo "🐳 Starting/updating stack (no downtime when possible)"
  if ! docker compose -f docker-compose.yml -f docker-compose.letsencrypt.yml up -d --build; then
    echo "⚠️ compose up failed; trying a clean restart (down -> up)"
    docker compose -f docker-compose.yml -f docker-compose.letsencrypt.yml down || true
    docker compose -f docker-compose.yml -f docker-compose.letsencrypt.yml up -d --build
  fi

  echo "✅ Stack running"
  docker compose ps

  echo
  echo "🌍 App:     https://${APP_HOSTNAME}/ (and https://${APP_HOSTNAME_WWW}/)"
  echo "📈 Grafana: https://${GRAFANA_HOSTNAME}/ (admin / password from .env)"
}

main() {
  install_docker_if_needed
  free_ports_80_443
  ensure_env_file
  run_compose
}

main "$@"
