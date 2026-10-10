"""Optional restore from bundled seed — only when DB is empty (manual restore via admin)."""

import logging

from sqlalchemy.orm import Session

from app.database import User
from app.services.backup_export import (
    import_backup_payload,
    load_bundled_seed_payload,
    load_seed_payload,
    write_runtime_snapshot,
)

logger = logging.getLogger(__name__)


def apply_startup_seed(db: Session, force: bool = False) -> bool:
    """Auto-restore only on a completely empty database (fresh deploy). No old seed overwrite."""
    payload = load_seed_payload()
    if not payload:
        return False
    if force:
        users_n, tasks_n, transfers_n = import_backup_payload(db, payload)
        logger.info("Forced restore: %s users, %s tasks, %s transfers", users_n, tasks_n, transfers_n)
        return True

    if db.query(User).count() == 0:
        users_n, tasks_n, transfers_n = import_backup_payload(db, payload)
        logger.info(
            "Empty DB restore: %s users, %s tasks, %s transfers",
            users_n,
            tasks_n,
            transfers_n,
        )
        return True
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
