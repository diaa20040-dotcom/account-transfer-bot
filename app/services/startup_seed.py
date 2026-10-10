"""Restore users, settings, and tasks from data/startup_seed.json on empty / fresh hosts."""

import json
import logging
from pathlib import Path

from sqlalchemy.orm import Session

from app.database import AppSetting, Task, User

logger = logging.getLogger(__name__)

SEED_PATH = Path(__file__).resolve().parents[2] / "data" / "startup_seed.json"


def apply_startup_seed(db: Session) -> None:
    if not SEED_PATH.is_file():
        return
    try:
        payload = json.loads(SEED_PATH.read_text(encoding="utf-8"))
    except Exception:
        logger.exception("Could not read startup seed")
        return

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
        elif user.points == 0 and pts > 0:
            user.points = pts
            if username and not user.username:
                user.username = username

    for key, value in (payload.get("settings") or {}).items():
        if key == "persisted_admin_ids":
            continue
        existing = db.query(AppSetting).filter_by(key=key).first()
        if existing is None:
            db.add(AppSetting(key=key, value=str(value)))
        elif not (existing.value or "").strip():
            existing.value = str(value)

    if db.query(Task).count() == 0:
        for row in payload.get("tasks") or []:
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
    logger.info("Startup seed applied from %s", SEED_PATH.name)
