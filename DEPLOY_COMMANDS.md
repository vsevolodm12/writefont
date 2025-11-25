# Команды для деплоя на проде

## 1. Обновление репо и БД (одна команда)

На сервере выполните:

```bash
cd /opt/consp_bot && git pull origin main && source venv/bin/activate && alembic upgrade head && deactivate && sudo systemctl restart consp-bot
```

Или используйте скрипт:

```bash
./update_server.sh
```

## 2. Копирование шаблонов и шрифтов на сервер

### С локальной машины на сервер:

```bash
# Шаблоны
rsync -avz templates/ user@server:/opt/consp_bot/templates/

# Шрифты создателя (папка sevafont)
rsync -avz sevafont/ user@server:/opt/consp_bot/sevafont/
```

### Или через scp:

```bash
# Шаблоны
scp -r templates/ user@server:/opt/consp_bot/

# Шрифты создателя
scp -r sevafont/ user@server:/opt/consp_bot/
```

### Важно:
- Замените `user@server` на ваши реальные данные (например, `root@your-server.com`)
- Убедитесь, что папки `templates/` и `sevafont/` существуют на сервере
- После копирования проверьте, что файлы на месте:
  ```bash
  ls -la /opt/consp_bot/templates/
  ls -la /opt/consp_bot/sevafont/
  ```

## 3. Проверка работы

```bash
# Проверка статуса сервиса
sudo systemctl status consp-bot

# Просмотр логов
sudo journalctl -u consp-bot -f
```

