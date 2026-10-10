"""Restore bundled / runtime snapshots on fresh Render deploys."""

import logging

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.database import TransferRequest, User
from app.services.backup_export import (
    import_backup_payload,
    load_bundled_seed_payload,
    load_seed_payload,
    write_runtime_snapshot,
)

logger = logging.getLogger(__name__)


def _seed_totals(payload: dict) -> tuple[int, int]:
    users = payload.get("users") or []
    return len(users), sum(int(u.get("points") or 0) for u in users)


def _needs_full_restore(db: Session, payload: dict) -> bool:
    user_count = db.query(User).count()
    if user_count == 0:
        return True

    total_pts = db.query(func.coalesce(func.sum(User.points), 0)).scalar() or 0
    seed_n, seed_pts = _seed_totals(payload)
    if seed_n == 0:
        return False

    # Fresh SQLite after Render deploy: many accounts in DB but almost no points vs bundled seed
    if seed_pts > 50 and total_pts < max(20, int(seed_pts * 0.15)):
        return True

    if user_count <= 5 and total_pts == 0 and seed_pts > 0:
        return True

    transfers = db.query(TransferRequest).count()
    seed_transfers = len(payload.get("transfers") or [])
    if seed_transfers > 0 and transfers == 0 and total_pts < seed_pts // 2:
        return True

    return False


def apply_startup_seed(db: Session, force: bool = False) -> bool:
    payload = load_seed_payload()
    if not payload:
        return False
    if force or _needs_full_restore(db, payload):
        users_n, tasks_n, transfers_n = import_backup_payload(db, payload)
        logger.info(
            "Full restore: %s users, %s tasks, %s transfers",
            users_n,
            tasks_n,
            transfers_n,
        )
        return True

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
    return False


def force_restore_bundled_seed(db: Session) -> tuple[int, int, int] | None:
    payload = load_bundled_seed_payload()
    if not payload:
        return None
    return import_backup_payload(db, payload)


def persist_runtime_snapshot(db: Session) -> None:
    try:
        write_runtime_snapshot(db)
    except Exception:
        logger.exception("Could not write runtime snapshot")
