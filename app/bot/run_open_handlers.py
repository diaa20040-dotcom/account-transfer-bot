from aiogram import Bot, F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import LabeledPrice, Message

from app.bot.keyboards import main_menu
from app.bot.states import RunOpenStates
from app.database import RunOpenRequest, SessionLocal, User, get_setting
from app.i18n import t
from app.services.admin_access import is_admin
from app.services.notify_admins import notify_admins
from app.services.users import get_or_create_user

router = Router()


def run_open_stars_amount(db) -> int:
    try:
        return max(1, int(get_setting(db, "run_open_stars", "10")))
    except ValueError:
        return 10


async def send_run_open_invoice(bot: Bot, chat_id: int, lang: str, user_db_id: int, stars: int) -> None:
    await bot.send_invoice(
        chat_id=chat_id,
        title=t(lang, "run_open_invoice_title"),
        description=t(lang, "run_open_invoice_desc", stars=stars),
        payload=f"runopen:{user_db_id}:{stars}",
        provider_token="",
        currency="XTR",
        prices=[LabeledPrice(label=t(lang, "run_open_price_label", stars=stars), amount=stars)],
    )


@router.message(F.text.in_({t("ar", "btn_run_open"), t("en", "btn_run_open")}))
async def run_open_start(message: Message, state: FSMContext, bot: Bot) -> None:
    await state.clear()
    db = SessionLocal()
    try:
        user, _ = get_or_create_user(
            db, message.from_user.id, message.from_user.username, message.from_user.first_name
        )
        lang = user.language
        stars = run_open_stars_amount(db)
        await send_run_open_invoice(bot, message.chat.id, lang, user.id, stars)
    finally:
        db.close()


@router.message(RunOpenStates.entering_name, F.text)
async def run_open_name(message: Message, state: FSMContext) -> None:
    if message.text.startswith("/"):
        return
    await state.update_data(account_name=message.text.strip())
    db = SessionLocal()
    try:
        user = db.query(User).filter_by(telegram_id=message.from_user.id).first()
        lang = user.language if user else "ar"
    finally:
        db.close()
    await state.set_state(RunOpenStates.entering_password)
    await message.answer(t(lang, "enter_password"))


@router.message(RunOpenStates.entering_password, F.text)
async def run_open_password(message: Message, state: FSMContext, bot: Bot) -> None:
    if message.text.startswith("/"):
        return
    data = await state.get_data()
    if not data.get("run_open_paid"):
        db = SessionLocal()
        try:
            user = db.query(User).filter_by(telegram_id=message.from_user.id).first()
            lang = user.language if user else "ar"
        finally:
            db.close()
        await state.clear()
        await message.answer(t(lang, "run_open_pay_first"))
        return

    password = message.text.strip()
    stars = int(data.get("stars_paid", 10))
    db = SessionLocal()
    try:
        user, _ = get_or_create_user(
            db, message.from_user.id, message.from_user.username, message.from_user.first_name
        )
        lang = user.language
        req = RunOpenRequest(
            user_id=user.id,
            account_name=data["account_name"],
            account_password=password,
            stars_paid=stars,
            status="pending",
        )
        db.add(req)
        db.commit()
        from app.services.snapshot_hook import snapshot_db

        snapshot_db()
        db.refresh(req)

        admin_text = (
            f"🔓 فتح نقاط تشغيل #{req.id}\n"
            f"المستخدم: {user.telegram_id} @{user.username or '—'}\n"
            f"النجوم المدفوعة: {stars}\n"
            f"الحساب: {req.account_name}\n"
            f"كلمة المرور: {req.account_password}\n"
            f"الحالة: pending"
        )
        await notify_admins(bot, admin_text)

        adm = is_admin(message.from_user.id, message.from_user.username)
        await message.answer(
            t(lang, "run_open_submitted"),
            reply_markup=main_menu(lang, adm),
        )
    finally:
        db.close()
    await state.clear()
