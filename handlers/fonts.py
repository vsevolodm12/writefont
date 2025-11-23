"""
Обработчики загрузки шрифтов
"""

from aiogram import Router, F
from aiogram.types import Message
from utils.db_utils import (
    save_font_file,
    get_user_info,
    analyze_and_register_font,
    get_font_requirement_progress,
    has_minimum_font_set,
    get_user_fonts_by_type,
)
from utils.telegram_retry import call_with_retries
import os
import logging

logger = logging.getLogger(__name__)
router = Router()

FONT_TYPE_LABELS = {
    "cyrillic_full": "Кириллический (строчные и заглавные)",
    "digits": "Цифры и спецсимволы",
    "latin": "Латиница",
}

UPLOAD_SEQUENCE = [
    "cyrillic_full",
    "digits",
    "latin",
]


def _format_progress(progress: dict) -> str:
    lines = []
    for font_type in UPLOAD_SEQUENCE:
        info = progress.get(font_type, {"current": 0, "required": 0})
        label = FONT_TYPE_LABELS.get(font_type, font_type)
        status_icon = "✅" if info["current"] >= info["required"] else "⬜️"
        lines.append(f"{status_icon} {label}: {info['current']}/{info['required']}")
    return "\n".join(lines)


async def handle_font_file(message: Message, file_ext: str):
    """Общий обработчик загрузки шрифта"""
    user_id = message.from_user.id
    
    try:
        # Убеждаемся что пользователь существует
        from utils.db_utils import get_or_create_user
        telegram_user = message.from_user
        get_or_create_user(
            user_id,
            username=getattr(telegram_user, "username", None),
            first_name=getattr(telegram_user, "first_name", None),
            last_name=getattr(telegram_user, "last_name", None),
        )
        
        # Получаем информацию о файле
        file = message.document
        
        if not file.file_name:
            await message.answer("❌ Не удалось определить имя файла.")
            return
        
        file_name = file.file_name
        
        await call_with_retries(message.answer, "⏳ Загружаю шрифт...")
        
        # Скачиваем файл
        bot = message.bot
        file_info = await bot.get_file(file.file_id)
        file_data = await bot.download_file(file_info.file_path)
        
        # Сохраняем файл
        font_path = save_font_file(file_data, file_name)
        result = analyze_and_register_font(user_id, font_path)
        progress = result["progress"]
        font_type_added = result.get("font_type")
        from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

        keyboard_buttons = [
            [InlineKeyboardButton(text="🏠 Главное меню", callback_data="menu_main")],
        ]
        if has_minimum_font_set(user_id):
            keyboard_buttons.insert(
                0,
                [InlineKeyboardButton(text="📄 Сгенерировать PDF", callback_data="menu_create_pdf")],
            )
        keyboard = InlineKeyboardMarkup(inline_keyboard=keyboard_buttons)

        progress_text = _format_progress(progress)

        font_type_text = ""
        if font_type_added and font_type_added in FONT_TYPE_LABELS:
            font_type_text = f"📂 Категория: {FONT_TYPE_LABELS[font_type_added]}\n\n"

        await call_with_retries(
            message.answer,
            (
                f"✅ Шрифт загружен: {file_name}\n\n"
                f"{font_type_text}"
                f"📊 Прогресс:\n{progress_text}"
            ),
            reply_markup=keyboard,
        )
    
    except Exception as e:
        logger.error(f"Ошибка при загрузке шрифта для пользователя {user_id}: {e}", exc_info=True)
        await call_with_retries(message.answer, f"❌ Ошибка при загрузке шрифта: {str(e)}")


@router.message(F.document & (F.document.file_name.endswith('.ttf') | F.document.file_name.endswith('.TTF')))
async def handle_ttf_font(message: Message):
    """Обработчик загрузки TTF-шрифта"""
    await handle_font_file(message, '.ttf')


@router.message(F.document)
async def handle_wrong_file_type(message: Message):
    """Обработчик неподходящего типа файла"""
    file = message.document
    file_name = file.file_name if file and file.file_name else "неизвестно"
    
    await call_with_retries(
        message.answer,
        f"❌ Неподходящий тип файла: {file_name}\n\n"
        f"Пожалуйста, отправьте файл с расширением .ttf\n\n"
        f"Используйте команду /upload_font для загрузки шрифта."
    )



