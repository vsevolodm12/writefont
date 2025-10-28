# Чеклист перед запуском бота

## ✅ Зависимости установлены!
Все Python пакеты установлены.

## ⚠️ Следующие шаги:

### 1. Запустить PostgreSQL:
```bash
brew services start postgresql@15
# ИЛИ если другой версии:
brew services start postgresql
```

### 2. Инициализировать базу данных:
```bash
source venv/bin/activate
python database/db_init.py
```

### 3. Проверить .env файл:
Убедитесь что в `.env` есть:
- `BOT_TOKEN` - установлен
- `DB_PASSWORD` - пароль PostgreSQL
- `ADMIN_USER_ID` - можно оставить как есть (не используется)

### 4. Запустить бота:
```bash
./start_bot.sh
```

### 5. Проверить статус:
```bash
./status_bot.sh
```

### 6. Проверить логи:
```bash
tail -f logs/bot.log
```

## Если PostgreSQL не установлен:

```bash
brew install postgresql@15
brew services start postgresql@15
```

## После запуска PostgreSQL:
1. Настройте пароль (если нужно)
2. Запустите `python database/db_init.py`
3. Запустите `./start_bot.sh`

