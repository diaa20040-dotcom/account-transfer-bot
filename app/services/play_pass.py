from sqlalchemy.orm import Session

from app.database import PlayPassRequest, get_setting, set_setting

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


def adjust_play_pass_max_slots(db: Session, delta: int) -> tuple[int, str | None]:
    """Returns (new_cap, error_message). cap 0 = unlimited."""
    cap = play_pass_max_slots(db)
    if delta > 0 and cap <= 0:
        used = play_pass_slots_used(db)
        new_cap = max(1, used + delta)
    elif cap <= 0 and delta < 0:
        return cap, "unlimited"
    else:
        new_cap = max(0, cap + delta)
    set_setting(db, SETTING_MAX_SLOTS, str(new_cap))
    db.commit()
    return new_cap, None
