"""
Конфигурация проекта
"""

import os
from dotenv import load_dotenv

load_dotenv()

# Telegram Bot Configuration
BOT_TOKEN = os.getenv('BOT_TOKEN')
try:
    ADMIN_USER_ID = int(os.getenv('ADMIN_USER_ID', 0))
except (ValueError, TypeError):
    ADMIN_USER_ID = 0  # Если не установлен, по умолчанию 0 (не используется)

# Database Configuration
DB_NAME = os.getenv('DB_NAME', 'consp_bot')
DB_USER = os.getenv('DB_USER', 'postgres')
DB_PASSWORD = os.getenv('DB_PASSWORD', '')
DB_HOST = os.getenv('DB_HOST', 'localhost')
DB_PORT = os.getenv('DB_PORT', '5432')

# Webhook/Deploy Configuration
# Если задан WEBHOOK_URL — запускаем режим webhook (VPS/прод), иначе — polling (локально)
WEBHOOK_URL = os.getenv('WEBHOOK_URL', '').strip()
WEBHOOK_SECRET = os.getenv('WEBHOOK_SECRET', '').strip()  # рекомендуется задать
WEBAPP_HOST = os.getenv('WEBAPP_HOST', '0.0.0.0')  # хост HTTP-сервера для webhook
WEBAPP_PORT = int(os.getenv('WEBAPP_PORT', '8080'))       # порт HTTP-сервера для webhook
WEBHOOK_PATH = os.getenv('WEBHOOK_PATH', '/webhook')      # путь, по которому Telegram стучится

# Directories
FONTS_DIR = 'fonts'
JOBS_DIR = 'jobs'
GENERATED_DIR = 'generated'
TEMPLATES_DIR = 'templates'

# Creator font - шрифт создателя для тестирования
# Папка с шрифтами создателя (sevafont)
CREATOR_FONT_DIR = 'sevafont'
CREATOR_FONT_PATH = None  # Будет определен при первом использовании

# Page Formats
PAGE_FORMATS = {
    'A4': 'A4',
    'A5': 'A5'
}


def is_dev_branch() -> bool:
    """Проверяет, находимся ли мы на dev ветке"""
    try:
        import subprocess
        result = subprocess.run(
            ['git', 'branch', '--show-current'],
            capture_output=True,
            text=True,
            cwd=os.path.dirname(os.path.abspath(__file__))
        )
        current_branch = result.stdout.strip()
        return current_branch == 'dev'
    except Exception:
        # Если git недоступен или произошла ошибка, возвращаем False
        return False

