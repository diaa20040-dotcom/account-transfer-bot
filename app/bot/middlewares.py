from typing import Any, Awaitable, Callable

from aiogram import BaseMiddleware
from aiogram.types import CallbackQuery, Message, TelegramObject

from app.database import SessionLocal
from app.services.admin_access import is_admin
from app.services.mandatory_sub import get_mandatory_sub_config, is_user_subscribed
from app.i18n import t
from app.bot.mandatory_keyboards import mandatory_sub_keyboard


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


def _user_from_event(event: TelegramObject) -> tuple[int, str | None] | None:
    if isinstance(event, Message) and event.from_user:
        return event.from_user.id, event.from_user.username
    if isinstance(event, CallbackQuery) and event.from_user:
        return event.from_user.id, event.from_user.username
    return None


class MandatorySubMiddleware(BaseMiddleware):
    """Block bot usage until the user joins the configured mandatory channel."""

    async def __call__(
        self,
        handler: Callable[[TelegramObject, dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: dict[str, Any],
    ) -> Any:
        user_info = _user_from_event(event)
        if user_info is None:
            return await handler(event, data)

        telegram_id, username = user_info
        if is_admin(telegram_id, username):
            return await handler(event, data)

        if isinstance(event, CallbackQuery) and event.data == "verify_mandatory":
            return await handler(event, data)

        bot = data.get("bot")
        if bot is None:
            return await handler(event, data)

        lang = "ar"
        invite_link: str | None = None
        db = SessionLocal()
        try:
            cfg = get_mandatory_sub_config(db)
            if not cfg.active:
                return await handler(event, data)
            invite_link = cfg.invite_link
            from app.database import User

            user = db.query(User).filter_by(telegram_id=telegram_id).first()
            if user:
                lang = user.language
            if await is_user_subscribed(bot, cfg.chat_id, telegram_id):
                return await handler(event, data)
        finally:
            db.close()

        if isinstance(event, CallbackQuery):
            await event.answer(t(lang, "mandatory_sub_fail"), show_alert=True)
            return None

        await event.answer(
            t(lang, "mandatory_sub_blocked"),
            reply_markup=mandatory_sub_keyboard(lang, invite_link),
        )
        return None
