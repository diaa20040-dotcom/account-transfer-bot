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
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    referred_by: Mapped["User | None"] = relationship(remote_side=[id])
    transfers: Mapped[list["TransferRequest"]] = relationship(back_populates="user")


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


class AppSetting(Base):
    __tablename__ = "app_settings"

    key: Mapped[str] = mapped_column(String(64), primary_key=True)
    value: Mapped[str] = mapped_column(Text)


DEFAULT_COUNTRIES = [
    ("امريكا", "America", 100, 1),
    ("ياباني", "Japan", 100, 2),
]


def sync_default_countries(db) -> None:
    """Replace all countries with the configured default list."""
    db.query(TransferRequest).delete()
    db.query(Country).delete()
    for ar, en, cost, order in DEFAULT_COUNTRIES:
        db.add(
            Country(name_ar=ar, name_en=en, point_cost=cost, sort_order=order, active=True)
        )
    db.commit()


def init_db() -> None:
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    try:
        if db.query(Country).count() == 0:
            sync_default_countries(db)
        if db.query(AppSetting).filter_by(key="referral_points").first() is None:
            db.add(AppSetting(key="referral_points", value="25"))
        db.commit()
        from app.services.admin_access import load_persisted_admins

        load_persisted_admins(db)
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
