"""
Главное меню и навигация
"""

import asyncio
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


def get_main_menu_keyboard(ready_to_generate: bool = True):
    """Главное меню с кнопками"""
    pdf_button_text = "📝 Создать PDF" if ready_to_generate else "📝 Создать PDF (после загрузки шрифтов)"
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=pdf_button_text, callback_data="menu_create_pdf")],
        [
            InlineKeyboardButton(text="⚙️ Настройки", callback_data="menu_settings"),
            InlineKeyboardButton(text="📥 Загрузить шрифты", callback_data="menu_upload_font")
        ],
        [
            InlineKeyboardButton(text="📚 Инструкция", callback_data="menu_instruction"),
            InlineKeyboardButton(text="📝 Промт для GPT", callback_data="menu_ai_prompt")
        ],
        [
            InlineKeyboardButton(text="👤 Познакомиться с создателем бота", url="https://t.me/vsevolodmarchenko")
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
        
        telegram_user = message.from_user
        user = get_or_create_user(
            user_id,
            username=getattr(telegram_user, "username", None),
            first_name=getattr(telegram_user, "first_name", None),
            last_name=getattr(telegram_user, "last_name", None),
        )
        user_info = get_user_info(user_id)
        
        fonts_by_type = get_user_fonts_by_type(user_id)
        progress = get_font_requirement_progress(user_id)
        ready_to_generate = has_minimum_font_set(user_id)

        welcome_text = "👋 Главное меню\n\n"
        
        if ready_to_generate:
            welcome_text += "✓ Готов к генерации PDF\n\n"
        else:
            welcome_text += "⚠️ Загрузите шрифты для генерации PDF\n\n"
            welcome_text += "💡 <b>Совет:</b> Вы можете попробовать шрифт создателя в меню загрузки шрифтов!\n\n"
        
        format_name = PAGE_FORMATS.get(user['page_format'], user['page_format'] or 'A4')
        grid_enabled = user_info.get('grid_enabled', False) if user_info else False
        grid_status = "Включен" if grid_enabled else "Выключен"
        
        welcome_text += "Настройки:\n"
        welcome_text += f"<b>Формат:</b> {format_name}\n"
        welcome_text += f"<b>Фон клетка:</b> {grid_status}\n"
        
        # Отправляем главное меню в фоне, чтобы обработчик не блокировался
        keyboard = get_main_menu_keyboard(ready_to_generate)
        
        async def send_start():
            try:
                await message.answer(welcome_text, reply_markup=keyboard, parse_mode="HTML")
                logger.info(f"✓ Successfully sent /start response to user {user_id}")
            except Exception as exc:
                logger.error(f"✗ Failed to send /start to user {user_id}: {exc}")
                # Пробуем еще раз через 2 секунды
                try:
                    await asyncio.sleep(2)
                    await message.answer(welcome_text, reply_markup=keyboard, parse_mode="HTML")
                    logger.info(f"✓ Successfully sent /start on retry to user {user_id}")
                except Exception as retry_exc:
                    logger.error(f"✗ Retry also failed for /start to user {user_id}: {retry_exc}")
        
        # Запускаем в фоне - обработчик сразу завершается
        asyncio.create_task(send_start())
        logger.info(f"✓ /start task created for user {user_id}")
        
    except Exception as e:
        logger.error(f"✗ Error in /start handler for user {user_id}: {e}", exc_info=True)
        # При ошибке удаляем из кэша, чтобы можно было повторить
        _processed_messages.discard(unique_key)
        raise


@router.callback_query(F.data == "menu_main")
async def menu_main(callback: CallbackQuery):
    """Главное меню"""
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
    ready_to_generate = has_minimum_font_set(user_id)

    welcome_text = "👋 Главное меню\n\n"
    
    if ready_to_generate:
        welcome_text += "✓ Готов к генерации PDF\n\n"
    else:
        welcome_text += "⚠️ Загрузите шрифты для генерации PDF\n\n"
    
    format_name = PAGE_FORMATS.get(user['page_format'], user['page_format'] or 'A4')
    grid_enabled = user_info.get('grid_enabled', False) if user_info else False
    grid_status = "Включен" if grid_enabled else "Выключен"
    
    welcome_text += "Настройки:\n"
    welcome_text += f"✓ Формат: {format_name}\n"
    welcome_text += f"✓ Фон клетка: {grid_status}\n"
    
    await call_with_retries(
        callback.message.edit_text,
        welcome_text,
        reply_markup=get_main_menu_keyboard(ready_to_generate),
        parse_mode="HTML"
    )
    await call_with_retries(callback.answer)


@router.callback_query(F.data == "menu_upload_font")
async def menu_upload_font(callback: CallbackQuery):
    """Меню загрузки шрифта"""
    user_id = callback.from_user.id
    progress = get_font_requirement_progress(user_id)
    ready = has_minimum_font_set(user_id)
    
    text = "📥 Загрузка шрифтов\n\n"
    
    # Детальный прогресс по типам
    for font_type in UPLOAD_SEQUENCE:
        info = progress.get(font_type, {"current": 0, "required": 0})
        label = FONT_TYPE_LABELS.get(font_type, font_type)
        status_icon = "✓" if info["current"] >= info["required"] else "⬜"
        text += f"{status_icon} {label}: {info['current']}/{info['required']}\n"
    
    text += "\n"
    
    if ready:
        text += "✓ Готов к генерации\n\n"
    else:
        text += "⚠️ Загрузите хотя бы один кириллический шрифт\n\n"
    
    text += (
        "Отправляйте .ttf файлы в любом порядке.\n"
        "Бот автоматически распознает тип каждого шрифта.\n\n"
        "Можно начать с одного кириллического шрифта, но для вариативности и лучшего качества нужны все."
    )
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✨ Попробовать шрифт создателя", callback_data="try_creator_font")],
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
    """Меню создания PDF - проверка готовности"""
    user_id = callback.from_user.id
    user = get_user_info(user_id)
    
    ready_fonts = has_minimum_font_set(user_id)
    format_selected = bool(user and user.get('page_format'))
    
    if not ready_fonts or not format_selected:
        # Не готово - показываем что не хватает
        text = "📝 Создание PDF\n\n"
        
        if not ready_fonts:
            text += "⚠️ Загрузите хотя бы один кириллический шрифт\n"
        else:
            text += "✓ Шрифты готовы\n"
        
        if not format_selected:
            text += "⚠️ Формат страницы не выбран\n"
        else:
            format_name = PAGE_FORMATS.get(user['page_format'], user['page_format'])
            text += f"✓ Формат: {format_name}\n"
        
        text += "\nИспользуйте меню настроек, чтобы исправить это."
        
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="⚙️ Настройки", callback_data="menu_settings")],
            [InlineKeyboardButton(text="🏠 Главное меню", callback_data="menu_main")]
        ])
        
        await call_with_retries(callback.message.edit_text, text, reply_markup=keyboard)
        await call_with_retries(callback.answer)
        return
    
    # Все готово - запрашиваем текст для генерации
    text = "📝 Создание PDF\n\nОтправьте текст для генерации конспекта."
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🏠 Главное меню", callback_data="menu_main")]
    ])
    
    await call_with_retries(callback.message.edit_text, text, reply_markup=keyboard)
    await call_with_retries(callback.answer)
    
    # Устанавливаем флаг, что пользователь в режиме создания PDF
    # Это будет использоваться в handle_text_message
    from utils.db_utils import set_user_pdf_mode
    set_user_pdf_mode(user_id, True)


