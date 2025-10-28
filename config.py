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

# Directories
FONTS_DIR = 'fonts'
JOBS_DIR = 'jobs'
GENERATED_DIR = 'generated'

# Page Formats
PAGE_FORMATS = {
    'A4': 'A4',
    'A5': 'A5'
}

