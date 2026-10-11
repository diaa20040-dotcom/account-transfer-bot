import asyncio
import logging

from aiogram import Bot
from sqlalchemy.orm import Session

from app.database import User

logger = logging.getLogger(__name__)

_BROADCAST_DELAY_SEC = 0.05


async def broadcast_message(
    bot: Bot,
    db: Session,
    *,
    text: str | None = None,
    photo_file_id: str | None = None,
    caption: str | None = None,
) -> tuple[int, int, int]:
    """Send to all users in DB. Returns (total, sent_ok, failed)."""
    users = db.query(User).order_by(User.id).all()
    total = len(users)
    ok = 0
    failed = 0
    body = (text or caption or "").strip()

    for user in users:
        try:
            if photo_file_id:
                await bot.send_photo(
                    user.telegram_id,
                    photo_file_id,
                    caption=body or None,
                )
            elif body:
                await bot.send_message(user.telegram_id, body)
            else:
                failed += 1
                continue
            ok += 1
        except Exception:
            failed += 1
            logger.debug("broadcast skip tid=%s", user.telegram_id)
        if total > 1:
            await asyncio.sleep(_BROADCAST_DELAY_SEC)

    return total, ok, failed
