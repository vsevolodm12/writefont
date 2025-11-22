"""
Middleware для обновления времени последнего визита пользователя
"""

from typing import Callable, Dict, Any, Awaitable
from aiogram import BaseMiddleware
from aiogram.types import TelegramObject, Update
from utils.db_utils import update_last_seen_at


class LastSeenMiddleware(BaseMiddleware):
    """Middleware для обновления last_seen_at при любом взаимодействии с ботом"""
    
    async def __call__(
        self,
        handler: Callable[[TelegramObject, Dict[str, Any]], Awaitable[Any]],
        event: Update,
        data: Dict[str, Any]
    ) -> Any:
        # Получаем user_id из события
        user_id = None
        
        if event.message:
            user_id = event.message.from_user.id if event.message.from_user else None
        elif event.callback_query:
            user_id = event.callback_query.from_user.id if event.callback_query.from_user else None
        elif event.edited_message:
            user_id = event.edited_message.from_user.id if event.edited_message.from_user else None
        
        # Обновляем last_seen_at если user_id найден
        if user_id:
            try:
                update_last_seen_at(user_id)
            except Exception:
                # Игнорируем ошибки обновления (не критично)
                pass
        
        # Продолжаем обработку
        return await handler(event, data)

