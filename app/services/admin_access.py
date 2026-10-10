from app.config import settings
from app.database import get_setting, set_setting
from app.services.admin_notify import add_admin_id, get_admin_ids


def _username_is_configured_admin(username: str | None) -> bool:
    if not username:
        return False
    un = username.lower()
    return any(u.lower() == un for u in settings.admin_usernames)


def is_admin(telegram_id: int, username: str | None = None) -> bool:
    if telegram_id in settings.admin_ids:
        return True
    if telegram_id in get_admin_ids():
        return True
    if _username_is_configured_admin(username):
        add_admin_id(telegram_id)
        return True
    return False


def load_persisted_admins(db) -> None:
    raw = get_setting(db, "persisted_admin_ids", "")
    for part in raw.split(","):
        part = part.strip()
        if part.isdigit():
            add_admin_id(int(part))


def persist_admin(db, telegram_id: int) -> None:
    add_admin_id(telegram_id)
    existing = {x.strip() for x in get_setting(db, "persisted_admin_ids", "").split(",") if x.strip()}
    existing.add(str(telegram_id))
    set_setting(db, "persisted_admin_ids", ",".join(sorted(existing, key=int)))
