"""Full database backup export / restore (users, settings, tasks)."""

import json
from typing import Any

from sqlalchemy.orm import Session

from app.database import AppSetting, Task, User


def build_backup_payload(db: Session) -> dict[str, Any]:
    return {
        "users": [
            {
                "telegram_id": u.telegram_id,
                "points": u.points,
                "language": u.language,
                "username": u.username,
            }
            for u in db.query(User).all()
        ],
        "settings": {r.key: r.value for r in db.query(AppSetting).all()},
        "tasks": [
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
        ],
    }


def backup_json_bytes(db: Session) -> bytes:
    payload = build_backup_payload(db)
    return json.dumps(payload, ensure_ascii=False, indent=2).encode("utf-8")


def import_backup_payload(db: Session, payload: dict[str, Any]) -> tuple[int, int]:
    """Restore from admin backup. Returns (users_updated, tasks_count)."""
    users_n = 0
    for row in payload.get("users") or []:
        tid = int(row["telegram_id"])
        pts = int(row.get("points") or 0)
        lang = row.get("language") or "ar"
        username = row.get("username")
        user = db.query(User).filter_by(telegram_id=tid).first()
        if user is None:
            db.add(
                User(
                    telegram_id=tid,
                    points=pts,
                    language=lang,
                    username=username,
                )
            )
        else:
            user.points = pts
            user.language = lang
            if username:
                user.username = username
        users_n += 1

    for key, value in (payload.get("settings") or {}).items():
        if key == "persisted_admin_ids":
            continue
        existing = db.query(AppSetting).filter_by(key=key).first()
        if existing:
            existing.value = str(value)
        else:
            db.add(AppSetting(key=key, value=str(value)))

    backup_tasks = payload.get("tasks") or []
    if backup_tasks:
        db.query(Task).delete()
        for row in backup_tasks:
            db.add(
                Task(
                    title_ar=row["title_ar"],
                    title_en=row["title_en"],
                    chat_id=row["chat_id"],
                    invite_link=row.get("invite_link"),
                    reward_points=int(row.get("reward_points") or 10),
                    active=bool(row.get("active", True)),
                    sort_order=int(row.get("sort_order") or 0),
                )
            )

    db.commit()
    return users_n, len(backup_tasks)
