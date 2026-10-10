"""Restore bundled / runtime snapshots on fresh Render deploys."""

import logging

from sqlalchemy.orm import Session

from app.database import TransferRequest, User
from app.services.backup_export import import_backup_payload, load_seed_payload, write_runtime_snapshot

logger = logging.getLogger(__name__)


def _needs_full_restore(db: Session) -> bool:
    users = db.query(User).count()
    if users == 0:
        return True
    transfers = db.query(TransferRequest).count()
    if transfers == 0 and users <= 3:
        max_pts = max((u.points for u in db.query(User).all()), default=0)
        if max_pts == 0:
            return True
    return False


def apply_startup_seed(db: Session) -> None:
    payload = load_seed_payload()
    if not payload:
        return
    if _needs_full_restore(db):
        users_n, tasks_n, transfers_n = import_backup_payload(db, payload)
        logger.info(
            "Full restore: %s users, %s tasks, %s transfers",
            users_n,
            tasks_n,
            transfers_n,
        )
        return

    for row in payload.get("users") or []:
        tid = int(row["telegram_id"])
        pts = int(row.get("points") or 0)
        user = db.query(User).filter_by(telegram_id=tid).first()
        if user is None:
            db.add(
                User(
                    telegram_id=tid,
                    points=pts,
                    language=row.get("language") or "ar",
                    username=row.get("username"),
                )
            )
        elif user.points == 0 and pts > 0:
            user.points = pts
    db.commit()


def persist_runtime_snapshot(db: Session) -> None:
    try:
        write_runtime_snapshot(db)
    except Exception:
        logger.exception("Could not write runtime snapshot")
