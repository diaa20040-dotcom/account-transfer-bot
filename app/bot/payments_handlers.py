import logging

from aiogram import Bot, F, Router
from aiogram.types import LabeledPrice, Message, PreCheckoutQuery

from app.bot.keyboards import main_menu
from app.database import SessionLocal, User, get_setting
from app.i18n import t
from app.services.notify_admins import notify_admins
from app.services.payments_record import save_successful_star_payment

logger = logging.getLogger(__name__)

router = Router()

_PAY_MAX = 10_000
_PAYOUT_USERNAME = "Diaoeldeen"


def payout_contact_username(db) -> str:
    return (get_setting(db, "payout_contact_username", _PAYOUT_USERNAME) or _PAYOUT_USERNAME).lstrip("@")


def _parse_sell_payload(payload: str) -> tuple[int, int] | None:
    if not payload.startswith("sellstars:"):
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


async def send_sell_stars_invoice(
    bot: Bot, chat_id: int, lang: str, user_db_id: int, stars: int
) -> None:
    await bot.send_invoice(
        chat_id=chat_id,
        title=t(lang, "sell_invoice_title"),
        description=t(lang, "sell_invoice_desc", stars=stars),
        payload=f"sellstars:{user_db_id}:{stars}",
        provider_token="",
        currency="XTR",
        prices=[LabeledPrice(label=t(lang, "sell_price_label", stars=stars), amount=stars)],
    )


@router.pre_checkout_query()
async def pre_checkout(query: PreCheckoutQuery) -> None:
    parsed = _parse_sell_payload(query.invoice_payload)
    if not parsed:
        await query.answer(ok=False, error_message="Invalid payment.")
        return
    user_id, stars = parsed
    if query.currency != "XTR" or query.total_amount != stars:
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
    parsed = _parse_sell_payload(payment.invoice_payload)
    if not parsed:
        logger.warning("Unknown payment payload: %s", payment.invoice_payload)
        return
    user_id, stars = parsed
    if payment.currency != "XTR" or payment.total_amount != stars:
        logger.warning("Sell-stars payment mismatch for user %s", user_id)
        return

    db = SessionLocal()
    try:
        user = db.query(User).filter_by(id=user_id, telegram_id=message.from_user.id).first()
        if not user:
            return
        lang = user.language
        save_successful_star_payment(db, user, payment)
        contact = payout_contact_username(db)
        from app.services.snapshot_hook import snapshot_db

        snapshot_db()
    finally:
        db.close()

    uname = message.from_user.username
    user_line = f"{message.from_user.id}"
    if uname:
        user_line += f" @{uname}"
    if message.from_user.first_name:
        user_line += f" ({message.from_user.first_name})"

    admin_text = (
        f"💰 **طلب بيع نجوم**\n"
        f"الكمية: **{stars}** ⭐\n"
        f"المستخدم: {user_line}\n\n"
        f"تواصل معه لتحويل المبلغ — حسابك للمتابعة: @{contact}"
    )
    await notify_admins(bot, admin_text)

    await message.answer(
        t(lang, "sell_paid_ok", stars=stars, contact=contact),
        reply_markup=main_menu(lang),
    )
