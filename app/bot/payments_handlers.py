import logging

from aiogram import Bot, F, Router
from aiogram.types import LabeledPrice, Message, PreCheckoutQuery

from app.bot.keyboards import main_menu
from app.database import SessionLocal, User
from app.i18n import t
from app.services.payments_record import save_successful_star_payment

logger = logging.getLogger(__name__)

router = Router()

_PAY_MAX = 10_000


def _parse_topup_payload(payload: str) -> tuple[int, int] | None:
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
    if points < 1 or points > _PAY_MAX:
        return None
    return user_id, points


async def send_topup_invoice(bot: Bot, chat_id: int, lang: str, user_db_id: int, stars: int) -> None:
    await bot.send_invoice(
        chat_id=chat_id,
        title=t(lang, "topup_invoice_title"),
        description=t(lang, "topup_invoice_desc", points=stars, stars=stars),
        payload=f"topup:{user_db_id}:{stars}",
        provider_token="",
        currency="XTR",
        prices=[LabeledPrice(label=t(lang, "topup_price_label", points=stars), amount=stars)],
    )


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
async def successful_payment(message: Message, bot: Bot) -> None:
    payment = message.successful_payment
    parsed = _parse_topup_payload(payment.invoice_payload)
    if not parsed:
        logger.warning("Unknown payment payload: %s", payment.invoice_payload)
        return
    user_id, points = parsed
    if payment.currency != "XTR" or payment.total_amount != points:
        logger.warning("Top-up payment mismatch for user %s", user_id)
        return

    db = SessionLocal()
    try:
        user = db.query(User).filter_by(id=user_id, telegram_id=message.from_user.id).first()
        if not user:
            return
        lang = user.language
        save_successful_star_payment(db, user, payment)
        user.points += points
        db.commit()
        from app.services.snapshot_hook import snapshot_db

        snapshot_db()
        db.refresh(user)
        await message.answer(
            t(lang, "topup_success", points=points, balance=user.points),
            reply_markup=main_menu(lang),
        )
    finally:
        db.close()
