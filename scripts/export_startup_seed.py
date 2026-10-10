#!/usr/bin/env python3
"""Export users + settings from local SQLite into data/startup_seed.json for cloud deploy."""

import json
from pathlib import Path

from app.database import SessionLocal, init_db
from app.services.backup_export import build_backup_payload

DATA_DIR = Path(__file__).resolve().parents[1] / "data"
OUT = DATA_DIR / "startup_seed.json"
BACKUP_COPY = DATA_DIR / "bot_backup_before_update.json"


def main() -> None:
    init_db()
    db = SessionLocal()
    payload = build_backup_payload(db)
    db.close()
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    text = json.dumps(payload, ensure_ascii=False, indent=2)
    OUT.write_text(text, encoding="utf-8")
    BACKUP_COPY.write_text(text, encoding="utf-8")
    print(
        f"Wrote {len(payload.get('users', []))} users, "
        f"{len(payload.get('promo_codes', []))} promos to {OUT} and {BACKUP_COPY.name}"
    )


if __name__ == "__main__":
    main()
