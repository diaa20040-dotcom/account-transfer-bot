#!/usr/bin/env python3
"""Push data/startup_seed.json to GitHub (uses GITHUB_BACKUP_TOKEN or GH_TOKEN)."""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.database import SessionLocal, init_db
from app.services.backup_export import build_backup_payload
from app.services.github_seed_sync import push_seed_to_github


def main() -> None:
    init_db()
    db = SessionLocal()
    try:
        payload = build_backup_payload(db)
    finally:
        db.close()
    ok = push_seed_to_github(payload, force=True)
    if not ok:
        print("Push failed — set GITHUB_BACKUP_TOKEN or GH_TOKEN with repo write access.")
        sys.exit(1)
    print(f"Pushed seed with {len(payload.get('users') or [])} users.")


if __name__ == "__main__":
    main()
