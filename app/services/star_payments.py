import logging
from datetime import timedelta

from aiogram import Bot
from aiogram.exceptions import TelegramBadRequest
from sqlalchemy.orm import Session

from app.database import PlayPassRequest, RunOpenRequest, StarPayment, User
from app.i18n import t

logger = logging.getLogger(__name__)


def admin_refund_feedback(ok: bool, detail: str, stars: int, telegram_id: int) -> str:
    if not ok:
        hints = {
            "missing_charge_id": (
                "لا يوجد معرّف دفع محفوظ لهذا السجل. افتح الطلب القديم والصق "
                "telegram_payment_charge_id من تفاصيل الدفع في تيليجرام."
            ),
            "already_refunded_db": (
                "السجل يقول «مُسترد» — إن النجوم لم تصل للمستخدم، راجع رصيد البوت "
                "(يجب أن يكون فيه نجوم كافية ولم تُسحب من Fragment)."
            ),
            "empty_charge_id": "أرسل telegram_payment_charge_id كاملاً (ليس رقم المعاملة من إعدادات النجوم فقط).",
            "api_failed": "تيليجرام رفض الاسترداد — تأكد من charge id وصاحب الدفع ورصيد نجوم البوت.",
        }
        return hints.get(detail, detail)
    if detail == "synced_telegram":
        return (
            f"✅ الدفع كان مُسترداً مسبقاً في تيليجرام — تم مزامنة السجل.\n"
            f"المستخدم: {telegram_id}"
        )
    return (
        f"✅ تم طلب الاسترداد من تيليجرام: **{stars}** نجمة → المستخدم {telegram_id}.\n"
        f"يجب أن تُخصم من رصيد البوت وتظهر في «نجومي» للمستخدم خلال ثوانٍ."
    )


def refund_error_message_ar(exc: Exception) -> str:
    text = str(exc)
    upper = text.upper()
    if "CHARGE_ALREADY_REFUNDED" in upper:
        return "هذا الدفع مُسترد مسبقاً في تيليجرام."
    if "CHARGE_ID_EMPTY" in upper or "CHARGE_ID_INVALID" in upper:
        return "معرّف الدفع فارغ أو غير صحيح."
    if "USER_ID_INVALID" in upper:
        return "معرّف المستخدم لا يطابق من دفع."
    if "PAYMENT" in upper and "NOT_FOUND" in upper:
        return "لم يُعثر على الدفع — تأكد من charge id ومن أن الدفع على نفس البوت."
    return text[:220]


async def telegram_refund_stars(
    bot: Bot, telegram_user_id: int, charge_id: str
) -> tuple[bool, str, bool]:
    """
    Call refundStarPayment. Returns (success, detail, already_refunded_on_telegram).
    """
    charge_id = (charge_id or "").strip()
    if not charge_id:
        return False, "empty_charge_id", False
    try:
        ok = await bot.refund_star_payment(
            user_id=telegram_user_id,
            telegram_payment_charge_id=charge_id,
        )
    except TelegramBadRequest as exc:
        msg = refund_error_message_ar(exc)
        already = "CHARGE_ALREADY_REFUNDED" in str(exc).upper()
        logger.warning(
            "refundStarPayment rejected user=%s charge=%s… err=%s",
            telegram_user_id,
            charge_id[:12],
            exc,
        )
        return False, msg, already
    except Exception as exc:
        logger.exception("refundStarPayment failed user=%s", telegram_user_id)
        return False, str(exc)[:220], False
    if not ok:
        logger.error(
            "refundStarPayment returned false user=%s charge=%s…",
            telegram_user_id,
            charge_id[:12],
        )
        return False, "api_failed", False
    logger.info(
        "refundStarPayment ok user=%s stars_charge=%s…",
        telegram_user_id,
        charge_id[:12],
    )
    return True, "ok", False


def payment_kind_from_payload(payload: str) -> str:
    if payload.startswith("sellstars:"):
        return "sell_stars"
    if payload.startswith("visa:"):
        return "visa"
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


