from aiogram import Bot, F, Router
from aiogram.filters import Command, CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

from app.bot.keyboards import main_menu, withdraw_options_keyboard
from app.bot.states import TopUpStates, WithdrawStates
from app.bot.withdraw_products import (
    product_admin_field,
    product_cost,
    product_prompt_key,
    product_short_key,
    product_title,
)
from app.config import settings
from app.database import SessionLocal, User, WithdrawRequest, get_setting
from app.i18n import t
from app.services.notify_admins import notify_admins
from app.services.users import (
    get_or_create_user,
    referral_count,
    referral_pending_count,
    try_award_referral,
)

router = Router()

_STARS_MIN = 1
_STARS_MAX = 10_000


def _menu_texts() -> frozenset[str]:
    keys = ("btn_available", "btn_referral", "btn_points", "btn_topup")
    return frozenset(t(lang, k) for lang in ("ar", "en") for k in keys)


@router.message(CommandStart())
async def cmd_start(message: Message, state: FSMContext, bot: Bot) -> None:
    await state.clear()
    referrer_id = None
    if message.text and len(message.text.split()) > 1:
        arg = message.text.split(maxsplit=1)[1]
        if arg.startswith("ref_"):
            try:
                referrer_id = int(arg.replace("ref_", ""))
            except ValueError:
                referrer_id = None

    db = SessionLocal()
    try:
        user, _ = get_or_create_user(
            db,
            message.from_user.id,
            message.from_user.username,
            message.from_user.first_name,
            referrer_id,
        )
        await try_award_referral(db, bot, user)
        db.refresh(user)
        lang = user.language
        name = message.from_user.first_name or "User"
        await message.answer(
            t(lang, "welcome_main", name=name, points=user.points),
            reply_markup=main_menu(lang),
        )
    finally:
        db.close()


@router.message(Command("menu"))
async def cmd_menu(message: Message, state: FSMContext) -> None:
    await state.clear()
    db = SessionLocal()
    try:
        user, _ = get_or_create_user(
            db, message.from_user.id, message.from_user.username, message.from_user.first_name
        )
        await message.answer(t(user.language, "use_menu"), reply_markup=main_menu(user.language))
    finally:
        db.close()


@router.message(F.text.in_({t("ar", "btn_points"), t("en", "btn_points")}))
async def show_points(message: Message) -> None:
    db = SessionLocal()
    try:
        user, _ = get_or_create_user(
            db, message.from_user.id, message.from_user.username, message.from_user.first_name
        )
        await message.answer(t(user.language, "points_info", points=user.points))
    finally:
        db.close()


@router.message(F.text.in_({t("ar", "btn_referral"), t("en", "btn_referral")}))
async def show_referral(message: Message, bot: Bot) -> None:
    db = SessionLocal()
    try:
        user, _ = get_or_create_user(
            db, message.from_user.id, message.from_user.username, message.from_user.first_name
        )
        me = await bot.get_me()
        username = settings.bot_username or me.username or "bot"
        link = f"https://t.me/{username}?start=ref_{user.telegram_id}"
        ref_pts = int(get_setting(db, "referral_points", "1"))
        await message.answer(
            t(
                user.language,
                "referral_info_simple",
                link=link,
                points=ref_pts,
                count=referral_count(db, user),
                pending=referral_pending_count(db, user),
            )
        )
    finally:
        db.close()


@router.message(F.text.in_({t("ar", "btn_topup"), t("en", "btn_topup")}))
async def topup_start(message: Message, state: FSMContext) -> None:
    await state.clear()
    db = SessionLocal()
    try:
        user, _ = get_or_create_user(
            db, message.from_user.id, message.from_user.username, message.from_user.first_name
        )
        lang = user.language
    finally:
        db.close()
    await state.set_state(TopUpStates.waiting_amount)
    await message.answer(t(lang, "topup_enter_amount"))


@router.message(TopUpStates.waiting_amount, F.text)
async def topup_amount(message: Message, state: FSMContext, bot: Bot) -> None:
    if message.text and message.text.strip().lower() in ("/cancel", "/menu"):
        await state.clear()
        db = SessionLocal()
        try:
            user, _ = get_or_create_user(
                db,
                message.from_user.id,
                message.from_user.username,
                message.from_user.first_name,
            )
            await message.answer(
                t(user.language, "cancelled"), reply_markup=main_menu(user.language)
            )
        finally:
            db.close()
        return
    db = SessionLocal()
    try:
        user, _ = get_or_create_user(
            db, message.from_user.id, message.from_user.username, message.from_user.first_name
        )
        lang = user.language
        try:
            stars = int((message.text or "").strip())
        except ValueError:
            await message.answer(t(lang, "topup_invalid_amount"))
            return
        if stars < _STARS_MIN or stars > _STARS_MAX:
            await message.answer(t(lang, "topup_invalid_amount"))
            return
        from app.bot.payments_handlers import send_topup_invoice

        await send_topup_invoice(bot, message.chat.id, lang, user.id, stars)
    finally:
        db.close()
    await state.clear()


@router.message(F.text.in_({t("ar", "btn_available"), t("en", "btn_available")}))
async def available_menu(message: Message, state: FSMContext) -> None:
    await state.clear()
    db = SessionLocal()
    try:
        user, _ = get_or_create_user(
            db, message.from_user.id, message.from_user.username, message.from_user.first_name
        )
        lang = user.language
    finally:
        db.close()
    await message.answer(
        t(lang, "withdraw_choose"),
        reply_markup=withdraw_options_keyboard(lang),
    )


