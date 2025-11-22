"""
Обработчики текстовых сообщений
"""

from aiogram import Router, F
from aiogram.types import Message, FSInputFile
from utils.db_utils import (
    get_user_info,
    update_job_pdf_path,
    update_job_status_failed,
    get_fonts_for_generation,
    has_minimum_font_set,
    get_font_requirement_progress,
)
from database.connection import get_db_connection, return_db_connection
from pdf_generator import generate_pdf_for_job
from utils.executors import pdf_executor
from utils.rate_limit import check_rate_limit
from utils.metrics import metrics
from utils.telegram_retry import call_with_retries, call_with_fast_retries
import time
import os
import asyncio
import logging
import unicodedata

logger = logging.getLogger(__name__)

router = Router()

FONT_TYPE_LABELS = {
    "cyrillic_full": "Кириллица (строчные и заглавные)",
    "digits": "Цифры и спецсимволы",
    "latin": "Латиница",
}

UPLOAD_SEQUENCE = ("cyrillic_full", "digits", "latin")

CATEGORY_TO_REQUIREMENT = {
    "cyrillic_lower": "cyrillic_full",
    "cyrillic_upper": "cyrillic_full",
    "latin_lower": "latin",
    "latin_upper": "latin",
    "digits": "digits",
    "symbols": "digits",
}


def _is_cyrillic(char: str) -> bool:
    try:
        return "CYRILLIC" in unicodedata.name(char)
    except ValueError:
        return False


def _is_latin(char: str) -> bool:
    try:
        return "LATIN" in unicodedata.name(char)
    except ValueError:
        return False


def _format_progress(progress: dict) -> str:
    lines = []
    for font_type in UPLOAD_SEQUENCE:
        info = progress.get(font_type, {"current": 0, "required": 0})
        label = FONT_TYPE_LABELS.get(font_type, font_type)
        status_icon = "✅" if info["current"] >= info["required"] else "⬜️"
        lines.append(f"{status_icon} {label}: {info['current']}/{info['required']}")
    return "\n".join(lines)


def _aggregate_font_support(font_sets: dict) -> dict:
    records = []
    base = font_sets.get("base")
    if base:
        records.append(base)
    for key in ("cyrillic", "latin", "digits", "other"):
        records.extend(font_sets.get(key, []))

    support = {
        "cyrillic_lower": any(rec.get("supports_cyrillic_lower") for rec in records),
        "cyrillic_upper": any(rec.get("supports_cyrillic_upper") for rec in records),
        "latin_lower": any(rec.get("supports_latin_lower") for rec in records),
        "latin_upper": any(rec.get("supports_latin_upper") for rec in records),
        "digits": any(rec.get("supports_digits") for rec in records),
        "symbols": any((rec.get("supports_symbols") or rec.get("supports_digits")) for rec in records),
    }
    return support


def _detect_missing_categories(text: str, support: dict) -> set[str]:
    missing: set[str] = set()
    for char in text:
        if not char or char.isspace():
            continue
        if char.isdigit():
            if not support.get("digits"):
                missing.add("digits")
            continue
        category = unicodedata.category(char)
        if _is_cyrillic(char):
            if char.isupper():
                if not support.get("cyrillic_upper"):
                    missing.add("cyrillic_upper")
            else:
                if not support.get("cyrillic_lower"):
                    missing.add("cyrillic_lower")
        elif _is_latin(char):
            if char.isupper():
                if not support.get("latin_upper"):
                    missing.add("latin_upper")
            else:
                if not support.get("latin_lower"):
                    missing.add("latin_lower")
        elif category and category[0] in {"P", "S"}:
            if not support.get("symbols"):
                missing.add("symbols")
        # Прочие символы (например, эмодзи) игнорируем — они будут заменены базовым шрифтом
    return missing


def _build_missing_message(missing: set[str], progress: dict) -> str:
    if not missing:
        return ""
    required_types = {CATEGORY_TO_REQUIREMENT.get(cat) for cat in missing if CATEGORY_TO_REQUIREMENT.get(cat)}
    required_types.discard(None)

    lines = ["⚠️ Не хватает шрифтов для некоторых символов:"]
    for font_type in sorted(required_types):
        label = FONT_TYPE_LABELS.get(font_type, font_type)
        info = progress.get(font_type, {"current": 0, "required": 0})
        lines.append(f"• {label}: {info['current']}/{info['required']} загружено")

    lines.append("\nЗагрузите недостающие шрифты через кнопку «📥 Загрузить шрифты».")
    return "\n".join(lines)


async def _deliver_pdf(message: Message, pdf_path: str, execution_time_ms: int, grid_enabled: bool, job_id: int) -> None:
    from handlers.menu import get_main_menu_keyboard
    from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

    try:
        pdf_file = FSInputFile(pdf_path)
        await call_with_fast_retries(
            message.answer_document,
            document=pdf_file,
            caption=f"✓ PDF сгенерирован\nВремя: {execution_time_ms}мс",
        )

        await call_with_retries(
            message.answer,
            "💡 Отправьте новый текст:\nя создам еще один конспект",
            reply_markup=get_main_menu_keyboard(),
        )
    except Exception as exc:
        logger.error("Не удалось отправить PDF (job_id=%s): %s", job_id, exc, exc_info=True)
        retry_keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🔄 Повторить отправку PDF", callback_data=f"retry_pdf_{job_id}")]
        ])
        await call_with_retries(
            message.answer,
            "⚠️ Не удалось отправить PDF из-за проблем с сетью.\n\nНажмите кнопку ниже, чтобы повторить отправку.",
            reply_markup=retry_keyboard,
        )


