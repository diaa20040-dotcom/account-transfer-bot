from aiogram import Bot, F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, LabeledPrice, Message

from app.bot.keyboards import main_menu
from app.bot.play_pass_keyboards import play_pass_pay_keyboard
from app.bot.states import PlayPassStates
from app.database import PlayPassRequest, SessionLocal, User, get_setting
from app.i18n import t
from app.services.admin_access import is_admin
from app.services.notify_admins import notify_admins
from app.services.play_pass import (
    play_pass_accepts_new,
    play_pass_max_slots,
    play_pass_slots_remaining,
    play_pass_slots_used,
)
from app.services.users import get_or_create_user

router = Router()

DEFAULT_PLAY_PASS_POINTS = 40
DEFAULT_PLAY_PASS_STARS = 20


def play_pass_points_cost(db) -> int:
    try:
        return max(1, int(get_setting(db, "play_pass_points", str(DEFAULT_PLAY_PASS_POINTS))))
    except ValueError:
        return DEFAULT_PLAY_PASS_POINTS


def play_pass_stars_cost(db) -> int:
    try:
        return max(1, int(get_setting(db, "play_pass_stars", str(DEFAULT_PLAY_PASS_STARS))))
    except ValueError:
        return DEFAULT_PLAY_PASS_STARS


def _play_pass_menu_text(db, lang: str, pts: int, stars: int) -> str:
    cap = play_pass_max_slots(db)
    if cap > 0:
        rem = play_pass_slots_remaining(db) or 0
        return t(
            lang,
            "play_pass_choose_pay_slots",
            points=pts,
            stars=stars,
            remaining=rem,
            max=cap,
        )
    return t(lang, "play_pass_choose_pay", points=pts, stars=stars)


async def send_play_pass_invoice(
    bot: Bot, chat_id: int, lang: str, user_db_id: int, stars: int
) -> None:
    await bot.send_invoice(
        chat_id=chat_id,
        title=t(lang, "play_pass_invoice_title"),
        description=t(lang, "play_pass_invoice_desc", stars=stars),
        payload=f"playpass:{user_db_id}:{stars}",
        provider_token="",
        currency="XTR",
        prices=[LabeledPrice(label=t(lang, "play_pass_price_label", stars=stars), amount=stars)],
    )


@router.message(F.text.in_({t("ar", "btn_play_pass"), t("en", "btn_play_pass")}))
async def play_pass_menu(message: Message, state: FSMContext) -> None:
    await state.clear()
    db = SessionLocal()
    try:
        user, _ = get_or_create_user(
            db, message.from_user.id, message.from_user.username, message.from_user.first_name
        )
        lang = user.language
        if not play_pass_accepts_new(db):
            cap = play_pass_max_slots(db)
            used = play_pass_slots_used(db)
            await message.answer(t(lang, "play_pass_full", used=used, max=cap))
            return
        pts = play_pass_points_cost(db)
        stars = play_pass_stars_cost(db)
        await message.answer(
            _play_pass_menu_text(db, lang, pts, stars),
            reply_markup=play_pass_pay_keyboard(lang, pts, stars),
        )
    finally:
        db.close()


@router.callback_query(F.data == "pp:cancel")
async def play_pass_cancel(callback: CallbackQuery, state: FSMContext) -> None:
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


@router.callback_query(F.data == "pp:points")
async def play_pass_pay_points(callback: CallbackQuery, state: FSMContext) -> None:
    db = SessionLocal()
    try:
        user, _ = get_or_create_user(
            db,
            callback.from_user.id,
            callback.from_user.username,
            callback.from_user.first_name,
        )
        lang = user.language
        if not play_pass_accepts_new(db):
            cap = play_pass_max_slots(db)
            await callback.answer(
                t(lang, "play_pass_full", used=play_pass_slots_used(db), max=cap),
                show_alert=True,
            )
            return
        cost = play_pass_points_cost(db)
        if user.points < cost:
            await callback.answer(
                t(lang, "need_points", cost=cost, have=user.points),
                show_alert=True,
            )
            return
        await state.update_data(
            play_pass_payment="points",
            play_pass_points=cost,
            play_pass_stars=0,
        )
        await state.set_state(PlayPassStates.entering_name)
        try:
            await callback.message.edit_reply_markup(reply_markup=None)
        except Exception:
            pass
        await callback.message.answer(t(lang, "play_pass_enter_name"))
        await callback.answer()
    finally:
        db.close()


