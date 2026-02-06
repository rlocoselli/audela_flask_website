#!/usr/bin/env bash

# ==========================
# CONFIG
# ==========================
DOMAIN="audeladedonnees.fr"
WWW_DOMAIN="www.audeladedonnees.fr"
EMAIL="admin@audeladedonnees.fr"

APP_NAME="audeladedonnees"
SRC_DIR="$(pwd)"
APP_DIR="/var/www/$APP_NAME"

VENV_DIR="$APP_DIR/.venv"
USER="www-data"
PORT="8000"

echo "🚀 Deploying Flask app factory project"
echo "📁 $SRC_DIR → $APP_DIR"

# ==========================
# CHECK
# ==========================
if [ ! -d "$SRC_DIR/audela" ]; then
  echo "❌ audela package not found (app factory expected)"
  exit 1
fi

# ==========================
# SYSTEM
# ==========================
apt update
apt install -y \
  python3 python3-venv python3-pip \
  nginx certbot python3-certbot-nginx rsync

# ==========================
# COPY APP
# ==========================
mkdir -p $APP_DIR
rsync -av --delete --exclude='.venv' "$SRC_DIR/" "$APP_DIR/"

# ==========================
# PERMISSIONS
# ==========================
chown -R $USER:$USER $APP_DIR
chmod -R 755 $APP_DIR

# ==========================
# VIRTUAL ENV
# ==========================
sudo -u $USER python3 -m venv $VENV_DIR
sudo -u $USER $VENV_DIR/bin/pip install --upgrade pip

if [ -f "$APP_DIR/requirements.txt" ]; then
  sudo -u $USER $VENV_DIR/bin/pip install -r $APP_DIR/requirements.txt
else
  sudo -u $USER $VENV_DIR/bin/pip install flask gunicorn
fi

# ==========================
# WSGI (FACTORY SAFE)
# ==========================
cat <<EOF > $APP_DIR/wsgi.py
from audela import create_app

app = create_app()
EOF

chown $USER:$USER $APP_DIR/wsgi.py

# ==========================
# SYSTEMD SERVICE
# ==========================
cat <<EOF > /etc/systemd/system/$APP_NAME.service
[Unit]
Description=Gunicorn $APP_NAME
After=network.target

[Service]
User=$USER
Group=$USER
WorkingDirectory=$APP_DIR
Environment="PATH=$VENV_DIR/bin"
ExecStart=$VENV_DIR/bin/gunicorn \
  --workers 2 \
  --bind 127.0.0.1:$PORT \
  wsgi:app

Restart=always
RestartSec=3

[Install]
WantedBy=multi-user.target
EOF

systemctl daemon-reload
systemctl enable $APP_NAME
systemctl restart $APP_NAME

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

# ==========================
# SSL
# ==========================
certbot --nginx \
  -d $DOMAIN \
  -d $WWW_DOMAIN \
  --non-interactive \
  --agree-tos \
  -m $EMAIL \
  --redirect

# ==========================
# DONE
# ==========================
echo ""
echo "✅ DEPLOY SUCCESSFUL"
echo "🌍 https://$DOMAIN"
echo "🚀 Gunicorn running (Flask app factory)"
echo "🔒 SSL auto-renew enabled"