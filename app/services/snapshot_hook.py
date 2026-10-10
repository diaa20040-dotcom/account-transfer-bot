from app.database import SessionLocal
from app.services.startup_seed import persist_runtime_snapshot


def snapshot_db() -> None:
    db = SessionLocal()
    try:
        persist_runtime_snapshot(db)
    finally:
        db.close()
