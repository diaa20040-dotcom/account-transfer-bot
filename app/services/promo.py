from datetime import datetime

from sqlalchemy.orm import Session

from app.database import PromoCode, PromoRedemption, User


def normalize_promo_code(raw: str) -> str:
    return raw.strip().upper().replace(" ", "")


def redeem_promo_code(db: Session, user: User, raw_code: str) -> tuple[bool, str, int]:
    """
    Returns (ok, message_key_or_text, points_awarded).
    message is an i18n key with optional suffix for errors.
    """
    code = normalize_promo_code(raw_code)
    if not code or len(code) > 64:
        return False, "promo_invalid", 0

    promo = db.query(PromoCode).filter_by(code=code).first()
    if not promo or not promo.active:
        return False, "promo_not_found", 0

    if promo.expires_at and promo.expires_at < datetime.utcnow():
        return False, "promo_expired", 0

    if promo.max_uses > 0 and promo.used_count >= promo.max_uses:
        return False, "promo_exhausted", 0

    already = (
        db.query(PromoRedemption)
        .filter_by(user_id=user.id, promo_id=promo.id)
        .first()
    )
    if already:
        return False, "promo_already_used", 0

    user.points += promo.points
    promo.used_count += 1
    db.add(PromoRedemption(user_id=user.id, promo_id=promo.id))
    db.commit()
    return True, "promo_success", promo.points
