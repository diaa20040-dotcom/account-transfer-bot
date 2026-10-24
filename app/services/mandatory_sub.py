import json
from dataclasses import dataclass

from aiogram import Bot
from sqlalchemy.orm import Session

from app.database import get_setting, set_setting

KEY_ENABLED = "mandatory_sub_enabled"
KEY_CHAT_ID = "mandatory_sub_chat_id"
KEY_INVITE_LINK = "mandatory_sub_invite_link"
KEY_TARGETS_JSON = "mandatory_sub_targets_json"

DEFAULT_TARGETS = [
    {"chat_id": "@questaplay", "invite_link": "https://t.me/questaplay", "label_ar": "📢 القناة"},
    {"chat_id": "@Minexaa", "invite_link": "https://t.me/Minexaa", "label_ar": "👥 الجروب"},
]


@dataclass
class MandatoryTarget:
    chat_id: str
    invite_link: str | None
    label_ar: str = "🔗 اشتراك"


@dataclass
class MandatorySubConfig:
    enabled: bool
    chat_id: str
    invite_link: str | None
    targets: list[MandatoryTarget]

    @property
    def active(self) -> bool:
        if self.enabled and self.targets:
            return True
        return self.enabled and bool(self.chat_id.strip())


def _parse_targets_json(raw: str) -> list[MandatoryTarget]:
    if not raw.strip():
        return []
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        return []
    out: list[MandatoryTarget] = []
    for item in data if isinstance(data, list) else []:
        if not isinstance(item, dict):
            continue
        cid = str(item.get("chat_id") or "").strip()
        if not cid:
            continue
        link = (item.get("invite_link") or "").strip() or None
        label = str(item.get("label_ar") or "🔗 اشتراك").strip()
        out.append(MandatoryTarget(chat_id=cid, invite_link=link, label_ar=label))
    return out


def get_mandatory_targets(db: Session) -> list[MandatoryTarget]:
    targets = _parse_targets_json(get_setting(db, KEY_TARGETS_JSON, ""))
    if targets:
        return targets
    cfg = get_mandatory_sub_config(db)
    if cfg.chat_id.strip():
        return [
            MandatoryTarget(
                chat_id=cfg.chat_id.strip(),
                invite_link=cfg.invite_link,
                label_ar="🔗 اشتراك",
            )
        ]
    return []


def get_mandatory_sub_config(db: Session) -> MandatorySubConfig:
    enabled = get_setting(db, KEY_ENABLED, "0") == "1"
    chat_id = get_setting(db, KEY_CHAT_ID, "").strip()
    link = get_setting(db, KEY_INVITE_LINK, "").strip() or None
    targets = get_mandatory_targets(db)
    return MandatorySubConfig(
        enabled=enabled, chat_id=chat_id, invite_link=link, targets=targets
    )


def ensure_default_mandatory_targets(db: Session) -> None:
    if get_setting(db, KEY_TARGETS_JSON, "").strip():
        return
    set_setting(db, KEY_TARGETS_JSON, json.dumps(DEFAULT_TARGETS, ensure_ascii=False))
    if get_setting(db, KEY_ENABLED, "0") != "1":
        set_setting(db, KEY_ENABLED, "1")


def normalize_chat_id(chat_id: str) -> str:
    cid = chat_id.strip()
    if cid.startswith("https://t.me/"):
        cid = "@" + cid.rstrip("/").split("/")[-1]
    return cid


async def is_user_subscribed(bot: Bot, chat_id: str, telegram_id: int) -> bool:
    cid = normalize_chat_id(chat_id)
    if not cid:
        return True
    try:
        member = await bot.get_chat_member(chat_id=cid, user_id=telegram_id)
        return member.status not in ("left", "kicked")
    except Exception:
        return False


async def is_user_subscribed_all(bot: Bot, targets: list[MandatoryTarget], telegram_id: int) -> bool:
    if not targets:
        return True
    for target in targets:
        if not await is_user_subscribed(bot, target.chat_id, telegram_id):
            return False
    return True
