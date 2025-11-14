# Локальный деплой бота на Mac

## Продовый деплой (Ubuntu / Systemd)

### Статистический бот `/start`

1. Обновить код: `cd /opt/consp_bot && git pull origin main`.
2. Настроить окружение статбота:
   ```bash
   cd /opt/consp_bot/stats_bot
   python3 -m venv venv
   source venv/bin/activate
   pip install -r requirements.txt
   deactivate
   ```
3. Создать `.env` (пример в `stats_bot/env.example`). Ключевые поля: `BOT_TOKEN`, `DB_*`, `DB_PASSWORD` (совпадает с основным ботом).
4. systemd-юнит `/etc/systemd/system/consp-stats.service`:
   ```ini
   [Unit]
   Description=Consp Statistics Bot
   After=network-online.target
   Wants=network-online.target

   [Service]
   Type=simple
   WorkingDirectory=/opt/consp_bot/stats_bot
   EnvironmentFile=/opt/consp_bot/stats_bot/.env
   ExecStart=/opt/consp_bot/stats_bot/venv/bin/python bot.py
   Restart=always
   RestartSec=5
   User=root
   Group=root

   [Install]
   WantedBy=multi-user.target
   ```
5. Запуск: `sudo systemctl daemon-reload && sudo systemctl enable consp-stats && sudo systemctl restart consp-stats`
6. Проверка: `sudo systemctl status consp-stats --no-pager`, `sudo journalctl -u consp-stats -f`. Команда `/start` в чате со статботом должна вернуть сводку.

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

### 4. Чек-лист по опыту деплой-2025
- **Следим за токеном.** Перед деплоем убеждаемся, что `.env` на сервере содержит продовый `BOT_TOKEN` без лишних символов. Проверка:  
  `curl -s "https://api.telegram.org/bot${BOT_TOKEN}/getMe"`.
- **Проверяем сеть.** Если бот падает с `TelegramNetworkError`, сначала смотрим доступность API:  
  `curl -I https://api.telegram.org`. При блокировках понадобится прокси/впн.
- **Логи при старте.** Если сервис сразу перезапускается, `journalctl` показывает причину. Пример: конфликт таймаутов в `bot.py` (ошибка `TypeError`) — фиксируется обновлением кода.
- **Ретраи сообщений.** В коде добавлен `utils/telegram_retry.py`; он гасит краткие обрывы. Если лог показывает «All retry attempts exhausted», значит обрыв долгий → снова проверить сеть или перезапустить сервис.
- **Контроль размера PDF.** Слишком тяжёлый файл тоже может вызвать таймаут. При подозрении тикет: `ls -lh generated`.
- **Advisory lock.** После краша polling освобождает лок. Если видите в логах «advisory lock не получен», значит уже запущен другой экземпляр (например, локальный dev). Надо остановить дубликат.

### 5. Частые ошибки и решения
- `HTTP Client says - ServerDisconnectedError`: Telegram рвёт соединение при отправке PDF. Проверяем `tail -f logs/bot_output.log`, ретраи уже настроены. Если ошибки повторяются — перезапуск `consp-bot`, проверка доступа до `https://api.telegram.org`, по необходимости прокси.
- `TypeError: unsupported operand type(s) for +: 'ClientTimeout' and 'int'`: возникает при кастомном `ClientTimeout`. В текущей версии используется простой `timeout=60`; если правите `bot.py`, не передавайте объект `ClientTimeout` в aiogram.
- `fe_sendauth: no password supplied`: статбот или основной бот не видит пароль к БД. Проверь `.env`: `DB_PASSWORD=...` должен совпадать для обоих сервисов.
- Отсутствие username в статистике: основной бот теперь сохраняет `username/first_name/last_name` при каждом апдейте. Если пусто, попросите пользователя написать боту ещё раз.

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

