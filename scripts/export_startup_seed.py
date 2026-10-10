#!/usr/bin/env python3
"""Export users + settings from local SQLite into data/startup_seed.json for cloud deploy."""

import json
from pathlib import Path

from app.database import SessionLocal
from app.services.backup_export import build_backup_payload

OUT = Path(__file__).resolve().parents[1] / "data" / "startup_seed.json"


def main() -> None:
    db = SessionLocal()
    payload = build_backup_payload(db)
    db.close()
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Wrote {len(payload.get('users', []))} users to {OUT}")


if __name__ == "__main__":
    main()
