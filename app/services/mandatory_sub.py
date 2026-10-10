from dataclasses import dataclass

from aiogram import Bot
from sqlalchemy.orm import Session

from app.database import get_setting

KEY_ENABLED = "mandatory_sub_enabled"
KEY_CHAT_ID = "mandatory_sub_chat_id"
KEY_INVITE_LINK = "mandatory_sub_invite_link"


@dataclass
class MandatorySubConfig:
    enabled: bool
    chat_id: str
    invite_link: str | None

    @property
    def active(self) -> bool:
        return self.enabled and bool(self.chat_id.strip())


def get_mandatory_sub_config(db: Session) -> MandatorySubConfig:
    enabled = get_setting(db, KEY_ENABLED, "0") == "1"
    chat_id = get_setting(db, KEY_CHAT_ID, "").strip()
    link = get_setting(db, KEY_INVITE_LINK, "").strip() or None
    return MandatorySubConfig(enabled=enabled, chat_id=chat_id, invite_link=link)


async def is_user_subscribed(bot: Bot, chat_id: str, telegram_id: int) -> bool:
    if not chat_id:
        return True
    cid = chat_id.strip()
    if cid.startswith("https://t.me/"):
        cid = "@" + cid.rstrip("/").split("/")[-1]
    try:
        member = await bot.get_chat_member(chat_id=cid, user_id=telegram_id)
        return member.status not in ("left", "kicked")
    except Exception:
        return False
