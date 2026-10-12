from sqlalchemy.orm import Session

from app.database import (
    BoxRequest,
    OrderDiscussion,
    PlayPassRequest,
    RunOpenRequest,
    TransferRequest,
    User,
)

ORDER_KINDS = frozenset({"transfer", "box", "run_open", "play_pass"})

_KIND_LABEL_AR = {
    "transfer": "تحويل",
    "box": "صندوق",
    "run_open": "جائزة أسبوعية",
    "play_pass": "Play Pass",
}

_KIND_LABEL_EN = {
    "transfer": "transfer",
    "box": "box",
    "run_open": "weekly reward",
    "play_pass": "Play Pass",
}


def order_kind_label(kind: str, lang: str) -> str:
    lang = lang if lang in ("ar", "en") else "ar"
    if lang == "ar":
        return _KIND_LABEL_AR.get(kind, kind)
    return _KIND_LABEL_EN.get(kind, kind)


def load_order(db: Session, kind: str, request_id: int):
    if kind == "transfer":
        return db.query(TransferRequest).filter_by(id=request_id).first()
    if kind == "box":
        return db.query(BoxRequest).filter_by(id=request_id).first()
    if kind == "run_open":
        return db.query(RunOpenRequest).filter_by(id=request_id).first()
    if kind == "play_pass":
        return db.query(PlayPassRequest).filter_by(id=request_id).first()
    return None


def order_user(order) -> User | None:
    if order is None:
        return None
    return getattr(order, "user", None)


def close_threads_for_user(db: Session, user_id: int) -> None:
    db.query(OrderDiscussion).filter_by(user_id=user_id, active=True).update(
        {"active": False}, synchronize_session=False
    )


def open_discussion(
    db: Session, user_id: int, admin_telegram_id: int, kind: str, request_id: int
) -> OrderDiscussion:
    close_threads_for_user(db, user_id)
    thread = OrderDiscussion(
        user_id=user_id,
        admin_telegram_id=admin_telegram_id,
        kind=kind,
        request_id=request_id,
        active=True,
    )
    db.add(thread)
    db.commit()
    db.refresh(thread)
    return thread


def get_active_thread_for_user(db: Session, user_id: int) -> OrderDiscussion | None:
    return (
        db.query(OrderDiscussion)
        .filter_by(user_id=user_id, active=True)
        .order_by(OrderDiscussion.id.desc())
        .first()
    )


def get_thread_by_id(db: Session, thread_id: int) -> OrderDiscussion | None:
    return db.query(OrderDiscussion).filter_by(id=thread_id).first()


def close_thread(db: Session, thread: OrderDiscussion) -> None:
    thread.active = False
    db.commit()
