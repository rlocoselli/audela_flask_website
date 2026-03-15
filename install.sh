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
MAIL_SERVER_ARG="${8:-}"
MAIL_PORT_ARG="${9:-}"
MAIL_USE_TLS_ARG="${10:-}"
MAIL_USE_SSL_ARG="${11:-}"
MAIL_USERNAME_ARG="${12:-}"
MAIL_PASSWORD_ARG="${13:-}"
MAIL_DEFAULT_SENDER_ARG="${14:-}"

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
  local existing_mail_server=""
  local existing_mail_port=""
  local existing_mail_use_tls=""
  local existing_mail_use_ssl=""
  local existing_mail_username=""
  local existing_mail_password=""
  local existing_mail_default_sender=""
  local site_url_effective=""
  local bridge_callback_url_effective=""
  local bridge_client_id_effective=""
  local bridge_client_secret_effective=""
  local bridge_base_url_effective=""
  local bridge_version_effective=""
  local powens_client_id_effective=""
  local powens_client_secret_effective=""
  local powens_webhook_secret_effective=""
  local encryption_key_effective=""
  local app_release_effective=""
  local grafana_hostname_alt_effective=""

  escape_sed_replacement () {
    printf "%s" "$1" | sed -e 's/[|&]/\\&/g'
  }

  upsert_env_var () {
    local key="$1"
    local val="$2"
    local escaped_val
    if [ -z "$val" ]; then
      return 0
    fi
    escaped_val="$(escape_sed_replacement "$val")"
    if grep -qE "^${key}=" "${env_file}"; then
      sed -i "s|^${key}=.*|${key}=${escaped_val}|" "${env_file}"
    else
      printf "\n%s=%s\n" "$key" "$val" >> "${env_file}"
    fi
  }

  get_env_value () {
    local key="$1"
    if [[ -f "${env_file}" ]]; then
      grep -E "^${key}=" "${env_file}" | tail -n1 | cut -d= -f2- || true
    fi
  }

  if [[ -f "${env_file}" ]]; then
    secret_key="$(grep -E '^SECRET_KEY=' "${env_file}" | tail -n1 | cut -d= -f2- || true)"
    data_key="$(grep -E '^DATA_KEY=' "${env_file}" | tail -n1 | cut -d= -f2- || true)"

    existing_mail_server="$(get_env_value MAIL_SERVER)"
    existing_mail_port="$(get_env_value MAIL_PORT)"
    existing_mail_use_tls="$(get_env_value MAIL_USE_TLS)"
    existing_mail_use_ssl="$(get_env_value MAIL_USE_SSL)"
    existing_mail_username="$(get_env_value MAIL_USERNAME)"
    existing_mail_password="$(get_env_value MAIL_PASSWORD)"
    existing_mail_default_sender="$(get_env_value MAIL_DEFAULT_SENDER)"

    site_url_effective="$(get_env_value SITE_URL)"
    bridge_callback_url_effective="$(get_env_value BRIDGE_CALLBACK_URL)"
    bridge_client_id_effective="$(get_env_value BRIDGE_CLIENT_ID)"
    bridge_client_secret_effective="$(get_env_value BRIDGE_CLIENT_SECRET)"
    bridge_base_url_effective="$(get_env_value BRIDGE_BASE_URL)"
    bridge_version_effective="$(get_env_value BRIDGE_VERSION)"
    powens_client_id_effective="$(get_env_value POWENS_CLIENT_ID)"
    powens_client_secret_effective="$(get_env_value POWENS_CLIENT_SECRET)"
    powens_webhook_secret_effective="$(get_env_value POWENS_WEBHOOK_SECRET)"
    encryption_key_effective="$(get_env_value ENCRYPTION_KEY)"
    app_release_effective="$(get_env_value APP_RELEASE)"
    grafana_hostname_alt_effective="$(get_env_value GRAFANA_HOSTNAME_ALT)"
  fi

  if [[ -z "${secret_key}" ]]; then secret_key="$(rand_hex_64)"; fi
  if [[ -z "${data_key}" ]]; then data_key="$(rand_hex_64)"; fi

  # ---- SMTP / Email effective values (arg > existing .env > defaults) ----
  local mail_server_effective="${MAIL_SERVER_ARG:-${existing_mail_server:-${SMTP_SERVER_DEFAULT:-}}}"
  local mail_port_effective="${MAIL_PORT_ARG:-${existing_mail_port:-${SMTP_PORT_DEFAULT:-587}}}"
  local mail_use_tls_effective="${MAIL_USE_TLS_ARG:-${existing_mail_use_tls:-${SMTP_USE_TLS_DEFAULT:-True}}}"
  local mail_use_ssl_effective="${MAIL_USE_SSL_ARG:-${existing_mail_use_ssl:-${SMTP_USE_SSL_DEFAULT:-False}}}"
  local mail_username_effective="${MAIL_USERNAME_ARG:-${existing_mail_username:-${SMTP_USERNAME_DEFAULT:-}}}"
  local mail_password_effective="${MAIL_PASSWORD_ARG:-${existing_mail_password:-}}"
  local mail_default_sender_effective="${MAIL_DEFAULT_SENDER_ARG:-${existing_mail_default_sender:-${SMTP_DEFAULT_SENDER_DEFAULT:-${EMAIL}}}}"

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

  site_url_effective="${SITE_URL:-${site_url_effective:-https://${APP_HOSTNAME}}}"
  bridge_callback_url_effective="${BRIDGE_CALLBACK_URL:-${bridge_callback_url_effective:-${site_url_effective%/}/finance/banks/callback}}"
  bridge_client_id_effective="${BRIDGE_CLIENT_ID:-${bridge_client_id_effective:-}}"
  bridge_client_secret_effective="${BRIDGE_CLIENT_SECRET:-${bridge_client_secret_effective:-}}"
  bridge_base_url_effective="${BRIDGE_BASE_URL:-${bridge_base_url_effective:-https://api.bridgeapi.io}}"
  bridge_version_effective="${BRIDGE_VERSION:-${bridge_version_effective:-2025-01-15}}"
  powens_client_id_effective="${POWENS_CLIENT_ID:-${powens_client_id_effective:-}}"
  powens_client_secret_effective="${POWENS_CLIENT_SECRET:-${powens_client_secret_effective:-}}"
  powens_webhook_secret_effective="${POWENS_WEBHOOK_SECRET:-${powens_webhook_secret_effective:-}}"
  encryption_key_effective="${ENCRYPTION_KEY:-${encryption_key_effective:-}}"
  app_release_effective="${APP_RELEASE:-${app_release_effective:-}}"
  grafana_hostname_alt_effective="${GRAFANA_HOSTNAME_ALT:-${grafana_hostname_alt_effective:-}}"

  echo "🔐 Writing .env for docker compose"
  umask 077
  if [[ ! -f "${env_file}" ]]; then
    cat > "${env_file}" <<EOF
