"""
Обработчики управления сеткой
"""

from aiogram import Router, F
from aiogram.types import CallbackQuery
from utils.db_utils import get_user_info, update_user_grid_setting, get_or_create_user
from handlers.menu import get_main_menu_keyboard, menu_main

router = Router()


@router.callback_query(F.data == "toggle_grid")
async def toggle_grid(callback: CallbackQuery):
    """Переключение фоновой сетки"""
    user_id = callback.from_user.id
    
    # Убеждаемся что пользователь существует
    telegram_user = callback.from_user
    get_or_create_user(
        user_id,
        username=getattr(telegram_user, "username", None),
        first_name=getattr(telegram_user, "first_name", None),
        last_name=getattr(telegram_user, "last_name", None),
    )
    
    # Получаем текущее состояние
    user = get_user_info(user_id)
    current_state = user.get('grid_enabled', False) if user else False
    
    # Переключаем
    new_state = not current_state
    
    # Обновляем в БД
    if update_user_grid_setting(user_id, new_state):
        status = "включен" if new_state else "выключен"
        await callback.answer(f"✅ Фон клетка {status}")
        
        # Обновляем главное меню
        await menu_main(callback)
    else:
        await callback.answer("❌ Ошибка при обновлении настроек")

