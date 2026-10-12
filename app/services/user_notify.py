from aiogram import Bot

from app.database import User
from app.i18n import t
from app.services.order_discussion import order_kind_label


_STATUS_KEYS = frozenset({"pending", "processing", "done", "rejected"})


async def notify_transfer_status(bot: Bot, user: User, req_id: int, status: str) -> None:
    if status not in _STATUS_KEYS:
        return
    lang = user.language if user.language in ("ar", "en") else "ar"
    text = t(lang, f"status_{status}", req_id=req_id)
    try:
        await bot.send_message(user.telegram_id, text)
    except Exception:
        pass


async def send_admin_message_to_user(
    bot: Bot, user: User, kind: str, req_id: int, body: str
) -> bool:
    lang = user.language if user.language in ("ar", "en") else "ar"
    label = order_kind_label(kind, lang)
    text = t(lang, "admin_inbox_order", kind=label, req_id=req_id, body=body)
    try:
        await bot.send_message(user.telegram_id, text)
        return True
    except Exception:
        return False


async def send_discussion_message_to_user(
    bot: Bot, user: User, kind: str, req_id: int, body: str
) -> bool:
    lang = user.language if user.language in ("ar", "en") else "ar"
    label = order_kind_label(kind, lang)
    text = t(lang, "discussion_admin_msg", kind=label, req_id=req_id, body=body)
    try:
        await bot.send_message(user.telegram_id, text)
        return True
    except Exception:
        return False
