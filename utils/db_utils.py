"""
Утилиты для работы с базой данных
"""

from database.connection import get_db_connection
from config import FONTS_DIR, ADMIN_USER_ID
import os


def is_admin(user_id: int) -> bool:
    """Проверяет, является ли пользователь администратором."""
    return user_id == ADMIN_USER_ID


def get_or_create_user(user_id: int):
    """Получает пользователя из БД или создает нового."""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    try:
        # Проверяем, существует ли пользователь
        cursor.execute("SELECT * FROM users WHERE user_id = %s", (user_id,))
        user = cursor.fetchone()
        
        if not user:
            # Создаем нового пользователя
            cursor.execute(
                """
                INSERT INTO users (user_id, page_format)
                VALUES (%s, %s)
                RETURNING user_id, font_path, page_format
                """,
                (user_id, 'A4')
            )
            conn.commit()
            user = cursor.fetchone()
        
        return {
            'user_id': user[0],
            'font_path': user[1],
            'page_format': user[2]
        }
    finally:
        cursor.close()
        conn.close()


def update_user_font(user_id: int, font_path: str):
    """Обновляет путь к шрифту пользователя."""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    try:
        cursor.execute(
            """
            UPDATE users 
            SET font_path = %s, updated_at = CURRENT_TIMESTAMP
            WHERE user_id = %s
            """,
            (font_path, user_id)
        )
        conn.commit()
        return cursor.rowcount > 0
    finally:
        cursor.close()
        conn.close()


def update_user_page_format(user_id: int, page_format: str):
    """Обновляет формат страницы пользователя."""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    try:
        cursor.execute(
            """
            UPDATE users 
            SET page_format = %s, updated_at = CURRENT_TIMESTAMP
            WHERE user_id = %s
            """,
            (page_format, user_id)
        )
        conn.commit()
        return cursor.rowcount > 0
    finally:
        cursor.close()
        conn.close()


def get_user_info(user_id: int):
    """Получает информацию о пользователе."""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    try:
        cursor.execute(
            "SELECT user_id, font_path, page_format, COALESCE(grid_enabled, FALSE) FROM users WHERE user_id = %s",
            (user_id,)
        )
        user = cursor.fetchone()
        
        if user:
            return {
                'user_id': user[0],
                'font_path': user[1],
                'page_format': user[2],
                'grid_enabled': user[3] if len(user) > 3 else False
            }
        return None
    finally:
        cursor.close()
        conn.close()


def update_user_grid_setting(user_id: int, grid_enabled: bool):
    """Обновляет настройку сетки пользователя."""
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
            # Добавляем колонку если не существует
            cursor.execute("""
                ALTER TABLE users 
                ADD COLUMN grid_enabled BOOLEAN DEFAULT FALSE
            """)
            conn.commit()
        
        cursor.execute(
            """
            UPDATE users 
            SET grid_enabled = %s, updated_at = CURRENT_TIMESTAMP
            WHERE user_id = %s
            """,
            (grid_enabled, user_id)
        )
        conn.commit()
        return cursor.rowcount > 0
    finally:
        cursor.close()
        conn.close()


def save_font_file(file, filename: str) -> str:
    """Сохраняет файл шрифта и возвращает путь к нему."""
    os.makedirs(FONTS_DIR, exist_ok=True)
    file_path = os.path.join(FONTS_DIR, filename)
    
    # Читаем файл по частям если это файловый объект
    with open(file_path, 'wb') as f:
        if hasattr(file, 'read'):
            # Если это BytesIO или файловый объект
            content = file.read()
            if isinstance(content, bytes):
                f.write(content)
            else:
                # Если read() вернул что-то другое, читаем заново
                file.seek(0)
                f.write(file.read())
        else:
            # Если это просто bytes
            f.write(file)
    
    return file_path


def update_job_pdf_path(job_id: int, pdf_path: str, execution_time_ms: int = None):
    """Обновляет путь к PDF и статус задачи в БД."""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    try:
        if execution_time_ms is not None:
            cursor.execute(
                """
                UPDATE jobs 
                SET pdf_path = %s, status = %s, completed_at = CURRENT_TIMESTAMP, 
                    execution_time_ms = %s
                WHERE id = %s
                """,
                (pdf_path, 'completed', execution_time_ms, job_id)
            )
        else:
            cursor.execute(
                """
                UPDATE jobs 
                SET pdf_path = %s, status = %s, completed_at = CURRENT_TIMESTAMP
                WHERE id = %s
                """,
                (pdf_path, 'completed', job_id)
            )
        conn.commit()
        return cursor.rowcount > 0
    finally:
        cursor.close()
        conn.close()


def update_job_status_failed(job_id: int, error_message: str = None):
    """Обновляет статус задачи на failed."""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    try:
        if error_message:
            # Можно добавить поле error_message в таблицу jobs если нужно
            cursor.execute(
                """
                UPDATE jobs 
                SET status = %s, completed_at = CURRENT_TIMESTAMP
                WHERE id = %s
                """,
                ('failed', job_id)
            )
        else:
            cursor.execute(
                """
                UPDATE jobs 
                SET status = %s, completed_at = CURRENT_TIMESTAMP
                WHERE id = %s
                """,
                ('failed', job_id)
            )
        conn.commit()
        return cursor.rowcount > 0
    finally:
        cursor.close()
        conn.close()

