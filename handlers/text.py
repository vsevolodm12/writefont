"""
Обработчики текстовых сообщений
"""

from aiogram import Router, F
from aiogram.types import Message, FSInputFile
from utils.db_utils import get_user_info, update_job_pdf_path, update_job_status_failed
from database.connection import get_db_connection
from pdf_generator import generate_pdf_for_job
import time
import os

router = Router()


@router.message(F.text & ~F.text.startswith('/'))
async def handle_text_message(message: Message):
    """Обработчик текстовых сообщений для сохранения в jobs и генерации PDF"""
    user_id = message.from_user.id
    text_content = message.text.strip()
    
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
        
        # Генерируем PDF
        start_time = time.time()
        pdf_path = generate_pdf_for_job(
            job_id, 
            text_content, 
            user['font_path'], 
            user['page_format'],
            grid_enabled
        )
        execution_time_ms = int((time.time() - start_time) * 1000)
        
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
            conn.close()

