# Статистический бот

Небольшой Telegram-бот, который по команде `/start` или `/stat` показывает оперативную сводку по основному проекту `consp_bot`.

## Где лежит код

Папка: `stats_bot/`

- `bot.py` — основной скрипт (aiogram 3). Отвечает на `/start` и `/stat`, выводит отчёт.
- `config.py` — загрузка настроек из `.env`.
- `database.py` — подключение к PostgreSQL.
- `stats_service.py` — SQL-запросы и формирование статистики.
- `requirements.txt` — зависимости для отдельного venv.
- `env.example` — пример переменных окружения.

## .env

Файл `stats_bot/.env` создаём из `env.example`. Ключевые переменные:

```
BOT_TOKEN=7040581622:AAGF-luIPYhb6WGVJNHYA6JOojZ-sM5TbP0
ADMIN_IDS=              # можно оставить пустым, доступ открыт всем
DB_HOST=localhost
DB_PORT=5432
DB_NAME=consp_bot
DB_USER=postgres
DB_PASSWORD=***
# REPORT_CHANNEL_ID=-1001234567890
```

Пароль БД должен совпадать с тем, что используется в основном боте (`/opt/consp_bot/.env`). При пустом пароле PostgreSQL отдаёт ошибку `fe_sendauth: no password supplied`.

## Развёртывание (Ubuntu)

1. Обновить репозиторий: `cd /opt/consp_bot && git pull origin main`.
2. Настроить окружение статбота:
   ```bash
   cd /opt/consp_bot/stats_bot
   python3 -m venv venv
   source venv/bin/activate
   pip install -r requirements.txt
   deactivate
   ```
3. Создать/обновить `.env` (см. выше).
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
5. Перезагрузить systemd и запустить сервис:
   ```bash
   sudo systemctl daemon-reload
   sudo systemctl enable consp-stats
   sudo systemctl restart consp-stats
   sudo systemctl status consp-stats --no-pager
   ```

Проверка: `sudo journalctl -u consp-stats -f` и сообщение `/start` боту.

## Известные грабли

- `ModuleNotFoundError: No module named 'stats_bot'` — случилось, когда запускали `python -m stats_bot.bot`. Исправлено: `ExecStart` теперь вызывает `python bot.py`, а в коде используются относительные импорты (`from config import ...`).
- `psycopg2.OperationalError: fe_sendauth: no password supplied` — в `.env` не было `DB_PASSWORD`. Нужно задать пароль (например `consp_pwd_12345`) и перезапустить сервис.
- При первом запуске забыли создать каталог `stats_bot` на сервере — нужно не забывать `git pull` после коммита.

## Выводимый отчёт

Бот отдаёт сводку вида:

```
📊 За сегодня:
- Новые пользователи: N
- Генераций PDF: M

📈 За всё время:
- Пользователей: X
- PDF: Y

Последние:
• user_id — Z PDF
```

Если в базе нет username, бот пытается получить его через `get_chat`. Если у пользователя скрыт username, показывается `Full Name (ID)` или просто ID.
