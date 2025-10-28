"""
Скрипт для проверки подключения к базе данных PostgreSQL.
"""

import sys
from database.connection import get_db_connection


def test_connection():
    """Проверяет подключение к базе данных."""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Выполняем простой запрос
        cursor.execute("SELECT version();")
        version = cursor.fetchone()
        print(f"✓ Успешное подключение к PostgreSQL")
        print(f"  Версия: {version[0]}")
        
        # Проверяем наличие таблиц
        cursor.execute("""
            SELECT table_name 
            FROM information_schema.tables 
            WHERE table_schema = 'public'
            ORDER BY table_name;
        """)
        tables = cursor.fetchall()
        
        if tables:
            print(f"\n✓ Найдено таблиц: {len(tables)}")
            for table in tables:
                print(f"  - {table[0]}")
        else:
            print("\n⚠ Таблицы не найдены. Запустите database/db_init.py")
        
        cursor.close()
        conn.close()
        return True
        
    except Exception as e:
        print(f"✗ Ошибка подключения к базе данных: {e}")
        print("\nПроверьте:")
        print("1. PostgreSQL запущен (brew services list)")
        print("2. Пароль в .env файле корректен")
        print("3. База данных создана (запустите database/db_init.py)")
        return False


if __name__ == "__main__":
    success = test_connection()
    sys.exit(0 if success else 1)

