import logging

from aiogram import Bot, F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, LabeledPrice, Message

from app.bot.keyboards import main_menu
from app.bot.visa_keyboards import visa_pay_keyboard
from app.database import SessionLocal, User, get_setting
from app.i18n import t
from app.services.admin_access import is_admin
from app.services.notify_admins import notify_admins
from app.services.users import get_or_create_user
from app.services.visa_delivery import count_available_visas, fulfill_visa_order

logger = logging.getLogger(__name__)

router = Router()

DEFAULT_VISA_POINTS = 15
DEFAULT_VISA_STARS = 15


def visa_points_cost(db) -> int:
    try:
        return max(1, int(get_setting(db, "visa_points", str(DEFAULT_VISA_POINTS))))
    except ValueError:
        return DEFAULT_VISA_POINTS


def visa_stars_cost(db) -> int:
    try:
        return max(1, int(get_setting(db, "visa_stars", str(DEFAULT_VISA_STARS))))
    except ValueError:
        return DEFAULT_VISA_STARS


async def send_visa_invoice(bot: Bot, chat_id: int, lang: str, user_db_id: int, stars: int) -> None:
    await bot.send_invoice(
        chat_id=chat_id,
        title=t(lang, "visa_invoice_title"),
        description=t(lang, "visa_invoice_desc", stars=stars),
        payload=f"visa:{user_db_id}:{stars}",
        provider_token="",
        currency="XTR",
        prices=[LabeledPrice(label=t(lang, "visa_price_label", stars=stars), amount=stars)],
    )


async def _send_visa_content(bot: Bot, telegram_id: int, lang: str, content: str) -> None:
    text = t(lang, "visa_delivered", content=content)
    try:
        await bot.send_message(telegram_id, text)
    except Exception:
        logger.exception("send visa to %s failed, retry plain", telegram_id)
        await bot.send_message(telegram_id, text, parse_mode=None)


async def deliver_visa_to_user(
    bot: Bot,
    user: User,
    lang: str,
    payment_method: str,
    points_paid: int,
    stars_paid: int,
) -> bool:
    """Fulfill order (points deducted inside fulfill). Returns True if delivered."""
    db = SessionLocal()
    try:
        db_user = db.query(User).filter_by(id=user.id).first()
        if not db_user:
            return False
        result = fulfill_visa_order(db, db_user, payment_method, points_paid, stars_paid)
        if result.ok and result.content:
            from app.services.snapshot_hook import snapshot_db

            snapshot_db()
            await _send_visa_content(bot, user.telegram_id, lang, result.content)
            await notify_admins(
                bot,
                f"✅ تسليم تلقائي فيزا #{result.request.id}\n"
                f"المستخدم: {user.telegram_id} @{user.username or '—'}\n"
                f"متبقي في المخزون: {count_available_visas(db)}",
            )
            return True
        if result.reason == "sold_out":
            await bot.send_message(user.telegram_id, t(lang, "visa_sold_out"))
            await notify_admins(
                bot,
                f"⚠️ نفذ مخزون الفيز — مستخدم {user.telegram_id} (دفع: {payment_method})",
            )
        elif result.reason == "error":
            await bot.send_message(user.telegram_id, t(lang, "visa_delivery_error"))
            await notify_admins(
                bot,
                f"❌ خطأ تسليم فيزا — مستخدم {user.telegram_id}. راجع السجلات.",
            )
        return False
    finally:
        db.close()


@router.message(F.text.in_({t("ar", "btn_visa"), t("en", "btn_visa")}))
async def visa_menu(message: Message, state: FSMContext) -> None:
    await state.clear()
    db = SessionLocal()
    try:
        user, _ = get_or_create_user(
            db, message.from_user.id, message.from_user.username, message.from_user.first_name
        )
        lang = user.language
        pts = visa_points_cost(db)
        stars = visa_stars_cost(db)
        remaining = count_available_visas(db)
        if remaining <= 0:
            await message.answer(t(lang, "visa_sold_out"))
            return
        await message.answer(
            t(lang, "visa_choose_pay", points=pts, stars=stars, remaining=remaining),
            reply_markup=visa_pay_keyboard(lang, pts, stars),
        )
    finally:
        db.close()


@router.callback_query(F.data == "visa:cancel")
async def visa_cancel(callback: CallbackQuery, state: FSMContext) -> None:
    db = SessionLocal()
    try:
        user = db.query(User).filter_by(telegram_id=callback.from_user.id).first()
        lang = user.language if user else "ar"
        adm = is_admin(callback.from_user.id, callback.from_user.username)
    finally:
        db.close()
    await state.clear()
    try:
        await callback.message.edit_reply_markup(reply_markup=None)
    except Exception:
        pass
    await callback.message.answer(t(lang, "cancelled"), reply_markup=main_menu(lang, adm))
    await callback.answer()


@router.callback_query(F.data == "visa:points")
async def visa_pay_points(callback: CallbackQuery, state: FSMContext, bot: Bot) -> None:
    lang = "ar"
    adm = is_admin(callback.from_user.id, callback.from_user.username)
    db = SessionLocal()
    try:
        user, _ = get_or_create_user(
            db,
            callback.from_user.id,
            callback.from_user.username,
            callback.from_user.first_name,
        )
        lang = user.language
        if count_available_visas(db) <= 0:
            await callback.answer(t(lang, "visa_sold_out"), show_alert=True)
            return
        cost = visa_points_cost(db)
        if user.points < cost:
            await callback.answer(
                t(lang, "visa_need_points", cost=cost, have=user.points),
                show_alert=True,
            )
            return
        result = fulfill_visa_order(db, user, "points", cost, 0)
        if not result.ok or not result.content:
            if result.reason == "sold_out":
                await callback.answer(t(lang, "visa_sold_out"), show_alert=True)
            elif result.reason == "error":
                await callback.answer(t(lang, "visa_delivery_error"), show_alert=True)
            else:
                await callback.answer(t(lang, "visa_sold_out"), show_alert=True)
            return
        from app.services.snapshot_hook import snapshot_db

        snapshot_db()
        content = result.content
        tg_id = user.telegram_id
    except Exception:
        logger.exception("visa_pay_points failed")
        await callback.answer(t(lang, "visa_delivery_error"), show_alert=True)
        return
    finally:
        db.close()

    try:
        await callback.message.edit_reply_markup(reply_markup=None)
    except Exception:
        pass
    await _send_visa_content(bot, tg_id, lang, content)
    rem_db = SessionLocal()
    try:
        remaining = count_available_visas(rem_db)
    finally:
        rem_db.close()
    await notify_admins(
        bot,
        f"✅ تسليم فيزا بالنقاط #{result.request.id}\n"
        f"المستخدم: {tg_id}\nمتبقي: {remaining}",
    )
    await callback.message.answer(t(lang, "visa_done_hint"), reply_markup=main_menu(lang, adm))
    await callback.answer()


@router.callback_query(F.data == "visa:stars")
async def visa_pay_stars(callback: CallbackQuery, state: FSMContext, bot: Bot) -> None:
    db = SessionLocal()
    try:
        user, _ = get_or_create_user(
            db,
            callback.from_user.id,
            callback.from_user.username,
            callback.from_user.first_name,
        )
        lang = user.language
        if count_available_visas(db) <= 0:
            await callback.answer(t(lang, "visa_sold_out"), show_alert=True)
            return
        stars = visa_stars_cost(db)
        await send_visa_invoice(bot, callback.message.chat.id, lang, user.id, stars)
    finally:
        db.close()
    await callback.answer()
