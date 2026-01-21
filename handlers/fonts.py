"""
Обработчики загрузки шрифтов
"""

from aiogram import Router, F
from aiogram.types import Message
from utils.db_utils import (
    save_font_file,
    get_user_info,
    analyze_and_register_font,
    get_font_requirement_progress,
    has_minimum_font_set,
    get_user_fonts_by_type,
)
from utils.telegram_retry import call_with_retries
import os
import logging

logger = logging.getLogger(__name__)
router = Router()

FONT_TYPE_LABELS = {
    "cyrillic_full": "Кириллический (строчные и заглавные)",
    "digits": "Цифры и спецсимволы",
    "latin": "Латиница",
}

UPLOAD_SEQUENCE = [
    "cyrillic_full",
    "digits",
    "latin",
]


def _format_progress(progress: dict) -> str:
    lines = []
    for font_type in UPLOAD_SEQUENCE:
        info = progress.get(font_type, {"current": 0, "required": 0})
        label = FONT_TYPE_LABELS.get(font_type, font_type)
        status_icon = "✅" if info["current"] >= info["required"] else "⬜️"
        lines.append(f"{status_icon} {label}: {info['current']}/{info['required']}")
    return "\n".join(lines)


async def handle_font_file(message: Message, file_ext: str):
    """Общий обработчик загрузки шрифта"""
    user_id = message.from_user.id
    
    try:
        # Убеждаемся что пользователь существует
        from utils.db_utils import get_or_create_user
        telegram_user = message.from_user
        get_or_create_user(
            user_id,
            username=getattr(telegram_user, "username", None),
            first_name=getattr(telegram_user, "first_name", None),
            last_name=getattr(telegram_user, "last_name", None),
        )
        
        # Получаем информацию о файле
        file = message.document
        
        if not file.file_name:
            await message.answer("❌ Не удалось определить имя файла.")
            return
        
        file_name = file.file_name
        
        await call_with_retries(message.answer, "⏳ Загружаю шрифт...")
        
        # Скачиваем файл
        bot = message.bot
        file_info = await bot.get_file(file.file_id)
        file_data = await bot.download_file(file_info.file_path)
        
        # Сохраняем файл
        font_path = save_font_file(file_data, file_name)
        result = analyze_and_register_font(user_id, font_path)
        progress = result["progress"]
        font_type_added = result.get("font_type")
        from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

        keyboard_buttons = [
            [InlineKeyboardButton(text="🏠 Главное меню", callback_data="menu_main")],
        ]
        if has_minimum_font_set(user_id):
            keyboard_buttons.insert(
                0,
                [InlineKeyboardButton(text="📄 Сгенерировать PDF", callback_data="menu_create_pdf")],
            )
        keyboard = InlineKeyboardMarkup(inline_keyboard=keyboard_buttons)

        progress_text = _format_progress(progress)

        font_type_text = ""
        if font_type_added and font_type_added in FONT_TYPE_LABELS:
            font_type_text = f"📂 Категория: {FONT_TYPE_LABELS[font_type_added]}\n\n"

        await call_with_retries(
            message.answer,
            (
                f"✅ Шрифт загружен: {file_name}\n\n"
                f"{font_type_text}"
                f"📊 Прогресс:\n{progress_text}"
            ),
            reply_markup=keyboard,
        )
    
    except Exception as e:
        logger.error(f"Ошибка при загрузке шрифта для пользователя {user_id}: {e}", exc_info=True)
        await call_with_retries(message.answer, f"❌ Ошибка при загрузке шрифта: {str(e)}")


@router.message(F.document & (F.document.file_name.endswith('.ttf') | F.document.file_name.endswith('.TTF')))
async def handle_ttf_font(message: Message):
    """Обработчик загрузки TTF-шрифта"""
    await handle_font_file(message, '.ttf')


