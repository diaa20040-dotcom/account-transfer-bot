import logging

from aiogram import Bot, F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import Message, PreCheckoutQuery

from app.bot.keyboards import main_menu
from app.bot.visa_handlers import deliver_visa_to_user, visa_stars_cost
from app.database import SessionLocal, User, get_setting
from app.i18n import t
from app.services.admin_access import is_admin
from app.services.payments_record import save_successful_star_payment
from app.services.star_payments import refund_stars_by_charge_id
from app.services.visa_delivery import count_available_visas

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
        if count_available_visas(db) <= 0:
            await query.answer(ok=False, error_message="نفذ مخزون الفيز حالياً.")
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
        charge_id = payment.telegram_payment_charge_id or ""
    finally:
        db.close()

    await state.clear()
    delivered = await deliver_visa_to_user(bot, user, lang, "stars", 0, stars)
    adm = is_admin(message.from_user.id, message.from_user.username)
    if delivered:
        await message.answer(t(lang, "visa_done_hint"), reply_markup=main_menu(lang, adm))
    else:
        if charge_id:
            db = SessionLocal()
            try:
                u = db.query(User).filter_by(id=user.id).first()
                if u:
                    ok, _ = await refund_stars_by_charge_id(
                        bot, db, u, charge_id, stars, "visa"
                    )
                    if ok:
                        await message.answer(t(lang, "visa_stars_refunded"), reply_markup=main_menu(lang, adm))
                        return
            finally:
                db.close()
        await message.answer(t(lang, "visa_sold_out"), reply_markup=main_menu(lang, adm))
