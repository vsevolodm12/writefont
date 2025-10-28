"""
Модуль для работы с подключением к базе данных PostgreSQL.
"""

import psycopg2
import os
from dotenv import load_dotenv

load_dotenv()


def get_db_connection():
    """Возвращает подключение к базе данных."""
    try:
        conn = psycopg2.connect(
            dbname=os.getenv('DB_NAME', 'consp_bot'),
            user=os.getenv('DB_USER', 'postgres'),
            password=os.getenv('DB_PASSWORD', ''),
            host=os.getenv('DB_HOST', 'localhost'),
            port=os.getenv('DB_PORT', '5432'),
            connect_timeout=5
        )
        return conn
    except psycopg2.OperationalError as e:
        raise ConnectionError(f"Не удалось подключиться к базе данных: {e}")
    except Exception as e:
        raise ConnectionError(f"Ошибка подключения: {e}")

