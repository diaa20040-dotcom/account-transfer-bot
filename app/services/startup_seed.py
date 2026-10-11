"""Restore from GitHub / bundled seed when Render wipes SQLite."""

import logging

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.config import settings
from app.database import BoxGame, Country, User
from app.services.backup_export import (
    import_backup_payload,
    load_bundled_seed_payload,
    load_seed_payload,
)
from app.services.github_seed_sync import fetch_seed_from_github

logger = logging.getLogger(__name__)


def _seed_stats(payload: dict) -> tuple[int, int]:
    users = payload.get("users") or []
    return len(users), sum(int(u.get("points") or 0) for u in users)


def _load_restore_payload() -> dict | None:
    payload = load_seed_payload()
    if not payload and settings.public_url.strip():
        payload = fetch_seed_from_github()
    return payload


def _needs_restore(db: Session, payload: dict) -> bool:
    if db.query(User).count() == 0:
        return True
    seed_n, seed_pts = _seed_stats(payload)
    if seed_n < 5:
        return False
    total_pts = int(db.query(func.coalesce(func.sum(User.points), 0)).scalar() or 0)
    user_n = db.query(User).count()
    if seed_pts > 200 and total_pts < max(50, seed_pts // 10):
        return True
    if user_n < seed_n // 3 and total_pts < seed_pts // 5:
        return True
    if db.query(BoxGame).count() == 0 and (payload.get("box_games") or []):
        return True
    if db.query(Country).count() == 0 and (payload.get("countries") or []):
        return True
    return False


def apply_startup_seed(db: Session, force: bool = False) -> bool:
    payload = _load_restore_payload()
    if not payload:
        logger.warning("No seed payload for restore")
        return False
    if force or _needs_restore(db, payload):
        users_n, tasks_n, transfers_n = import_backup_payload(db, payload)
        logger.info(
            "Restored from seed: %s users, %s tasks, %s transfers",
            users_n,
            tasks_n,
            transfers_n,
        )
        return True
    return False


def force_restore_bundled_seed(db: Session) -> tuple[int, int, int] | None:
    payload = load_bundled_seed_payload() or _load_restore_payload()
    if not payload:
        return None
    return import_backup_payload(db, payload)


def persist_runtime_snapshot(db: Session) -> None:
    try:
        import json

        from app.services.backup_export import BUNDLED_SEED, build_backup_payload
        from app.services.github_seed_sync import push_seed_to_github

        payload = build_backup_payload(db)
        user_n = len(payload.get("users") or [])
        if user_n < 3:
            logger.warning("Skip snapshot push: only %s users in DB", user_n)
            return
        from app.services.backup_export import write_runtime_snapshot

        write_runtime_snapshot(db)
        try:
            BUNDLED_SEED.parent.mkdir(parents=True, exist_ok=True)
            BUNDLED_SEED.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        except Exception:
            pass
        push_seed_to_github(payload)
    except Exception:
        logger.exception("Could not write runtime snapshot")
