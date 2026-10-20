from aiogram import Bot, F, Router
from aiogram.types import Message

from app.database import SessionLocal, User
from app.i18n import t
from app.services.admin_access import is_admin
from app.services.order_discussion import get_active_thread_for_user, order_kind_label

router = Router()


def _menu_button_texts() -> frozenset[str]:
    from app.i18n import t

    keys = (
        "btn_visa",
        "btn_referral",
        "btn_language",
        "btn_points",
    )
    return frozenset(t(lang, k) for lang in ("ar", "en") for k in keys)


def _user_discussion_text(message: Message) -> bool:
    if not message.from_user or not message.text:
        return False
    if message.text.startswith("/"):
        return False
    if message.text in _menu_button_texts():
        return False
    return _user_has_active_discussion(message)


def _user_has_active_discussion(message: Message) -> bool:
    if not message.from_user or is_admin(message.from_user.id, message.from_user.username):
        return False
    db = SessionLocal()
    try:
        user = db.query(User).filter_by(telegram_id=message.from_user.id).first()
        if not user:
            return False
        return get_active_thread_for_user(db, user.id) is not None
    finally:
        db.close()


@router.message(F.func(_user_discussion_text), F.text)
async def user_discussion_text(message: Message, bot: Bot) -> None:
    db = SessionLocal()
    try:
        user = db.query(User).filter_by(telegram_id=message.from_user.id).first()
        if not user:
            return
        thread = get_active_thread_for_user(db, user.id)
        if not thread:
            return
        lang = user.language if user.language in ("ar", "en") else "ar"
        kind_label = order_kind_label(thread.kind, "ar")
        header = (
            f"💬 رد من {user.telegram_id} @{user.username or '—'}\n"
            f"({kind_label} #{thread.request_id}):\n\n"
        )
        await bot.send_message(thread.admin_telegram_id, header + message.text.strip())
        await message.answer(t(lang, "discussion_sent_ack"))
    finally:
        db.close()


@router.message(F.func(_user_has_active_discussion), F.photo)
async def user_discussion_photo(message: Message, bot: Bot) -> None:
    db = SessionLocal()
    try:
        user = db.query(User).filter_by(telegram_id=message.from_user.id).first()
        if not user:
            return
        thread = get_active_thread_for_user(db, user.id)
        if not thread:
            return
        lang = user.language if user.language in ("ar", "en") else "ar"
        kind_label = order_kind_label(thread.kind, "ar")
        cap = message.caption or ""
        header = (
            f"📷 رد (صورة) من {user.telegram_id} @{user.username or '—'}\n"
            f"({kind_label} #{thread.request_id})"
        )
        if cap:
            header += f"\n{cap}"
        photo = message.photo[-1].file_id
        await bot.send_photo(thread.admin_telegram_id, photo, caption=header)
        await message.answer(t(lang, "discussion_sent_ack"))
    finally:
        db.close()
