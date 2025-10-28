"""
Главный файл Telegram-бота для генерации PDF-конспектов
"""

import asyncio
import logging
from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode

from config import BOT_TOKEN
from handlers import commands, fonts, callbacks, text, menu, grid

# Настройка логирования
import os

# Создаем директорию для логов
os.makedirs('logs', exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('logs/bot.log', encoding='utf-8'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)


async def main():
    """Главная функция запуска бота"""
    
    # Проверка обязательных параметров
    if not BOT_TOKEN:
        logger.error("BOT_TOKEN не установлен! Проверьте файл .env")
        import sys
        sys.exit(1)
    
    logger.info("Проверка подключения к базе данных...")
    try:
        from database.connection import get_db_connection
        conn = get_db_connection()
        conn.close()
        logger.info("✓ База данных доступна")
    except Exception as e:
        logger.error(f"✗ Ошибка подключения к БД: {e}")
        logger.error("Запустите: python database/db_init.py")
        import sys
        sys.exit(1)
    
    # Создаем бота и диспетчер
    bot = Bot(
        token=BOT_TOKEN,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML)
    )
    dp = Dispatcher()
    
    # Регистрируем роутеры
    # grid.router должен быть до menu.router, чтобы обрабатывать toggle_grid callback
    dp.include_router(grid.router)
    dp.include_router(menu.router)  # Главное меню - перехватывает /start
    dp.include_router(commands.router)
    dp.include_router(fonts.router)
    dp.include_router(callbacks.router)
    dp.include_router(text.router)
    
    logger.info("Бот запущен и готов к работе!")
    
    # Запускаем polling
    await dp.start_polling(bot)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Бот остановлен пользователем")

