from aiogram import Bot
from sqlalchemy.orm import Session

from app.database import User, get_setting
from app.services.mandatory_sub import get_mandatory_sub_config, is_user_subscribed


async def referral_requirement_met(db: Session, bot: Bot, user: User) -> bool:
    cfg = get_mandatory_sub_config(db)
    if not cfg.active:
        return True
    return await is_user_subscribed(bot, cfg.chat_id, user.telegram_id)


async def try_award_referral(db: Session, bot: Bot, user: User) -> bool:
    """Grant referrer points once the referred user meets the mandatory-channel rule."""
    if user.referral_credited or not user.referred_by_id:
        return False
    if not await referral_requirement_met(db, bot, user):
        return False
    referrer = db.query(User).filter_by(id=user.referred_by_id).first()
    if not referrer:
        user.referral_credited = True
        db.commit()
        return False
    ref_pts = int(get_setting(db, "referral_points", "25"))
    referrer.points += ref_pts
    user.referral_credited = True
    db.commit()
    db.refresh(user)
    return True


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
    db.commit()
    db.refresh(user)
    return user, created


def referral_count(db: Session, user: User) -> int:
    return (
        db.query(User)
        .filter_by(referred_by_id=user.id, referral_credited=True)
        .count()
    )
