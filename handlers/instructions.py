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
    
    instruction_text = """📚 Инструкция по созданию шрифта

<b>Шаг 1: Скачайте шаблоны</b>

Ниже вы получите PDF шаблоны для заполнения.

<b>Шаг 2: Заполните шаблоны от руки</b>

Правила заполнения:
• Писать строго по середине (особенно важно с заглавными буквами)
• Писать на одном уровне, иначе текст будет плясать
• Писать примерно похоже, без деталей, по которым можно опознать повторную букву

Что нужно заполнить:
• 3 русских шаблона
• 2 шаблона специальных знаков
• 2 английских шаблона

<b>Шаг 3: Отсканируйте шаблоны</b>

Отсканируйте каждый шаблон через принтер или телефон и сохраните РАЗНЫМИ файлами.

Например: "Russian 1", "Russian 2", "Russian 3", "Special 1", "Special 2", "English 1", "English 2"

<b>Шаг 4: Загрузите на Calligraphr</b>

1. Перейдите на Calligraphr (кнопка ниже)
2. Зарегистрируйтесь через Google аккаунт или как удобнее
3. Нажмите "Upload Template"
4. По очереди загрузите все отсканированные шаблоны
5. Дождитесь обработки и проверьте, что буквы корректно распознаны
6. Скачайте именно .ttf файл шрифта (.otf не поддерживается)

<b>Шаг 5: Загрузите шрифты в бота</b>

Нажмите "Загрузить шрифты" в главном меню и отправьте файлы.
Можно сразу все в любом порядке.

✅ Все готово!"""

    # Создаем клавиатуру с кнопкой Calligraphr для инструкции
    instruction_keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Открыть Calligraphr", url="https://www.calligraphr.com/en/webapp/app_home/?/fonts")]
    ])

    # Отправляем текст инструкции с кнопкой Calligraphr
    await call_with_retries(answer_method, instruction_text, reply_markup=instruction_keyboard, parse_mode="HTML")
    
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
    
    # Отправляем финальное сообщение о количестве шаблонов с кнопкой главного меню
    if sent_count > 0:
        final_text = f"Отправлено {sent_count} шаблонов. Следуйте инструкции выше."
    else:
        final_text = "Шаблоны не найдены. Обратитесь к администратору."
    
    final_keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📚 Инструкции", callback_data="menu_instruction")],
        [InlineKeyboardButton(text="🏠 Главное меню", callback_data="menu_main")]
    ])
    
    await call_with_retries(answer_method, final_text, reply_markup=final_keyboard)


@router.callback_query(F.data == "menu_instruction")
async def menu_instruction(callback: CallbackQuery):
    """Показывает выбор инструкций"""
    text = """📚 Инструкции

Внизу по кнопкам доступны текстовые инструкции.

Сначала делайте инструкцию по шрифтам, потом по печати.

YouTube: https://example.com

Rutube: https://example.com"""

    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Инструкция по созданию шрифтов", callback_data="instruction_fonts")],
        [InlineKeyboardButton(text="Инструкция для печати", callback_data="instruction_print")],
        [InlineKeyboardButton(text="🏠 Главное меню", callback_data="menu_main")]
    ])
    
    await call_with_retries(callback.message.edit_text, text, reply_markup=keyboard)
    await call_with_retries(callback.answer)


@router.callback_query(F.data == "instruction_fonts")
async def instruction_fonts(callback: CallbackQuery):
    """Показывает инструкцию по созданию шрифтов"""
    await call_with_retries(callback.answer)
    await send_instruction_with_templates(callback)


@router.callback_query(F.data == "instruction_print")
async def instruction_print(callback: CallbackQuery):
    """Показывает инструкцию для печати"""
    instruction_text = """📚 Инструкция для печати

<b>Шаг 1: Настройки формата</b>

1. Нажмите на "Настройки"
2. Выберите формат А5
3. Фон клетка — выключите
4. Первая страница — выберите правую (для примера)

<b>Шаг 2: Получение текста от нейросети</b>

5. Зайдите в "Промт для GPT" — копируйте его нажатием на текст
6. Вставьте в любую нейросеть вместе с практической работой
7. Скопируйте ответ нейросети и вставьте в бота

<b>Шаг 3: Создание и загрузка конспекта</b>

8. Загрузите в файлы полученный конспект

<b>Шаг 4: Настройки печати</b>

9. В настройках печати выберите А5
10. Качество печати — Высокое качество

<b>Шаг 5: Двусторонняя печать</b>

11. Печатайте сначала нечетные листы (1, 3, 5 и т.д.)
12. Переверните напечатанные листы, положите их обратной стороной в принтер (не переворачивая, прямо так)
13. Выберите печатать четные листы (2, 4, 6 и т.д.)

✅ Все готово!"""

    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📚 Инструкции", callback_data="menu_instruction")],
        [InlineKeyboardButton(text="🏠 Главное меню", callback_data="menu_main")]
    ])
    
    await call_with_retries(callback.message.edit_text, instruction_text, reply_markup=keyboard, parse_mode="HTML")
    await call_with_retries(callback.answer)

