from typing import Any, Awaitable, Callable

from aiogram import BaseMiddleware
from aiogram.types import CallbackQuery, Message, TelegramObject


def _chat_type(event: TelegramObject) -> str | None:
    if isinstance(event, Message):
        return event.chat.type
    if isinstance(event, CallbackQuery) and event.message:
        return event.message.chat.type
    return None


class PrivateChatsOnlyMiddleware(BaseMiddleware):
    """Ignore groups, supergroups, and channels — bot works only in private DMs."""

    async def __call__(
        self,
        handler: Callable[[TelegramObject, dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: dict[str, Any],
    ) -> Any:
        chat_type = _chat_type(event)
        if chat_type is not None and chat_type != "private":
            return None
        return await handler(event, data)
