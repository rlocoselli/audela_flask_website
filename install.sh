#!/usr/bin/env bash

# ==========================
# CONFIG
# ==========================
DOMAIN="audeladedonnees.fr"
WWW_DOMAIN="www.audeladedonnees.fr"
EMAIL="admin@audeladedonnees.fr"

APP_NAME="audela_flask_website"
SRC_DIR="$(pwd)"
APP_DIR="/root/audela_flask_website"

VENV_DIR="$APP_DIR/.venv"
USER="root"
PORT="8000"

echo "🚀 Deploying Flask app (root-based)"
echo "📁 $SRC_DIR → $APP_DIR"

# ==========================
# CHECK
# ==========================
if [ ! -d "$SRC_DIR/audela" ]; then
  echo "❌ audela package not found (Flask app factory expected)"
  exit 1
fi

# ==========================
# SYSTEM PACKAGES
# ==========================
apt update
apt install -y \
  python3 python3-venv python3-pip \
  nginx certbot python3-certbot-nginx rsync

# ==========================
# COPY APP
# ==========================
mkdir -p "$APP_DIR"
rsync -av --delete --exclude='.venv' "$SRC_DIR/" "$APP_DIR/"

# ==========================
# PERMISSIONS (root)
# ==========================
chmod -R 755 "$APP_DIR"
cd "$APP_DIR"
git fetch origin
git switch main
git reset --hard origin/main
git clean -fdx

# ==========================
# VIRTUAL ENV
# ==========================
python3 -m venv "$VENV_DIR"
"$VENV_DIR/bin/pip" install --upgrade pip

if [ -f "$APP_DIR/requirements.txt" ]; then
  "$VENV_DIR/bin/pip" install -r "$APP_DIR/requirements.txt"
else
  "$VENV_DIR/bin/pip" install flask gunicorn python-dotenv openai sqlalchemy psycopg2-binary
fi

# ==========================
# WSGI (FACTORY SAFE)
# ==========================
cat <<EOF > "$APP_DIR/wsgi.py"
from audela import create_app

app = create_app()
EOF

echo "🔐 Creating .env (workspace)"
umask 077
cat > "$APP_DIR/.env" <<EOF
HOST=${APP_HOST}
USER=${APP_USER}
PASSWORD=${APP_PASSWORD}
OPENAI_API_KEY=${APP_OPENAI_API_KEY}
EOF
chmod 600 "$APP_DIR/.env"

# ==========================
# SYSTEMD SERVICE
# ==========================
cat <<EOF > /etc/systemd/system/$APP_NAME.service
[Unit]
Description=Gunicorn $APP_NAME
After=network.target

[Service]
User=root
Group=root

WorkingDirectory=$APP_DIR
EnvironmentFile=$APP_DIR/.env

ExecStart=$VENV_DIR/bin/gunicorn \\
  --workers 2 \\
  --bind 127.0.0.1:$PORT \\
  wsgi:app

Restart=always
RestartSec=3

[Install]
WantedBy=multi-user.target
EOF

systemctl daemon-reload
systemctl enable "$APP_NAME"
systemctl restart "$APP_NAME"

# ==========================
# NGINX
# ==========================
cat <<EOF > /etc/nginx/sites-available/$APP_NAME
server {
    listen 80;
    server_name $DOMAIN $WWW_DOMAIN;

    location / {
        proxy_pass http://127.0.0.1:$PORT;

        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto https;
    }
}
EOF

ln -sf /etc/nginx/sites-available/$APP_NAME /etc/nginx/sites-enabled/$APP_NAME
rm -f /etc/nginx/sites-enabled/default

nginx -t
systemctl reload nginx

# ==========================n
# SSL
# ==========================
certbot --nginx \
  -d "$DOMAIN" \
  -d "$WWW_DOMAIN" \
  --non-interactive \
  --agree-tos \
  -m "$EMAIL" \
  --redirect

# ==========================
# DONE
# ==========================
echo ""
echo "✅ DEPLOY SUCCESSFUL"
echo "🌍 https://$DOMAIN"
echo "🚀 Gunicorn running as root"
echo "🔐 Environment loaded from $APP_DIR/.env"
echo "⚠️  Reminder: running as root is NOT recommended for prod"
