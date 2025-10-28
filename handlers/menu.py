"""
Главное меню и навигация
"""

from aiogram import Router, F
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.filters import Command
from utils.db_utils import get_or_create_user, get_user_info
from config import PAGE_FORMATS

router = Router()


def get_main_menu_keyboard(grid_enabled: bool = False):
    """Главное меню с кнопками"""
    grid_button_text = "✅ Фон: клетка" if grid_enabled else "📐 Фон: клетка"
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="📎 Загрузить шрифт", callback_data="menu_upload_font"),
            InlineKeyboardButton(text="📄 Выбрать формат", callback_data="menu_set_format")
        ],
        [
            InlineKeyboardButton(text=grid_button_text, callback_data="toggle_grid")
        ],
        [
            InlineKeyboardButton(text="📝 Создать PDF", callback_data="menu_create_pdf")
        ],
        [
            InlineKeyboardButton(text="ℹ️ О боте", callback_data="menu_info")
        ]
    ])
    return keyboard


def get_back_keyboard(callback_data: str = "menu_main"):
    """Кнопка Назад"""
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="◀️ Назад", callback_data=callback_data)]
    ])
    return keyboard


def get_format_keyboard():
    """Кнопки выбора формата"""
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="📄 A4", callback_data="format_A4"),
            InlineKeyboardButton(text="📄 A5", callback_data="format_A5")
        ],
        [InlineKeyboardButton(text="◀️ Назад", callback_data="menu_main")],
        [InlineKeyboardButton(text="🏠 Главное меню", callback_data="menu_main")]
    ])
    return keyboard


def get_create_pdf_keyboard():
    """Кнопки для создания PDF"""
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🏠 Главное меню", callback_data="menu_main")]
    ])
    return keyboard


import logging

logger = logging.getLogger(__name__)

# Глобальная защита от дублирования - используем set для отслеживания обработанных сообщений
import time
_processed_messages = set()  # Множество обработанных message_id

# Используем один декоратор для обеих команд, чтобы избежать дублирования
@router.message(Command("start", "menu"))
async def cmd_start(message: Message):
    """Обработчик команды /start - главное меню"""
    global _processed_messages
    
    user_id = message.from_user.id
    message_id = message.message_id
    
    # Создаем уникальный ключ для этого сообщения
    unique_key = (user_id, message_id)
    
    # Проверяем, не обрабатывали ли мы уже это сообщение
    if unique_key in _processed_messages:
        logger.warning(f"Duplicate /start ignored: user={user_id}, msg_id={message_id}")
        return
    
    # Помечаем сообщение как обрабатываемое
    _processed_messages.add(unique_key)
    
    # Очищаем старые записи (оставляем только последние 1000)
    if len(_processed_messages) > 1000:
        # Оставляем только последние 500 записей
        _processed_messages.clear()
        _processed_messages.add(unique_key)
    
    try:
        logger.info(f"Processing /start for user {user_id}, message_id={message_id}")
        
        user = get_or_create_user(user_id)
        user_info = get_user_info(user_id)
        
        welcome_text = (
            "👋 Добро пожаловать в бот для генерации PDF-конспектов!\n\n"
            "📋 Текущие настройки:\n"
        )
        
        if user['font_path']:
            font_name = user['font_path'].split('/')[-1]
            welcome_text += f"✓ Шрифт: {font_name}\n"
        else:
            welcome_text += "⚠ Шрифт не загружен\n"
        
        format_name = PAGE_FORMATS.get(user['page_format'], user['page_format'] or 'A4')
        welcome_text += f"✓ Формат: {format_name}\n"
        
        grid_enabled = user_info.get('grid_enabled', False) if user_info else False
        grid_status = "✓ Включен" if grid_enabled else "✗ Выключен"
        welcome_text += f"✓ Фон клетка: {grid_status}\n\n"
        
        welcome_text += "Выберите действие:"
        
        # Отправляем сообщение только один раз
        await message.answer(welcome_text, reply_markup=get_main_menu_keyboard(grid_enabled))
        logger.info(f"✓ Successfully sent /start response to user {user_id}")
        
    except Exception as e:
        logger.error(f"✗ Error in /start handler for user {user_id}: {e}", exc_info=True)
        # При ошибке удаляем из кэша, чтобы можно было повторить
        _processed_messages.discard(unique_key)
        raise


