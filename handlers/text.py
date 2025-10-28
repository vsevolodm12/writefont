"""
Обработчики текстовых сообщений
"""

from aiogram import Router, F
from aiogram.types import Message, FSInputFile
from utils.db_utils import get_user_info, update_job_pdf_path, update_job_status_failed
from database.connection import get_db_connection, return_db_connection
from pdf_generator import generate_pdf_for_job
from utils.executors import pdf_executor
from utils.rate_limit import check_rate_limit
from utils.metrics import metrics
import time
import os
import asyncio
import logging

logger = logging.getLogger(__name__)

router = Router()


@router.message(F.text & ~F.text.startswith('/'))
async def handle_text_message(message: Message):
    """Обработчик текстовых сообщений для сохранения в jobs и генерации PDF"""
    user_id = message.from_user.id
    text_content = message.text.strip()
    
    # Проверка rate limit
    allowed, error_msg = check_rate_limit(user_id)
    if not allowed:
        await message.answer(error_msg)
        logger.warning(f"Rate limit exceeded for user {user_id}")
        return
    
    # Проверка текста
    if not text_content:
        await message.answer("❌ Текст не может быть пустым.")
        return
    
    if len(text_content) < 3:
        await message.answer("❌ Текст слишком короткий (минимум 3 символа).")
        return
    
    if len(text_content) > 100000:
        await message.answer("❌ Текст слишком длинный (максимум 100000 символов).")
        return
    
    # Получаем информацию о пользователе
    user = get_user_info(user_id)
    if not user:
        from utils.db_utils import get_or_create_user
        user = get_or_create_user(user_id)
    
    from handlers.menu import get_back_keyboard
    
    # Проверка шрифта
    if not user['font_path']:
        from handlers.menu import get_main_menu_keyboard
        await message.answer(
            "❌ Шрифт не загружен.\n\nИспользуйте меню для загрузки шрифта.",
            reply_markup=get_main_menu_keyboard()
        )
        return
    
    if not os.path.exists(user['font_path']):
        from handlers.menu import get_main_menu_keyboard
        await message.answer(
            "❌ Файл шрифта не найден.\n\nЗагрузите шрифт заново через меню.",
            reply_markup=get_main_menu_keyboard()
        )
        return
    
    # Проверка формата страницы
    if not user['page_format']:
        from handlers.menu import get_main_menu_keyboard
        await message.answer(
            "❌ Формат страницы не выбран.\n\nВыберите формат через меню.",
            reply_markup=get_main_menu_keyboard()
        )
        return
    
    if user['page_format'] not in ['A4', 'A5']:
        from handlers.menu import get_main_menu_keyboard
        await message.answer(
            "❌ Некорректный формат страницы.\n\nВыберите формат через меню.",
            reply_markup=get_main_menu_keyboard()
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
        
        await message.answer("⏳ Генерирую PDF...")
        
        # Получаем настройку сетки
        grid_enabled = user.get('grid_enabled', False)
        
        # Генерируем PDF асинхронно в отдельном потоке
        start_time = time.time()
        loop = asyncio.get_event_loop()
        pdf_path = await loop.run_in_executor(
            pdf_executor,
            generate_pdf_for_job,
            job_id, 
            text_content, 
            user['font_path'], 
            user['page_format'],
            grid_enabled
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
            from handlers.menu import get_main_menu_keyboard
            
            pdf_file = FSInputFile(pdf_path)
            await message.answer_document(
                document=pdf_file,
                caption=f"✅ PDF сгенерирован успешно!\n⏱ Время: {execution_time_ms}мс"
            )
            
            # Предлагаем создать еще один
            await message.answer(
                "📝 Хотите создать еще один PDF?\nОтправьте новый текст.",
                reply_markup=get_main_menu_keyboard()
            )
        else:
            from handlers.menu import get_main_menu_keyboard
            await message.answer(
                "❌ Ошибка: PDF файл не найден",
                reply_markup=get_main_menu_keyboard()
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
        await message.answer(
            f"❌ Ошибка при генерации PDF: {str(e)}\n\nПопробуйте снова или вернитесь в меню.",
            reply_markup=get_main_menu_keyboard()
        )
    finally:
        if cursor:
            cursor.close()
        if conn:
            return_db_connection(conn)

