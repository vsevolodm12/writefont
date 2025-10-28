"""
Обработчики загрузки шрифтов
"""

from aiogram import Router, F
from aiogram.types import Message
from aiogram.filters import Command
from utils.db_utils import update_user_font, save_font_file
import os

router = Router()




async def handle_font_file(message: Message, file_ext: str):
    """Общий обработчик загрузки шрифта"""
    user_id = message.from_user.id
    
    try:
        # Убеждаемся что пользователь существует
        from utils.db_utils import get_or_create_user
        get_or_create_user(user_id)
        
        # Получаем информацию о файле
        file = message.document
        
        if not file.file_name:
            await message.answer("❌ Не удалось определить имя файла.")
            return
        
        file_name = file.file_name
        
        await message.answer("⏳ Загружаю шрифт...")
        
        # Скачиваем файл
        bot = message.bot
        file_info = await bot.get_file(file.file_id)
        file_data = await bot.download_file(file_info.file_path)
        
        # Сохраняем файл
        font_path = save_font_file(file_data, file_name)
        
        # Обновляем путь к шрифту в БД
        if update_user_font(user_id, font_path):
            from handlers.menu import get_main_menu_keyboard
            from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
            
            success_keyboard = InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="📄 Выбрать формат", callback_data="menu_set_format")],
                [InlineKeyboardButton(text="🏠 Главное меню", callback_data="menu_main")]
            ])
            
            await message.answer(
                f"✅ Шрифт успешно загружен!\n\n"
                f"📝 Файл: {file_name}\n\n"
                f"Теперь выберите формат страницы.",
                reply_markup=success_keyboard
            )
        else:
            from handlers.menu import get_back_keyboard
            await message.answer(
                "❌ Ошибка при сохранении шрифта в базу данных.",
                reply_markup=get_back_keyboard("menu_main")
            )
            
    except Exception as e:
        await message.answer(f"❌ Ошибка при загрузке шрифта: {str(e)}")


@router.message(F.document & (F.document.file_name.endswith('.ttf') | F.document.file_name.endswith('.TTF')))
async def handle_ttf_font(message: Message):
    """Обработчик загрузки TTF-шрифта"""
    await handle_font_file(message, '.ttf')


@router.message(F.document & (F.document.file_name.endswith('.otf') | F.document.file_name.endswith('.OTF')))
async def handle_otf_font(message: Message):
    """Обработчик загрузки OTF-шрифта"""
    await handle_font_file(message, '.otf')


@router.message(F.document)
async def handle_wrong_file_type(message: Message):
    """Обработчик неподходящего типа файла"""
    file = message.document
    file_name = file.file_name if file and file.file_name else "неизвестно"
    
    await message.answer(
        f"❌ Неподходящий тип файла: {file_name}\n\n"
        f"Пожалуйста, отправьте файл с расширением .ttf или .otf\n\n"
        f"Используйте команду /upload_font для загрузки шрифта."
    )

