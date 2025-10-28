#!/bin/bash

# Скрипт для быстрой настройки проекта

set -e

echo "🚀 Настройка проекта consp_bot..."

# Проверка Python
if ! command -v python3 &> /dev/null; then
    echo "❌ Python3 не найден. Установите Python 3.8+"
    exit 1
fi

# Создание виртуального окружения
if [ ! -d "venv" ]; then
    echo "📦 Создание виртуального окружения..."
    python3 -m venv venv
else
    echo "✓ Виртуальное окружение уже существует"
fi

# Активация виртуального окружения
echo "📥 Активация виртуального окружения..."
source venv/bin/activate

# Установка зависимостей
echo "📚 Установка зависимостей..."
pip install --upgrade pip
pip install -r requirements.txt

# Создание директорий
echo "📁 Создание директорий..."
mkdir -p fonts jobs

# Проверка .env файла
if [ ! -f ".env" ]; then
    echo "⚠️  Файл .env не найден. Создайте его на основе .env.example"
    echo "   cp .env.example .env"
    echo "   Затем отредактируйте .env и добавьте свои значения"
fi

echo ""
echo "✅ Настройка завершена!"
echo ""
echo "📋 Следующие шаги:"
echo "1. Установите PostgreSQL: brew install postgresql@15"
echo "2. Запустите PostgreSQL: brew services start postgresql@15"
echo "3. Создайте .env файл: cp .env.example .env"
echo "4. Отредактируйте .env и добавьте BOT_TOKEN, ADMIN_USER_ID и DB_PASSWORD"
echo "5. Инициализируйте БД: python database/db_init.py"
echo "6. Проверьте подключение: python database/test_connection.py"
echo ""
echo "Для активации виртуального окружения: source venv/bin/activate"