@router.callback_query(F.data == "menu_main")
async def menu_main(callback: CallbackQuery):
    """Главное меню"""
    user_id = callback.from_user.id
    user = get_or_create_user(user_id)
    user_info = get_user_info(user_id)
    
    welcome_text = (
        "👋 Главное меню\n\n"
        "📋 Текущие настройки:\n"
    )
    
    if user['font_path']:
        font_name = user['font_path'].split('/')[-1]
        welcome_text += f"✓ Шрифт: {font_name}\n"
    else:
        welcome_text += "⚠ Шрифт не загружен\n"
    
    format_name = PAGE_FORMATS.get(user['page_format'], user['page_format'] or 'A4')
    welcome_text += f"✓ Формат: {format_name}\n"
    
    grid_enabled = user_info.get('grid_enabled', False) if user_info else False
    grid_status = "✓ Включен" if grid_enabled else "✗ Выключен"
    welcome_text += f"✓ Фон клетка: {grid_status}\n\n"
    
    welcome_text += "Выберите действие:"
    
    await callback.message.edit_text(welcome_text, reply_markup=get_main_menu_keyboard(grid_enabled))


@router.callback_query(F.data == "menu_upload_font")
async def menu_upload_font(callback: CallbackQuery):
    """Меню загрузки шрифта"""
    user = get_user_info(callback.from_user.id)
    
    text = "📎 Загрузка шрифта\n\n"
    
    if user and user['font_path']:
        font_name = user['font_path'].split('/')[-1]
        text += f"Текущий шрифт: {font_name}\n\n"
    else:
        text += "⚠ Шрифт еще не загружен\n\n"
    
    text += "Отправьте файл с расширением .ttf или .otf в следующем сообщении."
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="◀️ Назад", callback_data="menu_main")],
        [InlineKeyboardButton(text="🏠 Главное меню", callback_data="menu_main")]
    ])
    
    await callback.message.edit_text(text, reply_markup=keyboard)
    await callback.answer()
    
    # Отправляем отдельное сообщение с инструкцией
    await callback.message.answer(
        "📤 Отправьте файл прямо сейчас:",
        reply_markup=keyboard
    )


@router.callback_query(F.data == "menu_set_format")
async def menu_set_format(callback: CallbackQuery):
    """Меню выбора формата"""
    user = get_user_info(callback.from_user.id)
    
    text = "📄 Выбор формата страницы\n\n"
    
    if user:
        current_format = PAGE_FORMATS.get(user['page_format'], user['page_format'] or 'A4')
        text += f"Текущий формат: {current_format}\n\n"
    
    text += "Выберите формат:"
    
    await callback.message.edit_text(text, reply_markup=get_format_keyboard())
    await callback.answer()


@router.callback_query(F.data == "menu_create_pdf")
async def menu_create_pdf(callback: CallbackQuery):
    """Меню создания PDF"""
    user_id = callback.from_user.id
    user = get_user_info(user_id)
    
    text = "📝 Создание PDF\n\n"
    
    # Проверяем готовность
    issues = []
    ready_to_create = True
    
    if not user or not user['font_path']:
        issues.append("❌ Шрифт не загружен")
        ready_to_create = False
    else:
        font_name = user['font_path'].split('/')[-1]
        text += f"✓ Шрифт: {font_name}\n"
    
    if not user or not user['page_format']:
        issues.append("❌ Формат не выбран")
        ready_to_create = False
    else:
        format_name = PAGE_FORMATS.get(user['page_format'], user['page_format'])
        text += f"✓ Формат: {format_name}\n"
    
    if issues:
        text += "\n" + "\n".join(issues)
        text += "\n\nИсправьте настройки и попробуйте снова."
    else:
        text += "\n✅ Все готово!\n\nОтправьте текст для генерации PDF в следующем сообщении."
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="◀️ Назад", callback_data="menu_main")],
        [InlineKeyboardButton(text="🏠 Главное меню", callback_data="menu_main")]
    ])
    
    await callback.message.edit_text(text, reply_markup=keyboard)
    await callback.answer()
    
    if ready_to_create:
        await callback.message.answer(
            "💬 Отправьте текст прямо сейчас:",
            reply_markup=keyboard
        )


@router.callback_query(F.data == "menu_info")
async def menu_info(callback: CallbackQuery):
    """Информация о боте"""
    text = (
        "ℹ️ О боте\n\n"
        "Этот бот генерирует PDF-конспекты с вашим рукописным шрифтом.\n\n"
        "📋 Доступные команды:\n"
        "• /start - главное меню\n"
        "• /menu - главное меню\n\n"
        "📝 Как использовать:\n"
        "1. Загрузите TTF/OTF шрифт\n"
        "2. Выберите формат страницы (A4 или Тетрадь)\n"
        "3. Отправьте текст боту\n\n"
        "Бот создаст PDF с вашим шрифтом!"
    )
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="◀️ Назад", callback_data="menu_main")],
        [InlineKeyboardButton(text="🏠 Главное меню", callback_data="menu_main")]
    ])
    
    await callback.message.edit_text(text, reply_markup=keyboard)
    await callback.answer()

