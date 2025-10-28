"""
Скрипт для инициализации базы данных PostgreSQL.
Создает необходимые таблицы для работы бота.
"""

import psycopg2
from psycopg2.extensions import ISOLATION_LEVEL_AUTOCOMMIT
import os
from dotenv import load_dotenv

load_dotenv()


def create_database():
    """Создает базу данных, если она не существует."""
    db_name = os.getenv('DB_NAME', 'consp_bot')
    db_user = os.getenv('DB_USER', 'postgres')
    db_password = os.getenv('DB_PASSWORD', '')
    db_host = os.getenv('DB_HOST', 'localhost')
    
    # Подключаемся к системной БД postgres для создания новой БД
    try:
        conn = psycopg2.connect(
            dbname='postgres',
            user=db_user,
            password=db_password,
            host=db_host
        )
        conn.set_isolation_level(ISOLATION_LEVEL_AUTOCOMMIT)
        cursor = conn.cursor()
        
        # Проверяем, существует ли база данных
        cursor.execute(
            "SELECT 1 FROM pg_database WHERE datname = %s",
            (db_name,)
        )
        exists = cursor.fetchone()
        
        if not exists:
            cursor.execute(f'CREATE DATABASE {db_name}')
            print(f"База данных '{db_name}' успешно создана.")
        else:
            print(f"База данных '{db_name}' уже существует.")
        
        cursor.close()
        conn.close()
    except Exception as e:
        print(f"Ошибка при создании базы данных: {e}")
        raise


def create_tables():
    """Создает необходимые таблицы в базе данных."""
    db_name = os.getenv('DB_NAME', 'consp_bot')
    db_user = os.getenv('DB_USER', 'postgres')
    db_password = os.getenv('DB_PASSWORD', '')
    db_host = os.getenv('DB_HOST', 'localhost')
    
    try:
        conn = psycopg2.connect(
            dbname=db_name,
            user=db_user,
            password=db_password,
            host=db_host
        )
        cursor = conn.cursor()
        
        # Создание таблицы users
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS users (
                user_id BIGINT PRIMARY KEY,
                font_path TEXT,
                page_format VARCHAR(20) DEFAULT 'A4',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
        """)
        
        # Создание таблицы jobs
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS jobs (
                id SERIAL PRIMARY KEY,
                user_id BIGINT NOT NULL REFERENCES users(user_id) ON DELETE CASCADE,
                text_content TEXT NOT NULL,
                pdf_path TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                completed_at TIMESTAMP,
                execution_time_ms INTEGER,
                status VARCHAR(20) DEFAULT 'pending'
            );
        """)
        
        conn.commit()
        print("Таблицы успешно созданы.")
        
        cursor.close()
        conn.close()
    except Exception as e:
        print(f"Ошибка при создании таблиц: {e}")
        raise


def init_database():
    """Главная функция для инициализации базы данных."""
    print("Инициализация базы данных...")
    create_database()
    create_tables()
    print("База данных успешно инициализирована!")


if __name__ == "__main__":
    init_database()

