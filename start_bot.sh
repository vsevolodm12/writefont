#!/bin/bash

# Скрипт запуска бота в фоновом режиме

cd "$(dirname "$0")"

# Проверка виртуального окружения
if [ ! -d "venv" ]; then
    echo "❌ Виртуальное окружение не найдено. Запустите setup.sh"
    exit 1
fi

# Проверка запущен ли уже бот
if [ -f "bot.pid" ]; then
    PID=$(cat bot.pid)
    if ps -p $PID > /dev/null 2>&1; then
        echo "⚠️  Бот уже запущен (PID: $PID)"
        echo "   Для остановки: ./stop_bot.sh"
        exit 1
    else
        # Удаляем старый PID файл
        rm bot.pid
    fi
fi

# Создаем директорию для логов если не существует
mkdir -p logs

echo "🚀 Запуск бота в фоновом режиме..."

# Запускаем бота в фоне с активацией venv и сохраняем PID
nohup bash -c "source venv/bin/activate && python bot.py" > logs/bot_output.log 2>&1 &
BOT_PID=$!

# Сохраняем PID
echo $BOT_PID > bot.pid

sleep 2

# Проверяем, что процесс все еще работает
if ps -p $BOT_PID > /dev/null 2>&1; then
    echo "✅ Бот успешно запущен!"
    echo "   PID: $BOT_PID"
    echo "   Логи: tail -f logs/bot.log"
    echo "   Остановка: ./stop_bot.sh"
else
    echo "❌ Ошибка запуска бота. Проверьте логи:"
    echo "   tail -n 50 logs/bot.log"
    echo "   tail -n 50 logs/bot_output.log"
    rm bot.pid
    exit 1
fi

