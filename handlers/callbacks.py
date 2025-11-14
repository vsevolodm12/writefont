"""
Обработчики callback-запросов (кнопки)
"""

from aiogram import Router
from aiogram.types import CallbackQuery, FSInputFile
from config import PAGE_FORMATS
from utils.db_utils import update_user_page_format, get_user_info, get_or_create_user
from aiogram.exceptions import TelegramBadRequest
from database.connection import get_db_connection, return_db_connection
from utils.telegram_retry import call_with_retries, call_with_fast_retries
from handlers.menu import get_main_menu_keyboard
import os
import logging

logger = logging.getLogger(__name__)

router = Router()


@router.callback_query(lambda c: c.data.startswith("format_"))
async def process_format_callback(callback: CallbackQuery):
    """Обработчик выбора формата страницы"""
    user_id = callback.from_user.id
    
    # Убеждаемся что пользователь существует
    telegram_user = callback.from_user
    get_or_create_user(
        user_id,
        username=getattr(telegram_user, "username", None),
        first_name=getattr(telegram_user, "first_name", None),
        last_name=getattr(telegram_user, "last_name", None),
    )
    
    # Извлекаем формат из callback_data
    format_type = callback.data.replace("format_", "")
    
    if format_type not in PAGE_FORMATS:
        await callback.answer("❌ Неверный формат.", show_alert=True)
        return
    
    # Проверяем текущий формат и при необходимости обновляем
    user_before = get_user_info(user_id) or {}
    current_before = user_before.get('page_format')
    update_ok = True
    if current_before != format_type:
        update_ok = update_user_page_format(user_id, format_type)

    if update_ok:
        # Пытаемся перейти в главное меню через общий обработчик
        try:
            from handlers.menu import menu_main
            await callback.answer("✅ Формат обновлен.", show_alert=False)
            await menu_main(callback)
        except TelegramBadRequest:
            # Резервный путь: отправим новое сообщение с главным меню
            from handlers.menu import get_main_menu_keyboard
            user = get_user_info(user_id) or {}
            current_format = PAGE_FORMATS.get(user.get('page_format'), user.get('page_format') or 'A4')
            grid_enabled = bool(user.get('grid_enabled', False))
            welcome_text = (
                "👋 Главное меню\n\n"
                "📋 Текущие настройки:\n"
                f"✓ Шрифт: {user.get('font_path', 'не загружен').split('/')[-1] if user.get('font_path') else 'не загружен'}\n"
                f"✓ Формат: {current_format}\n"
                f"✓ Фон клетка: {'✓ Включен' if grid_enabled else '✗ Выключен'}\n\n"
                "Выберите действие:"
            )
            await callback.message.answer(welcome_text, reply_markup=get_main_menu_keyboard(grid_enabled))
        except Exception:
            # Любая другая ошибка
            await callback.answer("⚠ Не удалось обновить экран. Откройте главное меню.")
    else:
        await callback.answer("❌ Ошибка при обновлении формата.", show_alert=True)


@router.callback_query(lambda c: c.data.startswith("retry_pdf_"))
async def retry_pdf_delivery(callback: CallbackQuery):
    """Обработчик повторной отправки PDF"""
    user_id = callback.from_user.id
    job_id_str = callback.data.replace("retry_pdf_", "")
    
    try:
        # Извлекаем job_id из callback_data
        try:
            job_id = int(job_id_str)
        except ValueError:
            await callback.answer("❌ Неверный запрос.", show_alert=True)
            return
        
        # Получаем информацию о job из БД
        conn = get_db_connection()
        cursor = conn.cursor()
        try:
            cursor.execute(
                """
                SELECT user_id, pdf_path, execution_time_ms, status
                FROM jobs
                WHERE id = %s
                """,
                (job_id,)
            )
            row = cursor.fetchone()
            
            if not row:
                await callback.answer("❌ PDF не найден.", show_alert=True)
                return
            
            job_user_id, pdf_path, execution_time_ms, status = row
            
            # Проверяем, что job принадлежит пользователю
            if job_user_id != user_id:
                await callback.answer("❌ Доступ запрещен.", show_alert=True)
                return
            
            # Проверяем, что PDF существует
            if not pdf_path or not os.path.exists(pdf_path):
                await callback.answer("❌ PDF файл не найден.", show_alert=True)
                return
            
            # Пытаемся отправить PDF
            await callback.answer("⏳ Отправляю PDF...", show_alert=False)
            
            pdf_file = FSInputFile(pdf_path)
            await call_with_fast_retries(
                callback.message.answer_document,
                document=pdf_file,
                caption=f"✓ PDF сгенерирован\nВремя: {execution_time_ms}мс" if execution_time_ms else "✓ PDF сгенерирован",
            )
            
            # Получаем настройки пользователя для меню
            user = get_user_info(user_id) or {}
            grid_enabled = user.get('grid_enabled', False)
            
            await call_with_retries(
                callback.message.answer,
                "💡 Отправьте новый текст:\nя создам еще один конспект",
                reply_markup=get_main_menu_keyboard(grid_enabled),
            )
            
        finally:
            cursor.close()
            return_db_connection(conn)
            
    except Exception as exc:
        logger.error("Ошибка при повторной отправке PDF (job_id=%s): %s", job_id_str, exc, exc_info=True)
        await callback.answer("❌ Не удалось отправить PDF. Попробуйте позже.", show_alert=True)

