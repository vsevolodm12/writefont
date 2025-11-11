# Локальный деплой бота на Mac

## Продовый деплой (Ubuntu / Systemd)

### 1. Обновление кода и миграций одной командой
На сервере (под пользователем с доступом к `/opt/consp_bot`):

```bash
(cd /opt/consp_bot && git pull origin main && source venv/bin/activate && alembic upgrade head && deactivate)
```

Эта команда:
- переходит в директорию проекта;
- подтягивает последний код из `main`;
- активирует виртуальное окружение;
- накатывает все миграции базы данных;
- отключает окружение.

### 2. Перезапуск сервиса и проверка
```bash
sudo systemctl restart consp-bot
sudo systemctl status consp-bot
```

### 3. Логи
- последние записи: `sudo journalctl -u consp-bot -n 200 --no-pager`
- потоковое наблюдение: `sudo journalctl -u consp-bot -f`

Если Telegram API временно рвёт соединение (ошибка `TelegramNetworkError`), повторный запуск сервиса восстанавливает polling. При стойких проблемах проверьте сетевые ограничения или настройте ретраи/прокси.

---

## Локальный запуск (macOS)

### Запуск бота в фоновом режиме:
```bash
./start_bot.sh
```

### Проверка статуса:
```bash
./status_bot.sh
```

### Остановка бота:
```bash
./stop_bot.sh
```

### Просмотр логов
- в реальном времени: `tail -f logs/bot.log`
- последние 100 строк: `tail -n 100 logs/bot.log`
- ошибки: `tail -f logs/bot_output.log`

### Первый запуск
1. Проверка окружения:
   ```bash
   python check_ready.py
   ```
2. Инициализация БД (при необходимости):
   ```bash
   python database/db_init.py
   ```
3. Старт бота:
   ```bash
   ./start_bot.sh
   ```

### Управление ботом
- Закройте терминал — бот продолжит работать.
- Статус: `./status_bot.sh`
- Остановка: `./stop_bot.sh`

### Решение проблем

**Бот не запускается:**
```bash
tail -n 50 logs/bot.log
tail -n 50 logs/bot_output.log
python check_ready.py
```

**Бот запущен, но не отвечает:**
```bash
./status_bot.sh
python database/test_connection.py
```

**Не удаётся остановить бот:**
```bash
ps aux | grep bot.py
kill -9 <PID>
rm bot.pid
```

### Важно

- Автостарт на macOS отсутствует — используйте `./start_bot.sh`.
- Все данные (БД, файлы) хранятся локально.
- Бот можно остановить/перезапустить в любой момент.

