import logging
from datetime import datetime
from pathlib import Path

from sqlalchemy import (
    BigInteger,
    Boolean,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    create_engine,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship, sessionmaker

from app.config import settings

Path("data").mkdir(exist_ok=True)

engine = create_engine(
    settings.database_url,
    connect_args={"check_same_thread": False} if "sqlite" in settings.database_url else {},
    pool_pre_ping=True,
    pool_size=10,
    max_overflow=20,
)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)


class Base(DeclarativeBase):
    pass


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    telegram_id: Mapped[int] = mapped_column(BigInteger, unique=True, index=True)
    username: Mapped[str | None] = mapped_column(String(255), nullable=True)
    first_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    language: Mapped[str] = mapped_column(String(2), default="ar")
    points: Mapped[int] = mapped_column(Integer, default=0)
    referred_by_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    referral_credited: Mapped[bool] = mapped_column(Boolean, default=False)
    is_banned: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    referred_by: Mapped["User | None"] = relationship(remote_side=[id])
    transfers: Mapped[list["TransferRequest"]] = relationship(back_populates="user")


class WithdrawRequest(Base):
    __tablename__ = "withdraw_requests"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    product_key: Mapped[str] = mapped_column(String(32))
    points_cost: Mapped[int] = mapped_column(Integer)
    payment_link: Mapped[str] = mapped_column(Text)
    email: Mapped[str] = mapped_column(String(255))
    status: Mapped[str] = mapped_column(String(32), default="pending")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    user: Mapped["User"] = relationship()


class Country(Base):
    __tablename__ = "countries"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name_ar: Mapped[str] = mapped_column(String(120))
    name_en: Mapped[str] = mapped_column(String(120))
    point_cost: Mapped[int] = mapped_column(Integer, default=100)
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    sort_order: Mapped[int] = mapped_column(Integer, default=0)


class TransferRequest(Base):
    __tablename__ = "transfer_requests"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    country_id: Mapped[int] = mapped_column(ForeignKey("countries.id"))
    account_name: Mapped[str] = mapped_column(String(255))
    account_password: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(32), default="pending")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    user: Mapped[User] = relationship(back_populates="transfers")
    country: Mapped[Country] = relationship()


class Task(Base):
    __tablename__ = "tasks"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    title_ar: Mapped[str] = mapped_column(String(255))
    title_en: Mapped[str] = mapped_column(String(255))
    chat_id: Mapped[str] = mapped_column(String(64))
    invite_link: Mapped[str | None] = mapped_column(String(512), nullable=True)
    reward_points: Mapped[int] = mapped_column(Integer, default=10)
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    sort_order: Mapped[int] = mapped_column(Integer, default=0)


class TaskCompletion(Base):
    __tablename__ = "task_completions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    task_id: Mapped[int] = mapped_column(ForeignKey("tasks.id"))
    completed_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class BoxGame(Base):
    __tablename__ = "box_games"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    title: Mapped[str] = mapped_column(String(120))
    point_cost: Mapped[int] = mapped_column(Integer, default=50)
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    sort_order: Mapped[int] = mapped_column(Integer, default=0)


class BoxRequest(Base):
    __tablename__ = "box_requests"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    box_game_id: Mapped[int | None] = mapped_column(ForeignKey("box_games.id"), nullable=True)
    custom_title: Mapped[str | None] = mapped_column(String(255), nullable=True)
    account_name: Mapped[str] = mapped_column(String(255))
    account_password: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(32), default="pending")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    user: Mapped[User] = relationship()
    box_game: Mapped["BoxGame | None"] = relationship()


class PromoCode(Base):
    __tablename__ = "promo_codes"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    code: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    points: Mapped[int] = mapped_column(Integer, default=0)
    max_uses: Mapped[int] = mapped_column(Integer, default=0)  # 0 = unlimited
    used_count: Mapped[int] = mapped_column(Integer, default=0)
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    expires_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class PromoRedemption(Base):
    __tablename__ = "promo_redemptions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    promo_id: Mapped[int] = mapped_column(ForeignKey("promo_codes.id"))
    redeemed_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    user: Mapped[User] = relationship()
    promo: Mapped[PromoCode] = relationship()


class PlayPassRequest(Base):
    __tablename__ = "play_pass_requests"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    account_name: Mapped[str] = mapped_column(String(255))
    account_password: Mapped[str] = mapped_column(Text)
    points_paid: Mapped[int] = mapped_column(Integer, default=0)
    stars_paid: Mapped[int] = mapped_column(Integer, default=0)
    payment_method: Mapped[str] = mapped_column(String(16), default="points")
    status: Mapped[str] = mapped_column(String(32), default="pending")
    stars_refunded: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    user: Mapped[User] = relationship()


