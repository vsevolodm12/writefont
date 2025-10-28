#!/bin/bash

# Скрипт проверки статуса бота

cd "$(dirname "$0")"

if [ ! -f "bot.pid" ]; then
    echo "❌ Бот не запущен (файл bot.pid не найден)"
    exit 0
fi

PID=$(cat bot.pid)

if [ -z "$PID" ]; then
    echo "⚠️  PID файл пуст"
    exit 0
fi

if ps -p $PID > /dev/null 2>&1; then
    echo "✅ Бот запущен"
    echo "   PID: $PID"
    echo ""
    echo "📊 Статистика процесса:"
    ps -p $PID -o pid,ppid,etime,rss,comm
    echo ""
    echo "📝 Последние строки логов:"
    if [ -f "logs/bot.log" ]; then
        tail -n 5 logs/bot.log
    else
        echo "   Логи не найдены"
    fi
else
    echo "⚠️  Процесс не найден (PID: $PID)"
    echo "   Удаляю старый PID файл"
    rm bot.pid
fi

