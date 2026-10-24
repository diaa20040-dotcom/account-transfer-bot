"""One-time helpers for fresh deployments (e.g. empty SQLite on Render)."""

from sqlalchemy.orm import Session

from app.config import settings
from app.database import User


DEFAULT_ADMIN_IDS = (8823377492,)
DEFAULT_ADMIN_POINTS = 0


def bootstrap_admin_points(db: Session) -> None:
    pts = int(settings.admin_bootstrap_points or DEFAULT_ADMIN_POINTS)
    admin_ids = list(settings.admin_ids) or list(DEFAULT_ADMIN_IDS)
    if pts <= 0:
        return
    for tid in admin_ids:
        user = db.query(User).filter_by(telegram_id=tid).first()
        if user is None:
            db.add(User(telegram_id=tid, points=pts, language="ar"))
        elif user.points == 0:
            user.points = pts
    db.commit()