# --- Generated by install.sh ---
EOF
  fi

  upsert_env_var "APP_HOSTNAME" "${APP_HOSTNAME}"
  upsert_env_var "APP_HOSTNAME_WWW" "${APP_HOSTNAME_WWW}"
  upsert_env_var "GRAFANA_HOSTNAME" "${GRAFANA_HOSTNAME}"
  upsert_env_var "GRAFANA_HOSTNAME_ALT" "${grafana_hostname_alt_effective}"

  upsert_env_var "SECRET_KEY" "${secret_key}"
  upsert_env_var "DATA_KEY" "${data_key}"

  upsert_env_var "OPENAI_API_KEY" "${OPENAI_API_KEY_ARG}"
  upsert_env_var "DATABASE_URL" "${database_url_effective}"
  upsert_env_var "APP_HOST" "${db_host_effective}"
  upsert_env_var "APP_USER" "${DB_USER_ARG}"
  upsert_env_var "APP_PASSWORD" "${DB_PASSWORD_ARG}"
  upsert_env_var "DB_NAME" "${DB_NAME_ARG}"
  upsert_env_var "DB_PORT" "${DB_PORT_ARG}"
  upsert_env_var "REDIS_URL" "redis://redis:6379/0"

  upsert_env_var "SITE_URL" "${site_url_effective}"
  upsert_env_var "BRIDGE_CALLBACK_URL" "${bridge_callback_url_effective}"
  upsert_env_var "BRIDGE_CLIENT_ID" "${bridge_client_id_effective}"
  upsert_env_var "BRIDGE_CLIENT_SECRET" "${bridge_client_secret_effective}"
  upsert_env_var "BRIDGE_BASE_URL" "${bridge_base_url_effective}"
  upsert_env_var "BRIDGE_VERSION" "${bridge_version_effective}"
  upsert_env_var "POWENS_CLIENT_ID" "${powens_client_id_effective}"
  upsert_env_var "POWENS_CLIENT_SECRET" "${powens_client_secret_effective}"
  upsert_env_var "POWENS_WEBHOOK_SECRET" "${powens_webhook_secret_effective}"
  upsert_env_var "ENCRYPTION_KEY" "${encryption_key_effective}"
  upsert_env_var "APP_RELEASE" "${app_release_effective}"

  upsert_env_var "MAIL_SERVER" "${mail_server_effective}"
  upsert_env_var "MAIL_PORT" "${mail_port_effective}"
  upsert_env_var "MAIL_USE_TLS" "${mail_use_tls_effective}"
  upsert_env_var "MAIL_USE_SSL" "${mail_use_ssl_effective}"
  upsert_env_var "MAIL_USERNAME" "${mail_username_effective}"
  upsert_env_var "MAIL_PASSWORD" "${mail_password_effective}"
  upsert_env_var "MAIL_DEFAULT_SENDER" "${mail_default_sender_effective}"

  upsert_env_var "POSTGRES_DB" "${DB_NAME_ARG}"
  upsert_env_var "POSTGRES_USER" "${DB_USER_ARG}"
  upsert_env_var "POSTGRES_PASSWORD" "${DB_PASSWORD_ARG}"

  upsert_env_var "GRAFANA_ADMIN_USER" "admin"
  upsert_env_var "GRAFANA_ADMIN_PASSWORD" "${DB_PASSWORD_ARG}"

  upsert_env_var "LETSENCRYPT_EMAIL" "${EMAIL}"

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
