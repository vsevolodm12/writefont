"""
Главное меню и навигация
"""

from aiogram import Router, F
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.filters import Command
from utils.db_utils import get_or_create_user, get_user_info, reset_user_fonts
from config import PAGE_FORMATS

router = Router()


def get_welcome_menu_keyboard():
    """Главное меню приветствия с выбором способа работы"""
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="✏️ Создать свой шрифт", callback_data="menu_create_custom_font")
        ],
        [
            InlineKeyboardButton(text="📦 Выбрать готовый шрифт", callback_data="menu_choose_preset")
        ]
    ])
    return keyboard


def get_main_menu_keyboard(grid_enabled: bool = False):
    """Меню для создания своего шрифта (старое главное меню)"""
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
            InlineKeyboardButton(text="🏠 Главное меню", callback_data="menu_main")
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
        [InlineKeyboardButton(text="◀️ Назад", callback_data="menu_create_custom_font")]
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
        
        welcome_text = (
            "👋 Привет! Это бот для создания конспектов с вашим почерком.\n\n"
            "📝 Бот преобразует ваш текст в PDF с реалистичным рукописным шрифтом.\n\n"
            "Вы можете:\n"
            "• ✏️ Создать свой уникальный шрифт\n"
            "• 📦 Использовать готовые наборы шрифтов\n\n"
            "Выберите вариант:"
        )
        
        # Отправляем сообщение только один раз
        await message.answer(welcome_text, reply_markup=get_welcome_menu_keyboard())
        logger.info(f"✓ Successfully sent /start response to user {user_id}")
        
    except Exception as e:
        logger.error(f"✗ Error in /start handler for user {user_id}: {e}", exc_info=True)
        # При ошибке удаляем из кэша, чтобы можно было повторить
        _processed_messages.discard(unique_key)
        raise


@router.callback_query(F.data == "menu_main")
async def menu_main(callback: CallbackQuery):
    """Главное меню приветствия"""
    welcome_text = (
        "👋 Привет! Это бот для создания конспектов с вашим почерком.\n\n"
        "📝 Бот преобразует ваш текст в PDF с реалистичным рукописным шрифтом.\n\n"
        "Вы можете:\n"
        "• ✏️ Создать свой уникальный шрифт\n"
        "• 📦 Использовать готовые наборы шрифтов\n\n"
        "Выберите вариант:"
    )
    
    await callback.message.edit_text(welcome_text, reply_markup=get_welcome_menu_keyboard())
    await callback.answer()


@router.callback_query(F.data == "menu_create_custom_font")
async def menu_create_custom_font(callback: CallbackQuery):
    """Меню создания своего шрифта (старое главное меню)"""
    user_id = callback.from_user.id
    user = get_or_create_user(user_id)
    user_info = get_user_info(user_id)
    
    welcome_text = "📋 Текущие настройки:\n\n"
    
    # Показываем все шрифты по порядку
    all_fonts = []
    if user['font_path']:
        all_fonts.append(user['font_path'])
    variant_fonts = user_info.get('variant_fonts', [])
    if variant_fonts:
        all_fonts.extend(variant_fonts)
    
    if all_fonts:
        welcome_text += "Шрифты:\n"
        for idx, font_path in enumerate(all_fonts, 1):
            font_name = font_path.split('/')[-1]
            welcome_text += f"{idx}. {font_name}\n"
    else:
        welcome_text += "Шрифты не загружены\n"
    
    format_name = PAGE_FORMATS.get(user['page_format'], user['page_format'] or 'A4')
    grid_enabled = user_info.get('grid_enabled', False) if user_info else False
    grid_status = "Включен" if grid_enabled else "Выключен"
    
    welcome_text += f"\nНастройки:\n"
    welcome_text += f"✓ Формат: {format_name}\n"
    welcome_text += f"✓ Фон клетка: {grid_status}\n\n"
    
    welcome_text += "Выберите действие:"
    
    await callback.message.edit_text(welcome_text, reply_markup=get_main_menu_keyboard(grid_enabled))
    await callback.answer()


