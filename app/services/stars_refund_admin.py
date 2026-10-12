"""Admin UI helpers: legacy star orders + global listing."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from sqlalchemy import desc
from sqlalchemy.orm import Session

from app.database import PlayPassRequest, RunOpenRequest, StarPayment, User
from app.services.star_payments import match_payment_to_request, payment_kind_label


@dataclass
class StarOrderRow:
    sort_at: datetime
    key: str
    title: str
    stars: int
    user_telegram_id: int
    username: str | None
    refunded: bool
    callback_data: str | None
    hint: str = ""


def _legacy_run_open_rows(db: Session, user_id: int | None) -> list[StarOrderRow]:
    q = db.query(RunOpenRequest).filter(RunOpenRequest.stars_paid > 0)
    if user_id is not None:
        q = q.filter(RunOpenRequest.user_id == user_id)
    rows: list[StarOrderRow] = []
    for r in q.order_by(desc(RunOpenRequest.created_at)).limit(200 if user_id else 500).all():
        refunded = bool(r.stars_refunded)
        cb = None
        hint = ""
        if not refunded:
            if match_payment_to_request(db, r.user_id, "run_open", r.stars_paid, r.created_at):
                cb = f"adm:oref:run_open:{r.id}"
            else:
                cb = f"adm:ocharge:run_open:{r.id}"
                hint = " (بدون سجل دفع — يحتاج charge id)"
        rows.append(
            StarOrderRow(
                sort_at=r.created_at,
                key=f"ro:{r.id}",
                title=f"جائزة أسبوعية #{r.id}",
                stars=r.stars_paid,
                user_telegram_id=r.user.telegram_id,
                username=r.user.username,
                refunded=refunded,
                callback_data=cb,
                hint=hint,
            )
        )
    return rows


def _legacy_play_pass_rows(db: Session, user_id: int | None) -> list[StarOrderRow]:
    q = db.query(PlayPassRequest).filter(PlayPassRequest.stars_paid > 0)
    if user_id is not None:
        q = q.filter(PlayPassRequest.user_id == user_id)
    rows: list[StarOrderRow] = []
    for r in q.order_by(desc(PlayPassRequest.created_at)).limit(200 if user_id else 500).all():
        refunded = bool(r.stars_refunded)
        cb = None
        hint = ""
        if not refunded:
            if match_payment_to_request(db, r.user_id, "play_pass", r.stars_paid, r.created_at):
                cb = f"adm:oref:play_pass:{r.id}"
            else:
                cb = f"adm:ocharge:play_pass:{r.id}"
                hint = " (بدون سجل دفع — يحتاج charge id)"
        rows.append(
            StarOrderRow(
                sort_at=r.created_at,
                key=f"pp:{r.id}",
                title=f"Play Pass #{r.id}",
                stars=r.stars_paid,
                user_telegram_id=r.user.telegram_id,
                username=r.user.username,
                refunded=refunded,
                callback_data=cb,
                hint=hint,
            )
        )
    return rows


def _payment_rows(db: Session, user_id: int | None) -> list[StarOrderRow]:
    q = db.query(StarPayment).order_by(desc(StarPayment.created_at))
    if user_id is not None:
        q = q.filter(StarPayment.user_id == user_id)
    rows: list[StarOrderRow] = []
    for p in q.limit(200 if user_id else 500).all():
        user = p.user
        label = payment_kind_label(p.payment_kind, "ar")
        cb = None if p.refunded else f"adm:srefund:{p.id}"
        rows.append(
            StarOrderRow(
                sort_at=p.created_at,
                key=f"sp:{p.id}",
                title=f"سجل دفع #{p.id} ({label})",
                stars=p.stars_amount,
                user_telegram_id=user.telegram_id if user else 0,
                username=user.username if user else None,
                refunded=bool(p.refunded),
                callback_data=cb,
            )
        )
    return rows


def collect_star_order_rows(db: Session, user_id: int | None = None) -> list[StarOrderRow]:
    merged = _payment_rows(db, user_id) + _legacy_run_open_rows(db, user_id) + _legacy_play_pass_rows(
        db, user_id
    )
    merged.sort(key=lambda x: x.sort_at, reverse=True)
    return merged


def paginate_star_orders(
    db: Session, page: int, per_page: int = 6, user_id: int | None = None
) -> tuple[list[StarOrderRow], int, int]:
    all_rows = collect_star_order_rows(db, user_id)
    total = len(all_rows)
    pages = max(1, (total + per_page - 1) // per_page)
    page = max(0, min(page, pages - 1))
    start = page * per_page
    return all_rows[start : start + per_page], page, pages


def get_request_for_refund(db: Session, kind: str, req_id: int):
    if kind == "run_open":
        return db.query(RunOpenRequest).filter_by(id=req_id).first()
    if kind == "play_pass":
        return db.query(PlayPassRequest).filter_by(id=req_id).first()
    return None


def mark_request_stars_refunded(db: Session, kind: str, req_id: int) -> None:
    req = get_request_for_refund(db, kind, req_id)
    if req:
        req.stars_refunded = True
        db.commit()
