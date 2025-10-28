# Проверка готовности перед запуском

## Ответы на ваши вопросы:

### 1. Работают ли базы данных?

**Проверить подключение:**
```bash
source venv/bin/activate
python database/test_connection.py
```

**Инициализировать БД (если еще не сделано):**
```bash
python database/db_init.py
```

**Полная проверка готовности:**
```bash
python check_ready.py
```

### 2. Как смотреть логи?

Логи сохраняются в файл `logs/bot.log` и выводятся в консоль.

**Просмотр логов в реальном времени:**
```bash
tail -f logs/bot.log
```

**Просмотр последних 50 строк:**
```bash
tail -n 50 logs/bot.log
```

**Очистка логов:**
```bash
> logs/bot.log
```

### 3. Что нужно для автономной работы?

#### ✅ Обязательно:
1. **.env файл** с заполненными полями:
   - `BOT_TOKEN` - токен бота (уже установлен)
   - `ADMIN_USER_ID` - ваш Telegram ID (получить у @userinfobot)
   - `DB_PASSWORD` - пароль PostgreSQL

2. **PostgreSQL запущен:**
   ```bash
   brew services start postgresql@15
   ```

3. **База данных инициализирована:**
   ```bash
   python database/db_init.py
   ```

4. **Зависимости установлены:**
   ```bash
   source venv/bin/activate
   pip install -r requirements.txt
   ```

#### ✅ Автоматически создаются:
- Директория `logs/` для логов
- Директория `fonts/` для шрифтов
- Директория `generated/` для PDF

#### 🔍 Быстрая проверка всего сразу:
```bash
python check_ready.py
```

## Перед запуском выполните:

```bash
# 1. Активируйте окружение
source venv/bin/activate

# 2. Проверьте готовность
python check_ready.py

# 3. Если все ОК - запустите бота
python bot.py
```

## Решение проблем:

**Ошибка: "ModuleNotFoundError: No module named 'database'"**
- Убедитесь что запускаете из корневой директории проекта
- Активируйте виртуальное окружение: `source venv/bin/activate`

**Ошибка подключения к БД:**
- Проверьте что PostgreSQL запущен: `brew services list`
- Проверьте пароль в `.env`
- Инициализируйте БД: `python database/db_init.py`

**Бот не отвечает:**
- Проверьте `ADMIN_USER_ID` в `.env`
- Проверьте логи: `tail -f logs/bot.log`

