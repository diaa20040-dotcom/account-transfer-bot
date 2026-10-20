from aiogram import Bot, F, Router
from aiogram.filters import Command, CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message, ReplyKeyboardRemove

from app.bot.keyboards import main_menu
from app.bot.mandatory_keyboards import mandatory_sub_keyboard
from app.config import settings
from app.database import SessionLocal, User, get_setting
from app.i18n import t
from app.services.admin_access import is_admin, persist_admin
from app.services.mandatory_sub import get_mandatory_sub_config, is_user_subscribed
from app.services.users import (
    get_or_create_user,
    referral_count,
    referral_pending_count,
    try_award_referral,
)

router = Router()


def _lang_btn_values() -> set[str]:
    keys = (
        "btn_visa",
        "btn_referral",
        "btn_language",
        "btn_points",
    )
    return {t(lang, k) for lang in ("ar", "en") for k in keys}


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
        ref_pts = int(get_setting(db, "referral_points", "1"))
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


@router.message()
async def fallback(message: Message) -> None:
    if message.text in _lang_btn_values():
        return
    db = SessionLocal()
    try:
        user, _ = get_or_create_user(
            db, message.from_user.id, message.from_user.username, message.from_user.first_name
        )
        adm = is_admin(message.from_user.id, message.from_user.username)
        await message.answer(t(user.language, "use_menu"), reply_markup=main_menu(user.language, adm))
    finally:
        db.close()
