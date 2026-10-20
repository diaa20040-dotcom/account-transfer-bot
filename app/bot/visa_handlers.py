from aiogram import Bot, F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, LabeledPrice, Message

from app.bot.keyboards import main_menu
from app.bot.states import VisaStates
from app.bot.visa_keyboards import visa_pay_keyboard
from app.database import SessionLocal, User, VisaRequest, get_setting
from app.i18n import t
from app.services.admin_access import is_admin
from app.services.notify_admins import notify_admins
from app.services.users import get_or_create_user

router = Router()

DEFAULT_VISA_POINTS = 15
DEFAULT_VISA_STARS = 15


def visa_points_cost(db) -> int:
    try:
        return max(1, int(get_setting(db, "visa_points", str(DEFAULT_VISA_POINTS))))
    except ValueError:
        return DEFAULT_VISA_POINTS


def visa_stars_cost(db) -> int:
    try:
        return max(1, int(get_setting(db, "visa_stars", str(DEFAULT_VISA_STARS))))
    except ValueError:
        return DEFAULT_VISA_STARS


async def send_visa_invoice(bot: Bot, chat_id: int, lang: str, user_db_id: int, stars: int) -> None:
    await bot.send_invoice(
        chat_id=chat_id,
        title=t(lang, "visa_invoice_title"),
        description=t(lang, "visa_invoice_desc", stars=stars),
        payload=f"visa:{user_db_id}:{stars}",
        provider_token="",
        currency="XTR",
        prices=[LabeledPrice(label=t(lang, "visa_price_label", stars=stars), amount=stars)],
    )


@router.message(F.text.in_({t("ar", "btn_visa"), t("en", "btn_visa")}))
async def visa_menu(message: Message, state: FSMContext) -> None:
    await state.clear()
    db = SessionLocal()
    try:
        user, _ = get_or_create_user(
            db, message.from_user.id, message.from_user.username, message.from_user.first_name
        )
        lang = user.language
        pts = visa_points_cost(db)
        stars = visa_stars_cost(db)
        await message.answer(
            t(lang, "visa_choose_pay", points=pts, stars=stars),
            reply_markup=visa_pay_keyboard(lang, pts, stars),
        )
    finally:
        db.close()


@router.callback_query(F.data == "visa:cancel")
async def visa_cancel(callback: CallbackQuery, state: FSMContext) -> None:
    db = SessionLocal()
    try:
        user = db.query(User).filter_by(telegram_id=callback.from_user.id).first()
        lang = user.language if user else "ar"
        adm = is_admin(callback.from_user.id, callback.from_user.username)
    finally:
        db.close()
    await state.clear()
    try:
        await callback.message.edit_reply_markup(reply_markup=None)
    except Exception:
        pass
    await callback.message.answer(t(lang, "cancelled"), reply_markup=main_menu(lang, adm))
    await callback.answer()


@router.callback_query(F.data == "visa:points")
async def visa_pay_points(callback: CallbackQuery, state: FSMContext) -> None:
    db = SessionLocal()
    try:
        user, _ = get_or_create_user(
            db,
            callback.from_user.id,
            callback.from_user.username,
            callback.from_user.first_name,
        )
        lang = user.language
        cost = visa_points_cost(db)
        if user.points < cost:
            await callback.answer(
                t(lang, "visa_need_points", cost=cost, have=user.points),
                show_alert=True,
            )
            return
        user.points -= cost
        db.commit()
        from app.services.snapshot_hook import snapshot_db

        snapshot_db()
    finally:
        db.close()
    await state.update_data(
        visa_paid=True,
        visa_payment="points",
        visa_points=cost,
        visa_stars=0,
    )
    await state.set_state(VisaStates.entering_details)
    try:
        await callback.message.edit_reply_markup(reply_markup=None)
    except Exception:
        pass
    await callback.message.answer(t(lang, "visa_enter_details", cost=cost))
    await callback.answer()


@router.callback_query(F.data == "visa:stars")
async def visa_pay_stars(callback: CallbackQuery, state: FSMContext, bot: Bot) -> None:
    db = SessionLocal()
    try:
        user, _ = get_or_create_user(
            db,
            callback.from_user.id,
            callback.from_user.username,
            callback.from_user.first_name,
        )
        lang = user.language
        stars = visa_stars_cost(db)
        await send_visa_invoice(bot, callback.message.chat.id, lang, user.id, stars)
    finally:
        db.close()
    await callback.answer()


@router.message(VisaStates.entering_details, F.text)
async def visa_submit_details(message: Message, state: FSMContext, bot: Bot) -> None:
    if message.text and message.text.startswith("/"):
        return
    data = await state.get_data()
    if not data.get("visa_paid"):
        db = SessionLocal()
        try:
            user = db.query(User).filter_by(telegram_id=message.from_user.id).first()
            lang = user.language if user else "ar"
        finally:
            db.close()
        await message.answer(t(lang, "visa_pay_first"))
        await state.clear()
        return

    details = (message.text or "").strip()
    if len(details) < 2:
        db = SessionLocal()
        try:
            user = db.query(User).filter_by(telegram_id=message.from_user.id).first()
            lang = user.language if user else "ar"
        finally:
            db.close()
        await message.answer(t(lang, "visa_details_short"))
        return

    db = SessionLocal()
    try:
        user, _ = get_or_create_user(
            db, message.from_user.id, message.from_user.username, message.from_user.first_name
        )
        lang = user.language
        payment = data.get("visa_payment", "points")
        pts = int(data.get("visa_points") or 0)
        stars = int(data.get("visa_stars") or 0)
        req = VisaRequest(
            user_id=user.id,
            details=details,
            points_paid=pts,
            stars_paid=stars,
            payment_method=payment,
            status="pending",
        )
        db.add(req)
        db.commit()
        from app.services.snapshot_hook import snapshot_db

        snapshot_db()
        db.refresh(req)

        pay_line = f"{pts} نقطة" if payment == "points" else f"{stars} نجمة"
        admin_text = (
            f"🆕 طلب فيزا #{req.id}\n"
            f"المستخدم: {user.telegram_id} @{user.username or '—'}\n"
            f"الدفع: {pay_line}\n"
            f"البيانات:\n{details}\n"
            f"الحالة: pending"
        )
        await notify_admins(bot, admin_text)

        adm = is_admin(message.from_user.id, message.from_user.username)
        await message.answer(t(lang, "visa_submitted"), reply_markup=main_menu(lang, adm))
    finally:
        db.close()
    await state.clear()