@router.callback_query(F.data == "menu_choose_page_side")
async def menu_choose_page_side(callback: CallbackQuery):
    """Меню выбора стороны первой страницы"""
    user_id = callback.from_user.id
    user_info = get_user_info(user_id)
    current_side = user_info.get('first_page_side', 'right') if user_info else 'right'
    
    side_label = "Правая страница ➡️" if current_side == 'right' else "⬅️ Левая страница"
    
    text = "📄 Выберите сторону первой страницы\n\n"
    text += "Это определит отступы для печати в тетрадь:\n"
    text += "• Левая страница — меньший отступ слева\n"
    text += "• Правая страница — больший отступ слева (для колец)\n\n"
    text += f"Текущий выбор: {side_label}"
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="⬅️ Левая страница", callback_data="first_page_left")],
        [InlineKeyboardButton(text="Правая страница ➡️", callback_data="first_page_right")],
        [InlineKeyboardButton(text="🏠 Главное меню", callback_data="menu_main")]
    ])
    
    await call_with_retries(callback.message.edit_text, text, reply_markup=keyboard)
    await call_with_retries(callback.answer)


@router.callback_query(F.data.in_(["first_page_left", "first_page_right"]))
async def set_first_page_side(callback: CallbackQuery):
    """Обработчик выбора стороны первой страницы"""
    from utils.db_utils import update_user_first_page_side, get_or_create_user
    
    user_id = callback.from_user.id
    telegram_user = callback.from_user
    get_or_create_user(
        user_id,
        username=getattr(telegram_user, "username", None),
        first_name=getattr(telegram_user, "first_name", None),
        last_name=getattr(telegram_user, "last_name", None),
    )
    
    side = 'left' if callback.data == "first_page_left" else 'right'
    
    if update_user_first_page_side(user_id, side):
        side_label = "Правая страница ➡️" if side == 'right' else "⬅️ Левая страница"
        await call_with_retries(callback.answer, f"✓ Выбрано: {side_label}")
        
        # Переходим к вводу текста
        text = "📝 Отправьте текст для генерации PDF\n\n"
        text += f"(Выбрана: {side_label})"
        
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="◀️ Назад", callback_data="menu_choose_page_side")]
        ])
        
        await call_with_retries(callback.message.edit_text, text, reply_markup=keyboard)
    else:
        await call_with_retries(callback.answer, "❌ Ошибка при сохранении настройки", show_alert=True)
    


