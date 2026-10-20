"""Random visa stock assignment — each card used at most once."""

import random
from dataclasses import dataclass
from datetime import datetime

from sqlalchemy.orm import Session

from app.database import User, VisaRequest, VisaStock


@dataclass
class VisaDeliveryResult:
    ok: bool
    reason: str  # delivered | sold_out
    request: VisaRequest | None = None
    content: str | None = None


def count_available_visas(db: Session) -> int:
    return db.query(VisaStock).filter_by(is_used=False).count()


def _pick_unused_stock(db: Session) -> VisaStock | None:
    rows = (
        db.query(VisaStock)
        .filter_by(is_used=False)
        .with_for_update()
        .all()
    )
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
    stock = _pick_unused_stock(db)
    if not stock:
        return VisaDeliveryResult(ok=False, reason="sold_out")

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
