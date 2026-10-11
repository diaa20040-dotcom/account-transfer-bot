from app.database import PlayPassRequest, SessionLocal, User, init_db, set_setting
from app.services.play_pass import (
    play_pass_accepts_new,
    play_pass_slots_remaining,
    play_pass_slots_used,
)


def test_play_pass_slots_unlimited_by_default():
    init_db()
    db = SessionLocal()
    try:
        set_setting(db, "play_pass_max_slots", "0")
        assert play_pass_slots_remaining(db) is None
        assert play_pass_accepts_new(db) is True
    finally:
        db.close()


def test_play_pass_slots_count_and_full():
    init_db()
    db = SessionLocal()
    try:
        set_setting(db, "play_pass_max_slots", "2")
        user = User(telegram_id=999001, username="t", first_name="T", language="ar", points=100)
        db.add(user)
        db.commit()
        db.add(
            PlayPassRequest(
                user_id=user.id,
                account_name="a",
                account_password="p",
                status="pending",
            )
        )
        db.add(
            PlayPassRequest(
                user_id=user.id,
                account_name="b",
                account_password="p",
                status="rejected",
            )
        )
        db.commit()
        assert play_pass_slots_used(db) == 1
        assert play_pass_slots_remaining(db) == 1
        assert play_pass_accepts_new(db) is True
        db.add(
            PlayPassRequest(
                user_id=user.id,
                account_name="c",
                account_password="p",
                status="done",
            )
        )
        db.commit()
        assert play_pass_slots_used(db) == 2
        assert play_pass_slots_remaining(db) == 0
        assert play_pass_accepts_new(db) is False
    finally:
        db.close()
