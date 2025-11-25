"""
Утилиты для работы с базой данных
"""

from __future__ import annotations

from typing import Dict, List, Optional

from database.connection import get_db_connection, return_db_connection
from config import FONTS_DIR, ADMIN_USER_ID, CREATOR_FONT_DIR
from utils.font_analyzer import analyze_font, FontCapabilities
import json
import os
import shutil


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
    Считает уникальные шрифты по их возможностям, а не по font_type.
    """
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        _ensure_fonts_table(cursor)
        # Получаем все шрифты пользователя
        cursor.execute(
            """
            SELECT DISTINCT path,
                   supports_cyrillic_lower,
                   supports_cyrillic_upper,
                   supports_latin_lower,
                   supports_latin_upper,
                   supports_digits,
                   supports_symbols
            FROM fonts
            WHERE user_id = %s
            """,
            (user_id,),
        )
        rows = cursor.fetchall() or []
    finally:
        cursor.close()
        return_db_connection(conn)

    # Считаем шрифты по их возможностям
    cyrillic_full_count = 0
    digits_count = 0
    latin_count = 0
    
    for row in rows:
        path, cyr_lower, cyr_upper, lat_lower, lat_upper, digits, symbols = row
        
        # Кириллический полный (строчные И заглавные)
        if cyr_lower and cyr_upper:
            cyrillic_full_count += 1
        
        # Цифры и спецсимволы
        if digits or symbols:
            digits_count += 1
        
        # Латиница (строчные ИЛИ заглавные)
        if lat_lower or lat_upper:
            latin_count += 1
    
    progress: Dict[str, Dict[str, int]] = {}
    progress["cyrillic_full"] = {
        "current": cyrillic_full_count,
        "required": FONT_REQUIREMENTS.get("cyrillic_full", 3),
    }
    progress["digits"] = {
        "current": digits_count,
        "required": FONT_REQUIREMENTS.get("digits", 2),
    }
    progress["latin"] = {
        "current": latin_count,
        "required": FONT_REQUIREMENTS.get("latin", 2),
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
    """Проверяет, достаточно ли шрифтов для генерации PDF.
    Достаточно хотя бы одного кириллического шрифта."""
    fonts_by_type = get_user_fonts_by_type(user_id)
    # Проверяем наличие хотя бы одного кириллического шрифта
    cyrillic_fonts = fonts_by_type.get("base", []) + fonts_by_type.get("cyrillic", [])
    return len(cyrillic_fonts) > 0


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


def get_or_create_user(
    user_id: int,
    username: Optional[str] = None,
    first_name: Optional[str] = None,
    last_name: Optional[str] = None,
):
    """Получает пользователя из БД или создает нового, обновляя профиль."""
    conn = get_db_connection()
    cursor = conn.cursor()

    try:
        # Проверяем наличие колонок профиля
        cursor.execute("""
            SELECT column_name 
            FROM information_schema.columns 
            WHERE table_name='users' AND column_name IN ('username', 'first_name', 'last_name', 'last_seen_at')
        """)
        existing_columns = {row[0] for row in cursor.fetchall()}
        
        has_profile_fields = 'username' in existing_columns
        
        if has_profile_fields:
            # Используем полный запрос с профильными полями
            cursor.execute(
                """
                INSERT INTO users (user_id, page_format, username, first_name, last_name, last_seen_at)
                VALUES (%s, %s, %s, %s, %s, CURRENT_TIMESTAMP)
                ON CONFLICT (user_id) DO UPDATE SET
                    username = COALESCE(EXCLUDED.username, users.username),
                    first_name = COALESCE(EXCLUDED.first_name, users.first_name),
                    last_name = COALESCE(EXCLUDED.last_name, users.last_name),
                    last_seen_at = CURRENT_TIMESTAMP,
                    updated_at = CURRENT_TIMESTAMP
                RETURNING user_id, font_path, page_format
                """,
                (user_id, 'A5', username, first_name, last_name),
            )
        else:
            # Используем упрощенный запрос без профильных полей
            cursor.execute(
                """
                INSERT INTO users (user_id, page_format)
                VALUES (%s, %s)
                ON CONFLICT (user_id) DO UPDATE SET
                    updated_at = CURRENT_TIMESTAMP
                RETURNING user_id, font_path, page_format
                """,
                (user_id, 'A5'),
            )
        
        user = cursor.fetchone()
        
        # Проверяем, является ли пользователь действительно новым (только что создан)
        # Проверяем created_at - если пользователь создан менее 5 секунд назад, это новый пользователь
        cursor.execute(
            """
            SELECT created_at, 
                   (CURRENT_TIMESTAMP - created_at) < INTERVAL '5 seconds' as is_recently_created
            FROM users 
            WHERE user_id = %s
            """,
            (user_id,)
        )
        user_created_info = cursor.fetchone()
        
        # Проверяем количество шрифтов
        _ensure_fonts_table(cursor)
        cursor.execute("SELECT COUNT(*) FROM fonts WHERE user_id = %s", (user_id,))
        font_count = cursor.fetchone()[0]
        
        # Пользователь считается новым только если:
        # 1. Он только что создан (менее 5 секунд назад)
        # 2. И у него нет шрифтов
        is_new_user = False
        if user_created_info:
            is_recently_created = user_created_info[1] if len(user_created_info) > 1 else False
            is_new_user = is_recently_created and font_count == 0
        
        conn.commit()
        
        # Автоматически добавляем шрифт создателя только для действительно новых пользователей
        if is_new_user:
            try:
                add_creator_font_to_user(user_id)
            except Exception as e:
                # Если не удалось добавить шрифт создателя, просто логируем
                # Не прерываем создание пользователя
                import logging
                logger = logging.getLogger(__name__)
                logger.warning(f"Не удалось добавить шрифт создателя для нового пользователя {user_id}: {e}")

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
        # Проверяем наличие колонок
        cursor.execute("""
            SELECT column_name 
            FROM information_schema.columns 
            WHERE table_name='users' AND column_name IN ('grid_enabled', 'variant_fonts', 'first_page_side', 'instruction_seen')
        """)
        existing_columns = {row[0] for row in cursor.fetchall()}
        
        has_grid = 'grid_enabled' in existing_columns
        has_variants = 'variant_fonts' in existing_columns
        has_first_page_side = 'first_page_side' in existing_columns
        has_instruction_seen = 'instruction_seen' in existing_columns
        
        # Формируем запрос в зависимости от наличия колонок
        select_fields = ["user_id", "font_path", "page_format"]
        if has_grid:
            select_fields.append("COALESCE(grid_enabled, FALSE)")
        else:
            select_fields.append("FALSE")
        
        if has_variants:
            select_fields.append("variant_fonts")
        else:
            select_fields.append("NULL")
        
        if has_first_page_side:
            select_fields.append("COALESCE(first_page_side, 'right')")
        else:
            select_fields.append("'right'")
        
        if has_instruction_seen:
            select_fields.append("COALESCE(instruction_seen, FALSE)")
        else:
            select_fields.append("FALSE")
        
        query = f"SELECT {', '.join(select_fields)} FROM users WHERE user_id = %s"
        cursor.execute(query, (user_id,))
        user = cursor.fetchone()
        
        if user:
            # Парсим JSON для variant_fonts
            variant_fonts = []
            variant_idx = 4 if has_variants else None
            if variant_idx is not None and len(user) > variant_idx and user[variant_idx]:
                try:
                    variant_fonts = json.loads(user[variant_idx]) if isinstance(user[variant_idx], str) else user[variant_idx]
                except (json.JSONDecodeError, TypeError):
                    variant_fonts = []
            
            first_page_side_idx = 5 if has_first_page_side else None
            first_page_side = user[first_page_side_idx] if first_page_side_idx is not None and len(user) > first_page_side_idx else 'right'
            
            instruction_seen_idx = 6 if has_instruction_seen else None
            instruction_seen = user[instruction_seen_idx] if instruction_seen_idx is not None and len(user) > instruction_seen_idx else False
            
            return {
                'user_id': user[0],
                'font_path': user[1],
                'page_format': user[2],
                'grid_enabled': user[3] if len(user) > 3 else False,
                'variant_fonts': variant_fonts if isinstance(variant_fonts, list) else [],
                'first_page_side': first_page_side,
                'instruction_seen': instruction_seen
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


def update_user_first_page_side(user_id: int, first_page_side: str):
    """Обновляет настройку стороны первой страницы пользователя."""
    if first_page_side not in ['left', 'right']:
        raise ValueError("first_page_side must be 'left' or 'right'")
    
    conn = get_db_connection()
    cursor = conn.cursor()
    
    try:
        # Проверяем существует ли колонка
        cursor.execute("""
            SELECT column_name 
            FROM information_schema.columns 
            WHERE table_name='users' AND column_name='first_page_side'
        """)
        
        if not cursor.fetchone():
            # Добавляем колонку если не существует
            cursor.execute("""
                ALTER TABLE users 
                ADD COLUMN first_page_side VARCHAR(10) DEFAULT 'right'
            """)
            conn.commit()
        
        cursor.execute(
            """
            UPDATE users 
            SET first_page_side = %s, updated_at = CURRENT_TIMESTAMP
            WHERE user_id = %s
            """,
            (first_page_side, user_id)
        )
        conn.commit()
        return cursor.rowcount > 0
    finally:
        if cursor:
            cursor.close()
        if conn:
            return_db_connection(conn)


def update_last_seen_at(user_id: int):
    """Обновляет время последнего визита пользователя."""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    try:
        # Проверяем существует ли колонка last_seen_at
        cursor.execute("""
            SELECT column_name 
            FROM information_schema.columns 
            WHERE table_name='users' AND column_name='last_seen_at'
        """)
        
        if cursor.fetchone():
            # Колонка существует, обновляем
            cursor.execute(
                """
                UPDATE users 
                SET last_seen_at = CURRENT_TIMESTAMP, updated_at = CURRENT_TIMESTAMP
                WHERE user_id = %s
                """,
                (user_id,)
            )
            conn.commit()
            return cursor.rowcount > 0
        else:
            # Колонка не существует, ничего не делаем
            return False
    except Exception as e:
        # В случае ошибки просто игнорируем (не критично)
        return False
    finally:
        if cursor:
            cursor.close()
        if conn:
            return_db_connection(conn)


def mark_instruction_seen(user_id: int):
    """Отмечает, что пользователь видел инструкцию"""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    try:
        # Проверяем существует ли колонка instruction_seen
        cursor.execute("""
            SELECT column_name 
            FROM information_schema.columns 
            WHERE table_name='users' AND column_name='instruction_seen'
        """)
        
        if not cursor.fetchone():
            # Добавляем колонку если не существует
            cursor.execute("""
                ALTER TABLE users 
                ADD COLUMN instruction_seen BOOLEAN DEFAULT FALSE
            """)
            conn.commit()
        
        # Обновляем флаг
        cursor.execute(
            """
            UPDATE users 
            SET instruction_seen = TRUE, updated_at = CURRENT_TIMESTAMP
            WHERE user_id = %s
            """,
            (user_id,)
        )
        conn.commit()
        return cursor.rowcount > 0
    except Exception as e:
        # В случае ошибки просто игнорируем (не критично)
        return False
    finally:
        if cursor:
            cursor.close()
        if conn:
            return_db_connection(conn)


def set_user_pdf_mode(user_id: int, enabled: bool):
    """Устанавливает режим создания PDF для пользователя"""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    try:
        # Проверяем существует ли колонка pdf_mode_enabled
        cursor.execute("""
            SELECT column_name 
            FROM information_schema.columns 
            WHERE table_name='users' AND column_name='pdf_mode_enabled'
        """)
        
        if not cursor.fetchone():
            # Добавляем колонку если не существует
            cursor.execute("""
                ALTER TABLE users 
                ADD COLUMN pdf_mode_enabled BOOLEAN DEFAULT FALSE
            """)
            conn.commit()
        
        # Обновляем флаг
        cursor.execute(
            """
            UPDATE users 
            SET pdf_mode_enabled = %s, updated_at = CURRENT_TIMESTAMP
            WHERE user_id = %s
            """,
            (enabled, user_id)
        )
        conn.commit()
        return cursor.rowcount > 0
    except Exception as e:
        # В случае ошибки просто игнорируем (не критично)
        return False
    finally:
        if cursor:
            cursor.close()
        if conn:
            return_db_connection(conn)


def is_user_in_pdf_mode(user_id: int) -> bool:
    """Проверяет, находится ли пользователь в режиме создания PDF"""
    user_info = get_user_info(user_id)
    if not user_info:
        return False
    
    # Проверяем наличие колонки в БД
    conn = get_db_connection()
    cursor = conn.cursor()
    
    try:
        cursor.execute("""
            SELECT column_name 
            FROM information_schema.columns 
            WHERE table_name='users' AND column_name='pdf_mode_enabled'
        """)
        
        if cursor.fetchone():
            # Колонка существует, получаем значение
            cursor.execute(
                "SELECT pdf_mode_enabled FROM users WHERE user_id = %s",
                (user_id,)
            )
            result = cursor.fetchone()
            return result[0] if result and result[0] else False
        else:
            return False
    except Exception:
        return False
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
        
        # Получаем пути к файлам шрифтов перед удалением из БД
        cursor.execute("SELECT path FROM fonts WHERE user_id = %s", (user_id,))
        font_paths = [row[0] for row in cursor.fetchall()]
        
        # Удаляем шрифты из БД
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
        
        # Удаляем файлы шрифтов с диска
        for font_path in font_paths:
            if font_path and os.path.exists(font_path):
                try:
                    os.remove(font_path)
                except Exception as e:
                    import logging
                    logger = logging.getLogger(__name__)
                    logger.warning(f"Не удалось удалить файл шрифта {font_path}: {e}")
    finally:
        if cursor:
            cursor.close()
        if conn:
            return_db_connection(conn)

    if reset_success:
        update_user_variant_fonts(user_id, [])
    return reset_success


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


def get_creator_font_paths() -> List[str]:
    """
    Возвращает список путей ко всем шрифтам создателя.
    Ищет ТОЛЬКО в папке sevafont/ - без fallback на другие папки.
    """
    font_paths = []
    
    # Используем ТОЛЬКО папку sevafont - без fallback
    if not os.path.exists(CREATOR_FONT_DIR):
        return font_paths
    
    for file in os.listdir(CREATOR_FONT_DIR):
        if file.lower().endswith('.ttf') and not file.startswith('.'):
            font_path = os.path.join(CREATOR_FONT_DIR, file)
            if os.path.isfile(font_path):
                font_paths.append(font_path)
    
    return font_paths


def add_creator_font_to_user(user_id: int) -> Dict[str, object]:
    """
    Добавляет ограниченное количество шрифтов создателя пользователю для тестирования.
    Выбирает: 3 кириллических, 2 латинских, 2 для цифр и спецсимволов.
    Проверяет, не добавлены ли уже шрифты создателя, чтобы избежать дублирования.
    """
    creator_font_paths = get_creator_font_paths()
    if not creator_font_paths:
        raise FileNotFoundError("Шрифты создателя не найдены. Обратитесь к администратору.")
    
    # Анализируем все шрифты и разделяем по типам
    cyrillic_fonts = []  # cyrillic_full
    latin_fonts = []      # latin
    digits_fonts = []     # digits или с поддержкой цифр/символов
    
    for font_path in creator_font_paths:
        if not os.path.exists(font_path):
            continue
        try:
            capabilities = analyze_font(font_path)
            if capabilities.is_cyrillic_full:
                cyrillic_fonts.append((font_path, capabilities))
            elif capabilities.font_type == "latin":
                latin_fonts.append((font_path, capabilities))
            elif capabilities.font_type == "digits" or (capabilities.supports_digits or capabilities.supports_symbols):
                digits_fonts.append((font_path, capabilities))
        except Exception as e:
            # Пропускаем шрифты, которые не удалось проанализировать
            import logging
            logger = logging.getLogger(__name__)
            logger.warning(f"Не удалось проанализировать шрифт {font_path}: {e}")
            continue
    
    # Сортируем по coverage_score (лучшие первыми) и берем нужное количество
    cyrillic_fonts.sort(key=lambda x: x[1].coverage_score, reverse=True)
    latin_fonts.sort(key=lambda x: x[1].coverage_score, reverse=True)
    digits_fonts.sort(key=lambda x: x[1].coverage_score, reverse=True)
    
    # Выбираем только нужное количество каждого типа
    selected_fonts = (
        [f[0] for f in cyrillic_fonts[:3]] +  # 3 кириллических
        [f[0] for f in latin_fonts[:2]] +      # 2 латинских
        [f[0] for f in digits_fonts[:2]]       # 2 для цифр и спецсимволов
    )
    
    if not selected_fonts:
        raise FileNotFoundError("Не найдено подходящих шрифтов создателя. Нужны: 3 кириллических, 2 латинских, 2 для цифр.")
    
    # Удаляем все старые шрифты создателя перед добавлением новых
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        _ensure_fonts_table(cursor)
        
        # Находим все старые шрифты создателя (с префиксом creator_{user_id}_)
        cursor.execute(
            """
            SELECT path FROM fonts 
            WHERE user_id = %s AND path LIKE %s
            """,
            (user_id, f"creator_{user_id}_%")
        )
        old_font_paths = [row[0] for row in cursor.fetchall()]
        
        # Удаляем старые шрифты из БД и файловой системы
        if old_font_paths:
            cursor.execute(
                """
                DELETE FROM fonts 
                WHERE user_id = %s AND path LIKE %s
                """,
                (user_id, f"creator_{user_id}_%")
            )
            conn.commit()
            
            # Удаляем файлы
            for old_path in old_font_paths:
                if os.path.exists(old_path):
                    try:
                        os.remove(old_path)
                    except:
                        pass
        
        added_count = 0
        skipped_count = 0
        errors = []
        
        # Добавляем только выбранные шрифты
        for creator_font_path in selected_fonts:
            if not os.path.exists(creator_font_path):
                continue
                
            font_filename = os.path.basename(creator_font_path)
            user_font_filename = f"creator_{user_id}_{font_filename}"
            user_font_path = os.path.join(FONTS_DIR, user_font_filename)
            
            # Если файл существует - удаляем его (мы уже удалили из БД выше)
            if os.path.exists(user_font_path):
                try:
                    os.remove(user_font_path)
                except:
                    pass
            
            try:
                # Копируем файл
                shutil.copy2(creator_font_path, user_font_path)
                
                # Регистрируем шрифт для пользователя
                analyze_and_register_font(user_id, user_font_path)
                added_count += 1
            except Exception as e:
                # Если ошибка, удаляем скопированный файл
                if os.path.exists(user_font_path):
                    try:
                        os.remove(user_font_path)
                    except:
                        pass
                errors.append(f"{font_filename}: {str(e)}")
                continue
        
        # Если не добавили ни одного шрифта (все уже были добавлены)
        if added_count == 0 and skipped_count > 0:
            return {
                "progress": get_font_requirement_progress(user_id),
                "font_type": None,
                "capabilities": None,
            }
        
        # Если были ошибки, но что-то добавили
        if errors:
            import logging
            logger = logging.getLogger(__name__)
            logger.warning(f"Ошибки при добавлении некоторых шрифтов создателя для пользователя {user_id}: {errors}")
        
        # Возвращаем финальный прогресс
        return {
            "progress": get_font_requirement_progress(user_id),
            "font_type": "multiple" if added_count > 1 else None,
            "capabilities": None,
            "added_count": added_count,
            "skipped_count": skipped_count,
        }
        
    finally:
        if cursor:
            cursor.close()
        if conn:
            return_db_connection(conn)