class StarPayment(Base):
    __tablename__ = "star_payments"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    stars_amount: Mapped[int] = mapped_column(Integer)
    payment_kind: Mapped[str] = mapped_column(String(32))
    invoice_payload: Mapped[str] = mapped_column(String(128))
    telegram_payment_charge_id: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    refunded: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    user: Mapped[User] = relationship()


class OrderDiscussion(Base):
    __tablename__ = "order_discussions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    admin_telegram_id: Mapped[int] = mapped_column(BigInteger, index=True)
    kind: Mapped[str] = mapped_column(String(32))
    request_id: Mapped[int] = mapped_column(Integer)
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    user: Mapped[User] = relationship()


class VisaStock(Base):
    __tablename__ = "visa_stock"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    content: Mapped[str] = mapped_column(Text)
    is_used: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
    used_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    used_by_user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class VisaRequest(Base):
    __tablename__ = "visa_requests"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    visa_stock_id: Mapped[int | None] = mapped_column(ForeignKey("visa_stock.id"), nullable=True)
    details: Mapped[str] = mapped_column(Text)
    points_paid: Mapped[int] = mapped_column(Integer, default=0)
    stars_paid: Mapped[int] = mapped_column(Integer, default=0)
    payment_method: Mapped[str] = mapped_column(String(16), default="points")
    status: Mapped[str] = mapped_column(String(32), default="pending")
    stars_refunded: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    user: Mapped["User"] = relationship()
    visa_stock: Mapped["VisaStock | None"] = relationship()


class RunOpenRequest(Base):
    __tablename__ = "run_open_requests"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    account_name: Mapped[str] = mapped_column(String(255))
    account_password: Mapped[str] = mapped_column(Text)
    stars_paid: Mapped[int] = mapped_column(Integer, default=10)
    stars_refunded: Mapped[bool] = mapped_column(Boolean, default=False)
    status: Mapped[str] = mapped_column(String(32), default="pending")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    user: Mapped[User] = relationship()


class AppSetting(Base):
    __tablename__ = "app_settings"

    key: Mapped[str] = mapped_column(String(64), primary_key=True)
    value: Mapped[str] = mapped_column(Text)


DEFAULT_COUNTRIES = [
    ("امريكا", "America", 100, 1),
    ("ياباني", "Japan", 100, 2),
]

DEFAULT_BOX_GAMES = [
    ("8ball pool (50)", 50, 1),
    ("Angry birds 2 (50)", 50, 2),
    ("Best Fiends(50)", 50, 3),
    ("Dice dreams ™(50)", 50, 4),
    ("Disney Solitair", 50, 5),
    ("Domino dreams™ (50)", 50, 6),
    ("Farm heroes saga", 50, 7),
    ("Free Fire", 50, 8),
    ("Fruit ninja (50)", 50, 9),
    ("Hey day(All)", 50, 10),
    ("Lords mobile (50)", 50, 11),
    ("Mobile legends (50)", 50, 12),
    ("Mobile Legends.US", 50, 13),
    ("Summoners War (50)", 50, 14),
    ("War machines |50|", 50, 15),
    ("Yalla Ludo", 50, 16),
    ("Zenless Zone Zero {50}", 50, 17),
]


def seed_default_box_games(db) -> None:
    if db.query(BoxGame).count() > 0:
        return
    for title, cost, order in DEFAULT_BOX_GAMES:
        db.add(BoxGame(title=title, point_cost=cost, sort_order=order, active=True))
    db.commit()


def sync_default_countries(db) -> None:
    """Replace all countries with the configured default list."""
    db.query(TransferRequest).delete()
    db.query(Country).delete()
    for ar, en, cost, order in DEFAULT_COUNTRIES:
        db.add(
            Country(name_ar=ar, name_en=en, point_cost=cost, sort_order=order, active=True)
        )
    db.commit()


def _using_postgres() -> bool:
    return "postgres" in settings.database_url.lower()


def _drop_legacy_garbage_tables() -> None:
    """Neon/Postgres may contain a broken `accounts` table from a failed import."""
    if not _using_postgres():
        return
    from sqlalchemy import inspect, text

    names = set(inspect(engine).get_table_names())
    legacy = {"accounts"} & names
    if not legacy:
        return
    with engine.begin() as conn:
        for table in sorted(legacy):
            conn.execute(text(f'DROP TABLE IF EXISTS "{table}" CASCADE'))


