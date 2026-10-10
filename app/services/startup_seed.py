"""Restore bundled / runtime snapshots on fresh Render deploys."""

import logging

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.config import settings
from app.database import TransferRequest, User
from app.services.backup_export import (
    import_backup_payload,
    load_bundled_seed_payload,
    load_seed_payload,
    write_runtime_snapshot,
)

logger = logging.getLogger(__name__)


def _using_sqlite() -> bool:
    return "sqlite" in settings.database_url.lower()


def _seed_totals(payload: dict) -> tuple[int, int]:
    users = payload.get("users") or []
    return len(users), sum(int(u.get("points") or 0) for u in users)


def _needs_full_restore(db: Session, payload: dict) -> bool:
    user_count = db.query(User).count()
    if user_count == 0:
        return True

    total_pts = int(db.query(func.coalesce(func.sum(User.points), 0)).scalar() or 0)
    seed_n, seed_pts = _seed_totals(payload)
    if seed_n == 0 or seed_pts == 0:
        return False

    # Wiped or nearly empty DB vs bundled backup
    if total_pts < max(30, int(seed_pts * 0.5)):
        return True

    if user_count < seed_n // 2 and total_pts < seed_pts:
        return True

    transfers = db.query(TransferRequest).count()
    seed_transfers = len(payload.get("transfers") or [])
    if seed_transfers > 0 and transfers == 0 and total_pts < int(seed_pts * 0.6):
        return True

    return False


def merge_bundled_seed_points(db: Session) -> int:
    """Raise each known user to at least bundled seed points (never lowers balance)."""
    payload = load_bundled_seed_payload()
    if not payload:
        return 0
    updated = 0
    for row in payload.get("users") or []:
        tid = int(row["telegram_id"])
        pts = int(row.get("points") or 0)
        if pts <= 0:
            continue
        user = db.query(User).filter_by(telegram_id=tid).first()
        if user is None:
            db.add(
                User(
                    telegram_id=tid,
                    points=pts,
                    language=row.get("language") or "ar",
                    username=row.get("username"),
                    referral_credited=bool(row.get("referral_credited", False)),
                )
            )
            updated += 1
        elif user.points < pts:
            user.points = pts
            updated += 1
    if updated:
        db.commit()
        logger.info("Merged bundled seed points for %s users", updated)
    return updated


def restore_user_points_from_seed(db: Session, telegram_id: int) -> bool:
    payload = load_bundled_seed_payload()
    if not payload:
        return False
    for row in payload.get("users") or []:
        if int(row["telegram_id"]) != telegram_id:
            continue
        pts = int(row.get("points") or 0)
        if pts <= 0:
            return False
        user = db.query(User).filter_by(telegram_id=telegram_id).first()
        if user is None:
            return False
        if user.points < pts:
            user.points = pts
            db.commit()
            return True
        return False
    return False


def apply_startup_seed(db: Session, force: bool = False) -> bool:
    payload = load_seed_payload()
    if not payload:
        logger.warning("No startup seed payload found")
        return False
    if force or _needs_full_restore(db, payload):
        users_n, tasks_n, transfers_n = import_backup_payload(db, payload)
        logger.info(
            "Full restore: %s users, %s tasks, %s transfers",
            users_n,
            tasks_n,
            transfers_n,
        )
        if _using_sqlite():
            merge_bundled_seed_points(db)
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
        elif user.points < pts:
            user.points = pts
    db.commit()

    if _using_sqlite():
        merge_bundled_seed_points(db)
    return False


def force_restore_bundled_seed(db: Session) -> tuple[int, int, int] | None:
    payload = load_bundled_seed_payload()
    if not payload:
        return None
    result = import_backup_payload(db, payload)
    merge_bundled_seed_points(db)
    return result


def persist_runtime_snapshot(db: Session) -> None:
    try:
        write_runtime_snapshot(db)
    except Exception:
        logger.exception("Could not write runtime snapshot")