@router.callback_query(F.data == "pp:stars")
async def play_pass_pay_stars(callback: CallbackQuery, state: FSMContext, bot: Bot) -> None:
    db = SessionLocal()
    try:
        user, _ = get_or_create_user(
            db,
            callback.from_user.id,
            callback.from_user.username,
            callback.from_user.first_name,
        )
        lang = user.language
        if not play_pass_accepts_new(db):
            cap = play_pass_max_slots(db)
            await callback.answer(
                t(lang, "play_pass_full", used=play_pass_slots_used(db), max=cap),
                show_alert=True,
            )
            return
        stars = play_pass_stars_cost(db)
        await send_play_pass_invoice(bot, callback.message.chat.id, lang, user.id, stars)
        await callback.answer()
    finally:
        db.close()


@router.message(PlayPassStates.entering_name, F.text)
async def play_pass_name(message: Message, state: FSMContext) -> None:
    if message.text.startswith("/"):
        return
    await state.update_data(account_name=message.text.strip())
    db = SessionLocal()
    try:
        user = db.query(User).filter_by(telegram_id=message.from_user.id).first()
        lang = user.language if user else "ar"
    finally:
        db.close()
    await state.set_state(PlayPassStates.entering_password)
    await message.answer(t(lang, "enter_password"))


@router.message(PlayPassStates.entering_password, F.text)
async def play_pass_password(message: Message, state: FSMContext, bot: Bot) -> None:
    if message.text.startswith("/"):
        return
    data = await state.get_data()
    payment = data.get("play_pass_payment")
    if payment == "stars" and not data.get("play_pass_paid"):
        db = SessionLocal()
        try:
            user = db.query(User).filter_by(telegram_id=message.from_user.id).first()
            lang = user.language if user else "ar"
        finally:
            db.close()
        await state.clear()
        await message.answer(t(lang, "play_pass_pay_first"))
        return

    password = message.text.strip()
    db = SessionLocal()
    try:
        user, _ = get_or_create_user(
            db, message.from_user.id, message.from_user.username, message.from_user.first_name
        )
        lang = user.language
        if not play_pass_accepts_new(db):
            cap = play_pass_max_slots(db)
            if payment == "stars":
                await message.answer(t(lang, "play_pass_paid_but_full"))
            else:
                await message.answer(
                    t(lang, "play_pass_full", used=play_pass_slots_used(db), max=cap)
                )
            await state.clear()
            return
        points_paid = 0
        stars_paid = 0
        if payment == "points":
            cost = int(data.get("play_pass_points", play_pass_points_cost(db)))
            if user.points < cost:
                await message.answer(t(lang, "need_points", cost=cost, have=user.points))
                await state.clear()
                return
            user.points -= cost
            points_paid = cost
        else:
            stars_paid = int(data.get("play_pass_stars", play_pass_stars_cost(db)))

        req = PlayPassRequest(
            user_id=user.id,
            account_name=data["account_name"],
            account_password=password,
            points_paid=points_paid,
            stars_paid=stars_paid,
            payment_method=payment or "stars",
            status="pending",
        )
        db.add(req)
        db.commit()
        from app.services.snapshot_hook import snapshot_db

        snapshot_db()
        db.refresh(req)

        pay_line = (
            f"النقاط: {points_paid}" if points_paid else f"النجوم: {stars_paid}"
        )
        admin_text = (
            f"👨‍👩‍👧 انضمام Play Pass #{req.id}\n"
            f"المستخدم: {user.telegram_id} @{user.username or '—'}\n"
            f"الدفع: {pay_line}\n"
            f"الحساب: {req.account_name}\n"
            f"كلمة المرور: {req.account_password}\n"
            f"الحالة: pending"
        )
        await notify_admins(bot, admin_text)

        adm = is_admin(message.from_user.id, message.from_user.username)
        await message.answer(
            t(lang, "play_pass_submitted"),
            reply_markup=main_menu(lang, adm),
        )
    finally:
        db.close()
    await state.clear()