@router.message(F.document & (F.document.file_name.endswith('.md') | F.document.file_name.endswith('.MD')))
async def handle_markdown_file(message: Message):
    """Обработчик загрузки Markdown файла (только в dev ветке)"""
    from config import is_dev_branch
    
    if not is_dev_branch():
        await call_with_retries(
            message.answer,
            "❌ Эта функция доступна только в dev ветке."
        )
        return
    
    user_id = message.from_user.id
    
    try:
        # Убеждаемся что пользователь существует
        from utils.db_utils import get_or_create_user, has_minimum_font_set, get_fonts_for_generation, get_user_info
        telegram_user = message.from_user
        get_or_create_user(
            user_id,
            username=getattr(telegram_user, "username", None),
            first_name=getattr(telegram_user, "first_name", None),
            last_name=getattr(telegram_user, "last_name", None),
        )
        
        # Получаем информацию о файле
        file = message.document
        
        if not file.file_name:
            await message.answer("❌ Не удалось определить имя файла.")
            return
        
        file_name = file.file_name
        
        await call_with_retries(message.answer, "⏳ Загружаю и обрабатываю Markdown файл...")
        
        # Скачиваем файл
        bot = message.bot
        file_info = await bot.get_file(file.file_id)
        file_data = await bot.download_file(file_info.file_path)
        
        # Читаем содержимое файла
        md_content = file_data.read().decode('utf-8')
        
        # Очищаем markdown разметку
        cleaned_text = _clean_markdown(md_content)
        
        if not cleaned_text or not cleaned_text.strip():
            await call_with_retries(
                message.answer,
                "❌ Файл не содержит текста или не удалось обработать содержимое."
            )
            return
        
        # Проверяем готовность к генерации
        if not has_minimum_font_set(user_id):
            from handlers.menu import get_main_menu_keyboard
            await call_with_retries(
                message.answer,
                "⚠️ Загрузите хотя бы один кириллический шрифт для генерации PDF.\n\n"
                "Используйте кнопку «📥 Загрузить шрифты».",
                reply_markup=get_main_menu_keyboard(ready_to_generate=False),
            )
            return
        
        # Получаем информацию о пользователе
        user = get_user_info(user_id)
        if not user or not user.get('page_format'):
            from handlers.menu import get_main_menu_keyboard
            await call_with_retries(
                message.answer,
                "❌ Формат страницы не выбран.\n\nВыберите формат через меню.",
                reply_markup=get_main_menu_keyboard(),
            )
            return
        
        # Проверка длины текста
        if len(cleaned_text) > 100000:
            await call_with_retries(
                message.answer,
                "❌ Текст слишком длинный (максимум 100000 символов после обработки)."
            )
            return
        
        # Генерируем PDF
        from database.connection import get_db_connection, return_db_connection
        from pdf_generator import generate_pdf_for_job
        from utils.executors import pdf_executor
        from utils.metrics import metrics
        from aiogram.types import FSInputFile, InlineKeyboardMarkup, InlineKeyboardButton
        from handlers.menu import get_main_menu_keyboard
        from utils.telegram_retry import call_with_fast_retries
        import time
        import asyncio
        
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
                (user_id, cleaned_text, 'pending')
            )
            
            job_id = cursor.fetchone()[0]
            conn.commit()
            
            await call_with_retries(message.answer, "⏳ Генерирую PDF из Markdown... (может занять до 1-2 минут)")
            
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
                cleaned_text, 
                font_sets,
                user['page_format'],
                grid_enabled,
                first_page_side,
            )
            execution_time_ms = int((time.time() - start_time) * 1000)
            
            # Записываем метрики
            metrics.record_pdf_time(execution_time_ms)
            metrics.record_request(user_id)
            logger.info(f"PDF generated from MD for user {user_id}, job {job_id}, time: {execution_time_ms}ms")
            
            # Обновляем путь к PDF в БД
            from utils.db_utils import update_job_pdf_path
            update_job_pdf_path(job_id, pdf_path, execution_time_ms)
            
            # Отправляем PDF пользователю
            if os.path.exists(pdf_path):
                try:
                    pdf_file = FSInputFile(pdf_path)
                    await call_with_fast_retries(
                        message.answer_document,
                        document=pdf_file,
                        caption=f"✓ PDF сгенерирован из Markdown\nВремя: {execution_time_ms}мс",
                    )
                    
                    await call_with_retries(
                        message.answer,
                        "💡 Отправьте новый Markdown файл или текст:\nя создам еще один конспект",
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
            else:
                from handlers.menu import get_main_menu_keyboard
                await call_with_retries(
                    message.answer,
                    "❌ Ошибка: PDF файл не найден",
                    reply_markup=get_main_menu_keyboard(),
                )
                from utils.db_utils import update_job_status_failed
                update_job_status_failed(job_id)
        
        except Exception as e:
            error_type = type(e).__name__
            metrics.record_error(error_type)
            logger.error(f"Error generating PDF from MD for user {user_id}, job {job_id}: {str(e)}", exc_info=True)
            
            if job_id:
                from utils.db_utils import update_job_status_failed
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
    
    except UnicodeDecodeError:
        await call_with_retries(
            message.answer,
            "❌ Ошибка: файл не в кодировке UTF-8. Пожалуйста, сохраните файл в UTF-8."
        )
    except Exception as e:
        logger.error(f"Ошибка при обработке Markdown файла для пользователя {user_id}: {e}", exc_info=True)
        await call_with_retries(message.answer, f"❌ Ошибка при обработке файла: {str(e)}")


def _clean_markdown(text: str) -> str:
    """
    Очищает markdown разметку, оставляя только текст
    Убирает: заголовки, списки, ссылки, код, изображения, таблицы и т.д.
    """
    import re
    
    # Убираем код блоки ```
    text = re.sub(r'```[\s\S]*?```', '', text)
    
    # Убираем inline код `
    text = re.sub(r'`([^`]+)`', r'\1', text)
    
    # Убираем заголовки (# ## ### и т.д.)
    text = re.sub(r'^#{1,6}\s+(.+)$', r'\1', text, flags=re.MULTILINE)
    
    # Убираем ссылки [текст](url) -> текст
    text = re.sub(r'\[([^\]]+)\]\([^\)]+\)', r'\1', text)
    
    # Убираем изображения ![alt](url)
    text = re.sub(r'!\[([^\]]*)\]\([^\)]+\)', '', text)
    
    # Убираем жирный текст **текст** -> текст
    text = re.sub(r'\*\*([^\*]+)\*\*', r'\1', text)
    text = re.sub(r'__([^_]+)__', r'\1', text)
    
    # Убираем курсив *текст* -> текст
    text = re.sub(r'(?<!\*)\*([^\*]+?)\*(?!\*)', r'\1', text)
    text = re.sub(r'(?<!_)_([^_]+?)_(?!_)', r'\1', text)
    
    # Убираем зачеркнутый текст ~~текст~~ -> текст
    text = re.sub(r'~~([^~]+)~~', r'\1', text)
    
    # Убираем горизонтальные линии ---
    text = re.sub(r'^---+$', '', text, flags=re.MULTILINE)
    
    # Преобразуем маркированные списки • -> • (оставляем как есть для PDF генератора)
    # Преобразуем нумерованные списки 1. -> • 
    text = re.sub(r'^\d+\.\s+', '• ', text, flags=re.MULTILINE)
    
    # Убираем маркеры списков -, *, +
    text = re.sub(r'^[\-\*\+]\s+', '• ', text, flags=re.MULTILINE)
    
    # Убираем таблицы (строки с |)
    lines = text.split('\n')
    cleaned_lines = []
    in_table = False
    for line in lines:
        if '|' in line and line.strip().startswith('|'):
            in_table = True
            continue
        elif in_table and line.strip() == '':
            in_table = False
        if not in_table:
            cleaned_lines.append(line)
    text = '\n'.join(cleaned_lines)
    
    # Убираем лишние пробелы и пустые строки (но оставляем структуру абзацев)
    lines = text.split('\n')
    cleaned_lines = []
    prev_empty = False
    for line in lines:
        cleaned_line = line.strip()
        if not cleaned_line:
            if not prev_empty:
                cleaned_lines.append('')
            prev_empty = True
        else:
            cleaned_lines.append(cleaned_line)
            prev_empty = False
    
    text = '\n'.join(cleaned_lines)
    
    # Убираем множественные пустые строки в конце
    text = text.rstrip() + '\n' if text.strip() else text.strip()
    
    return text


@router.message(F.document)
async def handle_wrong_file_type(message: Message):
    """Обработчик неподходящего типа файла"""
    file = message.document
    file_name = file.file_name if file and file.file_name else "неизвестно"
    
    # Проверяем, не является ли это md файлом в dev ветке (на случай если обработчик выше не сработал)
    from config import is_dev_branch
    if is_dev_branch() and (file_name.endswith('.md') or file_name.endswith('.MD')):
        # Передаем в обработчик md файлов
        await handle_markdown_file(message)
        return
    
    await call_with_retries(
        message.answer,
        f"❌ Неподходящий тип файла: {file_name}\n\n"
        f"Пожалуйста, отправьте файл с расширением .ttf\n\n"
        f"Используйте команду /upload_font для загрузки шрифта."
    )