@router.message(F.text & ~F.text.startswith('/'))
async def handle_text_message(message: Message):
    """Обработчик текстовых сообщений для сохранения в jobs и генерации PDF"""
    user_id = message.from_user.id
    text_content = message.text.strip()
    
    # Проверка rate limit
    allowed, error_msg = check_rate_limit(user_id)
    if not allowed:
        await call_with_retries(message.answer, error_msg)
        logger.warning(f"Rate limit exceeded for user {user_id}")
        return
    
    # Проверка текста
    if not text_content:
        await call_with_retries(message.answer, "❌ Текст не может быть пустым.")
        return
    
    if len(text_content) < 3:
        await call_with_retries(message.answer, "❌ Текст слишком короткий (минимум 3 символа).")
        return
    
    if len(text_content) > 100000:
        await call_with_retries(message.answer, "❌ Текст слишком длинный (максимум 100000 символов).")
        return
    
    # Получаем информацию о пользователе
    user = get_user_info(user_id)
    if not user:
        from utils.db_utils import get_or_create_user
        telegram_user = message.from_user
        user = get_or_create_user(
            user_id,
            username=getattr(telegram_user, "username", None),
            first_name=getattr(telegram_user, "first_name", None),
            last_name=getattr(telegram_user, "last_name", None),
        )
    # last_seen_at обновляется автоматически через middleware
    
    ready_font_set = has_minimum_font_set(user_id)
    if not ready_font_set:
        from handlers.menu import get_main_menu_keyboard
        await call_with_retries(
            message.answer,
            "⚠️ Загрузите хотя бы один кириллический шрифт для генерации PDF.\n\n"
            "Используйте кнопку «📥 Загрузить шрифты».",
            reply_markup=get_main_menu_keyboard(ready_to_generate=False),
        )
        return
    
    # Проверка формата страницы
    if not user['page_format']:
        from handlers.menu import get_main_menu_keyboard
        await call_with_retries(
            message.answer,
            "❌ Формат страницы не выбран.\n\nВыберите формат через меню.",
            reply_markup=get_main_menu_keyboard(),
        )
        return
    
    if user['page_format'] not in ['A4', 'A5']:
        from handlers.menu import get_main_menu_keyboard
        await call_with_retries(
            message.answer,
            "❌ Некорректный формат страницы.\n\nВыберите формат через меню.",
            reply_markup=get_main_menu_keyboard(),
        )
        return

    font_sets = get_fonts_for_generation(user_id)
    base_meta = font_sets.get("base")
    base_path = base_meta.get("path") if base_meta else None
    if not base_path or not os.path.exists(base_path):
        from handlers.menu import get_main_menu_keyboard
        await call_with_retries(
            message.answer,
            "❌ Шрифты не найдены.\n\nЗагрузите или переустановите шрифты.",
            reply_markup=get_main_menu_keyboard(ready_to_generate=False),
        )
        return

    support = _aggregate_font_support(font_sets)
    missing_categories = _detect_missing_categories(text_content, support)
    if missing_categories:
        progress = get_font_requirement_progress(user_id)
        warning_text = _build_missing_message(missing_categories, progress)
        from handlers.menu import get_main_menu_keyboard
        await call_with_retries(
            message.answer,
            warning_text,
            reply_markup=get_main_menu_keyboard(ready_to_generate=False),
        )
        return
    
    # Сохраняем задачу в БД
    conn = get_db_connection()
    cursor = conn.cursor()
    job_id = None
    
    try:
        cursor.execute(
            """
            INSERT INTO jobs (user_id, text_content, status)
            VALUES (%s, %s, %s)
            RETURNING id
            """,
            (user_id, text_content, 'pending')
        )
        
        job_id = cursor.fetchone()[0]
        conn.commit()
        
        await call_with_retries(message.answer, "⏳ Генерирую PDF... (может занять до 1-2 минут)")
        
        # Получаем настройки
        grid_enabled = user.get('grid_enabled', False)
        first_page_side = user.get('first_page_side', 'right')
        
        # Генерируем PDF асинхронно в отдельном потоке
        start_time = time.time()
        loop = asyncio.get_event_loop()
        pdf_path = await loop.run_in_executor(
            pdf_executor,
            generate_pdf_for_job,
            job_id, 
            text_content, 
            font_sets,
            user['page_format'],
            grid_enabled,
            first_page_side,
        )
        execution_time_ms = int((time.time() - start_time) * 1000)
        
        # Записываем метрики
        metrics.record_pdf_time(execution_time_ms)
        metrics.record_request(user_id)
        logger.info(f"PDF generated for user {user_id}, job {job_id}, time: {execution_time_ms}ms")
        
        # Обновляем путь к PDF в БД
        update_job_pdf_path(job_id, pdf_path, execution_time_ms)
        
        # Отправляем PDF пользователю
        if os.path.exists(pdf_path):
            asyncio.create_task(_deliver_pdf(message, pdf_path, execution_time_ms, grid_enabled, job_id))
        else:
            from handlers.menu import get_main_menu_keyboard
            await call_with_retries(
                message.answer,
                "❌ Ошибка: PDF файл не найден",
                reply_markup=get_main_menu_keyboard(),
            )
            update_job_status_failed(job_id)
        
    except Exception as e:
        # Записываем ошибку в метрики
        error_type = type(e).__name__
        metrics.record_error(error_type)
        logger.error(f"Error generating PDF for user {user_id}, job {job_id}: {str(e)}", exc_info=True)
        
        if job_id:
            update_job_status_failed(job_id)
        from handlers.menu import get_main_menu_keyboard
        await call_with_retries(
            message.answer,
            f"❌ Ошибка при генерации PDF: {str(e)}\n\nПопробуйте снова или вернитесь в меню.",
            reply_markup=get_main_menu_keyboard(),
        )
    finally:
        if cursor:
            cursor.close()
        if conn:
            return_db_connection(conn)

