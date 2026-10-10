"""Full database backup export / restore (users, settings, tasks, transfers)."""

import json
from pathlib import Path
from typing import Any

from sqlalchemy import inspect
from sqlalchemy.orm import Session

from app.database import (
    engine,
    AppSetting,
    BoxGame,
    PromoCode,
    PromoRedemption,
    Task,
    TransferRequest,
    User,
)

RUNTIME_SNAPSHOT = Path(__file__).resolve().parents[2] / "data" / "runtime_snapshot.json"
BUNDLED_SEED = Path(__file__).resolve().parents[2] / "data" / "startup_seed.json"


def _table_exists(name: str) -> bool:
    return name in inspect(engine).get_table_names()


def build_backup_payload(db: Session) -> dict[str, Any]:
    payload: dict[str, Any] = {
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
    if _table_exists("box_games"):
        payload["box_games"] = [
            {
                "title": g.title,
                "point_cost": g.point_cost,
                "active": g.active,
                "sort_order": g.sort_order,
            }
            for g in db.query(BoxGame).order_by(BoxGame.sort_order).all()
        ]
    if _table_exists("promo_codes"):
        payload["promo_codes"] = [
            {
                "code": p.code,
                "points": p.points,
                "max_uses": p.max_uses,
                "used_count": p.used_count,
                "active": p.active,
                "expires_at": p.expires_at.isoformat() if p.expires_at else None,
            }
            for p in db.query(PromoCode).all()
        ]
    if _table_exists("promo_redemptions"):
        payload["promo_redemptions"] = [
            {
                "user_telegram_id": r.user.telegram_id,
                "code": r.promo.code,
            }
            for r in db.query(PromoRedemption).all()
        ]
    return payload


def backup_json_bytes(db: Session) -> bytes:
    payload = build_backup_payload(db)
    return json.dumps(payload, ensure_ascii=False, indent=2).encode("utf-8")


def write_runtime_snapshot(db: Session) -> None:
    RUNTIME_SNAPSHOT.parent.mkdir(parents=True, exist_ok=True)
    RUNTIME_SNAPSHOT.write_text(
        json.dumps(build_backup_payload(db), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def _read_json_file(path: Path) -> dict[str, Any] | None:
    if not path.is_file():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None


def load_seed_payload() -> dict[str, Any] | None:
    """Pick the richest backup: bundled seed vs local runtime snapshot."""
    candidates: list[tuple[int, dict[str, Any]]] = []
    for path in (BUNDLED_SEED, RUNTIME_SNAPSHOT):
        data = _read_json_file(path)
        if not data:
            continue
        users = data.get("users") or []
        total_pts = sum(int(u.get("points") or 0) for u in users)
        score = len(users) * 1000 + total_pts
        candidates.append((score, data))
    if not candidates:
        return None
    candidates.sort(key=lambda x: x[0], reverse=True)
    return candidates[0][1]


def load_bundled_seed_payload() -> dict[str, Any] | None:
    return _read_json_file(BUNDLED_SEED)


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

    backup_box = payload.get("box_games") or []
    if backup_box:
        db.query(BoxGame).delete()
        for row in backup_box:
            db.add(
                BoxGame(
                    title=row["title"],
                    point_cost=int(row.get("point_cost") or 50),
                    active=bool(row.get("active", True)),
                    sort_order=int(row.get("sort_order") or 0),
                )
            )

    backup_promos = payload.get("promo_codes") or []
    if backup_promos:
        db.query(PromoRedemption).delete()
        db.query(PromoCode).delete()
        code_to_id: dict[str, int] = {}
        for row in backup_promos:
            from datetime import datetime

            exp = row.get("expires_at")
            expires_at = None
            if exp:
                try:
                    expires_at = datetime.fromisoformat(exp.replace("Z", ""))
                except ValueError:
                    expires_at = None
            promo = PromoCode(
                code=str(row["code"]).upper(),
                points=int(row.get("points") or 0),
                max_uses=int(row.get("max_uses") or 0),
                used_count=int(row.get("used_count") or 0),
                active=bool(row.get("active", True)),
                expires_at=expires_at,
            )
            db.add(promo)
            db.flush()
            code_to_id[promo.code] = promo.id
        for row in payload.get("promo_redemptions") or []:
            utid = int(row["user_telegram_id"])
            code = str(row["code"]).upper()
            user = db.query(User).filter_by(telegram_id=utid).first()
            pid = code_to_id.get(code)
            if user and pid:
                db.add(PromoRedemption(user_id=user.id, promo_id=pid))

    db.commit()
    return users_n, tasks_n, transfers_n
