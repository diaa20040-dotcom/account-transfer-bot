from sqlalchemy.orm import Session

from app.database import PlayPassRequest, get_setting

PLAY_PASS_OCCUPIED_STATUSES = ("pending", "processing", "done")
SETTING_MAX_SLOTS = "play_pass_max_slots"


def play_pass_max_slots(db: Session) -> int:
    """0 means unlimited."""
    try:
        return max(0, int(get_setting(db, SETTING_MAX_SLOTS, "0")))
    except ValueError:
        return 0


def play_pass_slots_used(db: Session) -> int:
    return (
        db.query(PlayPassRequest)
        .filter(PlayPassRequest.status.in_(PLAY_PASS_OCCUPIED_STATUSES))
        .count()
    )


def play_pass_slots_remaining(db: Session) -> int | None:
    cap = play_pass_max_slots(db)
    if cap <= 0:
        return None
    return max(0, cap - play_pass_slots_used(db))


def play_pass_accepts_new(db: Session) -> bool:
    remaining = play_pass_slots_remaining(db)
    return remaining is None or remaining > 0
