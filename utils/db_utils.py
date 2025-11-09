"""
Утилиты для работы с базой данных
"""

from __future__ import annotations

from typing import Dict, List, Optional

from database.connection import get_db_connection, return_db_connection
from config import FONTS_DIR, ADMIN_USER_ID
from utils.font_analyzer import analyze_font, FontCapabilities
import json
import os


FONT_REQUIREMENTS = {
    "cyrillic_full": 3,
    "digits": 2,
    "latin": 2,
}

FONT_TYPE_ORDER = ("cyrillic_full", "cyrillic_partial", "latin", "digits", "mixed", "other")


def is_admin(user_id: int) -> bool:
    """Проверяет, является ли пользователь администратором."""
    return user_id == ADMIN_USER_ID


def _ensure_fonts_table(cursor) -> None:
    cursor.execute(
        """
        SELECT COUNT(*)
        FROM information_schema.tables
        WHERE table_name = 'fonts'
        """
    )
    if cursor.fetchone()[0] == 0:
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS fonts (
                id SERIAL PRIMARY KEY,
                user_id BIGINT NOT NULL,
                path TEXT NOT NULL,
                font_type VARCHAR(32) NOT NULL,
                supports_cyrillic_lower BOOLEAN DEFAULT FALSE,
                supports_cyrillic_upper BOOLEAN DEFAULT FALSE,
                supports_latin_lower BOOLEAN DEFAULT FALSE,
                supports_latin_upper BOOLEAN DEFAULT FALSE,
                supports_digits BOOLEAN DEFAULT FALSE,
                supports_symbols BOOLEAN DEFAULT FALSE,
                coverage_score INTEGER DEFAULT 0,
                is_base BOOLEAN DEFAULT FALSE,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE (user_id, path)
            );
            """
        )
        cursor.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_fonts_user_type
            ON fonts (user_id, font_type);
            """
        )


def _decide_font_type(capabilities: FontCapabilities) -> str:
    return capabilities.font_type


def _insert_or_update_font(
    cursor,
    user_id: int,
    path: str,
    capabilities: FontCapabilities,
    is_base: bool,
) -> None:
    cursor.execute(
        """
        INSERT INTO fonts (
            user_id,
            path,
            font_type,
            supports_cyrillic_lower,
            supports_cyrillic_upper,
            supports_latin_lower,
            supports_latin_upper,
            supports_digits,
            supports_symbols,
            coverage_score,
            is_base
        )
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        ON CONFLICT (user_id, path) DO UPDATE SET
            font_type = EXCLUDED.font_type,
            supports_cyrillic_lower = EXCLUDED.supports_cyrillic_lower,
            supports_cyrillic_upper = EXCLUDED.supports_cyrillic_upper,
            supports_latin_lower = EXCLUDED.supports_latin_lower,
            supports_latin_upper = EXCLUDED.supports_latin_upper,
            supports_digits = EXCLUDED.supports_digits,
            supports_symbols = EXCLUDED.supports_symbols,
            coverage_score = EXCLUDED.coverage_score,
            is_base = EXCLUDED.is_base,
            created_at = CASE
                WHEN fonts.created_at IS NULL THEN CURRENT_TIMESTAMP
                ELSE fonts.created_at
            END
        """,
        (
            user_id,
            path,
            _decide_font_type(capabilities),
            capabilities.supports_cyrillic_lower,
            capabilities.supports_cyrillic_upper,
            capabilities.supports_latin_lower,
            capabilities.supports_latin_upper,
            capabilities.supports_digits,
            capabilities.supports_symbols,
            capabilities.coverage_score,
            is_base,
        ),
    )


def _set_base_font(cursor, user_id: int, path: str) -> None:
    cursor.execute(
        """
        UPDATE fonts
        SET is_base = (path = %s)
        WHERE user_id = %s
        """,
        (path, user_id),
    )
    cursor.execute(
        """
        UPDATE users
        SET font_path = %s, updated_at = CURRENT_TIMESTAMP
        WHERE user_id = %s
        """,
        (path, user_id),
    )


