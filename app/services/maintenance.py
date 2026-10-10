from sqlalchemy.orm import Session

from app.database import get_setting

KEY_MAINTENANCE = "bot_maintenance_enabled"


def is_bot_maintenance(db: Session) -> bool:
    return get_setting(db, KEY_MAINTENANCE, "0") == "1"
