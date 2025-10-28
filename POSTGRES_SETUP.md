# Инструкция по установке и настройке PostgreSQL на macOS

## Способ 1: Установка через Homebrew (рекомендуется)

### Шаг 1: Установка Homebrew

Если Homebrew не установлен, выполните:

```bash
/bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
```

### Шаг 2: Установка PostgreSQL

```bash
brew install postgresql@15
```

### Шаг 3: Запуск PostgreSQL

```bash
# Запуск с автозапуском при перезагрузке
brew services start postgresql@15

# Или запуск без автозапуска
pg_ctl -D /opt/homebrew/var/postgresql@15 start
```

### Шаг 4: Проверка статуса

```bash
# Проверить, запущен ли PostgreSQL
brew services list

# Или проверить процессы
ps aux | grep postgres
```

### Шаг 5: Первоначальная настройка

По умолчанию PostgreSQL создает пользователя с именем вашего текущего пользователя macOS. Для удобства можно использовать этого пользователя или создать нового:

```bash
# Подключиться к PostgreSQL
psql postgres

# Создать нового пользователя (если нужно)
CREATE USER postgres WITH PASSWORD 'your_password';
ALTER USER postgres WITH SUPERUSER;

# Выйти
\q
```

## Способ 2: Установка через официальный установщик

1. Скачайте установщик с [официального сайта](https://www.postgresql.org/download/macosx/)
2. Запустите установщик и следуйте инструкциям
3. Запомните пароль, который вы установите для пользователя `postgres`
4. PostgreSQL будет автоматически запускаться при загрузке системы

## Настройка для проекта

### 1. Создание базы данных

После установки PostgreSQL выполните:

```bash
# Активируйте виртуальное окружение
source venv/bin/activate

# Инициализируйте базу данных
python database/db_init.py
```

### 2. Проверка подключения

```bash
# Проверьте подключение к базе данных
python database/test_connection.py
```

### 3. Полезные команды

```bash
# Остановить PostgreSQL
brew services stop postgresql@15

# Перезапустить PostgreSQL
brew services restart postgresql@15

# Подключиться к базе данных через psql
psql -d consp_bot -U postgres

# Или просто
psql postgres
```

## Решение проблем

### Ошибка: "could not connect to server"

**Причина:** PostgreSQL не запущен

**Решение:**
```bash
brew services start postgresql@15
```

### Ошибка: "password authentication failed"

**Причина:** Неверный пароль в `.env` файле

**Решение:**
1. Проверьте пароль в `.env`
2. Если забыли пароль, сбросьте его:
```bash
psql postgres
ALTER USER postgres WITH PASSWORD 'new_password';
\q
```

### Ошибка: "database does not exist"

**Причина:** База данных не создана

**Решение:**
```bash
python database/db_init.py
```

### Ошибка: "role does not exist"

**Причина:** Пользователь PostgreSQL не существует

**Решение:**
```bash
psql postgres
CREATE USER postgres WITH PASSWORD 'your_password';
ALTER USER postgres WITH SUPERUSER;
\q
```

### Проверка версии PostgreSQL

```bash
psql --version
```

или

```bash
psql postgres -c "SELECT version();"
```

## Работа с базой данных

### Просмотр всех баз данных

```bash
psql postgres -c "\l"
```

### Просмотр таблиц в базе данных

```bash
psql -d consp_bot -c "\dt"
```

### Просмотр структуры таблицы

```bash
psql -d consp_bot -c "\d users"
psql -d consp_bot -c "\d jobs"
```

### Просмотр данных в таблице

```bash
psql -d consp_bot -c "SELECT * FROM users;"
psql -d consp_bot -c "SELECT * FROM jobs;"
```

### Удаление базы данных (для пересоздания)

```bash
psql postgres -c "DROP DATABASE consp_bot;"
python database/db_init.py
```

## Пути по умолчанию (Homebrew)

- **Данные:** `/opt/homebrew/var/postgresql@15`
- **Конфигурация:** `/opt/homebrew/var/postgresql@15/postgresql.conf`
- **Логи:** `/opt/homebrew/var/log/postgresql@15.log`

## Дополнительная информация

- [Документация PostgreSQL](https://www.postgresql.org/docs/)
- [PostgreSQL Homebrew formula](https://formulae.brew.sh/formula/postgresql@15)