def analyze_and_register_font(user_id: int, font_path: str) -> Dict[str, object]:
    """
    Анализирует шрифт и сохраняет информацию о нём в таблице fonts.
    Возвращает текущий прогресс по требованиям.
    """
    capabilities = analyze_font(font_path)
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        _ensure_fonts_table(cursor)
        font_type = _decide_font_type(capabilities)
        # Определяем, должен ли шрифт стать базовым
        is_base_candidate = capabilities.is_cyrillic_full

        if is_base_candidate:
            # Сбрасываем флаг базового позже через _set_base_font
            _insert_or_update_font(cursor, user_id, font_path, capabilities, True)
            _set_base_font(cursor, user_id, font_path)
        else:
            _insert_or_update_font(cursor, user_id, font_path, capabilities, False)

        conn.commit()
    finally:
        cursor.close()
        return_db_connection(conn)

    sync_user_font_variants(user_id)
    return {
        "progress": get_font_requirement_progress(user_id),
        "font_type": _decide_font_type(capabilities),
        "capabilities": capabilities,
    }


def get_font_requirement_progress(user_id: int) -> Dict[str, Dict[str, int]]:
    """
    Возвращает прогресс по требованиям к шрифтам.
    {
        "cyrillic_full": {"current": X, "required": 3},
        ...
    }
    """
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        _ensure_fonts_table(cursor)
        cursor.execute(
            """
            SELECT font_type, COUNT(*)
            FROM fonts
            WHERE user_id = %s
            GROUP BY font_type
            """,
            (user_id,),
        )
        rows = cursor.fetchall() or []
    finally:
        cursor.close()
        return_db_connection(conn)

    counts = {row[0]: row[1] for row in rows}
    progress: Dict[str, Dict[str, int]] = {}
    for font_type, required in FONT_REQUIREMENTS.items():
        progress[font_type] = {
            "current": counts.get(font_type, 0),
            "required": required,
        }
    return progress


def get_user_fonts_by_type(user_id: int) -> Dict[str, List[str]]:
    """Возвращает шрифты пользователя, сгруппированные по типам."""
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        _ensure_fonts_table(cursor)
        cursor.execute(
            """
            SELECT path,
                   font_type,
                   supports_cyrillic_lower,
                   supports_cyrillic_upper,
                   supports_latin_lower,
                   supports_latin_upper,
                   supports_digits,
                   supports_symbols,
                   is_base
            FROM fonts
            WHERE user_id = %s
            ORDER BY is_base DESC, coverage_score DESC
            """,
            (user_id,),
        )
        rows = cursor.fetchall() or []
    finally:
        cursor.close()
        return_db_connection(conn)

    result: Dict[str, List[str]] = {key: [] for key in FONT_TYPE_ORDER}
    result["base"] = []

    for (
        path,
        font_type,
        supports_cyrillic_lower,
        supports_cyrillic_upper,
        supports_latin_lower,
        supports_latin_upper,
        supports_digits,
        supports_symbols,
        is_base,
    ) in rows:
        if is_base:
            result.setdefault("base", []).append(path)
        result.setdefault(font_type, []).append(path)
        if supports_digits:
            result.setdefault("digits", []).append(path)
        if supports_latin_lower or supports_latin_upper:
            result.setdefault("latin", []).append(path)
        if supports_cyrillic_lower or supports_cyrillic_upper:
            result.setdefault("cyrillic_partial", []).append(path)
    return result


