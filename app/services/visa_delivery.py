"""Random visa stock assignment — each card used at most once."""

import logging
import random
from dataclasses import dataclass
from datetime import datetime

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.database import User, VisaRequest, VisaStock

logger = logging.getLogger(__name__)


@dataclass
class VisaDeliveryResult:
    ok: bool
    reason: str  # delivered | sold_out | insufficient_points | error
    request: VisaRequest | None = None
    content: str | None = None


def count_available_visas(db: Session) -> int:
    return db.query(VisaStock).filter_by(is_used=False).count()


def _pick_unused_stock(db: Session) -> VisaStock | None:
    try:
        row = (
            db.query(VisaStock)
            .filter_by(is_used=False)
            .order_by(func.random())
            .first()
        )
        if row:
            return row
    except Exception:
        logger.exception("visa stock random pick failed, using fallback")
    rows = db.query(VisaStock).filter_by(is_used=False).all()
    if not rows:
        return None
    return random.choice(rows)


def fulfill_visa_order(
    db: Session,
    user: User,
    payment_method: str,
    points_paid: int,
    stars_paid: int,
) -> VisaDeliveryResult:
    try:
        stock = _pick_unused_stock(db)
        if not stock:
            return VisaDeliveryResult(ok=False, reason="sold_out")

        if payment_method == "points" and points_paid > 0:
            if user.points < points_paid:
                return VisaDeliveryResult(ok=False, reason="insufficient_points")
            user.points -= points_paid

        stock.is_used = True
        stock.used_at = datetime.utcnow()
        stock.used_by_user_id = user.id

        req = VisaRequest(
            user_id=user.id,
            details=stock.content,
            visa_stock_id=stock.id,
            points_paid=points_paid,
            stars_paid=stars_paid,
            payment_method=payment_method,
            status="done",
        )
        db.add(req)
        db.commit()
        db.refresh(req)
        db.refresh(stock)
        return VisaDeliveryResult(ok=True, reason="delivered", request=req, content=stock.content)
    except Exception:
        logger.exception("fulfill_visa_order failed user_id=%s", user.id)
        db.rollback()
        return VisaDeliveryResult(ok=False, reason="error")
