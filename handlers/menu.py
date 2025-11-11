"""
Главное меню и навигация
"""

from aiogram import Router, F
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.filters import Command
from utils.db_utils import (
    get_or_create_user,
    get_user_info,
    reset_user_fonts,
    get_font_requirement_progress,
    has_minimum_font_set,
    get_user_fonts_by_type,
)
from config import PAGE_FORMATS
from utils.telegram_retry import call_with_retries

router = Router()

FONT_TYPE_LABELS = {
    "cyrillic_full": "Кириллица (строчные и заглавные)",
    "digits": "Цифры и спецсимволы",
    "latin": "Латиница",
}

UPLOAD_SEQUENCE = ["cyrillic_full", "digits", "latin"]


def get_main_menu_keyboard(grid_enabled: bool = False, ready_to_generate: bool = True):
    """Главное меню с кнопками"""
    grid_button_text = "✅ Фон: клетка" if grid_enabled else "📐 Фон: клетка"
    pdf_button_text = "📝 Создать PDF" if ready_to_generate else "📝 Создать PDF (после загрузки шрифтов)"
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="📥 Загрузить шрифты", callback_data="menu_upload_font"),
            InlineKeyboardButton(text="📄 Выбрать формат", callback_data="menu_set_format")
        ],
        [
            InlineKeyboardButton(text=grid_button_text, callback_data="toggle_grid")
        ],
        [
            InlineKeyboardButton(text=pdf_button_text, callback_data="menu_create_pdf")
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
        [InlineKeyboardButton(text="🏠 Главное меню", callback_data="menu_main")]
    ])
    return keyboard


def get_preset_fonts_keyboard():
    """Кнопки выбора готовых наборов шрифтов"""
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="📦 Набор 1", callback_data="preset_1")
        ],
        [
            InlineKeyboardButton(text="📦 Набор 2", callback_data="preset_2")
        ],
        [
            InlineKeyboardButton(text="📦 Набор 3", callback_data="preset_3")
        ],
        [
            InlineKeyboardButton(text="📦 Набор 4", callback_data="preset_4")
        ],
        [
            InlineKeyboardButton(text="📦 Набор 5", callback_data="preset_5")
        ],
        [
            InlineKeyboardButton(text="🏠 Главное меню", callback_data="menu_main")
        ]
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
        
        fonts_by_type = get_user_fonts_by_type(user_id)
        progress = get_font_requirement_progress(user_id)
        ready_to_generate = has_minimum_font_set(user_id)

        welcome_text = "📋 Текущие настройки:\n\n"

        base_fonts = fonts_by_type.get("base", [])
        if base_fonts:
            welcome_text += f"👑 Базовый кириллический шрифт:\n• {base_fonts[0].split('/')[-1]}\n\n"
        else:
            welcome_text += "⚠️ Базовый кириллический шрифт не выбран\n\n"

        welcome_text += "📊 Прогресс загрузки шрифтов:\n"
        for font_type in UPLOAD_SEQUENCE:
            info = progress.get(font_type, {"current": 0, "required": 0})
            label = FONT_TYPE_LABELS.get(font_type, font_type)
            status_icon = "✅" if info["current"] >= info["required"] else "⬜️"
            welcome_text += f"{status_icon} {label}: {info['current']}/{info['required']}\n"
        welcome_text += "\n"
        
        format_name = PAGE_FORMATS.get(user['page_format'], user['page_format'] or 'A4')
        grid_enabled = user_info.get('grid_enabled', False) if user_info else False
        grid_status = "Включен" if grid_enabled else "Выключен"
        
        welcome_text += f"\nНастройки:\n"
        welcome_text += f"✓ Формат: {format_name}\n"
        welcome_text += f"✓ Фон клетка: {grid_status}\n\n"
        
        if not ready_to_generate:
            welcome_text += "⚠️ Загрузите шрифты по шагам, прежде чем создавать PDF.\n\n"
        welcome_text += "Выберите действие:"
        
        # Отправляем сообщение только один раз
        await call_with_retries(
            message.answer,
            welcome_text,
            reply_markup=get_main_menu_keyboard(grid_enabled, ready_to_generate),
        )
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
    
    fonts_by_type = get_user_fonts_by_type(user_id)
    progress = get_font_requirement_progress(user_id)
    ready_to_generate = has_minimum_font_set(user_id)

    welcome_text = "📋 Текущие настройки:\n\n"

    base_fonts = fonts_by_type.get("base", [])
    if base_fonts:
        welcome_text += f"👑 Базовый кириллический шрифт:\n• {base_fonts[0].split('/')[-1]}\n\n"
    else:
        welcome_text += "⚠️ Базовый кириллический шрифт не выбран\n\n"

    welcome_text += "📊 Прогресс загрузки шрифтов:\n"
    for font_type in UPLOAD_SEQUENCE:
        info = progress.get(font_type, {"current": 0, "required": 0})
        label = FONT_TYPE_LABELS.get(font_type, font_type)
        status_icon = "✅" if info["current"] >= info["required"] else "⬜️"
        welcome_text += f"{status_icon} {label}: {info['current']}/{info['required']}\n"
    welcome_text += "\n"
    
    format_name = PAGE_FORMATS.get(user['page_format'], user['page_format'] or 'A4')
    grid_enabled = user_info.get('grid_enabled', False) if user_info else False
    grid_status = "Включен" if grid_enabled else "Выключен"
    
    welcome_text += f"\nНастройки:\n"
    welcome_text += f"✓ Формат: {format_name}\n"
    welcome_text += f"✓ Фон клетка: {grid_status}\n\n"
    
    if not ready_to_generate:
        welcome_text += "⚠️ Загрузите шрифты по шагам, прежде чем создавать PDF.\n\n"
    welcome_text += "Выберите действие:"
    
    await call_with_retries(
        callback.message.edit_text,
        welcome_text,
        reply_markup=get_main_menu_keyboard(grid_enabled, ready_to_generate),
    )
    await call_with_retries(callback.answer)


