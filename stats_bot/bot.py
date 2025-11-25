import asyncio
from typing import List

from aiogram import Bot, Dispatcher, Router
from aiogram.filters import Command
from aiogram.types import Message

from config import Settings, get_settings
from stats_service import fetch_stats


def format_number(value: int) -> str:
    return f"{value:,}".replace(",", " ")


async def resolve_username(bot: Bot, user_id: int) -> str:
    try:
        chat = await bot.get_chat(user_id)
        if chat.username:
            return f"@{chat.username}"
        if chat.full_name:
            return f"{chat.full_name} ({user_id})"
    except Exception:
        pass
    return str(user_id)


async def format_recent(stats, bot: Bot) -> str:
    if not stats.recent_users:
        return "—"
    lines: List[str] = []
    for item in stats.recent_users:
        label: str
        user_tag = item.username.strip() if item.username else ""
        if user_tag:
            label = f"@{user_tag}"
        else:
            name_parts = [part for part in [item.first_name.strip(), item.last_name.strip()] if part]
            if name_parts:
                label = f"{' '.join(name_parts)} ({item.user_id})"
            else:
                label = await resolve_username(bot, item.user_id)
        lines.append(f"• {label} — {format_number(item.pdf_count)} PDF")
    return "\n".join(lines)


async def format_section(title: str, items: List[str]) -> str:
    return title + ("\n".join(items) if items else "—")


async def format_report(stats, bot: Bot) -> str:
    return (
        "📊 За сегодня:\n"
        f"- Новые пользователи: {format_number(stats.new_users_today)}\n"
        f"- Активных пользователей: {format_number(stats.active_today)}\n"
        f"- Генераций PDF: {format_number(stats.pdf_today)}\n\n"
        "📈 За всё время:\n"
        f"- Пользователей: {format_number(stats.total_users)}\n"
        f"- PDF: {format_number(stats.pdf_total)}\n\n"
        "Последние генерации:\n"
        f"{await format_recent(stats, bot)}\n\n"
        "💬 Последние визиты:\n"
        f"{await format_recent_visitors(stats, bot)}"
    )


async def format_recent_visitors(stats, bot: Bot) -> str:
    if not stats.recent_visitors:
        return "—"
    lines: List[str] = []
    for idx, item in enumerate(stats.recent_visitors, 1):
        user_tag = item.username.strip() if item.username else ""
        if user_tag:
            label = f"@{user_tag}"
        else:
            name_parts = [part for part in [item.first_name.strip(), item.last_name.strip()] if part]
            if name_parts:
                label = f"{' '.join(name_parts)} ({item.user_id})"
            else:
                label = await resolve_username(bot, item.user_id)
        lines.append(f"{idx}. {label}")
    return "\n".join(lines)


def build_router(settings: Settings) -> Router:
    router = Router()

    async def send_stats(message: Message):
        stats = await asyncio.to_thread(fetch_stats, settings)
        
        # Логируем количество визитов для отладки
        import logging
        logger = logging.getLogger(__name__)
        logger.info(f"Получено визитов из БД: {len(stats.recent_visitors)}")
        
        text = await format_report(stats, message.bot)
        
        # Telegram ограничение: 4096 символов на сообщение
        # Если сообщение слишком длинное, разбиваем на части
        MAX_MESSAGE_LENGTH = 4000  # Оставляем запас
        
        if len(text) <= MAX_MESSAGE_LENGTH:
            await message.answer(text)
        else:
            # Отправляем основную часть
            main_text = (
                "📊 За сегодня:\n"
                f"- Новые пользователи: {format_number(stats.new_users_today)}\n"
                f"- Активных пользователей: {format_number(stats.active_today)}\n"
                f"- Генераций PDF: {format_number(stats.pdf_today)}\n\n"
                "📈 За всё время:\n"
                f"- Пользователей: {format_number(stats.total_users)}\n"
                f"- PDF: {format_number(stats.pdf_total)}\n\n"
                "Последние генерации:\n"
                f"{await format_recent(stats, message.bot)}\n\n"
                "💬 Последние визиты:\n"
            )
            await message.answer(main_text)
            
            # Отправляем список визитов отдельным сообщением
            visitors_text = await format_recent_visitors(stats, message.bot)
            if len(visitors_text) > MAX_MESSAGE_LENGTH:
                # Если список все еще слишком длинный, разбиваем на части по 30 строк
                lines = visitors_text.split('\n')
                chunk_size = 30
                for i in range(0, len(lines), chunk_size):
                    chunk = '\n'.join(lines[i:i+chunk_size])
                    await message.answer(chunk)
            else:
                await message.answer(visitors_text)

    @router.message(Command("stat"))
    async def cmd_stat(message: Message):
        await send_stats(message)

    @router.message(Command("start"))
    async def cmd_start(message: Message):
        await send_stats(message)

    return router


async def main():
    settings = get_settings()
    bot = Bot(settings.bot_token)
    dp = Dispatcher()
    dp.include_router(build_router(settings))
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())

