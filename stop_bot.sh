#!/bin/bash

# Скрипт остановки бота

cd "$(dirname "$0")"

if [ ! -f "bot.pid" ]; then
    echo "⚠️  Файл bot.pid не найден. Бот может быть не запущен."
    exit 0
fi

PID=$(cat bot.pid)

if [ -z "$PID" ]; then
    echo "⚠️  PID файл пуст"
    rm bot.pid
    exit 0
fi

if ! ps -p $PID > /dev/null 2>&1; then
    echo "⚠️  Процесс с PID $PID не найден. Удаляю bot.pid"
    rm bot.pid
    exit 0
fi

echo "🛑 Остановка бота (PID: $PID)..."

# Отправляем SIGTERM для корректного завершения
kill -TERM $PID 2>/dev/null || kill $PID

# Ждем до 10 секунд
for i in {1..10}; do
    if ! ps -p $PID > /dev/null 2>&1; then
        echo "✅ Бот успешно остановлен"
        rm bot.pid
        exit 0
    fi
    sleep 1
done

# Если процесс все еще работает, убиваем принудительно
if ps -p $PID > /dev/null 2>&1; then
    echo "⚠️  Процесс не завершился, принудительная остановка..."
    kill -9 $PID
    sleep 1
    
    if ! ps -p $PID > /dev/null 2>&1; then
        echo "✅ Бот остановлен принудительно"
        rm bot.pid
        exit 0
    else
        echo "❌ Не удалось остановить бот"
        exit 1
    fi
fi

rm bot.pid

