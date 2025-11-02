#!/usr/bin/env bash
set -euo pipefail

# One-step деплой для Ubuntu 22.04+ (root или sudo)
# Делает: системные пакеты, Python venv, .env, установку зависимостей,
# systemd unit, nginx reverse-proxy, webhook.

APP_DIR="/opt/consp_bot"
PYTHON_BIN="python3"
SERVICE_NAME="consp-bot"
NGINX_SITE="consp_bot"

# Обязательные переменные окружения (передайте при запуске или пропишите ниже)
: "${BOT_TOKEN:?BOT_TOKEN is required}"
: "${DB_HOST:=localhost}"
: "${DB_PORT:=5432}"
: "${DB_NAME:=consp_bot}"
: "${DB_USER:=postgres}"
: "${DB_PASSWORD:=}"

# Webhook настройки
: "${DOMAIN:?DOMAIN (e.g. bot.example.com) is required}"
: "${WEBAPP_PORT:=8080}"
: "${WEBHOOK_PATH:=/webhook}"
: "${WEBHOOK_SECRET:=$(openssl rand -hex 16)}"
WEBHOOK_URL="https://${DOMAIN}${WEBHOOK_PATH}"

if [ "${EUID}" -ne 0 ]; then
  echo "Please run as root (sudo)." >&2
  exit 1
fi

echo "==> Install system dependencies"
apt-get update -y
apt-get install -y python3 python3-venv python3-pip git nginx curl

# Создаём директорию приложения
mkdir -p "$APP_DIR"
chown -R "$SUDO_USER:${SUDO_USER:-root}" "$APP_DIR" || true

# Копируем проект в /opt (если запускаем из исходников локально через scp/rsync — пропустит)
if [ ! -d "$APP_DIR/.git" ] && [ -d "$(pwd)/.git" ]; then
  echo "==> Copying project to $APP_DIR"
  rsync -a --delete --exclude 'venv' --exclude '.git' ./ "$APP_DIR/"
fi

cd "$APP_DIR"

echo "==> Create venv and install requirements"
$PYTHON_BIN -m venv venv
source venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt

# Создаём .env
echo "==> Write .env"
cat > .env <<ENV
BOT_TOKEN=${BOT_TOKEN}
DB_HOST=${DB_HOST}
DB_PORT=${DB_PORT}
DB_NAME=${DB_NAME}
DB_USER=${DB_USER}
DB_PASSWORD=${DB_PASSWORD}
WEBHOOK_URL=${WEBHOOK_URL}
WEBHOOK_SECRET=${WEBHOOK_SECRET}
WEBAPP_HOST=0.0.0.0
WEBAPP_PORT=${WEBAPP_PORT}
WEBHOOK_PATH=${WEBHOOK_PATH}
ENV

# Инициализация БД (безопасно, idempotent)
echo "==> DB init"
source venv/bin/activate
$PYTHON_BIN database/db_init.py || true

# Systemd unit
echo "==> Install systemd unit"
cat > /etc/systemd/system/${SERVICE_NAME}.service <<UNIT
[Unit]
Description=Consp Bot (Aiogram) Webhook Service
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
WorkingDirectory=${APP_DIR}
EnvironmentFile=${APP_DIR}/.env
ExecStart=${APP_DIR}/venv/bin/python ${APP_DIR}/bot.py
Restart=always
RestartSec=5
User=${SUDO_USER:-root}
Group=${SUDO_USER:-root}

[Install]
WantedBy=multi-user.target
UNIT

systemctl daemon-reload
systemctl enable ${SERVICE_NAME}

# Nginx reverse-proxy
echo "==> Configure nginx"
cat > /etc/nginx/sites-available/${NGINX_SITE} <<NGINX
server {
    listen 80;
    server_name ${DOMAIN};

    location / {
        return 301 https://$host$request_uri;
    }
}

server {
    listen 443 ssl http2;
    server_name ${DOMAIN};

    # Здесь предполагается, что сертификаты уже установлены (например, через certbot)
    ssl_certificate     /etc/letsencrypt/live/${DOMAIN}/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/${DOMAIN}/privkey.pem;

    location ${WEBHOOK_PATH} {
        proxy_pass http://127.0.0.1:${WEBAPP_PORT}${WEBHOOK_PATH};
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_set_header X-Telegram-Bot-Api-Secret-Token ${WEBHOOK_SECRET};
    }
}
NGINX

ln -sf /etc/nginx/sites-available/${NGINX_SITE} /etc/nginx/sites-enabled/${NGINX_SITE}
nginx -t
systemctl restart nginx

# Старт сервиса
echo "==> Start service"
systemctl restart ${SERVICE_NAME}
sleep 2
systemctl status --no-pager ${SERVICE_NAME} || true

# Подсказки по SSL
cat <<NOTE

Done. Next steps:
- Issue SSL certificates with certbot, e.g.:
  apt-get install -y certbot python3-certbot-nginx
  certbot --nginx -d ${DOMAIN} --redirect --non-interactive --agree-tos -m you@example.com
- After certs installed, rerun: systemctl restart nginx && systemctl restart ${SERVICE_NAME}

Check logs:
  journalctl -u ${SERVICE_NAME} -f
NOTE

