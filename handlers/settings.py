"""
Меню настроек
"""

from aiogram import Router, F
from aiogram.types import CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from utils.db_utils import get_user_info, get_or_create_user, get_font_requirement_progress, get_user_fonts_by_type
from config import PAGE_FORMATS
from utils.telegram_retry import call_with_retries
from handlers.menu import get_main_menu_keyboard, get_format_keyboard

router = Router()

FONT_TYPE_LABELS = {
    "cyrillic_full": "Кириллица (строчные и заглавные)",
    "digits": "Цифры и спецсимволы",
    "latin": "Латиница",
}

UPLOAD_SEQUENCE = ["cyrillic_full", "digits", "latin"]


@router.callback_query(F.data == "menu_settings")
async def menu_settings(callback: CallbackQuery):
    """Меню настроек"""
    user_id = callback.from_user.id
    telegram_user = callback.from_user
    user = get_or_create_user(
        user_id,
        username=getattr(telegram_user, "username", None),
        first_name=getattr(telegram_user, "first_name", None),
        last_name=getattr(telegram_user, "last_name", None),
    )
    user_info = get_user_info(user_id)
    
    fonts_by_type = get_user_fonts_by_type(user_id)
    progress = get_font_requirement_progress(user_id)
    
    text = "⚙️ Настройки\n\n"
    
    # Формат
    format_name = PAGE_FORMATS.get(user['page_format'], user['page_format'] or 'A4')
    text += f"📄 Формат: {format_name}\n"
    
    # Сетка
    grid_enabled = user_info.get('grid_enabled', False) if user_info else False
    grid_status = "✓ Включен" if grid_enabled else "✗ Выключен"
    text += f"📐 Фон клетка: {grid_status}\n\n"
    
    # Прогресс шрифтов
    text += "📊 Прогресс шрифтов:\n"
    for font_type in UPLOAD_SEQUENCE:
        info = progress.get(font_type, {"current": 0, "required": 0})
        label = FONT_TYPE_LABELS.get(font_type, font_type)
        status_icon = "✓" if info["current"] >= info["required"] else "⬜"
        text += f"{status_icon} {label}: {info['current']}/{info['required']}\n"
    
    # Убрано упоминание базового шрифта из интерфейса
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📄 Изменить формат", callback_data="menu_set_format")],
        [InlineKeyboardButton(text="📐 Фон: клетка", callback_data="toggle_grid")],
        [InlineKeyboardButton(text="🏠 Главное меню", callback_data="menu_main")]
    ])
    
    await call_with_retries(callback.message.edit_text, text, reply_markup=keyboard)
    await call_with_retries(callback.answer)