def match_payment_to_request(
    db: Session,
    user_id: int,
    kind: str,
    stars: int,
    around,
    window_minutes: int = 180,
) -> StarPayment | None:
    if stars <= 0:
        return None
    start = around - timedelta(minutes=window_minutes)
    end = around + timedelta(minutes=45)
    return (
        db.query(StarPayment)
        .filter(
            StarPayment.user_id == user_id,
            StarPayment.payment_kind == kind,
            StarPayment.stars_amount == stars,
            StarPayment.refunded.is_(False),
            StarPayment.created_at >= start,
            StarPayment.created_at <= end,
        )
        .order_by(StarPayment.created_at.desc())
        .first()
    )


def mark_orders_refunded_for_payment(db: Session, payment: StarPayment) -> None:
    if payment.payment_kind not in ("run_open", "play_pass"):
        return
    start = payment.created_at - timedelta(minutes=180)
    end = payment.created_at + timedelta(minutes=45)
    if payment.payment_kind == "run_open":
        rows = (
            db.query(RunOpenRequest)
            .filter(
                RunOpenRequest.user_id == payment.user_id,
                RunOpenRequest.stars_paid == payment.stars_amount,
                RunOpenRequest.stars_refunded.is_(False),
                RunOpenRequest.created_at >= start,
                RunOpenRequest.created_at <= end,
            )
            .all()
        )
        for r in rows:
            r.stars_refunded = True
    else:
        rows = (
            db.query(PlayPassRequest)
            .filter(
                PlayPassRequest.user_id == payment.user_id,
                PlayPassRequest.stars_paid == payment.stars_amount,
                PlayPassRequest.stars_refunded.is_(False),
                PlayPassRequest.created_at >= start,
                PlayPassRequest.created_at <= end,
            )
            .all()
        )
        for r in rows:
            r.stars_refunded = True


def list_refundable_payments(db: Session, user_id: int, limit: int = 15) -> list[StarPayment]:
    return (
        db.query(StarPayment)
        .filter_by(user_id=user_id, refunded=False)
        .order_by(StarPayment.created_at.desc())
        .limit(limit)
        .all()
    )


_KIND_LABEL_AR = {
    "sell_stars": "بيع نجوم",
    "visa": "فيزا",
    "topup": "شحن نقاط",
    "run_open": "جائزة أسبوعية",
    "play_pass": "Play Pass",
    "other": "دفع",
}


def payment_kind_label(kind: str, lang: str = "ar") -> str:
    if lang == "en":
        labels = {
            "visa": "Visa",
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
        return False, "already_refunded_db"
    user = db.query(User).filter_by(id=payment.user_id).first()
    if not user:
        return False, "no_user"
    charge_id = (payment.telegram_payment_charge_id or "").strip()
    if not charge_id:
        return False, "missing_charge_id"
    ok, detail, already_tg = await telegram_refund_stars(bot, user.telegram_id, charge_id)
    if not ok and not already_tg:
        return False, detail
    payment.refunded = True
    if payment.payment_kind == "topup":
        user.points = max(0, user.points - payment.stars_amount)
    mark_orders_refunded_for_payment(db, payment)
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
    if already_tg:
        return True, "synced_telegram"
    return True, "ok"


async def refund_stars_by_charge_id(
    bot: Bot,
    db: Session,
    user: User,
    charge_id: str,
    stars: int,
    kind: str,
) -> tuple[bool, str]:
    charge_id = (charge_id or "").strip()
    if not charge_id:
        return False, "empty_charge_id"
    existing = db.query(StarPayment).filter_by(telegram_payment_charge_id=charge_id).first()
    if existing:
        if existing.refunded:
            return False, "already_refunded_db"
        return await refund_star_payment_record(bot, db, existing)
    ok, detail, already_tg = await telegram_refund_stars(bot, user.telegram_id, charge_id)
    if not ok and not already_tg:
        return False, detail
    row = StarPayment(
        user_id=user.id,
        stars_amount=stars,
        payment_kind=kind,
        invoice_payload=f"legacy:{kind}",
        telegram_payment_charge_id=charge_id,
        refunded=True,
    )
    db.add(row)
    db.commit()
    lang = user.language if user.language in ("ar", "en") else "ar"
    try:
        await bot.send_message(
            user.telegram_id,
            t(
                lang,
                "stars_refunded_user",
                stars=stars,
                kind=payment_kind_label(kind, lang),
            ),
        )
    except Exception:
        pass
    if already_tg:
        return True, "synced_telegram"
    return True, "ok"