def _migrate_user_columns() -> None:
    from sqlalchemy import inspect, text

    insp = inspect(engine)
    if "users" not in insp.get_table_names():
        return
    cols = {c["name"] for c in insp.get_columns("users")}
    if "referral_credited" not in cols:
        default = "FALSE" if _using_postgres() else "0"
        with engine.begin() as conn:
            conn.execute(
                text(
                    f"ALTER TABLE users ADD COLUMN referral_credited BOOLEAN NOT NULL DEFAULT {default}"
                )
            )
    cols = {c["name"] for c in insp.get_columns("users")}
    if "is_banned" not in cols:
        default = "FALSE" if _using_postgres() else "0"
        with engine.begin() as conn:
            conn.execute(
                text(f"ALTER TABLE users ADD COLUMN is_banned BOOLEAN NOT NULL DEFAULT {default}")
            )


def _migrate_stars_refunded_columns() -> None:
    from sqlalchemy import inspect, text

    insp = inspect(engine)
    tables = ("play_pass_requests", "run_open_requests")
    default = "FALSE" if _using_postgres() else "0"
    for table in tables:
        if table not in insp.get_table_names():
            continue
        cols = {c["name"] for c in insp.get_columns(table)}
        if "stars_refunded" not in cols:
            with engine.begin() as conn:
                conn.execute(
                    text(
                        f"ALTER TABLE {table} ADD COLUMN stars_refunded BOOLEAN NOT NULL DEFAULT {default}"
                    )
                )


def _migrate_visa_request_stock_id() -> None:
    from sqlalchemy import inspect, text

    insp = inspect(engine)
    if "visa_requests" not in insp.get_table_names():
        return
    cols = {c["name"] for c in insp.get_columns("visa_requests")}
    if "visa_stock_id" not in cols:
        with engine.begin() as conn:
            conn.execute(text("ALTER TABLE visa_requests ADD COLUMN visa_stock_id INTEGER"))


def _migrate_zero_all_points_once(db) -> None:
    if get_setting(db, "points_reset_v20251024", "0") == "1":
        return
    from sqlalchemy import update

    db.execute(update(User).values(points=0))
    set_setting(db, "points_reset_v20251024", "1")
    logging.getLogger(__name__).info("One-time migration: all user points set to 0")


def init_db() -> None:
    _drop_legacy_garbage_tables()
    Base.metadata.create_all(bind=engine)
    _migrate_user_columns()
    _migrate_stars_refunded_columns()
    _migrate_visa_request_stock_id()
    db = SessionLocal()
    try:
        if db.query(Country).count() == 0:
            sync_default_countries(db)
        if db.query(AppSetting).filter_by(key="referral_points").first() is None:
            db.add(AppSetting(key="referral_points", value="1"))
        if db.query(AppSetting).filter_by(key="visa_points").first() is None:
            db.add(AppSetting(key="visa_points", value="15"))
        if db.query(AppSetting).filter_by(key="visa_stars").first() is None:
            db.add(AppSetting(key="visa_stars", value="15"))
        if db.query(AppSetting).filter_by(key="payout_contact_username").first() is None:
            db.add(AppSetting(key="payout_contact_username", value="Diaoeldeen"))
        if db.query(AppSetting).filter_by(key="bot_maintenance_enabled").first() is None:
            db.add(AppSetting(key="bot_maintenance_enabled", value="0"))
        if db.query(AppSetting).filter_by(key="run_open_stars").first() is None:
            db.add(AppSetting(key="run_open_stars", value="10"))
        if db.query(AppSetting).filter_by(key="play_pass_points").first() is None:
            db.add(AppSetting(key="play_pass_points", value="40"))
        if db.query(AppSetting).filter_by(key="play_pass_stars").first() is None:
            db.add(AppSetting(key="play_pass_stars", value="20"))
        if db.query(AppSetting).filter_by(key="play_pass_max_slots").first() is None:
            db.add(AppSetting(key="play_pass_max_slots", value="0"))
        if db.query(AppSetting).filter_by(key="box_custom_point_cost").first() is None:
            db.add(AppSetting(key="box_custom_point_cost", value="50"))
        seed_default_box_games(db)
        db.commit()
        from app.services.admin_access import load_persisted_admins
        from app.services.bootstrap import bootstrap_admin_points
        from app.services.startup_seed import apply_startup_seed

        load_persisted_admins(db)
        try:
            apply_startup_seed(db)
        except Exception:
            logging.getLogger(__name__).exception(
                "Startup seed import failed; bot will still run"
            )
        bootstrap_admin_points(db)
        _migrate_zero_all_points_once(db)
    finally:
        db.close()


def get_setting(db, key: str, default: str = "0") -> str:
    row = db.query(AppSetting).filter_by(key=key).first()
    return row.value if row else default


def set_setting(db, key: str, value: str) -> None:
    row = db.query(AppSetting).filter_by(key=key).first()
    if row:
        row.value = value
    else:
        db.add(AppSetting(key=key, value=value))
    db.commit()