@router.callback_query(F.data == "reset_fonts")
async def reset_fonts_handler(callback: CallbackQuery):
    """Обработчик сброса всех шрифтов"""
    user_id = callback.from_user.id
    
    if reset_user_fonts(user_id):
        await call_with_retries(callback.answer, "✅ Шрифты сброшены")
        await menu_upload_font(callback)
    else:
        await call_with_retries(callback.answer, "❌ Ошибка при сбросе шрифтов", show_alert=True)


@router.callback_query(F.data == "try_creator_font")
async def try_creator_font_handler(callback: CallbackQuery):
    """Обработчик добавления шрифта создателя для тестирования"""
    from utils.db_utils import add_creator_font_to_user, get_font_requirement_progress, has_minimum_font_set
    from handlers.menu import get_main_menu_keyboard
    
    user_id = callback.from_user.id
    
    try:
        await call_with_retries(callback.answer, "⏳ Проверяю шрифт создателя...")
        
        result = add_creator_font_to_user(user_id)
        progress = result["progress"]
        font_type = result.get("font_type")
        added_count = result.get("added_count", 0)
        skipped_count = result.get("skipped_count", 0)
        
        progress_text = ""
        for font_type_key in ["cyrillic_full", "digits", "latin"]:
            info = progress.get(font_type_key, {"current": 0, "required": 0})
            label = FONT_TYPE_LABELS.get(font_type_key, font_type_key)
            status_icon = "✓" if info["current"] >= info["required"] else "⬜"
            progress_text += f"{status_icon} {label}: {info['current']}/{info['required']}\n"
        
        ready = has_minimum_font_set(user_id)
        keyboard = get_main_menu_keyboard(ready)
        
        # Если font_type is None, значит все шрифты уже были добавлены ранее
        if font_type is None and skipped_count > 0:
            message_text = (
                f"ℹ️ Шрифты создателя уже добавлены ({skipped_count} шрифтов)!\n\n"
                f"📊 Прогресс:\n{progress_text}\n"
            )
        elif added_count > 0:
            if added_count == 1:
                message_text = (
                    "✅ Шрифт создателя добавлен!\n\n"
                    f"📊 Прогресс:\n{progress_text}\n"
                )
            else:
                message_text = (
                    f"✅ Добавлено {added_count} шрифтов создателя!\n\n"
                    f"📊 Прогресс:\n{progress_text}\n"
                )
        else:
            message_text = (
                "✅ Шрифты создателя добавлены!\n\n"
                f"📊 Прогресс:\n{progress_text}\n"
            )
        
        if ready:
            message_text += "✓ Готов к генерации PDF!\n\n"
            message_text += "Теперь вы можете создать конспект с этим шрифтом."
        else:
            message_text += "⚠️ Загрузите еще шрифты для полной функциональности."
        
        await call_with_retries(
            callback.message.edit_text,
            message_text,
            reply_markup=keyboard
        )
        
    except FileNotFoundError as e:
        await call_with_retries(
            callback.answer,
            f"❌ {str(e)}",
            show_alert=True
        )
    except Exception as e:
        logger.error(f"Ошибка при добавлении шрифта создателя для пользователя {user_id}: {e}", exc_info=True)
        await call_with_retries(
            callback.answer,
            f"❌ Ошибка при добавлении шрифта: {str(e)}",
            show_alert=True
        )


@router.callback_query(F.data == "menu_ai_prompt")
async def menu_ai_prompt(callback: CallbackQuery):
    """Меню с промтом для GPT"""
    prompt_text = """📝 Промт для GPT

<pre><code>Роль: Ты решаешь практические, лабораторные и другие работы, чтобы отправить текст который ты сгенерировал в бота по созданию рукописных конспектов.

- Пиши так, как будто ты студент

- Если в отправленных на решение работах есть ссылки на литературу - используй преимущественно их, но не упоминай их в тексте. Если их нет решай как обычно.

- Никогда не используй оформление в стиле markdown файла (например: **жирный текст / *косой текст / --- разделяющая линия (как явление а не только тремя тире) и тд) 

- В качестве используемых специальных знаков у тебя доступны строго только следующие специальные знаки: !#()*+,-./:;=?\\_«»""• 

- Никогда не используй эмодзи 

- Не пиши ответ на вопрос в начале ответа, а так же заключение в конце ответа например: (начало) «Понял, отправлю решение этой работы» и тд, (конец) «Можешь смело отправлять эту работу на генерацию» и тд. Только решение работы и ничего больше

- При решении работы используй структуру: Например пиши Задание 1. (В 2-3 словах описать задание)

- Если задание подразумевает под собой перечисление (например термины или что-то похожее) органично используй перечисление через интерпункт «•». Перечисление должно всегда начинаться с большой буквы и идти с абзацем. 

Пример:

• Яблоки бывают очень вкусными

• Позитивное мышление и тд.

- Пиши текст чуть покороче и попроще, но сохраняя научный стиль

- Не создавай таблицы если тебя прямо об этом не просят</code></pre>

Скопируйте промт выше и отправьте в ChatGPT вместе с заданием."""

    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🏠 Главное меню", callback_data="menu_main")]
    ])
    
    await call_with_retries(callback.message.edit_text, prompt_text, reply_markup=keyboard, parse_mode="HTML")
    await call_with_retries(callback.answer)