@router.callback_query(F.data == "wd:cancel")
async def withdraw_cancel(callback: CallbackQuery, state: FSMContext) -> None:
    await state.clear()
    db = SessionLocal()
    try:
        user = db.query(User).filter_by(telegram_id=callback.from_user.id).first()
        lang = user.language if user else "ar"
    finally:
        db.close()
    try:
        await callback.message.edit_reply_markup(reply_markup=None)
    except Exception:
        pass
    await callback.message.answer(t(lang, "cancelled"), reply_markup=main_menu(lang))
    await callback.answer()


@router.callback_query(F.data.startswith("wd:"))
async def withdraw_pick(callback: CallbackQuery, state: FSMContext) -> None:
    if callback.data == "wd:cancel":
        return
    key = callback.data.split(":", 1)[1]
    cost = product_cost(key)
    if cost <= 0:
        await callback.answer("—", show_alert=True)
        return
    db = SessionLocal()
    try:
        user, _ = get_or_create_user(
            db,
            callback.from_user.id,
            callback.from_user.username,
            callback.from_user.first_name,
        )
        lang = user.language
        if user.points < cost:
            await callback.answer(
                t(lang, "withdraw_need_points", cost=cost, have=user.points),
                show_alert=True,
            )
            return
    finally:
        db.close()
    await state.update_data(withdraw_product=key, withdraw_cost=cost)
    await state.set_state(WithdrawStates.payment_link)
    try:
        await callback.message.edit_reply_markup(reply_markup=None)
    except Exception:
        pass
    await callback.message.answer(
        t(
            lang,
            product_prompt_key(key),
            product=product_title(key, lang),
            cost=cost,
        )
    )
    await callback.answer()


@router.message(WithdrawStates.payment_link, F.text)
async def withdraw_got_link(message: Message, state: FSMContext) -> None:
    data = await state.get_data()
    product_key = data.get("withdraw_product") or ""
    link = (message.text or "").strip()
    if len(link) < 5:
        db = SessionLocal()
        try:
            user = db.query(User).filter_by(telegram_id=message.from_user.id).first()
            lang = user.language if user else "ar"
        finally:
            db.close()
        await message.answer(t(lang, product_short_key(product_key)))
        return
    await state.update_data(payment_link=link)
    db = SessionLocal()
    try:
        user = db.query(User).filter_by(telegram_id=message.from_user.id).first()
        lang = user.language if user else "ar"
    finally:
        db.close()
    await state.set_state(WithdrawStates.email)
    await message.answer(t(lang, "withdraw_send_email"))


@router.message(WithdrawStates.email, F.text)
async def withdraw_got_email(message: Message, state: FSMContext, bot: Bot) -> None:
    email = (message.text or "").strip()
    if "@" not in email or len(email) < 5:
        db = SessionLocal()
        try:
            user = db.query(User).filter_by(telegram_id=message.from_user.id).first()
            lang = user.language if user else "ar"
        finally:
            db.close()
        await message.answer(t(lang, "withdraw_email_invalid"))
        return

    data = await state.get_data()
    key = data.get("withdraw_product")
    cost = int(data.get("withdraw_cost") or 0)
    link = data.get("payment_link") or ""
    if not key or cost <= 0:
        await state.clear()
        return

    db = SessionLocal()
    try:
        user, _ = get_or_create_user(
            db, message.from_user.id, message.from_user.username, message.from_user.first_name
        )
        lang = user.language
        if user.points < cost:
            await message.answer(
                t(lang, "withdraw_need_points", cost=cost, have=user.points),
                reply_markup=main_menu(lang),
            )
            await state.clear()
            return
        user.points -= cost
        req = WithdrawRequest(
            user_id=user.id,
            product_key=key,
            points_cost=cost,
            payment_link=link,
            email=email,
            status="pending",
        )
        db.add(req)
        db.commit()
        from app.services.snapshot_hook import snapshot_db

        snapshot_db()
        db.refresh(req)

        uname = message.from_user.username or "—"
        field_label = product_admin_field(key, "ar")
        admin_text = (
            f"📤 طلب سحب #{req.id}\n"
            f"🛒 الخدمة: {product_title(key, 'ar')}\n"
            f"💎 النقاط: {cost}\n"
            f"👤 المستخدم: {user.telegram_id} @{uname}\n"
            f"📧 الإيميل: {email}\n"
            f"📎 {field_label}:\n{link}"
        )
        await notify_admins(bot, admin_text)

        await message.answer(
            t(lang, "withdraw_submitted", product=product_title(key, lang)),
            reply_markup=main_menu(lang),
        )
    finally:
        db.close()
    await state.clear()


@router.message()
async def fallback(message: Message, state: FSMContext) -> None:
    if message.text in _menu_texts():
        return
    current = await state.get_state()
    if current:
        return
    db = SessionLocal()
    try:
        user, _ = get_or_create_user(
            db, message.from_user.id, message.from_user.username, message.from_user.first_name
        )
        await message.answer(t(user.language, "use_menu"), reply_markup=main_menu(user.language))
    finally:
        db.close()
