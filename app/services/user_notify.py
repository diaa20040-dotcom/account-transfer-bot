from aiogram import Bot

from app.database import TransferRequest, User
from app.i18n import t


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
    bot: Bot, user: User, req_id: int, body: str
) -> bool:
    lang = user.language if user.language in ("ar", "en") else "ar"
    text = t(lang, "admin_inbox", req_id=req_id, body=body)
    try:
        await bot.send_message(user.telegram_id, text)
        return True
    except Exception:
        return False
