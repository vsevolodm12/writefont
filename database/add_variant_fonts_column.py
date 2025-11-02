"""
Скрипт для добавления колонки variant_fonts в таблицу users
"""

from database.connection import get_db_connection

def add_variant_fonts_column():
    """Добавляет колонку variant_fonts в таблицу users"""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    try:
        # Проверяем существует ли колонка
        cursor.execute("""
            SELECT column_name 
            FROM information_schema.columns 
            WHERE table_name='users' AND column_name='variant_fonts'
        """)
        
        if not cursor.fetchone():
            # Добавляем колонку
            cursor.execute("""
                ALTER TABLE users 
                ADD COLUMN variant_fonts JSONB DEFAULT '[]'::jsonb
            """)
            conn.commit()
            print("✓ Колонка variant_fonts добавлена")
        else:
            print("✓ Колонка variant_fonts уже существует")
        
    except Exception as e:
        print(f"Ошибка: {e}")
        conn.rollback()
    finally:
        cursor.close()
        conn.close()

if __name__ == "__main__":
    add_variant_fonts_column()

