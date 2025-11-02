"""
Утилиты для работы с базой данных
"""

from database.connection import get_db_connection, return_db_connection
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
        if cursor:
            cursor.close()
        if conn:
            return_db_connection(conn)


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
        # Пишем в список последних шрифтов
        try:
            add_recent_font(user_id, font_path)
        except Exception:
            # Не валим основной поток при ошибке записи истории
            pass
        return cursor.rowcount > 0
    finally:
        if cursor:
            cursor.close()
        if conn:
            return_db_connection(conn)


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
        if cursor:
            cursor.close()
        if conn:
            return_db_connection(conn)


def get_user_info(user_id: int):
    """Получает информацию о пользователе."""
    import json
    conn = get_db_connection()
    cursor = conn.cursor()
    
    try:
        cursor.execute(
            "SELECT user_id, font_path, page_format, COALESCE(grid_enabled, FALSE), variant_fonts FROM users WHERE user_id = %s",
            (user_id,)
        )
        user = cursor.fetchone()
        
        if user:
            # Парсим JSON для variant_fonts
            variant_fonts = []
            if len(user) > 4 and user[4]:
                try:
                    variant_fonts = json.loads(user[4]) if isinstance(user[4], str) else user[4]
                except (json.JSONDecodeError, TypeError):
                    variant_fonts = []
            
            return {
                'user_id': user[0],
                'font_path': user[1],
                'page_format': user[2],
                'grid_enabled': user[3] if len(user) > 3 else False,
                'variant_fonts': variant_fonts if isinstance(variant_fonts, list) else []
            }
        return None
    finally:
        if cursor:
            cursor.close()
        if conn:
            return_db_connection(conn)


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
        if cursor:
            cursor.close()
        if conn:
            return_db_connection(conn)


def _ensure_recent_fonts_table(cursor):
    """Гарантирует наличие таблицы для хранения последних шрифтов."""
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS user_recent_fonts (
            id SERIAL PRIMARY KEY,
            user_id BIGINT NOT NULL,
            font_path TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        """)
    # Индекс по пользователю и времени
    cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_user_recent_fonts_user_time
        ON user_recent_fonts (user_id, created_at DESC);
    """)


def add_recent_font(user_id: int, font_path: str, keep_last: int = 10):
    """Добавляет запись о недавно выбранном/загруженном шрифте, хранит только последние N."""
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        _ensure_recent_fonts_table(cursor)
        # Удалим старые дубликаты того же пути, чтобы поднять его наверх
        cursor.execute(
            "DELETE FROM user_recent_fonts WHERE user_id = %s AND font_path = %s",
            (user_id, font_path)
        )
        # Вставим свежую запись
        cursor.execute(
            "INSERT INTO user_recent_fonts (user_id, font_path) VALUES (%s, %s)",
            (user_id, font_path)
        )
        # Оставим только последние keep_last
        cursor.execute(
            """
            DELETE FROM user_recent_fonts
            WHERE id IN (
                SELECT id FROM user_recent_fonts
                WHERE user_id = %s
                ORDER BY created_at DESC, id DESC
                OFFSET %s
            )
            """,
            (user_id, keep_last)
        )
        conn.commit()
    finally:
        if cursor:
            cursor.close()
        if conn:
            return_db_connection(conn)


def get_recent_fonts(user_id: int, limit: int = 3):
    """Возвращает список путей к последним шрифтам пользователя (не более limit)."""
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        _ensure_recent_fonts_table(cursor)
        cursor.execute(
            """
            SELECT font_path
            FROM user_recent_fonts
            WHERE user_id = %s
            ORDER BY created_at DESC, id DESC
            LIMIT %s
            """,
            (user_id, limit)
        )
        rows = cursor.fetchall() or []
        return [r[0] for r in rows]
    finally:
        if cursor:
            cursor.close()
        if conn:
            return_db_connection(conn)


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
        if cursor:
            cursor.close()
        if conn:
            return_db_connection(conn)


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
        if cursor:
            cursor.close()
        if conn:
            return_db_connection(conn)


def update_user_variant_fonts(user_id: int, variant_fonts: list):
    """Обновляет список вариативных шрифтов пользователя."""
    import json
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
            # Добавляем колонку если не существует
            cursor.execute("""
                ALTER TABLE users 
                ADD COLUMN variant_fonts JSONB DEFAULT '[]'::jsonb
            """)
            conn.commit()
        
        cursor.execute(
            """
            UPDATE users 
            SET variant_fonts = %s, updated_at = CURRENT_TIMESTAMP
            WHERE user_id = %s
            """,
            (json.dumps(variant_fonts), user_id)
        )
        conn.commit()
        return cursor.rowcount > 0
    finally:
        if cursor:
            cursor.close()
        if conn:
            return_db_connection(conn)


def add_variant_font(user_id: int, font_path: str):
    """Добавляет шрифт в список вариативных шрифтов пользователя."""
    user = get_user_info(user_id)
    if not user:
        return False
    
    variant_fonts = user.get('variant_fonts', [])
    if font_path not in variant_fonts:
        variant_fonts.append(font_path)
        return update_user_variant_fonts(user_id, variant_fonts)
    return True  # Шрифт уже есть - это не ошибка


def remove_variant_font(user_id: int, font_path: str):
    """Удаляет шрифт из списка вариативных шрифтов пользователя."""
    user = get_user_info(user_id)
    if not user:
        return False
    
    variant_fonts = user.get('variant_fonts', [])
    if font_path in variant_fonts:
        variant_fonts.remove(font_path)
        return update_user_variant_fonts(user_id, variant_fonts)
    return False


def reset_user_fonts(user_id: int):
    """Сбрасывает все шрифты пользователя (основной и вариативные)."""
    import json
    conn = get_db_connection()
    cursor = conn.cursor()
    
    try:
        # Проверяем существует ли колонка variant_fonts
        cursor.execute("""
            SELECT column_name 
            FROM information_schema.columns 
            WHERE table_name='users' AND column_name='variant_fonts'
        """)
        
        if not cursor.fetchone():
            # Добавляем колонку если не существует
            cursor.execute("""
                ALTER TABLE users 
                ADD COLUMN variant_fonts JSONB DEFAULT '[]'::jsonb
            """)
            conn.commit()
        
        cursor.execute(
            """
            UPDATE users 
            SET font_path = NULL, variant_fonts = %s, updated_at = CURRENT_TIMESTAMP
            WHERE user_id = %s
            """,
            (json.dumps([]), user_id)
        )
        conn.commit()
        return cursor.rowcount > 0
    finally:
        if cursor:
            cursor.close()
        if conn:
            return_db_connection(conn)

