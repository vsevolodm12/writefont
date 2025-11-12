import asyncio
from typing import List

from aiogram import Bot, Dispatcher, Router
from aiogram.filters import Command
from aiogram.types import Message

from config import Settings, get_settings
from stats_service import fetch_stats


def format_number(value: int) -> str:
    return f"{value:,}".replace(",", " ")


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
            try:
                chat = await bot.get_chat(item.user_id)
                if chat.username:
                    label = f"@{chat.username}"
                elif chat.full_name:
                    label = f"{chat.full_name} ({item.user_id})"
                else:
                    label = str(item.user_id)
            except Exception:
                label = str(item.user_id)
        lines.append(f"• {label} — {format_number(item.pdf_count)} PDF")
    return "\n".join(lines)


async def format_report(stats, bot: Bot) -> str:
    return (
        "📊 За сегодня:\n"
        f"- Новые пользователи: {format_number(stats.new_users_today)}\n"
        f"- Генераций PDF: {format_number(stats.pdf_today)}\n\n"
        "📈 За всё время:\n"
        f"- Пользователей: {format_number(stats.total_users)}\n"
        f"- PDF: {format_number(stats.pdf_total)}\n\n"
        "Последние:\n"
        f"{await format_recent(stats, bot)}"
    )


def build_router(settings: Settings) -> Router:
    router = Router()

    async def send_stats(message: Message):
        stats = await asyncio.to_thread(fetch_stats, settings)
        text = await format_report(stats, message.bot)
        await message.answer(text)

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

