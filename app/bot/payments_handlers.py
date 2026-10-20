import logging

from aiogram import Bot, F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import Message, PreCheckoutQuery

from app.bot.states import VisaStates
from app.database import SessionLocal, User, get_setting
from app.i18n import t
from app.services.payments_record import save_successful_star_payment
from app.services.users import get_or_create_user

logger = logging.getLogger(__name__)

router = Router()

_PAY_MAX = 10_000


def _parse_visa_payload(payload: str) -> tuple[int, int] | None:
    if not payload.startswith("visa:"):
        return None
    parts = payload.split(":")
    if len(parts) != 3:
        return None
    try:
        user_id = int(parts[1])
        stars = int(parts[2])
    except ValueError:
        return None
    if stars < 1 or stars > _PAY_MAX:
        return None
    return user_id, stars


@router.pre_checkout_query()
async def pre_checkout(query: PreCheckoutQuery) -> None:
    parsed = _parse_visa_payload(query.invoice_payload)
    if not parsed:
        await query.answer(ok=False, error_message="Invalid payment.")
        return
    user_id, stars = parsed
    if query.currency != "XTR" or query.total_amount != stars:
        await query.answer(ok=False, error_message="Amount mismatch.")
        return
    db = SessionLocal()
    try:
        expected = int(get_setting(db, "visa_stars", "15"))
        if stars != expected:
            await query.answer(ok=False, error_message="Price changed.")
            return
        if not db.query(User).filter_by(id=user_id, telegram_id=query.from_user.id).first():
            await query.answer(ok=False, error_message="User mismatch.")
            return
    finally:
        db.close()
    await query.answer(ok=True)


@router.message(F.successful_payment)
async def successful_payment(message: Message, state: FSMContext, bot: Bot) -> None:
    payment = message.successful_payment
    parsed = _parse_visa_payload(payment.invoice_payload)
    if not parsed:
        logger.warning("Unknown payment payload: %s", payment.invoice_payload)
        return
    user_id, stars = parsed
    if payment.currency != "XTR" or payment.total_amount != stars:
        logger.warning("Visa payment mismatch for user %s", user_id)
        return

    db = SessionLocal()
    try:
        user = db.query(User).filter_by(id=user_id, telegram_id=message.from_user.id).first()
        if not user:
            return
        lang = user.language
        save_successful_star_payment(db, user, payment)
    finally:
        db.close()

    await state.clear()
    await state.update_data(
        visa_paid=True,
        visa_payment="stars",
        visa_points=0,
        visa_stars=stars,
    )
    await state.set_state(VisaStates.entering_details)
    await message.answer(t(lang, "visa_paid_enter_details", stars=stars))