@router.callback_query(F.data == "menu_upload_font")
async def menu_upload_font(callback: CallbackQuery):
    """Меню загрузки шрифта"""
    user = get_user_info(callback.from_user.id)
    
    progress = get_font_requirement_progress(callback.from_user.id)
    fonts_by_type = get_user_fonts_by_type(callback.from_user.id)

    text = "📥 Инструкция по загрузке шрифтов\n\n"
    text += "Следуйте шагам:\n"
    for font_type in UPLOAD_SEQUENCE:
        info = progress.get(font_type, {"current": 0, "required": 0})
        label = FONT_TYPE_LABELS.get(font_type, font_type)
        status_icon = "✅" if info["current"] >= info["required"] else "⬜️"
        text += f"{status_icon} {label}: {info['current']}/{info['required']}\n"
    text += "\n"

    base_fonts = fonts_by_type.get("base", [])
    if base_fonts:
        text += f"👑 Базовый шрифт: {base_fonts[0].split('/')[-1]}\n\n"
    else:
        text += "⚠️ Базовый кириллический шрифт ещё не выбран.\n\n"

    text += (
        "🔁 Порядок загрузки:\n"
        "1) Три кириллических шрифта (строчные и заглавные).\n"
        "2) Два шрифта с цифрами и спецсимволами.\n"
        "3) Два шрифта с латиницей.\n\n"
        "📤 Отправляйте .ttf или .otf файлы по одному. "
        "Бот автоматически распознает тип каждого шрифта.\n"
    )
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🗑 Сбросить шрифты", callback_data="reset_fonts")],
        [InlineKeyboardButton(text="🏠 Главное меню", callback_data="menu_main")]
    ])
    
    await call_with_retries(callback.message.edit_text, text, reply_markup=keyboard)
    await call_with_retries(callback.answer)


@router.callback_query(F.data == "menu_set_format")
async def menu_set_format(callback: CallbackQuery):
    """Меню выбора формата"""
    user = get_user_info(callback.from_user.id)
    
    text = "📄 Выбор формата страницы\n\n"
    
    if user:
        current_format = PAGE_FORMATS.get(user['page_format'], user['page_format'] or 'A4')
        text += f"Текущий формат: {current_format}\n\n"
    
    text += "Выберите формат страницы:"
    
    await call_with_retries(callback.message.edit_text, text, reply_markup=get_format_keyboard())
    await call_with_retries(callback.answer)


@router.callback_query(F.data == "menu_create_pdf")
async def menu_create_pdf(callback: CallbackQuery):
    """Меню создания PDF"""
    user_id = callback.from_user.id
    user = get_user_info(user_id)
    
    text = "📝 Создание PDF\n\n"

    ready_fonts = has_minimum_font_set(user_id)
    format_selected = bool(user and user.get('page_format'))
    if ready_fonts:
        text += "✅ Шрифты загружены\n"
    else:
        progress = get_font_requirement_progress(user_id)
        progress_lines = []
        for font_type in UPLOAD_SEQUENCE:
            info = progress.get(font_type, {"current": 0, "required": 0})
            label = FONT_TYPE_LABELS.get(font_type, font_type)
            status_icon = "✅" if info["current"] >= info["required"] else "⬜️"
            progress_lines.append(f"{status_icon} {label}: {info['current']}/{info['required']}")
        text += "⚠️ Не хватает обязательных шрифтов.\n\n" + "\n".join(progress_lines) + "\n\n"
    
    if format_selected:
        format_name = PAGE_FORMATS.get(user['page_format'], user['page_format'])
        text += f"✅ Формат: {format_name}\n"
    else:
        text += "⚠️ Формат страницы не выбран\n"
    
    if ready_fonts and format_selected:
        text += "\n✅ Все готово!\n\nОтправьте текст для генерации PDF:"
    else:
        text += "\nИспользуйте меню, чтобы загрузить недостающие шрифты и выбрать формат."
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🏠 Главное меню", callback_data="menu_main")]
    ])
    
    await call_with_retries(callback.message.edit_text, text, reply_markup=keyboard)
    await call_with_retries(callback.answer)
    


@router.callback_query(F.data == "reset_fonts")
async def reset_fonts_handler(callback: CallbackQuery):
    """Обработчик сброса всех шрифтов"""
    user_id = callback.from_user.id
    
    if reset_user_fonts(user_id):
        await call_with_retries(callback.answer, "✅ Шрифты сброшены")
        await menu_upload_font(callback)
    else:
        await call_with_retries(callback.answer, "❌ Ошибка при сбросе шрифтов", show_alert=True)


