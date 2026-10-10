#!/usr/bin/env python3
"""Export users + settings from local SQLite into data/startup_seed.json for cloud deploy."""

import json
from pathlib import Path

from app.database import SessionLocal, AppSetting, Task, User

OUT = Path(__file__).resolve().parents[1] / "data" / "startup_seed.json"


def main() -> None:
    db = SessionLocal()
    users = [
        {
            "telegram_id": u.telegram_id,
            "points": u.points,
            "language": u.language,
            "username": u.username,
        }
        for u in db.query(User).all()
    ]
    settings = {r.key: r.value for r in db.query(AppSetting).all()}
    tasks = [
        {
            "title_ar": t.title_ar,
            "title_en": t.title_en,
            "chat_id": t.chat_id,
            "invite_link": t.invite_link,
            "reward_points": t.reward_points,
            "active": t.active,
            "sort_order": t.sort_order,
        }
        for t in db.query(Task).all()
    ]
    db.close()
    payload = {"users": users, "settings": settings, "tasks": tasks}
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Wrote {len(users)} users to {OUT}")


if __name__ == "__main__":
    main()
