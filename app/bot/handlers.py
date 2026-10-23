from aiogram import Bot, F, Router
from aiogram.filters import Command, CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.types import Message

from app.bot.keyboards import main_menu
from app.bot.states import SellStarsStates
from app.database import SessionLocal
from app.i18n import t
from app.services.users import get_or_create_user

router = Router()

_STARS_MIN = 1
_STARS_MAX = 10_000


@router.message(CommandStart())
async def cmd_start(message: Message, state: FSMContext) -> None:
    await state.clear()
    db = SessionLocal()
    try:
        user, _ = get_or_create_user(
            db,
            message.from_user.id,
            message.from_user.username,
            message.from_user.first_name,
        )
        lang = user.language
        name = message.from_user.first_name or "User"
        await message.answer(
            t(lang, "welcome_sell", name=name),
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


@router.message(F.text.in_({t("ar", "btn_sell_stars"), t("en", "btn_sell_stars")}))
async def sell_stars_start(message: Message, state: FSMContext) -> None:
    await state.clear()
    db = SessionLocal()
    try:
        user, _ = get_or_create_user(
            db, message.from_user.id, message.from_user.username, message.from_user.first_name
        )
        lang = user.language
    finally:
        db.close()
    await state.set_state(SellStarsStates.waiting_amount)
    await message.answer(t(lang, "sell_enter_amount"))


@router.message(SellStarsStates.waiting_amount, F.text)
async def sell_stars_amount(message: Message, state: FSMContext, bot: Bot) -> None:
    if message.text and message.text.startswith("/"):
        if message.text.strip().lower() in ("/cancel", "/menu"):
            await state.clear()
            db = SessionLocal()
            try:
                user, _ = get_or_create_user(
                    db,
                    message.from_user.id,
                    message.from_user.username,
                    message.from_user.first_name,
                )
                await message.answer(t(user.language, "cancelled"), reply_markup=main_menu(user.language))
            finally:
                db.close()
        return
    db = SessionLocal()
    try:
        user, _ = get_or_create_user(
            db, message.from_user.id, message.from_user.username, message.from_user.first_name
        )
        lang = user.language
        raw = (message.text or "").strip()
        try:
            stars = int(raw)
        except ValueError:
            await message.answer(t(lang, "sell_invalid_amount"))
            return
        if stars < _STARS_MIN or stars > _STARS_MAX:
            await message.answer(t(lang, "sell_invalid_amount"))
            return
        from app.bot.payments_handlers import send_sell_stars_invoice

        await send_sell_stars_invoice(bot, message.chat.id, lang, user.id, stars)
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
        await message.answer(t(user.language, "use_menu"), reply_markup=main_menu(user.language))
    finally:
        db.close()
