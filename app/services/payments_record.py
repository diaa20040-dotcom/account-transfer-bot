"""Persist Telegram Stars payments on successful_payment."""

import logging

from sqlalchemy.orm import Session

from app.database import User
from app.services.star_payments import record_star_payment

logger = logging.getLogger(__name__)


def save_successful_star_payment(db: Session, user: User, payment) -> None:
    if payment.currency != "XTR":
        return
    charge_id = payment.telegram_payment_charge_id or ""
    if not charge_id:
        logger.error(
            "successful_payment missing telegram_payment_charge_id tg=%s payload=%s",
            user.telegram_id,
            payment.invoice_payload,
        )
    row = record_star_payment(
        db,
        user,
        int(payment.total_amount),
        payment.invoice_payload or "",
        charge_id,
    )
    if not row and charge_id:
        logger.warning("star payment not recorded tg=%s charge=%s…", user.telegram_id, charge_id[:12])
