import logging

from aiogram import Bot, F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, LabeledPrice, Message, PreCheckoutQuery

from app.bot.stars_keyboards import topup_amounts_keyboard
from app.bot.states import TopUpStates
from app.database import SessionLocal, User
from app.i18n import t
from app.services.users import get_or_create_user

logger = logging.getLogger(__name__)

router = Router()

_TOPUP_MAX = 10_000
_TOPUP_MIN = 1


def _parse_topup_payload(payload: str) -> tuple[int, int] | None:
    # topup:{user_db_id}:{points}
    if not payload.startswith("topup:"):
        return None
    parts = payload.split(":")
    if len(parts) != 3:
        return None
    try:
        user_id = int(parts[1])
        points = int(parts[2])
    except ValueError:
        return None
    if points < _TOPUP_MIN or points > _TOPUP_MAX:
        return None
    return user_id, points


async def _send_stars_invoice(bot: Bot, chat_id: int, lang: str, user_db_id: int, stars: int) -> None:
    await bot.send_invoice(
        chat_id=chat_id,
        title=t(lang, "topup_invoice_title"),
        description=t(lang, "topup_invoice_desc", points=stars, stars=stars),
        payload=f"topup:{user_db_id}:{stars}",
        provider_token="",
        currency="XTR",
        prices=[LabeledPrice(label=t(lang, "topup_price_label", points=stars), amount=stars)],
    )


@router.message(F.text.in_({t("ar", "btn_topup"), t("en", "btn_topup")}))
async def topup_menu(message: Message, state: FSMContext) -> None:
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
        t(lang, "topup_choose"),
        reply_markup=topup_amounts_keyboard(lang),
    )


@router.callback_query(F.data == "topup:custom")
async def topup_custom(callback: CallbackQuery, state: FSMContext) -> None:
    db = SessionLocal()
    try:
        user = db.query(User).filter_by(telegram_id=callback.from_user.id).first()
        lang = user.language if user else "ar"
    finally:
        db.close()
    await state.set_state(TopUpStates.amount)
    await callback.message.answer(t(lang, "topup_enter_amount"))
    await callback.answer()


@router.callback_query(F.data.startswith("topup:"))
async def topup_preset(callback: CallbackQuery, bot: Bot, state: FSMContext) -> None:
    if callback.data == "topup:custom":
        return
    stars = int(callback.data.split(":")[1])
    await state.clear()
    db = SessionLocal()
    try:
        user, _ = get_or_create_user(
            db,
            callback.from_user.id,
            callback.from_user.username,
            callback.from_user.first_name,
        )
        lang = user.language
        await _send_stars_invoice(bot, callback.message.chat.id, lang, user.id, stars)
    finally:
        db.close()
    await callback.answer()


@router.message(TopUpStates.amount, F.text)
async def topup_custom_amount(message: Message, state: FSMContext, bot: Bot) -> None:
    db = SessionLocal()
    try:
        user, _ = get_or_create_user(
            db, message.from_user.id, message.from_user.username, message.from_user.first_name
        )
        lang = user.language
        raw = message.text.strip()
        try:
            stars = int(raw)
        except ValueError:
            await message.answer(t(lang, "topup_invalid_amount"))
            return
        if stars < _TOPUP_MIN or stars > _TOPUP_MAX:
            await message.answer(t(lang, "topup_invalid_amount"))
            return
        await _send_stars_invoice(bot, message.chat.id, lang, user.id, stars)
    finally:
        db.close()
    await state.clear()


@router.pre_checkout_query()
async def pre_checkout(query: PreCheckoutQuery) -> None:
    parsed = _parse_topup_payload(query.invoice_payload)
    if not parsed:
        await query.answer(ok=False, error_message="Invalid payment.")
        return
    user_id, points = parsed
    if query.currency != "XTR" or query.total_amount != points:
        await query.answer(ok=False, error_message="Amount mismatch.")
        return
    db = SessionLocal()
    try:
        if not db.query(User).filter_by(id=user_id, telegram_id=query.from_user.id).first():
            await query.answer(ok=False, error_message="User mismatch.")
            return
    finally:
        db.close()
    await query.answer(ok=True)


@router.message(F.successful_payment)
async def successful_payment(message: Message) -> None:
    payment = message.successful_payment
    parsed = _parse_topup_payload(payment.invoice_payload)
    if not parsed:
        logger.warning("Unknown payment payload: %s", payment.invoice_payload)
        return
    user_id, points = parsed
    if payment.currency != "XTR" or payment.total_amount != points:
        logger.warning("Payment amount mismatch for user %s", user_id)
        return

    db = SessionLocal()
    try:
        user = db.query(User).filter_by(id=user_id, telegram_id=message.from_user.id).first()
        if not user:
            return
        user.points += points
        db.commit()
        lang = user.language
        await message.answer(
            t(lang, "topup_success", points=points, balance=user.points),
        )
    finally:
        db.close()
