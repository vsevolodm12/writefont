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
        format_name = PAGE_FORMATS[format_type]
        await callback.answer(f"✅ Формат установлен: {format_name}", show_alert=True)
        
        from handlers.menu import get_main_menu_keyboard
        from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
        
        next_keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="📝 Создать PDF", callback_data="menu_create_pdf")],
            [InlineKeyboardButton(text="🏠 Главное меню", callback_data="menu_main")]
        ])
        
        text = (
            f"✅ Формат страницы изменен!\n\n"
            f"📄 Формат: {format_name}\n\n"
            "Теперь можете создавать PDF. Отправьте текст боту или используйте кнопку ниже."
        )
        
        await callback.message.edit_text(text, reply_markup=next_keyboard)
    else:
        await callback.answer("❌ Ошибка при обновлении формата.", show_alert=True)

