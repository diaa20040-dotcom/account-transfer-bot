"""One-time helpers for fresh deployments (e.g. empty SQLite on Render)."""

from sqlalchemy.orm import Session

from app.config import settings
from app.database import User


def bootstrap_admin_points(db: Session) -> None:
    pts = int(settings.admin_bootstrap_points or 0)
    if pts <= 0 or not settings.admin_ids:
        return
    for tid in settings.admin_ids:
        user = db.query(User).filter_by(telegram_id=tid).first()
        if user is None:
            db.add(User(telegram_id=tid, points=pts, language="ar"))
        elif user.points == 0:
            user.points = pts
    db.commit()