def get_fonts_for_generation(user_id: int) -> Dict[str, List[Dict[str, object]]]:
    """
    Возвращает наборы шрифтов для генерации:
    {
        "base": {...} или None,
        "cyrillic": [ {...}, ... ],
        "latin": [...],
        "digits": [...],
        "other": [...],
        "all": [...]
    }
    """
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        _ensure_fonts_table(cursor)
        cursor.execute(
            """
            SELECT path,
                   font_type,
                   supports_cyrillic_lower,
                   supports_cyrillic_upper,
                   supports_latin_lower,
                   supports_latin_upper,
                   supports_digits,
                   supports_symbols,
                   coverage_score,
                   is_base
            FROM fonts
            WHERE user_id = %s
            ORDER BY is_base DESC, coverage_score DESC
            """,
            (user_id,),
        )
        rows = cursor.fetchall() or []
    finally:
        cursor.close()
        return_db_connection(conn)

    records: List[Dict[str, object]] = []
    for row in rows:
        (
            path,
            font_type,
            supports_cyrillic_lower,
            supports_cyrillic_upper,
            supports_latin_lower,
            supports_latin_upper,
            supports_digits,
            supports_symbols,
            coverage_score,
            is_base,
        ) = row
        records.append(
            {
                "path": path,
                "font_type": font_type,
                "supports_cyrillic_lower": supports_cyrillic_lower,
                "supports_cyrillic_upper": supports_cyrillic_upper,
                "supports_latin_lower": supports_latin_lower,
                "supports_latin_upper": supports_latin_upper,
                "supports_digits": supports_digits,
                "supports_symbols": supports_symbols,
                "coverage_score": coverage_score,
                "is_base": is_base,
            }
        )

    base_record: Optional[Dict[str, object]] = None
    cyrillic_records: List[Dict[str, object]] = []
    latin_records: List[Dict[str, object]] = []
    digit_records: List[Dict[str, object]] = []
    other_records: List[Dict[str, object]] = []

    for record in records:
        if record["is_base"] and base_record is None:
            base_record = record
        font_type = record["font_type"]
        if font_type in ("cyrillic_full", "cyrillic_partial", "mixed"):
            cyrillic_records.append(record)
        elif font_type == "latin":
            latin_records.append(record)
        elif font_type == "digits":
            digit_records.append(record)
        else:
            other_records.append(record)

    # Если базовый шрифт отсутствует в таблице, пробуем взять из users.font_path
    if base_record is None:
        user = get_user_info(user_id)
        base_path = user.get("font_path") if user else None
        if base_path:
            base_record = {
                "path": base_path,
                "font_type": "cyrillic_full",
                "supports_cyrillic_lower": True,
                "supports_cyrillic_upper": True,
                "supports_latin_lower": False,
                "supports_latin_upper": False,
                "supports_digits": False,
                "supports_symbols": False,
                "coverage_score": 0,
                "is_base": True,
            }

    all_records = records.copy()
    if base_record and base_record not in all_records:
        all_records.insert(0, base_record)

    return {
        "base": base_record,
        "cyrillic": cyrillic_records,
        "latin": latin_records,
        "digits": digit_records,
        "other": other_records,
        "all": all_records,
    }


def has_minimum_font_set(user_id: int) -> bool:
    progress = get_font_requirement_progress(user_id)
    for requirement, info in progress.items():
        if info["current"] < info["required"]:
            return False
    return True


def sync_user_font_variants(user_id: int) -> None:
    """Обновляет список вариативных шрифтов пользователя из таблицы fonts."""
    fonts = get_fonts_for_generation(user_id)
    base = fonts.get("base")
    base_path = base["path"] if base else None
    cyrillic_variants = [
        record["path"] for record in fonts.get("cyrillic", [])
        if record["path"] != base_path
    ]
    # Добавляем латиницу и цифры как вариативные для совместимости старого UI
    additional = [
        record["path"]
        for record in fonts.get("latin", []) + fonts.get("digits", [])
        if record["path"] != base_path
    ]
    variants = cyrillic_variants + additional
    update_user_variant_fonts(user_id, variants)


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
    conn = get_db_connection()
    cursor = conn.cursor()
    
    try:
        _ensure_fonts_table(cursor)
        cursor.execute("DELETE FROM fonts WHERE user_id = %s", (user_id,))
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
        reset_success = cursor.rowcount > 0
    finally:
        if cursor:
            cursor.close()
        if conn:
            return_db_connection(conn)

    if reset_success:
        update_user_variant_fonts(user_id, [])
    return reset_success

