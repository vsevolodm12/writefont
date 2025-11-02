#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."

if [ ! -f "alembic.ini" ]; then
  echo "alembic.ini not found in $(pwd)" >&2
  exit 1
fi

# Подхватить .env
if [ -f .env ]; then
  set -a; source .env; set +a
fi

# Установить URL для Alembic из .env, если нужно
export DB_USER="${DB_USER:-postgres}"
export DB_PASSWORD="${DB_PASSWORD:-}"
export DB_HOST="${DB_HOST:-localhost}"
export DB_PORT="${DB_PORT:-5432}"
export DB_NAME="${DB_NAME:-consp_bot}"

# Прогон миграций до последней версии
alembic upgrade head



