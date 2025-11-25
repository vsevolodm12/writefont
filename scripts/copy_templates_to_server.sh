#!/bin/bash

# Скрипт для копирования шаблонов на сервер
# Использование: ./scripts/copy_templates_to_server.sh

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
TEMPLATES_DIR="$PROJECT_ROOT/templates"

echo "📁 Копирование шаблонов на сервер..."

# Проверяем существование папки templates
if [ ! -d "$TEMPLATES_DIR" ]; then
    echo "❌ Папка templates не найдена: $TEMPLATES_DIR"
    exit 1
fi

# Проверяем наличие PDF файлов
PDF_COUNT=$(find "$TEMPLATES_DIR" -name "*.pdf" -type f | wc -l)

if [ "$PDF_COUNT" -eq 0 ]; then
    echo "⚠️  В папке templates не найдено PDF файлов"
    echo "Убедитесь, что шаблоны находятся в папке templates/"
    exit 1
fi

echo "✓ Найдено PDF файлов: $PDF_COUNT"

# Выводим список файлов для проверки
echo ""
echo "📄 Файлы для копирования:"
find "$TEMPLATES_DIR" -name "*.pdf" -type f -exec basename {} \; | sort

echo ""
echo "✅ Шаблоны готовы к использованию на сервере"
echo ""
echo "Для копирования на удаленный сервер используйте:"
echo "  scp -r $TEMPLATES_DIR user@server:/path/to/consp_bot/"
echo ""
echo "Или через rsync:"
echo "  rsync -avz $TEMPLATES_DIR/ user@server:/path/to/consp_bot/templates/"

