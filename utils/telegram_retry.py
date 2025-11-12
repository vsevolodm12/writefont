"""
Вспомогательные функции для повторной отправки сообщений в Telegram.
"""

import asyncio
import logging
from typing import Any, Callable, Awaitable

from aiogram.exceptions import TelegramNetworkError, TelegramRetryAfter

logger = logging.getLogger(__name__)


async def call_with_retries(
    method: Callable[..., Awaitable[Any]],
    *args: Any,
    attempts: int = 4,
    base_delay: float = 1.0,
    **kwargs: Any,
) -> Any:
    """
    Выполнить Telegram-метод с повторными попытками при сетевых ошибках.

    :param method: корутина aiogram, например message.answer
    :param attempts: количество попыток
    :param base_delay: базовая задержка между повторениями
    :param args: позиционные аргументы для метода
    :param kwargs: именованные аргументы для метода
    """
    last_exc: Exception | None = None

    for attempt in range(1, attempts + 1):
        try:
            return await method(*args, **kwargs)
        except TelegramRetryAfter as exc:
            last_exc = exc
            wait_time = max(exc.retry_after + 0.5, base_delay)
            logger.warning(
                "TelegramRetryAfter (%.1fs). Attempt %s/%s",
                wait_time,
                attempt,
                attempts,
            )
        except TelegramNetworkError as exc:
            last_exc = exc
            wait_time = base_delay * attempt
            logger.warning(
                "TelegramNetworkError (%s). Attempt %s/%s, retry in %.1fs",
                exc,
                attempt,
                attempts,
                wait_time,
            )
        else:
            return

        if attempt == attempts:
            logger.error("All retry attempts exhausted. Raising error.")
            if last_exc is not None:
                raise last_exc
            raise RuntimeError("Retry attempts exhausted without captured exception")

        await asyncio.sleep(wait_time)



