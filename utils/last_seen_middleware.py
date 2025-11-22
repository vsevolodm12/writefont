"""
Middleware для обновления времени последнего визита пользователя
"""

from typing import Callable, Dict, Any, Awaitable
from aiogram import BaseMiddleware
from aiogram.types import TelegramObject, Message, CallbackQuery, EditedMessage
from utils.db_utils import update_last_seen_at


class LastSeenMiddleware(BaseMiddleware):
    """Middleware для обновления last_seen_at при любом взаимодействии с ботом"""
    
    async def __call__(
        self,
        handler: Callable[[TelegramObject, Dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: Dict[str, Any]
    ) -> Any:
        # Получаем user_id из события
        user_id = None
        
        if isinstance(event, Message):
            user_id = event.from_user.id if event.from_user else None
        elif isinstance(event, CallbackQuery):
            user_id = event.from_user.id if event.from_user else None
        elif isinstance(event, EditedMessage):
            user_id = event.from_user.id if event.from_user else None
        
        # Обновляем last_seen_at если user_id найден
        if user_id:
            try:
                update_last_seen_at(user_id)
            except Exception:
                # Игнорируем ошибки обновления (не критично)
                pass
        
        # Продолжаем обработку
        return await handler(event, data)


