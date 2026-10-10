from sqlalchemy.orm import Session

from app.database import User, get_setting


def get_or_create_user(
    db: Session,
    telegram_id: int,
    username: str | None,
    first_name: str | None,
    referrer_telegram_id: int | None = None,
) -> tuple[User, bool]:
    user = db.query(User).filter_by(telegram_id=telegram_id).first()
    created = False
    if user:
        if username:
            user.username = username
        if first_name:
            user.first_name = first_name
        db.commit()
        return user, False

    user = User(
        telegram_id=telegram_id,
        username=username,
        first_name=first_name,
        language="ar",
        points=0,
    )
    db.add(user)
    db.flush()
    created = True

    if referrer_telegram_id and referrer_telegram_id != telegram_id:
        referrer = db.query(User).filter_by(telegram_id=referrer_telegram_id).first()
        if referrer:
            user.referred_by_id = referrer.id
            ref_pts = int(get_setting(db, "referral_points", "25"))
            referrer.points += ref_pts
    db.commit()
    db.refresh(user)
    return user, created


def referral_count(db: Session, user: User) -> int:
    return db.query(User).filter_by(referred_by_id=user.id).count()
