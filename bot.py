"""
Главный файл Telegram-бота для генерации PDF-конспектов
"""

import asyncio
import logging
from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode

from config import BOT_TOKEN
from config import WEBHOOK_URL, WEBHOOK_SECRET, WEBAPP_HOST, WEBAPP_PORT, WEBHOOK_PATH
from handlers import commands, fonts, callbacks, text, menu, grid, settings

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


async def periodic_cleanup():
    """Периодическая очистка старых файлов"""
    from utils.cleanup import cleanup_old_pdfs
    
    while True:
        await asyncio.sleep(3600)  # Каждый час
        try:
            deleted = cleanup_old_pdfs(days_old=7)
            if deleted > 0:
                logger.info(f"✓ Очищено {deleted} старых PDF файлов")
        except Exception as e:
            logger.error(f"Ошибка в периодической очистке: {e}")


async def log_statistics():
    """Периодически выводит статистику производительности"""
    from utils.metrics import metrics
    
    while True:
        await asyncio.sleep(300)  # Каждые 5 минут
        try:
            metrics.log_stats()
        except Exception as e:
            logger.error(f"Ошибка при выводе статистики: {e}")


async def main():
    """Главная функция запуска бота"""
    
    # Проверка обязательных параметров
    if not BOT_TOKEN:
        logger.error("BOT_TOKEN не установлен! Проверьте файл .env")
        import sys
        sys.exit(1)
    
    logger.info("Проверка подключения к базе данных...")
    try:
        from database.connection import get_db_connection, return_db_connection
        conn = get_db_connection()
        return_db_connection(conn)
        logger.info("✓ База данных доступна")
    except Exception as e:
        logger.error(f"✗ Ошибка подключения к БД: {e}")
        logger.error("Запустите: python database/db_init.py")
        import sys
        sys.exit(1)
    
    # Определяем режим работы: webhook (прод) или polling (локально)
    use_webhook = bool((WEBHOOK_URL or '').strip())
    lock_conn = None
    if not use_webhook:
        # Глобальная защита от параллельного запуска только для polling
        try:
            from database.connection import get_db_connection
            import psycopg2
            lock_conn = get_db_connection()
            lock_conn.autocommit = True
            with lock_conn.cursor() as cur:
                LOCK_KEY = 8149608598
                cur.execute("SELECT pg_try_advisory_lock(%s)", (LOCK_KEY,))
                acquired = cur.fetchone()[0]
                if not acquired:
                    logger.error("✗ Запуск отклонён: уже работает другой экземпляр (advisory lock не получен)")
                    import sys
                    sys.exit(1)
            logger.info("✓ Advisory lock получен — этот инстанс назначен лидером polling")
        except Exception as e:
            logger.error(f"✗ Не удалось установить advisory lock: {e}")
            import sys
            sys.exit(1)

    # Создаем бота и диспетчер
    bot = Bot(
        token=BOT_TOKEN,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML)
    )
    dp = Dispatcher()
    
    # Регистрируем middleware для обновления last_seen_at
    from utils.last_seen_middleware import LastSeenMiddleware
    dp.message.middleware(LastSeenMiddleware())
    dp.callback_query.middleware(LastSeenMiddleware())
    # edited_message обрабатывается через message.middleware
    
    # Регистрируем роутеры (важен порядок!)
    # grid.router должен быть до menu.router, чтобы обрабатывать toggle_grid callback
    dp.include_router(grid.router)
    
    # menu.router регистрируем первым из основных, чтобы он обрабатывал /start
    dp.include_router(menu.router)  # Главное меню - перехватывает /start и /menu
    dp.include_router(settings.router)  # Меню настроек
    
    # Остальные роутеры (commands.router пустой, но оставляем на случай)
    dp.include_router(commands.router)
    dp.include_router(fonts.router)
    dp.include_router(callbacks.router)
    dp.include_router(text.router)  # Последним, чтобы не перехватывать команды
    
    logger.info(f"✓ Зарегистрировано роутеров: {len(dp.sub_routers)}")
    
    # Запускаем периодическую очистку в фоне
    asyncio.create_task(periodic_cleanup())
    logger.info("✓ Периодическая очистка файлов запущена")
    
    # Запускаем логирование статистики
    asyncio.create_task(log_statistics())
    logger.info("✓ Логирование метрик запущено")
    
    if use_webhook:
        # WEBHOOK режим: поднимаем aiohttp-сервер и устанавливаем webhook
        from aiohttp import web
        from aiogram.webhook.aiohttp_server import SimpleRequestHandler, setup_application

        final_webhook_url = WEBHOOK_URL.rstrip('/') + WEBHOOK_PATH
        try:
            await bot.set_webhook(final_webhook_url, secret_token=(WEBHOOK_SECRET or None), drop_pending_updates=True)
            logger.info(f"✓ Webhook установлен: {final_webhook_url}")
        except Exception as e:
            logger.error(f"✗ Не удалось установить webhook: {e}")
            import sys
            sys.exit(1)

        app = web.Application()
        SimpleRequestHandler(dispatcher=dp, bot=bot, secret_token=(WEBHOOK_SECRET or None)).register(app, path=WEBHOOK_PATH)
        setup_application(app, dp, bot=bot)

        logger.info(f"HTTP сервер для webhook слушает {WEBAPP_HOST}:{WEBAPP_PORT}{WEBHOOK_PATH}")
        runner = web.AppRunner(app)
        await runner.setup()
        site = web.TCPSite(runner, host=WEBAPP_HOST, port=WEBAPP_PORT)
        await site.start()

        logger.info("Бот запущен в режиме WEBHOOK и готов к работе!")
        await asyncio.Event().wait()  # бесконечно держим процесс
    else:
        # POLLING режим: убедимся, что webhook отключен, чтобы не конфликтовать
        try:
            info = await bot.get_webhook_info()
            if (info.url or '').strip():
                await bot.delete_webhook(drop_pending_updates=True)
                logger.info("✓ Webhook удалён для режима polling")
        except Exception as e:
            logger.warning(f"Не удалось проверить/удалить webhook: {e}")

        logger.info("Бот запущен в режиме POLLING и готов к работе!")
        try:
            await dp.start_polling(bot)
        finally:
            # Освобождаем advisory lock при завершении
            try:
                if lock_conn is not None:
                    with lock_conn.cursor() as cur:
                        LOCK_KEY = 8149608598
                        cur.execute("SELECT pg_advisory_unlock(%s)", (LOCK_KEY,))
                    lock_conn.close()
                    logger.info("✓ Advisory lock освобождён")
            except Exception as e:
                logger.warning(f"Не удалось освободить advisory lock: {e}")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Бот остановлен пользователем")

