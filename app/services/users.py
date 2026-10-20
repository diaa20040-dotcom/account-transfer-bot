from aiogram import Bot
from sqlalchemy.orm import Session

from app.database import User, get_setting
from app.i18n import t
from app.services.mandatory_sub import get_mandatory_sub_config, is_user_subscribed


async def referral_requirement_met(db: Session, bot: Bot, user: User) -> bool:
    """Referral counts only after the invited user joins the mandatory channel."""
    cfg = get_mandatory_sub_config(db)
    if not cfg.active:
        return True
    return await is_user_subscribed(bot, cfg.chat_id, user.telegram_id)


def _get_or_create_referrer(db: Session, referrer_telegram_id: int) -> User | None:
    if referrer_telegram_id <= 0:
        return None
    referrer = db.query(User).filter_by(telegram_id=referrer_telegram_id).first()
    if referrer:
        return referrer
    referrer = User(telegram_id=referrer_telegram_id, language="ar", points=0)
    db.add(referrer)
    db.flush()
    return referrer


def link_referrer(
    db: Session, user: User, referrer_telegram_id: int | None
) -> bool:
    """Attach referrer on first /start with ref_… (referrer row created if needed)."""
    if not referrer_telegram_id or referrer_telegram_id == user.telegram_id:
        return False
    if user.referred_by_id:
        return False
    referrer = _get_or_create_referrer(db, referrer_telegram_id)
    if not referrer or referrer.id == user.id:
        return False
    user.referred_by_id = referrer.id
    db.commit()
    db.refresh(user)
    return True


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
    ref_pts = int(get_setting(db, "referral_points", "1"))
    referrer.points += ref_pts
    user.referral_credited = True
    db.commit()
    db.refresh(user)
    db.refresh(referrer)
    lang = referrer.language if referrer.language in ("ar", "en") else "ar"
    try:
        await bot.send_message(
            referrer.telegram_id,
            t(lang, "referral_earned", points=ref_pts),
        )
    except Exception:
        pass
    return True


async def maybe_credit_referral(db: Session, bot: Bot, telegram_id: int) -> None:
    user = db.query(User).filter_by(telegram_id=telegram_id).first()
    if user and user.referred_by_id and not user.referral_credited:
        await try_award_referral(db, bot, user)


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
        link_referrer(db, user, referrer_telegram_id)
        db.commit()
        db.refresh(user)
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
    link_referrer(db, user, referrer_telegram_id)
    db.commit()
    db.refresh(user)
    return user, created


def referral_count(db: Session, user: User) -> int:
    return (
        db.query(User)
        .filter_by(referred_by_id=user.id, referral_credited=True)
        .count()
    )


def referral_pending_count(db: Session, user: User) -> int:
    return (
        db.query(User)
        .filter_by(referred_by_id=user.id, referral_credited=False)
        .count()
    )
