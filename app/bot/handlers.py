from aiogram import Bot, F, Router
from aiogram.filters import Command, CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message, ReplyKeyboardRemove

from app.bot.keyboards import countries_keyboard, main_menu, tasks_keyboard
from app.bot.mandatory_keyboards import mandatory_sub_keyboard
from app.bot.states import TransferStates
from app.config import settings
from app.services.admin_access import is_admin, persist_admin
from app.services.admin_notify import get_admin_ids
from app.database import (
    Country,
    SessionLocal,
    Task,
    TaskCompletion,
    TransferRequest,
    User,
    get_setting,
)
from app.i18n import t
from app.services.mandatory_sub import get_mandatory_sub_config, is_user_subscribed
from app.services.users import (
    get_or_create_user,
    referral_count,
    referral_pending_count,
    try_award_referral,
)

router = Router()


def _lang_btn_values() -> set[str]:
    return {t("ar", "btn_transfer"), t("en", "btn_transfer"), t("ar", "btn_tasks"), t("en", "btn_tasks"),
            t("ar", "btn_referral"), t("en", "btn_referral"), t("ar", "btn_language"), t("en", "btn_language"),
            t("ar", "btn_points"), t("en", "btn_points"),
            t("ar", "btn_topup"), t("en", "btn_topup")}


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
        admin = is_admin(message.from_user.id, message.from_user.username)
        if admin:
            persist_admin(db, message.from_user.id)
        lang = user.language
        name = message.from_user.first_name or "User"
        msub = get_mandatory_sub_config(db)
        if (
            msub.active
            and not admin
            and not await is_user_subscribed(bot, msub.chat_id, message.from_user.id)
        ):
            await message.answer(
                t(lang, "mandatory_sub_prompt"),
                reply_markup=ReplyKeyboardRemove(),
            )
            await message.answer(
                "⬇️",
                reply_markup=mandatory_sub_keyboard(lang, msub.invite_link),
            )
            return
        await try_award_referral(db, bot, user)
        db.refresh(user)
        await message.answer(
            t(lang, "welcome", name=name, points=user.points),
            reply_markup=main_menu(lang, admin),
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
        adm = is_admin(message.from_user.id, message.from_user.username)
        await message.answer(t(user.language, "use_menu"), reply_markup=main_menu(user.language, adm))
    finally:
        db.close()


@router.message(F.text.in_({t("ar", "btn_language"), t("en", "btn_language")}))
async def toggle_language(message: Message) -> None:
    db = SessionLocal()
    try:
        user, _ = get_or_create_user(
            db, message.from_user.id, message.from_user.username, message.from_user.first_name
        )
        user.language = "en" if user.language == "ar" else "ar"
        db.commit()
        adm = is_admin(message.from_user.id, message.from_user.username)
        await message.answer(
            t(user.language, "lang_switched"), reply_markup=main_menu(user.language, adm)
        )
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
        ref_pts = int(get_setting(db, "referral_points", "25"))
        count = referral_count(db, user)
        pending = referral_pending_count(db, user)
        await message.answer(
            t(
                user.language,
                "referral_info",
                link=link,
                points=ref_pts,
                count=count,
                pending=pending,
            )
        )
    finally:
        db.close()


@router.message(F.text.in_({t("ar", "btn_tasks"), t("en", "btn_tasks")}))
async def show_tasks(message: Message) -> None:
    db = SessionLocal()
    try:
        user, _ = get_or_create_user(
            db, message.from_user.id, message.from_user.username, message.from_user.first_name
        )
        tasks = db.query(Task).filter_by(active=True).order_by(Task.sort_order).all()
        lang = user.language
        if not tasks:
            await message.answer(t(lang, "no_tasks"))
            return
        lines = [t(lang, "tasks_header")]
        for task in tasks:
            title = task.title_ar if lang == "ar" else task.title_en
            lines.append(t(lang, "task_line", title=title, reward=task.reward_points))
        await message.answer("\n".join(lines), reply_markup=tasks_keyboard(lang, tasks))
    finally:
        db.close()


@router.callback_query(F.data == "verify_mandatory")
async def verify_mandatory(callback: CallbackQuery, bot: Bot) -> None:
    db = SessionLocal()
    try:
        user, _ = get_or_create_user(
            db,
            callback.from_user.id,
            callback.from_user.username,
            callback.from_user.first_name,
        )
        lang = user.language
        msub = get_mandatory_sub_config(db)
        if not msub.active:
            await callback.answer("—", show_alert=True)
            return
        if not await is_user_subscribed(bot, msub.chat_id, callback.from_user.id):
            await callback.answer(t(lang, "mandatory_sub_fail"), show_alert=True)
            return
        admin = is_admin(callback.from_user.id, callback.from_user.username)
        name = callback.from_user.first_name or "User"
        db.refresh(user)
        await try_award_referral(db, bot, user)
        db.refresh(user)
        await callback.answer(t(lang, "mandatory_sub_ok"), show_alert=True)
        try:
            await callback.message.edit_reply_markup(reply_markup=None)
        except Exception:
            pass
        await callback.message.answer(
            t(lang, "welcome", name=name, points=user.points),
            reply_markup=main_menu(lang, admin),
        )
    finally:
        db.close()


@router.callback_query(F.data.startswith("verify_task:"))
async def verify_task(callback: CallbackQuery, bot: Bot) -> None:
    task_id = int(callback.data.split(":")[1])
    db = SessionLocal()
    try:
        user, _ = get_or_create_user(
            db,
            callback.from_user.id,
            callback.from_user.username,
            callback.from_user.first_name,
        )
        lang = user.language
        task = db.query(Task).filter_by(id=task_id, active=True).first()
        if not task:
            await callback.answer("—", show_alert=True)
            return
        done = (
            db.query(TaskCompletion)
            .filter_by(user_id=user.id, task_id=task.id)
            .first()
        )
        if done:
            await callback.answer(t(lang, "task_already"), show_alert=True)
            return
        try:
            member = await bot.get_chat_member(chat_id=task.chat_id, user_id=user.telegram_id)
            if member.status in ("left", "kicked"):
                await callback.answer(t(lang, "task_fail"), show_alert=True)
                return
        except Exception:
            await callback.answer(t(lang, "task_fail"), show_alert=True)
            return
        db.add(TaskCompletion(user_id=user.id, task_id=task.id))
        user.points += task.reward_points
        db.commit()
        await callback.answer(
            t(lang, "task_done", reward=task.reward_points),
            show_alert=True,
        )
    finally:
        db.close()


@router.message(F.text.in_({t("ar", "btn_transfer"), t("en", "btn_transfer")}))
async def start_transfer(message: Message, state: FSMContext) -> None:
    db = SessionLocal()
    try:
        user, _ = get_or_create_user(
            db, message.from_user.id, message.from_user.username, message.from_user.first_name
        )
        countries = db.query(Country).filter_by(active=True).order_by(Country.sort_order).all()
        lang = user.language
        if not countries:
            await message.answer("No countries configured." if lang == "en" else "لا توجد دول مفعّلة.")
            return
        await state.set_state(TransferStates.choosing_country)
        await message.answer(
            t(lang, "choose_country"),
            reply_markup=countries_keyboard(lang, countries),
        )
    finally:
        db.close()


@router.callback_query(F.data == "cancel_transfer")
async def cancel_transfer(callback: CallbackQuery, state: FSMContext) -> None:
    db = SessionLocal()
    try:
        user = db.query(User).filter_by(telegram_id=callback.from_user.id).first()
        lang = user.language if user else "ar"
    finally:
        db.close()
    await state.clear()
    await callback.message.edit_reply_markup(reply_markup=None)
    await callback.message.answer(t(lang, "cancelled"))


@router.callback_query(TransferStates.choosing_country, F.data.startswith("country:"))
async def country_chosen(callback: CallbackQuery, state: FSMContext) -> None:
    country_id = int(callback.data.split(":")[1])
    db = SessionLocal()
    try:
        user, _ = get_or_create_user(
            db,
            callback.from_user.id,
            callback.from_user.username,
            callback.from_user.first_name,
        )
        lang = user.language
        country = db.query(Country).filter_by(id=country_id, active=True).first()
        if not country:
            await callback.answer("—")
            return
        if user.points < country.point_cost:
            await callback.answer(
                t(lang, "need_points", cost=country.point_cost, have=user.points),
                show_alert=True,
            )
            return
        await state.update_data(country_id=country.id, point_cost=country.point_cost)
        await state.set_state(TransferStates.entering_username)
        await callback.message.edit_reply_markup(reply_markup=None)
        await callback.message.answer(t(lang, "enter_username"))
        await callback.answer()
    finally:
        db.close()


@router.message(TransferStates.entering_username, F.text)
async def got_username(message: Message, state: FSMContext) -> None:
    if message.text.startswith("/"):
        return
    await state.update_data(account_name=message.text.strip())
    db = SessionLocal()
    try:
        user = db.query(User).filter_by(telegram_id=message.from_user.id).first()
        lang = user.language if user else "ar"
    finally:
        db.close()
    await state.set_state(TransferStates.entering_password)
    await message.answer(t(lang, "enter_password"))


@router.message(TransferStates.entering_password, F.text)
async def got_password(message: Message, state: FSMContext, bot: Bot) -> None:
    if message.text.startswith("/"):
        return
    data = await state.get_data()
    password = message.text.strip()
    db = SessionLocal()
    try:
        user, _ = get_or_create_user(
            db, message.from_user.id, message.from_user.username, message.from_user.first_name
        )
        lang = user.language
        country = db.query(Country).filter_by(id=data["country_id"]).first()
        cost = data["point_cost"]
        if not country or user.points < cost:
            await message.answer(t(lang, "need_points", cost=cost, have=user.points))
            await state.clear()
            return
        user.points -= cost
        req = TransferRequest(
            user_id=user.id,
            country_id=country.id,
            account_name=data["account_name"],
            account_password=password,
            status="pending",
        )
        db.add(req)
        db.commit()
        db.refresh(req)

        cname = country.name_ar if lang == "ar" else country.name_en
        admin_text = (
            f"🆕 طلب تحويل #{req.id}\n"
            f"المستخدم: {user.telegram_id} @{user.username or '—'}\n"
            f"الدولة: {cname}\n"
            f"الحساب: {req.account_name}\n"
            f"كلمة المرور: {req.account_password}\n"
            f"الحالة: pending"
        )
        for admin_id in get_admin_ids():
            try:
                await bot.send_message(admin_id, admin_text)
            except Exception:
                pass

        adm = is_admin(message.from_user.id, message.from_user.username)
        await message.answer(
            t(lang, "transfer_submitted", cost=cost), reply_markup=main_menu(lang, adm)
        )
    finally:
        db.close()
    await state.clear()


@router.message()
async def fallback(message: Message) -> None:
    db = SessionLocal()
    try:
        user, _ = get_or_create_user(
            db, message.from_user.id, message.from_user.username, message.from_user.first_name
        )
        adm = is_admin(message.from_user.id, message.from_user.username)
        await message.answer(t(user.language, "use_menu"), reply_markup=main_menu(user.language, adm))
    finally:
        db.close()
