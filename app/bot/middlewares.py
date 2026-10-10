from typing import Any, Awaitable, Callable

from aiogram import BaseMiddleware
from aiogram.types import CallbackQuery, Message, TelegramObject

from app.database import SessionLocal, User
from app.services.admin_access import is_admin
from app.services.maintenance import is_bot_maintenance
from app.services.mandatory_sub import get_mandatory_sub_config, is_user_subscribed
from app.services.users import maybe_credit_referral
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
        msub_active = False
        chat_id = ""
        db = SessionLocal()
        try:
            cfg = get_mandatory_sub_config(db)
            if not cfg.active:
                msub_active = False
            else:
                msub_active = True
                invite_link = cfg.invite_link
                chat_id = cfg.chat_id
                from app.database import User

                user = db.query(User).filter_by(telegram_id=telegram_id).first()
                if user:
                    lang = user.language
        finally:
            db.close()

        if not msub_active:
            db2 = SessionLocal()
            try:
                await maybe_credit_referral(db2, bot, telegram_id)
            finally:
                db2.close()
            return await handler(event, data)

        if await is_user_subscribed(bot, chat_id, telegram_id):
            db2 = SessionLocal()
            try:
                await maybe_credit_referral(db2, bot, telegram_id)
            finally:
                db2.close()
            return await handler(event, data)

        if isinstance(event, CallbackQuery):
            await event.answer(t(lang, "mandatory_sub_fail"), show_alert=True)
            return None

        await event.answer(
            t(lang, "mandatory_sub_blocked"),
            reply_markup=mandatory_sub_keyboard(lang, invite_link),
        )
        return None


class MaintenanceMiddleware(BaseMiddleware):
    """When maintenance is on, block non-admins (admins and Stars payments still work)."""

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

        if isinstance(event, Message) and event.successful_payment:
            return await handler(event, data)

        db = SessionLocal()
        try:
            if not is_bot_maintenance(db):
                return await handler(event, data)
            user = db.query(User).filter_by(telegram_id=telegram_id).first()
            lang = user.language if user else "ar"
        finally:
            db.close()

        if isinstance(event, CallbackQuery):
            await event.answer(t(lang, "bot_maintenance"), show_alert=True)
            return None

        if isinstance(event, Message):
            await event.answer(t(lang, "bot_maintenance"))
            return None

        return None
