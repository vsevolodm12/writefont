"""
Обработчики callback-запросов (кнопки)
"""

from aiogram import Router
from aiogram.types import CallbackQuery
from config import PAGE_FORMATS
from utils.db_utils import update_user_page_format, get_user_info, get_or_create_user

router = Router()


@router.callback_query(lambda c: c.data.startswith("format_"))
async def process_format_callback(callback: CallbackQuery):
    """Обработчик выбора формата страницы"""
    user_id = callback.from_user.id
    
    # Убеждаемся что пользователь существует
    get_or_create_user(user_id)
    
    # Извлекаем формат из callback_data
    format_type = callback.data.replace("format_", "")
    
    if format_type not in PAGE_FORMATS:
        await callback.answer("❌ Неверный формат.", show_alert=True)
        return
    
    # Обновляем формат в БД
    if update_user_page_format(user_id, format_type):
        # Без уведомлений - просто обновляем меню выбора формата
        from handlers.menu import get_format_keyboard
        from utils.db_utils import get_user_info
        
        user = get_user_info(user_id)
        
        text = "📄 Выбор формата страницы\n\n"
        
        if user:
            current_format = PAGE_FORMATS.get(user['page_format'], user['page_format'] or 'A4')
            text += f"Текущий формат: {current_format}\n\n"
        
        text += "Выберите формат:"
        
        await callback.message.edit_text(text, reply_markup=get_format_keyboard())
        await callback.answer()  # Тихий ответ без текста
    else:
        await callback.answer("❌ Ошибка при обновлении формата.", show_alert=True)

