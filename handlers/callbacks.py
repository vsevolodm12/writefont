"""
Обработчики callback-запросов (кнопки)
"""

from aiogram import Router
from aiogram.types import CallbackQuery
from config import PAGE_FORMATS
from utils.db_utils import update_user_page_format, get_user_info, get_or_create_user
from aiogram.exceptions import TelegramBadRequest

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

