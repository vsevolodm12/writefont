"""
Обработчик инструкции для новых пользователей
"""

from aiogram import Router, F
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton, FSInputFile
from aiogram.filters import Command
from utils.db_utils import get_user_info, get_or_create_user, mark_instruction_seen
from utils.telegram_retry import call_with_retries
import os
from config import TEMPLATES_DIR

router = Router()


def is_new_user(user_id: int) -> bool:
    """Проверяет, является ли пользователь новым (не видел инструкцию)"""
    user_info = get_user_info(user_id)
    if not user_info:
        return True
    
    # Проверяем, видел ли пользователь инструкцию
    instruction_seen = user_info.get('instruction_seen', False)
    return not instruction_seen


async def send_instruction_with_templates(message_or_callback):
    """Отправляет инструкцию с встроенными PDF шаблонами"""
    # Определяем метод для отправки сообщений
    if isinstance(message_or_callback, CallbackQuery):
        answer_method = message_or_callback.message.answer
        answer_document_method = message_or_callback.message.answer_document
    else:
        answer_method = message_or_callback.answer
        answer_document_method = message_or_callback.answer_document
    
    instruction_text = """Инструкция по созданию шрифта

Шаг 1: Заполните шаблоны
Ниже вы получите PDF шаблоны. Распечатайте, заполните от руки, отсканируйте.

Шаг 2: Загрузите на Calligraphr
1. Перейдите на https://www.calligraphr.com/
2. Нажмите "Upload Templates"
3. Загрузите отсканированные шаблоны
4. Скачайте шрифт (.ttf или .otf)

Шаг 3: Загрузите шрифт в бота
Нажмите "Загрузить шрифты" в главном меню и отправьте файл."""

    # Отправляем текст инструкции
    await call_with_retries(answer_method, instruction_text)
    
    # Ищем PDF файлы в папке templates
    pdf_files = []
    if os.path.exists(TEMPLATES_DIR):
        for file in os.listdir(TEMPLATES_DIR):
            if file.lower().endswith('.pdf'):
                pdf_files.append(file)
        pdf_files.sort()  # Сортируем для предсказуемого порядка
    
    # Отправляем каждый PDF файл
    sent_count = 0
    for pdf_file in pdf_files:
        pdf_path = os.path.join(TEMPLATES_DIR, pdf_file)
        try:
            pdf_document = FSInputFile(pdf_path)
            await call_with_retries(answer_document_method, document=pdf_document, caption=pdf_file)
            sent_count += 1
        except Exception as e:
            # Продолжаем отправку остальных
            pass
    
    # Отправляем финальное сообщение с кнопками
    if sent_count > 0:
        final_text = f"Отправлено {sent_count} шаблонов. Следуйте инструкции выше."
    else:
        final_text = "Шаблоны не найдены. Обратитесь к администратору."
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Открыть Calligraphr", url="https://www.calligraphr.com/")],
        [InlineKeyboardButton(text="Главное меню", callback_data="menu_main")]
    ])
    
    await call_with_retries(answer_method, final_text, reply_markup=keyboard)


@router.callback_query(F.data == "menu_instruction")
async def menu_instruction(callback: CallbackQuery):
    """Показывает инструкцию по запросу из главного меню"""
    await call_with_retries(callback.answer)
    await send_instruction_with_templates(callback)

