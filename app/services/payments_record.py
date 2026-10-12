"""Persist Telegram Stars payments on successful_payment."""

from sqlalchemy.orm import Session

from app.database import User
from app.services.star_payments import record_star_payment


def save_successful_star_payment(db: Session, user: User, payment) -> None:
    if payment.currency != "XTR":
        return
    record_star_payment(
        db,
        user,
        int(payment.total_amount),
        payment.invoice_payload or "",
        payment.telegram_payment_charge_id or "",
    )
