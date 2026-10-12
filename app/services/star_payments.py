import logging

from aiogram import Bot
from sqlalchemy.orm import Session

from app.database import StarPayment, User
from app.i18n import t

logger = logging.getLogger(__name__)


def payment_kind_from_payload(payload: str) -> str:
    if payload.startswith("topup:"):
        return "topup"
    if payload.startswith("runopen:"):
        return "run_open"
    if payload.startswith("playpass:"):
        return "play_pass"
    return "other"


def record_star_payment(
    db: Session,
    user: User,
    stars: int,
    payload: str,
    charge_id: str,
) -> StarPayment | None:
    if not charge_id:
        return None
    existing = db.query(StarPayment).filter_by(telegram_payment_charge_id=charge_id).first()
    if existing:
        return existing
    row = StarPayment(
        user_id=user.id,
        stars_amount=stars,
        payment_kind=payment_kind_from_payload(payload),
        invoice_payload=payload[:128],
        telegram_payment_charge_id=charge_id,
        refunded=False,
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


def list_refundable_payments(db: Session, user_id: int, limit: int = 15) -> list[StarPayment]:
    return (
        db.query(StarPayment)
        .filter_by(user_id=user_id, refunded=False)
        .order_by(StarPayment.created_at.desc())
        .limit(limit)
        .all()
    )


_KIND_LABEL_AR = {
    "topup": "شحن نقاط",
    "run_open": "جائزة أسبوعية",
    "play_pass": "Play Pass",
    "other": "دفع",
}


def payment_kind_label(kind: str, lang: str = "ar") -> str:
    if lang == "en":
        labels = {
            "topup": "top-up",
            "run_open": "weekly reward",
            "play_pass": "Play Pass",
            "other": "payment",
        }
        return labels.get(kind, kind)
    return _KIND_LABEL_AR.get(kind, kind)


async def refund_star_payment_record(
    bot: Bot, db: Session, payment: StarPayment
) -> tuple[bool, str]:
    if payment.refunded:
        return False, "already_refunded"
    user = db.query(User).filter_by(id=payment.user_id).first()
    if not user:
        return False, "no_user"
    try:
        ok = await bot.refund_star_payment(
            user_id=user.telegram_id,
            telegram_payment_charge_id=payment.telegram_payment_charge_id,
        )
    except Exception as exc:
        logger.exception("refund_star_payment failed id=%s", payment.id)
        return False, str(exc)
    if not ok:
        return False, "api_failed"
    payment.refunded = True
    if payment.payment_kind == "topup":
        user.points = max(0, user.points - payment.stars_amount)
    db.commit()
    lang = user.language if user.language in ("ar", "en") else "ar"
    try:
        await bot.send_message(
            user.telegram_id,
            t(
                lang,
                "stars_refunded_user",
                stars=payment.stars_amount,
                kind=payment_kind_label(payment.payment_kind, lang),
            ),
        )
    except Exception:
        pass
    return True, "ok"
