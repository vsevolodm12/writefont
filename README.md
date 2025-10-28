# Telegram Bot для генерации PDF-конспектов

Telegram-бот для создания PDF-конспектов с использованием кастомного рукописного шрифта.

## Возможности

- Загрузка TTF-шрифта пользователя
- Генерация PDF в формате A4 или тетрадного листа
- Локальное хранение всех данных
- Работа только для одного пользователя (администратора)

## Технологии

- Python 3.8+
- Aiogram 3.x (Telegram Bot Framework)
- ReportLab (PDF генерация)
- Pillow (обработка изображений)
- PostgreSQL (база данных)
- psycopg2 (драйвер PostgreSQL)

## Установка и настройка

### 1. Создание виртуального окружения

```bash
cd /Users/vsevolodmarcenko/Desktop/consp_bot
python3 -m venv venv
source venv/bin/activate
```

### 2. Установка зависимостей

```bash
pip install -r requirements.txt
```

### 3. Установка PostgreSQL на macOS

#### Вариант 1: Используя Homebrew (рекомендуется)

```bash
# Установка Homebrew (если не установлен)
/bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"

# Установка PostgreSQL
brew install postgresql@15

# Запуск PostgreSQL
brew services start postgresql@15

# Или запуск без автозапуска
pg_ctl -D /opt/homebrew/var/postgresql@15 start
```

#### Вариант 2: Используя официальный установщик

Скачайте установщик с [официального сайта PostgreSQL](https://www.postgresql.org/download/macosx/)

### 4. Создание пользователя и базы данных

После установки PostgreSQL выполните:

```bash
# Войти в PostgreSQL
psql postgres

# Создать пользователя (если нужно)
CREATE USER postgres WITH PASSWORD 'your_password';

# Дать права суперпользователя (для MVP)
ALTER USER postgres WITH SUPERUSER;

# Выйти
\q
```

### 5. Настройка переменных окружения

Скопируйте `.env.example` в `.env` и заполните значения:

```bash
cp .env.example .env
```

Отредактируйте `.env`:
- `BOT_TOKEN` - токен вашего Telegram-бота (получить у @BotFather)
- `ADMIN_USER_ID` - ваш Telegram user ID (получить у @userinfobot)
- `DB_PASSWORD` - пароль для PostgreSQL

### 6. Инициализация базы данных

```bash
python database/db_init.py
```

Это создаст:
- Базу данных `consp_bot`
- Таблицу `users` для хранения данных пользователя
- Таблицу `jobs` для хранения задач генерации PDF

## Структура проекта

```
consp_bot/
├── database/
│   ├── __init__.py
│   ├── connection.py      # Подключение к БД
│   └── db_init.py         # Инициализация БД
├── fonts/                 # Загруженные шрифты (создается автоматически)
├── jobs/                  # Сгенерированные PDF (создается автоматически)
├── .env                   # Переменные окружения (не в git)
├── .env.example           # Пример переменных окружения
├── .gitignore
├── requirements.txt       # Зависимости проекта
└── README.md
```

## Использование

```bash
# Активировать виртуальное окружение
source venv/bin/activate

# Запустить бота
python bot.py
```

## Структура базы данных

### Таблица `users`

- `user_id` (BIGINT, PRIMARY KEY) - Telegram ID пользователя
- `font_path` (TEXT) - путь к загруженному TTF-шрифту
- `page_format` (VARCHAR) - выбранный формат страницы (A4 или notebook)
- `created_at` (TIMESTAMP) - время создания записи
- `updated_at` (TIMESTAMP) - время последнего обновления

### Таблица `jobs`

- `id` (SERIAL, PRIMARY KEY) - ID задачи
- `user_id` (BIGINT) - ID пользователя (FK)
- `text_content` (TEXT) - текст для генерации PDF
- `pdf_path` (TEXT) - путь к сгенерированному PDF
- `created_at` (TIMESTAMP) - время создания задачи
- `completed_at` (TIMESTAMP) - время завершения задачи
- `execution_time_ms` (INTEGER) - время выполнения в миллисекундах
- `status` (VARCHAR) - статус задачи (pending, completed, failed)

## Полезные команды PostgreSQL

```bash
# Остановить PostgreSQL
brew services stop postgresql@15

# Перезапустить PostgreSQL
brew services restart postgresql@15

# Подключиться к базе данных
psql -d consp_bot -U postgres

# Посмотреть все таблицы
\dt

# Посмотреть структуру таблицы
\d users
\d jobs

# Удалить базу данных (если нужно пересоздать)
DROP DATABASE consp_bot;
```

## Troubleshooting

### Ошибка подключения к PostgreSQL

Убедитесь, что PostgreSQL запущен:
```bash
brew services list
```

### Ошибка прав доступа

Проверьте пароль в `.env` и права пользователя:
```bash
psql -U postgres -d consp_bot
```

### Не найден модуль psycopg2

Переустановите зависимости:
```bash
pip install --upgrade psycopg2-binary
```

