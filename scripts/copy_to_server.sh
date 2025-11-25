#!/bin/bash

# Скрипт для копирования шаблонов и шрифтов создателя на сервер
# Использование: ./scripts/copy_to_server.sh [SERVER_USER] [SERVER_HOST] [SERVER_PATH]

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
TEMPLATES_DIR="$PROJECT_ROOT/templates"
FONTS_DIR="$PROJECT_ROOT/fonts"
CREATOR_FONT_DIR="$FONTS_DIR/creator"

# Параметры сервера (можно передать как аргументы)
SERVER_USER="${1:-user}"
SERVER_HOST="${2:-your-server.com}"
SERVER_PATH="${3:-/path/to/consp_bot}"

echo "📦 Подготовка файлов для копирования на сервер..."
echo ""

# Проверяем шаблоны
echo "📁 Проверка шаблонов..."
if [ ! -d "$TEMPLATES_DIR" ]; then
    echo "❌ Папка templates не найдена: $TEMPLATES_DIR"
    exit 1
fi

PDF_COUNT=$(find "$TEMPLATES_DIR" -name "*.pdf" -type f | wc -l | tr -d ' ')
if [ "$PDF_COUNT" -eq 0 ]; then
    echo "⚠️  В папке templates не найдено PDF файлов"
else
    echo "✓ Найдено PDF файлов: $PDF_COUNT"
    echo "  Файлы:"
    find "$TEMPLATES_DIR" -name "*.pdf" -type f -exec basename {} \; | sort | sed 's/^/    - /'
fi

echo ""

# Проверяем шрифты создателя
echo "🔤 Проверка шрифтов создателя..."
if [ ! -d "$CREATOR_FONT_DIR" ]; then
    echo "⚠️  Папка fonts/creator/ не найдена"
    echo "   Создайте папку и поместите туда шрифт создателя"
else
    TTF_COUNT=$(find "$CREATOR_FONT_DIR" -name "*.ttf" -type f | wc -l | tr -d ' ')
    if [ "$TTF_COUNT" -eq 0 ]; then
        echo "⚠️  В папке fonts/creator/ не найдено .ttf файлов"
    else
        echo "✓ Найдено .ttf файлов: $TTF_COUNT"
        echo "  Файлы:"
        find "$CREATOR_FONT_DIR" -name "*.ttf" -type f -exec basename {} \; | sed 's/^/    - /'
    fi
fi

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "📋 Команды для копирования на сервер:"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""

# Команды для копирования шаблонов
if [ "$PDF_COUNT" -gt 0 ]; then
    echo "📄 Копирование шаблонов:"
    echo ""
    echo "  # Через scp:"
    echo "  scp -r $TEMPLATES_DIR $SERVER_USER@$SERVER_HOST:$SERVER_PATH/"
    echo ""
    echo "  # Или через rsync:"
    echo "  rsync -avz $TEMPLATES_DIR/ $SERVER_USER@$SERVER_HOST:$SERVER_PATH/templates/"
    echo ""
fi

# Команды для копирования шрифтов создателя
if [ -d "$CREATOR_FONT_DIR" ] && [ "$(find "$CREATOR_FONT_DIR" -name "*.ttf" -type f | wc -l | tr -d ' ')" -gt 0 ]; then
    echo "🔤 Копирование шрифтов создателя:"
    echo ""
    echo "  # Создать папку на сервере (если не существует):"
    echo "  ssh $SERVER_USER@$SERVER_HOST 'mkdir -p $SERVER_PATH/fonts/creator'"
    echo ""
    echo "  # Копировать через scp:"
    echo "  scp -r $CREATOR_FONT_DIR/* $SERVER_USER@$SERVER_HOST:$SERVER_PATH/fonts/creator/"
    echo ""
    echo "  # Или через rsync:"
    echo "  rsync -avz $CREATOR_FONT_DIR/ $SERVER_USER@$SERVER_HOST:$SERVER_PATH/fonts/creator/"
    echo ""
fi

echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""
echo "💡 Подсказка:"
echo "   Замените параметры SERVER_USER, SERVER_HOST и SERVER_PATH на реальные значения"
echo "   или передайте их как аргументы:"
echo "   ./scripts/copy_to_server.sh user example.com /home/user/consp_bot"
echo ""

