"""Full database backup export / restore (users, settings, tasks, transfers)."""

import json
from pathlib import Path
from typing import Any

from sqlalchemy.orm import Session

from app.database import AppSetting, Task, TransferRequest, User

RUNTIME_SNAPSHOT = Path(__file__).resolve().parents[2] / "data" / "runtime_snapshot.json"
BUNDLED_SEED = Path(__file__).resolve().parents[2] / "data" / "startup_seed.json"


def build_backup_payload(db: Session) -> dict[str, Any]:
    return {
        "users": [
            {
                "telegram_id": u.telegram_id,
                "points": u.points,
                "language": u.language,
                "username": u.username,
                "referral_credited": bool(u.referral_credited),
                "referred_by_telegram_id": (
                    u.referred_by.telegram_id if u.referred_by else None
                ),
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
        "transfers": [
            {
                "user_telegram_id": tr.user.telegram_id,
                "country_id": tr.country_id,
                "account_name": tr.account_name,
                "account_password": tr.account_password,
                "status": tr.status,
            }
            for tr in db.query(TransferRequest).join(User).all()
        ],
    }


def backup_json_bytes(db: Session) -> bytes:
    payload = build_backup_payload(db)
    return json.dumps(payload, ensure_ascii=False, indent=2).encode("utf-8")


def write_runtime_snapshot(db: Session) -> None:
    RUNTIME_SNAPSHOT.parent.mkdir(parents=True, exist_ok=True)
    RUNTIME_SNAPSHOT.write_text(
        json.dumps(build_backup_payload(db), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def load_seed_payload() -> dict[str, Any] | None:
    for path in (RUNTIME_SNAPSHOT, BUNDLED_SEED):
        if path.is_file():
            try:
                return json.loads(path.read_text(encoding="utf-8"))
            except Exception:
                continue
    return None


def import_backup_payload(db: Session, payload: dict[str, Any]) -> tuple[int, int, int]:
    """Restore from backup. Returns (users, tasks, transfers)."""
    id_by_tid: dict[int, int] = {}
    users_n = 0
    for row in payload.get("users") or []:
        tid = int(row["telegram_id"])
        pts = int(row.get("points") or 0)
        lang = row.get("language") or "ar"
        username = row.get("username")
        user = db.query(User).filter_by(telegram_id=tid).first()
        if user is None:
            user = User(
                telegram_id=tid,
                points=pts,
                language=lang,
                username=username,
                referral_credited=bool(row.get("referral_credited", False)),
            )
            db.add(user)
            db.flush()
        else:
            user.points = pts
            user.language = lang
            if username:
                user.username = username
            user.referral_credited = bool(row.get("referral_credited", user.referral_credited))
        id_by_tid[tid] = user.id
        users_n += 1

    for row in payload.get("users") or []:
        tid = int(row["telegram_id"])
        ref_tid = row.get("referred_by_telegram_id")
        if ref_tid:
            user = db.query(User).filter_by(telegram_id=tid).first()
            referrer = db.query(User).filter_by(telegram_id=int(ref_tid)).first()
            if user and referrer:
                user.referred_by_id = referrer.id

    for key, value in (payload.get("settings") or {}).items():
        if key == "persisted_admin_ids":
            continue
        existing = db.query(AppSetting).filter_by(key=key).first()
        if existing:
            existing.value = str(value)
        else:
            db.add(AppSetting(key=key, value=str(value)))

    backup_tasks = payload.get("tasks") or []
    tasks_n = 0
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
        tasks_n = len(backup_tasks)

    transfers_n = 0
    backup_transfers = payload.get("transfers") or []
    if backup_transfers:
        db.query(TransferRequest).delete()
        for row in backup_transfers:
            utid = int(row["user_telegram_id"])
            user = db.query(User).filter_by(telegram_id=utid).first()
            if not user:
                continue
            db.add(
                TransferRequest(
                    user_id=user.id,
                    country_id=int(row["country_id"]),
                    account_name=row["account_name"],
                    account_password=row["account_password"],
                    status=row.get("status") or "pending",
                )
            )
            transfers_n += 1

    db.commit()
    return users_n, tasks_n, transfers_n