@router.callback_query(F.data == "menu_choose_preset")
async def menu_choose_preset(callback: CallbackQuery):
    """Меню выбора готовых наборов шрифтов"""
    text = (
        "📦 Выбор готового набора шрифтов\n\n"
        "Выберите один из готовых наборов шрифтов:\n\n"
        "💡 Каждый набор содержит несколько вариаций шрифта для реалистичного почерка."
    )
    
    await callback.message.edit_text(text, reply_markup=get_preset_fonts_keyboard())
    await callback.answer()


@router.callback_query(F.data.startswith("preset_"))
async def handle_preset_choice(callback: CallbackQuery):
    """Обработчик выбора preset (заглушка)"""
    preset_num = callback.data.split("_")[1]
    
    text = (
        f"📦 Набор {preset_num}\n\n"
        "🚧 Функция в разработке\n\n"
        "Скоро здесь будут готовые наборы шрифтов для быстрого старта."
    )
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="◀️ Назад", callback_data="menu_choose_preset")]
    ])
    
    await callback.message.edit_text(text, reply_markup=keyboard)
    await callback.answer()


@router.callback_query(F.data == "menu_upload_font")
async def menu_upload_font(callback: CallbackQuery):
    """Меню загрузки шрифта"""
    user = get_user_info(callback.from_user.id)
    
    text = "📎 Загрузка шрифтов\n\n"
    
    # Показываем все шрифты по порядку
    all_fonts = []
    if user and user['font_path']:
        all_fonts.append(user['font_path'])
    variant_fonts = user.get('variant_fonts', [])
    if variant_fonts:
        all_fonts.extend(variant_fonts)
    
    if all_fonts:
        text += "Загружено шрифтов:\n"
        for idx, font_path in enumerate(all_fonts, 1):
            font_name = font_path.split('/')[-1]
            text += f"{idx}. {font_name}\n"
        text += "\n"
    else:
        text += "⚠ Шрифты еще не загружены\n\n"
    
    text += (
        "💡 Для реалистичного почерка загрузите 2-3 похожих шрифта.\n\n"
        "📤 Отправьте файлы .ttf или .otf по одному."
    )
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🗑 Сбросить шрифты", callback_data="reset_fonts")],
        [InlineKeyboardButton(text="◀️ Назад", callback_data="menu_create_custom_font")]
    ])
    
    await callback.message.edit_text(text, reply_markup=keyboard)
    await callback.answer()


@router.callback_query(F.data == "menu_set_format")
async def menu_set_format(callback: CallbackQuery):
    """Меню выбора формата"""
    user = get_user_info(callback.from_user.id)
    
    text = "📄 Выбор формата страницы\n\n"
    
    if user:
        current_format = PAGE_FORMATS.get(user['page_format'], user['page_format'] or 'A4')
        text += f"Текущий формат: {current_format}\n\n"
    
    text += "Выберите формат страницы:"
    
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
        issues.append("Шрифт не загружен")
        ready_to_create = False
    else:
        text += "✅ Шрифты загружены\n"
    
    if not user or not user['page_format']:
        issues.append("Формат не выбран")
        ready_to_create = False
    else:
        format_name = PAGE_FORMATS.get(user['page_format'], user['page_format'])
        text += f"✅ Формат: {format_name}\n"
    
    if issues:
        text += "\n⚠ Ошибки:\n" + "\n".join([f"• {issue}" for issue in issues])
        text += "\n\nИсправьте настройки и попробуйте снова."
    else:
        text += "\n✅ Все готово!\n\nОтправьте текст для генерации PDF:"
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="◀️ Назад", callback_data="menu_create_custom_font")]
    ])
    
    await callback.message.edit_text(text, reply_markup=keyboard)
    await callback.answer()
    


@router.callback_query(F.data == "reset_fonts")
async def reset_fonts_handler(callback: CallbackQuery):
    """Обработчик сброса всех шрифтов"""
    user_id = callback.from_user.id
    
    if reset_user_fonts(user_id):
        await callback.answer("✅ Шрифты сброшены")
        await menu_upload_font(callback)
    else:
        await callback.answer("❌ Ошибка при сбросе шрифтов", show_alert=True)


