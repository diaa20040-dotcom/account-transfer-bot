from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import Message

from app.bot.keyboards import main_menu
from app.bot.states import PromoStates
from app.database import SessionLocal, User
from app.i18n import t
from app.services.admin_access import is_admin
from app.services.promo import redeem_promo_code
from app.services.users import get_or_create_user

router = Router()


@router.message(F.text.in_({t("ar", "btn_promo"), t("en", "btn_promo")}))
async def promo_start(message: Message, state: FSMContext) -> None:
    await state.clear()
    db = SessionLocal()
    try:
        user, _ = get_or_create_user(
            db, message.from_user.id, message.from_user.username, message.from_user.first_name
        )
        lang = user.language
    finally:
        db.close()
    await state.set_state(PromoStates.entering_code)
    await message.answer(t(lang, "promo_enter_code"))


@router.message(PromoStates.entering_code, F.text)
async def promo_apply(message: Message, state: FSMContext) -> None:
    if message.text.startswith("/"):
        if message.text.strip().lower() == "/cancel":
            db = SessionLocal()
            try:
                user = db.query(User).filter_by(telegram_id=message.from_user.id).first()
                lang = user.language if user else "ar"
                adm = is_admin(message.from_user.id, message.from_user.username)
            finally:
                db.close()
            await state.clear()
            await message.answer(t(lang, "cancelled"), reply_markup=main_menu(lang, adm))
        return

    db = SessionLocal()
    try:
        user, _ = get_or_create_user(
            db, message.from_user.id, message.from_user.username, message.from_user.first_name
        )
        lang = user.language
        ok, msg_key, points = redeem_promo_code(db, user, message.text)
        if ok:
            from app.services.snapshot_hook import snapshot_db

            snapshot_db()
            db.refresh(user)
            text = t(lang, msg_key, points=points, balance=user.points)
        else:
            text = t(lang, msg_key)
        adm = is_admin(message.from_user.id, message.from_user.username)
        await message.answer(text, reply_markup=main_menu(lang, adm))
    finally:
        db.close()
    await state.clear()
