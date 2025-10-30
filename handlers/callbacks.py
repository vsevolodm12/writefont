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
        # После выбора формата возвращаем в главное меню
        from handlers.menu import get_main_menu_keyboard
        user = get_user_info(user_id)
        
        # Сообщение как в меню
        welcome_text = (
            "👋 Главное меню\n\n"
            "📋 Текущие настройки:\n"
        )
        
        if user and user.get('font_path'):
            font_name = user['font_path'].split('/')[-1]
            welcome_text += f"✓ Шрифт: {font_name}\n"
        else:
            welcome_text += "⚠ Шрифт не загружен\n"
        
        current_format = PAGE_FORMATS.get(user.get('page_format') if user else None, (user and user.get('page_format')) or 'A4')
        welcome_text += f"✓ Формат: {current_format}\n"
        
        grid_enabled = (user or {}).get('grid_enabled', False)
        grid_status = "✓ Включен" if grid_enabled else "✗ Выключен"
        welcome_text += f"✓ Фон клетка: {grid_status}\n\n"
        welcome_text += "Выберите действие:"
        
        await callback.message.edit_text(welcome_text, reply_markup=get_main_menu_keyboard(grid_enabled))
        await callback.answer(f"✅ Формат установлен: {current_format}")
    else:
        await callback.answer("❌ Ошибка при обновлении формата.", show_alert=True)

