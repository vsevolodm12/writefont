# Контекст проекта (Consp Bot)

Документ для быстрого погружения: структура, ключевая логика, недавние изменения, текущий статус и чек‑листы.

## Структура репозитория (высокоуровнево)

```
consp_bot/
  bot.py                   – точка входа; инициализация бота, роутеры, режим webhook/polling
  pdf_generator.py         – генерация PDF (ReportLab)
  config.py                – конфигурация (BOT_TOKEN, DB, WEBHOOK_* и пр.)
  handlers/                – обработчики aiogram
    menu.py                – главное меню, клавиатуры, навигация
    text.py                – обработка текстов, запуск генерации PDF
    callbacks.py           – обработка callback кнопок (в т.ч. выбор формата)
    commands.py            – (резерв) обработчики команд
    fonts.py               – загрузка пользовательских шрифтов
    grid.py                – переключение видимости сетки в PDF
  utils/                   – утилиты
    cleanup.py             – периодическая чистка старых PDF
    db_utils.py            – работа с пользователями/настройками в БД
    executors.py           – вспомогательные исполнители задач
    rate_limit.py          – лимиты на частоту
    metrics.py             – метрики производительности
    font_cache.py          – кеш шрифтов
  database/                – БД и миграции
    connection.py          – подключение к Postgres
    db_init.py             – инициализация БД
    add_grid_column.py     – миграция (добавление столбца grid)
    test_connection.py     – тест соединения
  start_bot.sh             – запуск единственного инстанса (PID + очистка дублей)
  stop_bot.sh              – остановка процесса по PID
  status_bot.sh            – быстрый статус
  setup.sh                 – подготовка окружения
  fonts/                   – встроенные шрифты
  generated/               – выходные PDF
  logs/                    – логи (bot.log, bot_output.log)
  README.md, *.md          – документация/инструкции
  requirements.txt         – зависимости
  venv/                    – виртуальное окружение
```

## Ключевые элементы логики

- Точка входа `bot.py`:
  - Инициализация Bot/Dispatcher и регистрация роутеров (`grid` → `menu` → `commands/fonts/callbacks/text`).
  - Два режима работы:
    - Polling (локально): при пустом `WEBHOOK_URL`. Включена защита от дублей через PostgreSQL advisory lock.
    - Webhook (прод/VPS): при заданном `WEBHOOK_URL` запускается aiohttp‑сервер (`WEBAPP_HOST/PORT`, `WEBHOOK_PATH`) и устанавливается webhook с `WEBHOOK_SECRET`.
  - Фоновые задачи: `periodic_cleanup()` и `log_statistics()`.

- Обработчики (`handlers/`):
  - `menu.py`: главное меню, клавиатуры, навигация между разделами.
  - `callbacks.py`: выбор формата страницы; после выбора – переход в главное меню (есть fallback).
  - `text.py`: обработка пользовательского текста и запуск генерации PDF.
  - `fonts.py`: загрузка шрифтов пользователем.
  - `grid.py`: переключение сетки в PDF.

- PDF (`pdf_generator.py`):
  - Разметка листа в клетку, отступ 1 клетка сверху и 2 слева.
  - Текст строго вписывается в клетки (подобран размер шрифта/межстрочный интервал).
  - Убраны рандомные «красные строки».

- БД (`database/`, `utils/db_utils.py`):
  - Postgres через `psycopg2`.
  - Пользователи, формат страницы, флаг сетки и пр.

- Скрипты запуска:
  - `start_bot.sh`: PID‑файл, очистка зависших `python .* bot.py`, запуск в фоне, логи в `logs/bot_output.log`.
  - `stop_bot.sh`: корректная остановка SIGTERM → KILL при необходимости.
  - `status_bot.sh`: краткий статус.

## Конфигурация (config.py → .env)

- BOT_TOKEN – токен Telegram бота.
- DB_HOST, DB_PORT, DB_NAME, DB_USER, DB_PASSWORD – Postgres.
- WEBHOOK_URL – если задан, включается режим webhook.
- WEBHOOK_SECRET – секрет для проверки подписи Telegram.
- WEBAPP_HOST/WEBAPP_PORT – где слушает aiohttp сервер.
- WEBHOOK_PATH – путь для webhook (по умолчанию `/webhook`).

## Недавние изменения и попытки

- PDF разметка:
  - Удалены случайные отступы параграфов, выровнаны базовые линии по сетке.
  - Зафиксированы отступы: 1 клетка сверху, 2 слева; текст не выходит за границы клеток.

- UX выбора формата (A4/A5):
  - После выбора формата – мгновенный возврат в главное меню.
  - Если формат не меняется – считаем успешным выбором и всё равно показываем меню.

- Анти‑конфликт Telegram (масштабируемость):
  - В polling‑режиме: PostgreSQL advisory lock → единственный лидер.
  - В webhook‑режиме: aiohttp + set_webhook; удаление webhook перед polling.
  - Добавлены env‑переменные для простого переключения режимов.

- Запуск/остановка:
  - `start_bot.sh` теперь перед запуском убивает все локальные процессы `bot.py`, чтобы исключить дубли.

## Текущий статус

- Рабочий профиль: локально на macOS, режим polling.
- Скрипт запуска чистит локальные дубликаты; `bot.py` страхует advisory‑локом.
- Ранее наблюдался TelegramConflictError из‑за параллельных инстансов; локально устранено.

## Быстрые команды

- Запуск: `./start_bot.sh`
- Остановка: `./stop_bot.sh`
- Статус: `./status_bot.sh`
- Логи: `tail -f logs/bot_output.log` и `logs/bot.log`
- Инициализация БД: `python database/db_init.py`

## Чек‑лист перед тестом

- `.env` содержит `BOT_TOKEN` и параметры БД.
- `./stop_bot.sh` (на всякий случай), затем `./start_bot.sh`.
- Нет дублирующихся ответов в чате.
- Выбор A4/A5 → возврат в главное меню.
- PDF: визуально проверить отступы/вписывание текста в клетки.

## Идеи/бэклог

- Подготовить VPS, включить webhook, настроить HTTPS reverse‑proxy.
- Пресеты форматирования (кнопки: размер шрифта, интервал).
- История последних конспектов пользователя.
- Метрики/алерты (Prometheus/Grafana/BetterStack).

## Точки внимания

- Не запускать бота одновременно из IDE и `start_bot.sh`.
- Локально порт не используется (polling). В webhook – `WEBAPP_PORT`.
- При смене режима (webhook↔polling) нужен перезапуск.

## Деплой на VPS (one-step)

- Скрипт: `deploy_vps.sh` — устанавливает зависимости, создаёт venv, пишет `.env`, настраивает `systemd` и `nginx`, включает webhook.
- Пример переменных: см. `.env.example` (нужны `BOT_TOKEN`, `DOMAIN`, `DB_*`).
- Запуск:
  - Скопируй репозиторий на VPS (например, в `/opt/consp_bot`).
  - Выполни (от root):
    ```bash
    BOT_TOKEN=xxxx DOMAIN=bot.example.com DB_PASSWORD=... bash deploy_vps.sh
    ```
  - Выпусти SSL (certbot) и перезапусти nginx.
- Сервис: `systemctl status consp-bot`, логи `journalctl -u consp-bot -f`.
- После включения webhook локальный polling запускать не нужно.
