"""
Скрипт для добавления колонки grid_enabled в таблицу users
"""

from database.connection import get_db_connection

def add_grid_column():
    """Добавляет колонку grid_enabled в таблицу users"""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    try:
        # Проверяем существует ли колонка
        cursor.execute("""
            SELECT column_name 
            FROM information_schema.columns 
            WHERE table_name='users' AND column_name='grid_enabled'
        """)
        
        if not cursor.fetchone():
            # Добавляем колонку
            cursor.execute("""
                ALTER TABLE users 
                ADD COLUMN grid_enabled BOOLEAN DEFAULT FALSE
            """)
            conn.commit()
            print("✓ Колонка grid_enabled добавлена")
        else:
            print("✓ Колонка grid_enabled уже существует")
        
    except Exception as e:
        print(f"Ошибка: {e}")
        conn.rollback()
    finally:
        cursor.close()
        conn.close()

if __name__ == "__main__":
    add_grid_column()

