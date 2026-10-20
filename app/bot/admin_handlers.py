import json
from datetime import datetime

from aiogram import Bot, F, Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import BufferedInputFile, CallbackQuery, Message
from sqlalchemy import desc

from app.bot.admin_keyboards import (
    ADMIN_BTN_AR,
    ADMIN_BTN_EN,
    admin_main_inline,
    broadcast_confirm_keyboard,
    box_game_actions_keyboard,
    box_games_admin_keyboard,
    box_pricing_admin_keyboard,
    box_status_keyboard,
    countries_admin_keyboard,
    country_actions_keyboard,
    maintenance_admin_keyboard,
    promo_actions_keyboard,
    promos_admin_keyboard,
    runopen_status_keyboard,
    stars_refund_menu_keyboard,
    task_actions_keyboard,
    tasks_admin_keyboard,
    discussion_admin_keyboard,
    transfer_status_keyboard,
    visa_status_keyboard,
    visa_price_admin_keyboard,
    mandatory_sub_admin_keyboard,
)
from app.bot.admin_states import (
    AdminAddBoxGame,
    AdminAddPromo,
    AdminAddPoints,
    AdminAddTask,
    AdminBroadcast,
    AdminSetAllBoxCost,
    AdminSetBoxCost,
    AdminSetBoxCustomCost,
    AdminSetCountryCost,
    AdminSetReferral,
    AdminBanUser,
    AdminSetPlayPassSlots,
    AdminSetPlayPassStars,
    AdminSetRunOpenStars,
    AdminMandatorySub,
    AdminDiscussion,
    AdminMessageUser,
    AdminRestoreBackup,
    AdminStarsRefund,
    AdminAddVisaStock,
    AdminSetVisaPrice,
)
from app.bot.keyboards import main_menu
from app.bot.play_pass_keyboards import (
    playpass_admin_list_keyboard,
    playpass_admin_settings_keyboard,
    playpass_status_keyboard,
    user_admin_profile_keyboard,
)
from app.database import (
    BoxGame,
    BoxRequest,
    Country,
    PromoCode,
    PromoRedemption,
    PlayPassRequest,
    RunOpenRequest,
    SessionLocal,
    StarPayment,
    Task,
    TransferRequest,
    VisaRequest,
    VisaStock,
    User,
    get_setting,
    set_setting,
)
from app.services.maintenance import KEY_MAINTENANCE, is_bot_maintenance
from app.services.promo import normalize_promo_code
from app.services.admin_access import is_admin, persist_admin
from app.services.mandatory_sub import (
    KEY_CHAT_ID,
    KEY_ENABLED,
    KEY_INVITE_LINK,
    get_mandatory_sub_config,
)
from app.services.backup_export import backup_json_bytes, import_backup_payload
from app.services.broadcast import broadcast_message
from app.services.order_discussion import (
    ORDER_KINDS,
    close_thread,
    get_thread_by_id,
    load_order,
    open_discussion,
    order_kind_label,
    order_user,
)
from app.services.star_payments import (
    admin_refund_feedback,
    match_payment_to_request,
    payment_kind_label,
    refund_star_payment_record,
    refund_stars_by_charge_id,
)
from app.services.stars_refund_admin import (
    get_request_for_refund,
    mark_request_stars_refunded,
    paginate_star_orders,
)
from app.services.user_notify import (
    notify_transfer_status,
    send_admin_message_to_user,
    send_discussion_message_to_user,
)
from app.services.users import get_or_create_user

router = Router()


def _admin_only_message(message: Message) -> bool:
    return is_admin(message.from_user.id, message.from_user.username)


def _admin_only_callback(callback: CallbackQuery) -> bool:
    return is_admin(callback.from_user.id, callback.from_user.username)


@router.message(Command("admin"))
@router.message(F.text.in_({ADMIN_BTN_AR, ADMIN_BTN_EN}))
async def admin_open(message: Message, state: FSMContext) -> None:
    if not _admin_only_message(message):
        return
    db = SessionLocal()
    try:
        persist_admin(db, message.from_user.id)
        user, _ = get_or_create_user(
            db, message.from_user.id, message.from_user.username, message.from_user.first_name
        )
        lang = user.language
    finally:
        db.close()
    await state.clear()
    await message.answer(
        "🛠 **لوحة الإدارة**\nاختر القسم:",
        reply_markup=admin_main_inline(),
        parse_mode="Markdown",
    )


@router.callback_query(F.data == "adm:close")
async def admin_close(callback: CallbackQuery, state: FSMContext) -> None:
    if not _admin_only_callback(callback):
        await callback.answer("غير مصرح", show_alert=True)
        return
    await state.clear()
    db = SessionLocal()
    try:
        user = db.query(User).filter_by(telegram_id=callback.from_user.id).first()
        lang = user.language if user else "ar"
        admin = is_admin(callback.from_user.id, callback.from_user.username)
    finally:
        db.close()
    await callback.message.delete()
    await callback.message.answer("تم إغلاق لوحة الإدارة.", reply_markup=main_menu(lang, admin))
    await callback.answer()


@router.callback_query(F.data == "adm:menu")
async def admin_menu(callback: CallbackQuery, state: FSMContext) -> None:
    if not _admin_only_callback(callback):
        await callback.answer("غير مصرح", show_alert=True)
        return
    await state.clear()
    await callback.message.edit_text(
        "🛠 **لوحة الإدارة**\nاختر القسم:",
        reply_markup=admin_main_inline(),
        parse_mode="Markdown",
    )
    await callback.answer()


@router.callback_query(F.data.startswith("adm:visas:"))
async def admin_visas(callback: CallbackQuery) -> None:
    if not _admin_only_callback(callback):
        await callback.answer("غير مصرح", show_alert=True)
        return
    page = int(callback.data.split(":")[-1])
    per_page = 5
    db = SessionLocal()
    try:
        q = db.query(VisaRequest).order_by(desc(VisaRequest.created_at))
        total = q.count()
        items = q.offset(page * per_page).limit(per_page).all()
        if not items:
            text = "لا توجد طلبات فيزا."
            kb = admin_main_inline()
        else:
            lines = [f"💳 طلبات الفيزا ({page + 1}/{(total - 1) // per_page + 1})"]
            for r in items:
                pay = f"{r.points_paid} نقطة" if r.payment_method == "points" else f"{r.stars_paid}⭐"
                lines.append(
                    f"\n#{r.id} | {r.status} | {pay}\n"
                    f"👤 {r.user.telegram_id} @{r.user.username or '—'}\n"
                    f"📝 {r.details[:120]}{'…' if len(r.details) > 120 else ''}"
                )
            text = "\n".join(lines)
            from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

            nav = []
            if page > 0:
                nav.append(
                    InlineKeyboardButton(text="◀️", callback_data=f"adm:visas:{page - 1}")
                )
            if (page + 1) * per_page < total:
                nav.append(
                    InlineKeyboardButton(text="▶️", callback_data=f"adm:visas:{page + 1}")
                )
            rows = [
                [InlineKeyboardButton(text=f"⚙️ فيزا #{r.id}", callback_data=f"adm:visa:{r.id}")]
                for r in items
            ]
            if nav:
                rows.append(nav)
            rows.append([InlineKeyboardButton(text="◀️ الإدارة", callback_data="adm:menu")])
            kb = InlineKeyboardMarkup(inline_keyboard=rows)
        await callback.message.edit_text(text, reply_markup=kb)
    finally:
        db.close()
    await callback.answer()


@router.callback_query(F.data.startswith("adm:visa:"))
async def admin_visa_detail(callback: CallbackQuery) -> None:
    if not _admin_only_callback(callback):
        await callback.answer("غير مصرح", show_alert=True)
        return
    if callback.data.count(":") != 2:
        await callback.answer("—", show_alert=True)
        return
    req_id = int(callback.data.split(":")[-1])
    db = SessionLocal()
    try:
        r = db.query(VisaRequest).filter_by(id=req_id).first()
        if not r:
            await callback.answer("غير موجود", show_alert=True)
            return
        pay = f"{r.points_paid} نقطة" if r.payment_method == "points" else f"{r.stars_paid} نجمة"
        text = (
            f"فيزا #{r.id}\n"
            f"الحالة: {r.status}\n"
            f"المستخدم: {r.user.telegram_id} @{r.user.username or '—'}\n"
            f"الدفع: {pay}\n"
            f"البيانات:\n{r.details}"
        )
        await callback.message.edit_text(text, reply_markup=visa_status_keyboard(r.id))
    finally:
        db.close()
    await callback.answer()


@router.callback_query(F.data == "adm:visa_stock")
async def admin_visa_stock_menu(callback: CallbackQuery) -> None:
    if not _admin_only_callback(callback):
        await callback.answer("غير مصرح", show_alert=True)
        return
    from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

    from app.services.visa_delivery import count_available_visas

    db = SessionLocal()
    try:
        total = db.query(VisaStock).count()
        available = count_available_visas(db)
        used = total - available
        text = (
            f"📦 مخزون الفيز\n\n"
            f"متاح: {available}\nمُسلَّم: {used}\nالإجمالي: {total}\n\n"
            "أضف فيزا جديدة (واحدة لكل رسالة). لإضافة عدة فيزات في رسالة واحدة افصل بينها بسطر:\n"
            "`---`"
        )
        kb = InlineKeyboardMarkup(
            inline_keyboard=[
                [InlineKeyboardButton(text="➕ إضافة فيزا", callback_data="adm:visa_stock_add")],
                [InlineKeyboardButton(text="📋 عرض المتاح", callback_data="adm:visa_stock_list")],
                [InlineKeyboardButton(text="◀️ الإدارة", callback_data="adm:menu")],
            ]
        )
        await callback.message.edit_text(text, reply_markup=kb, parse_mode="Markdown")
    finally:
        db.close()
    await callback.answer()


@router.callback_query(F.data == "adm:visa_stock_add")
async def admin_visa_stock_add_start(callback: CallbackQuery, state: FSMContext) -> None:
    if not _admin_only_callback(callback):
        return
    await state.set_state(AdminAddVisaStock.waiting_content)
    await callback.message.answer(
        "أرسل بيانات الفيزا (رسالة واحدة = فيزا واحدة).\n"
        "لإضافة أكثر من فيزا في نفس الرسالة ضع `---` بين كل فيزا وأخرى.\n"
        "أو /cancel للإلغاء.",
        parse_mode="Markdown",
    )
    await callback.answer()


@router.message(AdminAddVisaStock.waiting_content, F.text)
async def admin_visa_stock_add_save(message: Message, state: FSMContext) -> None:
    if not _admin_only_message(message):
        return
    if message.text.strip().lower() in ("/cancel", "cancel"):
        await state.clear()
        await message.answer("تم الإلغاء.")
        return
    raw = message.text.strip()
    parts = [p.strip() for p in raw.split("\n---\n") if p.strip()]
    if not parts and "---" in raw:
        parts = [p.strip() for p in raw.split("---") if p.strip()]
    if not parts:
        parts = [raw]
    db = SessionLocal()
    try:
        for content in parts:
            db.add(VisaStock(content=content, is_used=False))
        db.commit()
        from app.services.snapshot_hook import snapshot_db
        from app.services.visa_delivery import count_available_visas

        snapshot_db()
        avail = count_available_visas(db)
        await message.answer(f"✅ تمت إضافة {len(parts)} فيزا. المتاح الآن: {avail}")
    finally:
        db.close()
    await state.clear()


@router.callback_query(F.data == "adm:visa_stock_list")
async def admin_visa_stock_list(callback: CallbackQuery) -> None:
    if not _admin_only_callback(callback):
        return
    from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

    db = SessionLocal()
    try:
        items = (
            db.query(VisaStock)
            .filter_by(is_used=False)
            .order_by(VisaStock.id)
            .limit(20)
            .all()
        )
        if not items:
            text = "لا توجد فيزات متاحة في المخزون."
        else:
            lines = ["📋 الفيز المتاحة:"]
            for s in items:
                preview = s.content.replace("\n", " ")[:60]
                lines.append(f"\n#{s.id} — {preview}{'…' if len(s.content) > 60 else ''}")
            text = "\n".join(lines)
        kb = InlineKeyboardMarkup(
            inline_keyboard=[
                [InlineKeyboardButton(text="◀️ مخزون الفيز", callback_data="adm:visa_stock")]
            ]
        )
        await callback.message.edit_text(text, reply_markup=kb)
    finally:
        db.close()
    await callback.answer()


@router.callback_query(F.data.startswith("adm:visa_st:"))
async def admin_visa_set_status(callback: CallbackQuery, bot: Bot) -> None:
    if not _admin_only_callback(callback):
        await callback.answer("غير مصرح", show_alert=True)
        return
    _, _, req_id, status = callback.data.split(":", 3)
    db = SessionLocal()
    try:
        r = db.query(VisaRequest).filter_by(id=int(req_id)).first()
        if not r:
            await callback.answer("غير موجود", show_alert=True)
            return
        r.status = status
        db.commit()
        await notify_transfer_status(bot, r.user, r.id, status)
        await callback.answer(f"تم: {status}", show_alert=True)
        pay = f"{r.points_paid} نقطة" if r.payment_method == "points" else f"{r.stars_paid} نجمة"
        text = (
            f"فيزا #{r.id}\n"
            f"الحالة: {r.status}\n"
            f"المستخدم: {r.user.telegram_id}\n"
            f"الدفع: {pay}\n"
            f"البيانات:\n{r.details}"
        )
        await callback.message.edit_text(text, reply_markup=visa_status_keyboard(r.id))
    finally:
        db.close()


@router.callback_query(F.data.startswith("adm:transfers:"))
async def admin_transfers(callback: CallbackQuery) -> None:
    if not _admin_only_callback(callback):
        await callback.answer("غير مصرح", show_alert=True)
        return
    page = int(callback.data.split(":")[-1])
    per_page = 5
    db = SessionLocal()
    try:
        q = db.query(TransferRequest).order_by(desc(TransferRequest.created_at))
        total = q.count()
        items = q.offset(page * per_page).limit(per_page).all()
        if not items:
            text = "لا توجد طلبات."
            kb = admin_main_inline()
        else:
            lines = [f"📥 الطلبات ({page + 1}/{(total - 1) // per_page + 1})"]
            for r in items:
                lines.append(
                    f"\n#{r.id} | {r.status}\n"
                    f"👤 {r.user.telegram_id} @{r.user.username or '—'}\n"
                    f"🌍 {r.country.name_ar}\n"
                    f"📧 {r.account_name}\n"
                    f"🔑 {r.account_password}"
                )
            text = "\n".join(lines)
            from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

            nav = []
            if page > 0:
                nav.append(
                    InlineKeyboardButton(text="◀️", callback_data=f"adm:transfers:{page - 1}")
                )
            if (page + 1) * per_page < total:
                nav.append(
                    InlineKeyboardButton(text="▶️", callback_data=f"adm:transfers:{page + 1}")
                )
            rows = [[InlineKeyboardButton(text=f"⚙️ طلب #{r.id}", callback_data=f"adm:req:{r.id}")] for r in items]
            if nav:
                rows.append(nav)
            rows.append([InlineKeyboardButton(text="◀️ الإدارة", callback_data="adm:menu")])
            kb = InlineKeyboardMarkup(inline_keyboard=rows)
        await callback.message.edit_text(text, reply_markup=kb)
    finally:
        db.close()
    await callback.answer()


@router.callback_query(F.data.startswith("adm:req:"))
async def admin_req_detail(callback: CallbackQuery) -> None:
    if not _admin_only_callback(callback):
        await callback.answer("غير مصرح", show_alert=True)
        return
    req_id = int(callback.data.split(":")[-1])
    db = SessionLocal()
    try:
        r = db.query(TransferRequest).filter_by(id=req_id).first()
        if not r:
            await callback.answer("غير موجود", show_alert=True)
            return
        text = (
            f"طلب #{r.id}\n"
            f"الحالة: {r.status}\n"
            f"المستخدم: {r.user.telegram_id} @{r.user.username or '—'}\n"
            f"الدولة: {r.country.name_ar}\n"
            f"الحساب: {r.account_name}\n"
            f"كلمة المرور: {r.account_password}"
        )
        await callback.message.edit_text(text, reply_markup=transfer_status_keyboard(req_id))
    finally:
        db.close()
    await callback.answer()


def _parse_order_callback(data: str, prefix: str) -> tuple[str, int] | None:
    parts = data.split(":")
    # adm:umsg:12 (legacy transfer)
    if len(parts) == 3 and parts[1] == prefix:
        return "transfer", int(parts[2])
    if len(parts) == 4 and parts[1] == prefix:
        kind, req_id = parts[2], int(parts[3])
        if kind in ORDER_KINDS:
            return kind, req_id
    return None


@router.callback_query(F.data.startswith("adm:umsg:"))
async def admin_message_user_start(callback: CallbackQuery, state: FSMContext) -> None:
    if not _admin_only_callback(callback):
        await callback.answer("غير مصرح", show_alert=True)
        return
    parsed = _parse_order_callback(callback.data, "umsg")
    if not parsed:
        await callback.answer("طلب غير صالح", show_alert=True)
        return
    kind, req_id = parsed
    db = SessionLocal()
    try:
        order = load_order(db, kind, req_id)
        user = order_user(order)
        if not user:
            await callback.answer("غير موجود", show_alert=True)
            return
        kind_label = order_kind_label(kind, "ar")
        await state.update_data(
            msg_kind=kind,
            msg_req_id=req_id,
            msg_target_tid=user.telegram_id,
        )
        await state.set_state(AdminMessageUser.waiting_text)
        await callback.message.answer(
            f"💬 رسالة واحدة ({kind_label} #{req_id}):\n"
            f"المستخدم: `{user.telegram_id}` @{user.username or '—'}\n"
            "أرسل `/cancel` للإلغاء.",
            parse_mode="Markdown",
        )
        await callback.answer()
    finally:
        db.close()


@router.message(AdminMessageUser.waiting_text, F.text)
async def admin_message_user_send(message: Message, state: FSMContext, bot: Bot) -> None:
    if not _admin_only_message(message):
        return
    if message.text.strip().lower() == "/cancel":
        await state.clear()
        await message.answer("تم الإلغاء.")
        return
    data = await state.get_data()
    req_id = data.get("msg_req_id")
    kind = data.get("msg_kind", "transfer")
    target_tid = data.get("msg_target_tid")
    if not target_tid:
        await state.clear()
        await message.answer("انتهت الجلسة. افتح الطلب مرة أخرى.")
        return
    db = SessionLocal()
    try:
        user = db.query(User).filter_by(telegram_id=target_tid).first()
        if not user:
            await message.answer("المستخدم غير موجود في قاعدة البيانات.")
            return
        ok = await send_admin_message_to_user(
            bot, user, kind, int(req_id or 0), message.text.strip()
        )
        if ok:
            label = order_kind_label(kind, "ar")
            await message.answer(f"✅ تم الإرسال ({label} #{req_id}).")
        else:
            await message.answer(
                "❌ تعذّر الإرسال. ربما المستخدم حظر البوت أو لم يضغط Start."
            )
    finally:
        db.close()
    await state.clear()


@router.callback_query(F.data.startswith("adm:udisc:"))
async def admin_discussion_start(callback: CallbackQuery, state: FSMContext, bot: Bot) -> None:
    if not _admin_only_callback(callback):
        await callback.answer("غير مصرح", show_alert=True)
        return
    parsed = _parse_order_callback(callback.data, "udisc")
    if not parsed:
        await callback.answer("طلب غير صالح", show_alert=True)
        return
    kind, req_id = parsed
    db = SessionLocal()
    try:
        order = load_order(db, kind, req_id)
        user = order_user(order)
        if not user:
            await callback.answer("غير موجود", show_alert=True)
            return
        thread = open_discussion(
            db, user.id, callback.from_user.id, kind, req_id
        )
        kind_label = order_kind_label(kind, "ar")
        lang = user.language if user.language in ("ar", "en") else "ar"
        try:
            await bot.send_message(
                user.telegram_id,
                t(
                    lang,
                    "discussion_opened_user",
                    kind=order_kind_label(kind, lang),
                    req_id=req_id,
                ),
                parse_mode="Markdown",
            )
        except Exception:
            pass
        await state.set_state(AdminDiscussion.active)
        await state.update_data(disc_thread_id=thread.id)
        await callback.message.answer(
            t("ar", "discussion_opened_admin", kind=kind_label, req_id=req_id),
            reply_markup=discussion_admin_keyboard(thread.id),
            parse_mode="Markdown",
        )
        await callback.answer("وضع المناقشة مفعّل")
    finally:
        db.close()


@router.callback_query(F.data.startswith("adm:udisc_end:"))
async def admin_discussion_end(callback: CallbackQuery, state: FSMContext, bot: Bot) -> None:
    if not _admin_only_callback(callback):
        return
    thread_id = int(callback.data.split(":")[-1])
    db = SessionLocal()
    try:
        thread = get_thread_by_id(db, thread_id)
        if not thread or not thread.active:
            await callback.answer("المناقشة منتهية", show_alert=True)
            return
        if thread.admin_telegram_id != callback.from_user.id:
            await callback.answer("هذه المناقشة لإداري آخر", show_alert=True)
            return
        user = thread.user
        lang = user.language if user.language in ("ar", "en") else "ar"
        close_thread(db, thread)
        try:
            await bot.send_message(user.telegram_id, t(lang, "discussion_ended_user"))
        except Exception:
            pass
        await state.clear()
        await callback.message.answer(t("ar", "discussion_ended_admin"))
        await callback.answer()
    finally:
        db.close()


@router.message(AdminDiscussion.active, F.text)
async def admin_discussion_send(message: Message, state: FSMContext, bot: Bot) -> None:
    if not _admin_only_message(message):
        return
    if message.text.strip().lower() in {"/cancel", "/end"}:
        data = await state.get_data()
        thread_id = data.get("disc_thread_id")
        if thread_id:
            db = SessionLocal()
            try:
                thread = get_thread_by_id(db, int(thread_id))
                if thread and thread.active:
                    user = thread.user
                    lang = user.language if user.language in ("ar", "en") else "ar"
                    close_thread(db, thread)
                    try:
                        await bot.send_message(user.telegram_id, t(lang, "discussion_ended_user"))
                    except Exception:
                        pass
            finally:
                db.close()
        await state.clear()
        await message.answer(t("ar", "discussion_ended_admin"))
        return
    data = await state.get_data()
    thread_id = data.get("disc_thread_id")
    if not thread_id:
        await state.clear()
        await message.answer("انتهت المناقشة. افتحها من الطلب مرة أخرى.")
        return
    db = SessionLocal()
    try:
        thread = get_thread_by_id(db, int(thread_id))
        if not thread or not thread.active:
            await state.clear()
            await message.answer("المناقشة مغلقة.")
            return
        user = thread.user
        ok = await send_discussion_message_to_user(
            bot, user, thread.kind, thread.request_id, message.text.strip()
        )
        if ok:
            await message.answer(
                "✅ تم الإرسال.",
                reply_markup=discussion_admin_keyboard(thread.id),
            )
        else:
            await message.answer("❌ تعذّر الإرسال للمستخدم.")
    finally:
        db.close()


@router.message(AdminDiscussion.active, F.photo)
async def admin_discussion_send_photo(message: Message, state: FSMContext, bot: Bot) -> None:
    if not _admin_only_message(message):
        return
    data = await state.get_data()
    thread_id = data.get("disc_thread_id")
    if not thread_id:
        return
    db = SessionLocal()
    try:
        thread = get_thread_by_id(db, int(thread_id))
        if not thread or not thread.active:
            return
        user = thread.user
        lang = user.language if user.language in ("ar", "en") else "ar"
        label = order_kind_label(thread.kind, lang)
        cap = message.caption or ""
        header = t(lang, "discussion_admin_msg", kind=label, req_id=thread.request_id, body=cap or "—")
        try:
            await bot.send_photo(user.telegram_id, message.photo[-1].file_id, caption=header)
            await message.answer("✅ تم إرسال الصورة.", reply_markup=discussion_admin_keyboard(thread.id))
        except Exception:
            await message.answer("❌ تعذّر الإرسال.")
    finally:
        db.close()


@router.callback_query(F.data.startswith("adm:st:"))
async def admin_set_status(callback: CallbackQuery, bot: Bot) -> None:
    if not _admin_only_callback(callback):
        await callback.answer("غير مصرح", show_alert=True)
        return
    _, _, req_id, status = callback.data.split(":", 3)
    db = SessionLocal()
    try:
        r = db.query(TransferRequest).filter_by(id=int(req_id)).first()
        if r:
            r.status = status
            db.commit()
            await notify_transfer_status(bot, r.user, r.id, status)
            await callback.answer(f"تم: {status}", show_alert=True)
            text = (
                f"طلب #{r.id}\n"
                f"الحالة: {r.status}\n"
                f"المستخدم: {r.user.telegram_id}\n"
                f"الحساب: {r.account_name}"
            )
            await callback.message.edit_text(text, reply_markup=transfer_status_keyboard(r.id))
        else:
            await callback.answer("غير موجود", show_alert=True)
    finally:
        db.close()


@router.callback_query(F.data == "adm:countries")
async def admin_countries(callback: CallbackQuery) -> None:
    if not _admin_only_callback(callback):
        await callback.answer("غير مصرح", show_alert=True)
        return
    db = SessionLocal()
    try:
        items = db.query(Country).order_by(Country.sort_order).all()
        await callback.message.edit_text(
            "🌍 الدول — اختر للتعديل:",
            reply_markup=countries_admin_keyboard(items),
        )
    finally:
        db.close()
    await callback.answer()


@router.callback_query(F.data.startswith("adm:country:"))
async def admin_country_detail(callback: CallbackQuery) -> None:
    if not _admin_only_callback(callback):
        await callback.answer("غير مصرح", show_alert=True)
        return
    cid = int(callback.data.split(":")[-1])
    db = SessionLocal()
    try:
        c = db.query(Country).filter_by(id=cid).first()
        if not c:
            await callback.answer("—", show_alert=True)
            return
        text = f"{c.name_ar} / {c.name_en}\nالنقاط: {c.point_cost}\nنشط: {'نعم' if c.active else 'لا'}"
        await callback.message.edit_text(text, reply_markup=country_actions_keyboard(c.id, c.active))
    finally:
        db.close()
    await callback.answer()


@router.callback_query(F.data.startswith("adm:ctoggle:"))
async def admin_country_toggle(callback: CallbackQuery) -> None:
    if not _admin_only_callback(callback):
        return
    cid = int(callback.data.split(":")[-1])
    db = SessionLocal()
    try:
        c = db.query(Country).filter_by(id=cid).first()
        if c:
            c.active = not c.active
            db.commit()
            await callback.message.edit_reply_markup(
                reply_markup=country_actions_keyboard(c.id, c.active)
            )
    finally:
        db.close()
    await callback.answer("تم")


@router.callback_query(F.data.startswith("adm:ccost:"))
async def admin_country_cost_start(callback: CallbackQuery, state: FSMContext) -> None:
    if not _admin_only_callback(callback):
        return
    cid = int(callback.data.split(":")[-1])
    await state.set_state(AdminSetCountryCost.waiting_cost)
    await state.update_data(country_id=cid)
    await callback.message.answer("أرسل عدد النقاط الجديد لهذه الدولة:")
    await callback.answer()


@router.message(AdminSetCountryCost.waiting_cost, F.text)
async def admin_country_cost_save(message: Message, state: FSMContext) -> None:
    if not _admin_only_message(message):
        return
    try:
        cost = int(message.text.strip())
    except ValueError:
        await message.answer("أرسل رقمًا فقط.")
        return
    data = await state.get_data()
    db = SessionLocal()
    try:
        c = db.query(Country).filter_by(id=data["country_id"]).first()
        if c:
            c.point_cost = cost
            db.commit()
            await message.answer(f"✅ تم تحديث {c.name_ar} إلى {cost} نقطة.")
            from app.services.snapshot_hook import snapshot_db

            snapshot_db()
    finally:
        db.close()
    await state.clear()


@router.callback_query(F.data == "adm:tasks")
async def admin_tasks(callback: CallbackQuery) -> None:
    if not _admin_only_callback(callback):
        return
    db = SessionLocal()
    try:
        items = db.query(Task).order_by(Task.sort_order).all()
        await callback.message.edit_text("📋 المهام:", reply_markup=tasks_admin_keyboard(items))
    finally:
        db.close()
    await callback.answer()


@router.callback_query(F.data.startswith("adm:task:"))
async def admin_task_detail(callback: CallbackQuery) -> None:
    if not _admin_only_callback(callback):
        return
    tid = int(callback.data.split(":")[-1])
    db = SessionLocal()
    try:
        task = db.query(Task).filter_by(id=tid).first()
        if not task:
            await callback.answer("—", show_alert=True)
            return
        text = (
            f"{task.title_ar}\nChat: {task.chat_id}\nنقاط: {task.reward_points}\n"
            f"رابط: {task.invite_link or '—'}"
        )
        await callback.message.edit_text(text, reply_markup=task_actions_keyboard(tid, task.active))
    finally:
        db.close()
    await callback.answer()


@router.callback_query(F.data.startswith("adm:ttoggle:"))
async def admin_task_toggle(callback: CallbackQuery) -> None:
    if not _admin_only_callback(callback):
        return
    tid = int(callback.data.split(":")[-1])
    db = SessionLocal()
    try:
        task = db.query(Task).filter_by(id=tid).first()
        if task:
            task.active = not task.active
            db.commit()
            await callback.message.edit_reply_markup(
                reply_markup=task_actions_keyboard(tid, task.active)
            )
    finally:
        db.close()
    await callback.answer("تم")


@router.callback_query(F.data.startswith("adm:tdel:"))
async def admin_task_delete(callback: CallbackQuery) -> None:
    if not _admin_only_callback(callback):
        return
    tid = int(callback.data.split(":")[-1])
    db = SessionLocal()
    try:
        task = db.query(Task).filter_by(id=tid).first()
        if task:
            db.delete(task)
            db.commit()
        items = db.query(Task).order_by(Task.sort_order).all()
        await callback.message.edit_text("📋 المهام:", reply_markup=tasks_admin_keyboard(items))
    finally:
        db.close()
    await callback.answer("حُذفت")


@router.callback_query(F.data == "adm:task_new")
async def admin_task_new(callback: CallbackQuery, state: FSMContext) -> None:
    if not _admin_only_callback(callback):
        return
    await state.set_state(AdminAddTask.title_ar)
    await callback.message.answer("عنوان المهمة بالعربي:")
    await callback.answer()


@router.message(AdminAddTask.title_ar, F.text)
async def adm_task_ar(message: Message, state: FSMContext) -> None:
    if not _admin_only_message(message):
        return
    await state.update_data(title_ar=message.text.strip())
    await state.set_state(AdminAddTask.title_en)
    await message.answer("Title in English:")


@router.message(AdminAddTask.title_en, F.text)
async def adm_task_en(message: Message, state: FSMContext) -> None:
    if not _admin_only_message(message):
        return
    await state.update_data(title_en=message.text.strip())
    await state.set_state(AdminAddTask.chat_id)
    await message.answer("Chat ID (مثل -100... أو @channel):")


@router.message(AdminAddTask.chat_id, F.text)
async def adm_task_chat(message: Message, state: FSMContext) -> None:
    if not _admin_only_message(message):
        return
    await state.update_data(chat_id=message.text.strip())
    await state.set_state(AdminAddTask.reward)
    await message.answer("نقاط المكافأة (رقم):")


@router.message(AdminAddTask.reward, F.text)
async def adm_task_reward(message: Message, state: FSMContext) -> None:
    if not _admin_only_message(message):
        return
    try:
        reward = int(message.text.strip())
    except ValueError:
        await message.answer("رقم فقط.")
        return
    await state.update_data(reward=reward)
    await state.set_state(AdminAddTask.invite_link)
    await message.answer("رابط الانضمام (أو اكتب - لتخطيه):")


@router.message(AdminAddTask.invite_link, F.text)
async def adm_task_link(message: Message, state: FSMContext) -> None:
    if not _admin_only_message(message):
        return
    data = await state.get_data()
    link = message.text.strip()
    if link == "-":
        link = None
    db = SessionLocal()
    try:
        db.add(
            Task(
                title_ar=data["title_ar"],
                title_en=data["title_en"],
                chat_id=data["chat_id"],
                reward_points=data["reward"],
                invite_link=link,
                active=True,
            )
        )
        db.commit()
        await message.answer("✅ تمت إضافة المهمة.")
    finally:
        db.close()
    await state.clear()


def _mandatory_sub_admin_text(cfg) -> str:
    status = "مفعّل ✅" if cfg.enabled else "متوقف ⛔"
    chat = cfg.chat_id or "— لم يُعيَّن —"
    link = cfg.invite_link or "—"
    return (
        "📢 **الاشتراك الإجباري**\n\n"
        f"الحالة: {status}\n"
        f"Chat ID: `{chat}`\n"
        f"رابط القناة: {link}\n\n"
        "يجب أن يكون البوت **أدمن** في القناة/الجروب للتحقق.\n"
        "بعد التفعيل، المستخدم لا يرى القائمة حتى يشترك ويضغط تحقق."
    )


@router.callback_query(F.data == "adm:msub")
async def admin_mandatory_sub(callback: CallbackQuery, state: FSMContext) -> None:
    if not _admin_only_callback(callback):
        await callback.answer("غير مصرح", show_alert=True)
        return
    await state.clear()
    db = SessionLocal()
    try:
        cfg = get_mandatory_sub_config(db)
    finally:
        db.close()
    await callback.message.edit_text(
        _mandatory_sub_admin_text(cfg),
        reply_markup=mandatory_sub_admin_keyboard(cfg.enabled),
        parse_mode="Markdown",
    )
    await callback.answer()


@router.callback_query(F.data == "adm:msub_toggle")
async def admin_mandatory_sub_toggle(callback: CallbackQuery) -> None:
    if not _admin_only_callback(callback):
        await callback.answer("غير مصرح", show_alert=True)
        return
    db = SessionLocal()
    try:
        cfg = get_mandatory_sub_config(db)
        if not cfg.enabled and not cfg.chat_id:
            await callback.answer("عيّن Chat ID للقناة أولاً", show_alert=True)
            return
        new_val = "0" if cfg.enabled else "1"
        set_setting(db, KEY_ENABLED, new_val)
        cfg = get_mandatory_sub_config(db)
        await callback.message.edit_text(
            _mandatory_sub_admin_text(cfg),
            reply_markup=mandatory_sub_admin_keyboard(cfg.enabled),
            parse_mode="Markdown",
        )
        await callback.answer("تم التحديث")
    finally:
        db.close()


@router.callback_query(F.data == "adm:msub_chat")
async def admin_mandatory_sub_chat(callback: CallbackQuery, state: FSMContext) -> None:
    if not _admin_only_callback(callback):
        return
    await state.set_state(AdminMandatorySub.chat_id)
    await callback.message.answer(
        "أرسل **Chat ID** للقناة أو الجروب (مثل `-100123...` أو `@channel`):",
        parse_mode="Markdown",
    )
    await callback.answer()


@router.message(AdminMandatorySub.chat_id, F.text)
async def admin_mandatory_sub_chat_save(message: Message, state: FSMContext) -> None:
    if not _admin_only_message(message):
        return
    chat_id = message.text.strip()
    db = SessionLocal()
    try:
        set_setting(db, KEY_CHAT_ID, chat_id)
        await message.answer(f"✅ تم حفظ Chat ID: `{chat_id}`", parse_mode="Markdown")
    finally:
        db.close()
    await state.clear()


@router.callback_query(F.data == "adm:msub_link")
async def admin_mandatory_sub_link(callback: CallbackQuery, state: FSMContext) -> None:
    if not _admin_only_callback(callback):
        return
    await state.set_state(AdminMandatorySub.invite_link)
    await callback.message.answer("أرسل رابط القناة (t.me/...) أو اكتب `-` لحذف الرابط:")
    await callback.answer()


@router.message(AdminMandatorySub.invite_link, F.text)
async def admin_mandatory_sub_link_save(message: Message, state: FSMContext) -> None:
    if not _admin_only_message(message):
        return
    link = message.text.strip()
    if link == "-":
        link = ""
    db = SessionLocal()
    try:
        set_setting(db, KEY_INVITE_LINK, link)
        await message.answer("✅ تم حفظ رابط القناة." if link else "✅ تم حذف الرابط.")
    finally:
        db.close()
    await state.clear()


@router.callback_query(F.data == "adm:visa_price")
async def admin_visa_price_menu(callback: CallbackQuery, state: FSMContext) -> None:
    if not _admin_only_callback(callback):
        return
    await state.clear()
    db = SessionLocal()
    try:
        pts = get_setting(db, "visa_points", "15")
        stars = get_setting(db, "visa_stars", "15")
    finally:
        db.close()
    text = (
        "💰 **سعر الفيزا**\n\n"
        f"الدفع بالنقاط: **{pts}** نقطة\n"
        f"الدفع بالنجوم: **{stars}** نجمة\n\n"
        "اختر ما تريد تغييره:"
    )
    await callback.message.edit_text(
        text,
        reply_markup=visa_price_admin_keyboard(),
        parse_mode="Markdown",
    )
    await callback.answer()


@router.callback_query(F.data == "adm:visa_price_pts")
async def admin_visa_price_pts_start(callback: CallbackQuery, state: FSMContext) -> None:
    if not _admin_only_callback(callback):
        return
    db = SessionLocal()
    try:
        pts = get_setting(db, "visa_points", "15")
    finally:
        db.close()
    await state.set_state(AdminSetVisaPrice.waiting_points)
    await callback.message.answer(
        f"سعر النقاط الحالي: **{pts}**\nأرسل الرقم الجديد (1–10000):",
        parse_mode="Markdown",
    )
    await callback.answer()


@router.callback_query(F.data == "adm:visa_price_stars")
async def admin_visa_price_stars_start(callback: CallbackQuery, state: FSMContext) -> None:
    if not _admin_only_callback(callback):
        return
    db = SessionLocal()
    try:
        stars = get_setting(db, "visa_stars", "15")
    finally:
        db.close()
    await state.set_state(AdminSetVisaPrice.waiting_stars)
    await callback.message.answer(
        f"سعر النجوم الحالي: **{stars}**\nأرسل الرقم الجديد (1–10000):",
        parse_mode="Markdown",
    )
    await callback.answer()


@router.message(AdminSetVisaPrice.waiting_points, F.text)
async def admin_visa_price_pts_save(message: Message, state: FSMContext) -> None:
    if not _admin_only_message(message):
        return
    try:
        pts = int(message.text.strip())
    except ValueError:
        await message.answer("رقم فقط.")
        return
    if pts < 1 or pts > 10_000:
        await message.answer("من 1 إلى 10000.")
        return
    db = SessionLocal()
    try:
        set_setting(db, "visa_points", str(pts))
        from app.services.snapshot_hook import snapshot_db

        snapshot_db()
        await message.answer(f"✅ سعر الفيزا بالنقاط: **{pts}** نقطة", parse_mode="Markdown")
    finally:
        db.close()
    await state.clear()


@router.message(AdminSetVisaPrice.waiting_stars, F.text)
async def admin_visa_price_stars_save(message: Message, state: FSMContext) -> None:
    if not _admin_only_message(message):
        return
    try:
        stars = int(message.text.strip())
    except ValueError:
        await message.answer("رقم فقط.")
        return
    if stars < 1 or stars > 10_000:
        await message.answer("من 1 إلى 10000.")
        return
    db = SessionLocal()
    try:
        set_setting(db, "visa_stars", str(stars))
        from app.services.snapshot_hook import snapshot_db

        snapshot_db()
        await message.answer(f"✅ سعر الفيزا بالنجوم: **{stars}** نجمة", parse_mode="Markdown")
    finally:
        db.close()
    await state.clear()


@router.callback_query(F.data == "adm:referral")
async def admin_referral(callback: CallbackQuery, state: FSMContext) -> None:
    if not _admin_only_callback(callback):
        return
    db = SessionLocal()
    try:
        pts = get_setting(db, "referral_points", "25")
    finally:
        db.close()
    await callback.message.answer(f"نقاط الإحالة الحالية: **{pts}**\nأرسل الرقم الجديد في رسالة:", parse_mode="Markdown")
    await state.set_state(AdminSetReferral.waiting_points)
    await callback.answer()


@router.message(AdminSetReferral.waiting_points, F.text)
async def admin_referral_save(message: Message, state: FSMContext) -> None:
    if not _admin_only_message(message):
        return
    try:
        pts = int(message.text.strip())
    except ValueError:
        await message.answer("رقم فقط.")
        return
    db = SessionLocal()
    try:
        set_setting(db, "referral_points", str(pts))
        await message.answer(f"✅ نقاط الإحالة: {pts}")
    finally:
        db.close()
    await state.clear()


def _find_user_by_target(db, text: str) -> User | None:
    raw = text.strip()
    if raw.startswith("@"):
        return db.query(User).filter(User.username == raw[1:]).first()
    if raw.isdigit():
        tid = int(raw)
        return db.query(User).filter(User.telegram_id == tid).first()
    return db.query(User).filter(User.username == raw).first()


@router.callback_query(F.data == "adm:addpoints")
async def admin_add_points_start(callback: CallbackQuery, state: FSMContext) -> None:
    if not _admin_only_callback(callback):
        return
    await state.set_state(AdminAddPoints.target)
    await callback.message.answer(
        "أرسل **معرّف تيليجرام** (رقم) أو **@يوزرنيم** للشخص.\n"
        "يجب أن يكون قد فتح البوت مرة واحدة على الأقل.",
        parse_mode="Markdown",
    )
    await callback.answer()


@router.callback_query(F.data.startswith("adm:uprof:"))
async def admin_user_profile(callback: CallbackQuery) -> None:
    if not _admin_only_callback(callback):
        return
    uid = int(callback.data.split(":")[-1])
    db = SessionLocal()
    try:
        user = db.query(User).filter_by(id=uid).first()
        if not user:
            await callback.answer("غير موجود", show_alert=True)
            return
        status = "🚫 محظور" if user.is_banned else "✅ نشط"
        text = (
            f"👤 مستخدم\n"
            f"المعرّف: {user.telegram_id}\n"
            f"@{user.username or '—'}\n"
            f"النقاط: {user.points}\n"
            f"الحالة: {status}"
        )
        await callback.message.edit_text(
            text,
            reply_markup=user_admin_profile_keyboard(user.id, user.is_banned),
        )
    finally:
        db.close()
    await callback.answer()


def _stars_refund_list_markup(db, page: int, user_db_id: int | None):
    from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

    items, page, pages = paginate_star_orders(db, page, per_page=6, user_id=user_db_id)
    if user_db_id:
        user = db.query(User).filter_by(id=user_db_id).first()
        header = f"↩️ استرداد نجوم — {user.telegram_id if user else user_db_id}"
        page_cb = f"adm:stusr:{user_db_id}"
        back_row = [
            InlineKeyboardButton(text="◀️ المستخدم", callback_data=f"adm:uprof:{user_db_id}")
        ]
    else:
        header = "↩️ كل طلبات النجوم (سجلات الدفع + الطلبات القديمة)"
        page_cb = "adm:stars_all"
        back_row = [InlineKeyboardButton(text="◀️ استرداد النجوم", callback_data="adm:stars_menu")]
    lines = [header, f"صفحة {page + 1}/{pages}", ""]
    rows: list[list] = []
    if not items:
        lines.append("لا توجد طلبات نجوم لهذا العرض.")
    for item in items:
        state = "✅ مسترد" if item.refunded else "↩️ متاح"
        lines.append(
            f"• {item.title} | {item.stars}⭐ | 👤 {item.user_telegram_id} | {state}{item.hint}"
        )
        if item.callback_data:
            btn_text = f"↩️ {item.stars}⭐ {item.title[:22]}"
            rows.append([InlineKeyboardButton(text=btn_text, callback_data=item.callback_data)])
    nav = []
    if page > 0:
        nav.append(InlineKeyboardButton(text="◀️", callback_data=f"{page_cb}:{page - 1}"))
    if page < pages - 1:
        nav.append(InlineKeyboardButton(text="▶️", callback_data=f"{page_cb}:{page + 1}"))
    if nav:
        rows.append(nav)
    rows.append(back_row)
    return "\n".join(lines), InlineKeyboardMarkup(inline_keyboard=rows)


@router.callback_query(F.data == "adm:stars_menu")
async def admin_stars_refund_menu(callback: CallbackQuery) -> None:
    if not _admin_only_callback(callback):
        return
    await callback.message.edit_text(
        "↩️ **استرداد النجوم**\n\n"
        "• **كل طلبات النجوم**: كل الطلبات القديمة والجديدة (جائزة أسبوعية، Play Pass، شحن).\n"
        "• **بحث بمعرّف**: عرض طلبات مستخدم واحد.\n\n"
        "الاسترداد الحقيقي يتم عبر تيليجرام: النجوم تُخصم من رصيد **البوت** وتُعاد للمستخدم.\n"
        "إذا سحبت نجوم البوت إلى Fragment أو الرصيد غير كافٍ، الاسترداد يفشل.\n\n"
        "_ملاحظة: هذا مختلف عن «استعادة نسخة» (النسخ الاحتياطي)._",
        reply_markup=stars_refund_menu_keyboard(),
        parse_mode="Markdown",
    )
    await callback.answer()


@router.callback_query(F.data.startswith("adm:stars_all:"))
async def admin_stars_refund_all(callback: CallbackQuery) -> None:
    if not _admin_only_callback(callback):
        return
    page = int(callback.data.split(":")[-1])
    db = SessionLocal()
    try:
        text, kb = _stars_refund_list_markup(db, page, None)
        await callback.message.edit_text(text, reply_markup=kb)
    finally:
        db.close()
    await callback.answer()


@router.callback_query(F.data.startswith("adm:stusr:"))
async def admin_stars_refund_user_page(callback: CallbackQuery) -> None:
    if not _admin_only_callback(callback):
        return
    parts = callback.data.split(":")
    user_db_id = int(parts[2])
    page = int(parts[3])
    db = SessionLocal()
    try:
        text, kb = _stars_refund_list_markup(db, page, user_db_id)
        await callback.message.edit_text(text, reply_markup=kb)
    finally:
        db.close()
    await callback.answer()


@router.callback_query(F.data == "adm:stars_find")
async def admin_stars_refund_find(callback: CallbackQuery, state: FSMContext) -> None:
    if not _admin_only_callback(callback):
        return
    await state.set_state(AdminStarsRefund.waiting_user)
    await callback.message.answer(
        "أرسل **معرّف تيليجرام** (رقم) أو **@يوزرنيم** لعرض كل طلبات النجوم الخاصة به.",
        parse_mode="Markdown",
    )
    await callback.answer()


@router.message(AdminStarsRefund.waiting_user)
async def admin_stars_refund_find_user(message: Message, state: FSMContext) -> None:
    if not _admin_only_message(message):
        return
    db = SessionLocal()
    try:
        user = _find_user_by_target(db, message.text or "")
        if not user:
            await message.answer("لم يُعثر على مستخدم — تأكد أنه فتح البوت مرة واحدة.")
            return
        text, kb = _stars_refund_list_markup(db, 0, user.id)
        await message.answer(text, reply_markup=kb)
    finally:
        db.close()
    await state.clear()


@router.callback_query(F.data.startswith("adm:upstars:"))
async def admin_user_star_payments(callback: CallbackQuery) -> None:
    if not _admin_only_callback(callback):
        return
    user_db_id = int(callback.data.split(":")[-1])
    db = SessionLocal()
    try:
        user = db.query(User).filter_by(id=user_db_id).first()
        if not user:
            await callback.answer("غير موجود", show_alert=True)
            return
        text, kb = _stars_refund_list_markup(db, 0, user_db_id)
        await callback.message.edit_text(text, reply_markup=kb)
    finally:
        db.close()
    await callback.answer()


@router.callback_query(F.data.startswith("adm:oref:"))
async def admin_order_stars_refund(
    callback: CallbackQuery, bot: Bot, state: FSMContext
) -> None:
    if not _admin_only_callback(callback):
        return
    _, _, kind, req_id_s = callback.data.split(":", 3)
    req_id = int(req_id_s)
    db = SessionLocal()
    try:
        req = get_request_for_refund(db, kind, req_id)
        if not req or req.stars_paid <= 0 or req.stars_refunded:
            await callback.answer("غير متاح", show_alert=True)
            return
        payment = match_payment_to_request(db, req.user_id, kind, req.stars_paid, req.created_at)
        if not payment:
            await state.set_state(AdminStarsRefund.waiting_charge_id)
            await state.update_data(refund_kind=kind, refund_req_id=req_id)
            await callback.message.answer(
                f"لا يوجد سجل دفع مطابق تلقائياً.\n"
                f"أرسل **telegram_payment_charge_id** لاسترداد {req.stars_paid} نجمة "
                f"لطلب #{req_id} (مستخدم {req.user.telegram_id}).",
                parse_mode="Markdown",
            )
            await callback.answer()
            return
        ok, detail = await refund_star_payment_record(bot, db, payment)
        if ok:
            mark_request_stars_refunded(db, kind, req_id)
            await callback.answer("تم الاسترداد في تيليجرام", show_alert=True)
            await callback.message.answer(
                admin_refund_feedback(ok, detail, req.stars_paid, req.user.telegram_id),
                parse_mode="Markdown",
            )
        else:
            await callback.answer(
                admin_refund_feedback(ok, detail, req.stars_paid, req.user.telegram_id)[:180],
                show_alert=True,
            )
    finally:
        db.close()


@router.callback_query(F.data.startswith("adm:ocharge:"))
async def admin_order_charge_refund_start(
    callback: CallbackQuery, state: FSMContext
) -> None:
    if not _admin_only_callback(callback):
        return
    _, _, kind, req_id_s = callback.data.split(":", 3)
    req_id = int(req_id_s)
    db = SessionLocal()
    try:
        req = get_request_for_refund(db, kind, req_id)
        if not req or req.stars_paid <= 0 or req.stars_refunded:
            await callback.answer("غير متاح", show_alert=True)
            return
        await state.set_state(AdminStarsRefund.waiting_charge_id)
        await state.update_data(refund_kind=kind, refund_req_id=req_id)
        await callback.message.answer(
            f"أرسل **telegram_payment_charge_id** لاسترداد {req.stars_paid} نجمة\n"
            f"لطلب {kind} #{req_id} — المستخدم {req.user.telegram_id}.\n\n"
            "يُرسل من تيليجرام مع تفاصيل الدفع (للطلبات القديمة قبل تسجيل السجل).",
            parse_mode="Markdown",
        )
    finally:
        db.close()
    await callback.answer()


@router.message(AdminStarsRefund.waiting_charge_id)
async def admin_order_charge_refund_save(message: Message, state: FSMContext, bot: Bot) -> None:
    if not _admin_only_message(message):
        return
    data = await state.get_data()
    kind = data.get("refund_kind")
    req_id = data.get("refund_req_id")
    if not kind or not req_id:
        await state.clear()
        return
    db = SessionLocal()
    try:
        req = get_request_for_refund(db, kind, int(req_id))
        if not req:
            await message.answer("الطلب غير موجود.")
            await state.clear()
            return
        ok, detail = await refund_stars_by_charge_id(
            bot,
            db,
            req.user,
            (message.text or "").strip(),
            req.stars_paid,
            kind,
        )
        if ok:
            mark_request_stars_refunded(db, kind, int(req_id))
            await message.answer(
                admin_refund_feedback(ok, detail, req.stars_paid, req.user.telegram_id),
                parse_mode="Markdown",
            )
        else:
            await message.answer(
                "❌ " + admin_refund_feedback(ok, detail, req.stars_paid, req.user.telegram_id)
            )
    finally:
        db.close()
    await state.clear()


@router.callback_query(F.data.startswith("adm:srefund:"))
async def admin_refund_prompt(callback: CallbackQuery) -> None:
    if not _admin_only_callback(callback):
        return
    pay_id = int(callback.data.split(":")[-1])
    db = SessionLocal()
    try:
        payment = db.query(StarPayment).filter_by(id=pay_id).first()
        if not payment or payment.refunded:
            await callback.answer("غير متاح", show_alert=True)
            return
        user = payment.user
        label = payment_kind_label(payment.payment_kind, "ar")
        from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

        extra = ""
        if payment.payment_kind == "topup":
            extra = f"\nسيتم خصم {payment.stars_amount} نقطة من رصيده (شحن سابق)."
        charge_hint = ""
        cid = (payment.telegram_payment_charge_id or "").strip()
        if cid:
            charge_hint = f"\nCharge: `{cid[:20]}…`"
        elif payment.payment_kind != "topup":
            charge_hint = "\n⚠️ لا يوجد charge id محفوظ — قد تحتاج لصقه يدوياً."
        text = (
            f"تأكيد استرداد **{payment.stars_amount}** نجمة عبر تيليجرام؟\n"
            f"النوع: {label}\n"
            f"المستخدم: {user.telegram_id} @{user.username or '—'}"
            f"{extra}{charge_hint}"
        )
        kb = InlineKeyboardMarkup(
            inline_keyboard=[
                [
                    InlineKeyboardButton(
                        text="✅ تأكيد الاسترداد",
                        callback_data=f"adm:srefund_ok:{pay_id}",
                    ),
                    InlineKeyboardButton(text="❌ إلغاء", callback_data=f"adm:upstars:{user.id}"),
                ]
            ]
        )
        await callback.message.edit_text(text, reply_markup=kb, parse_mode="Markdown")
    finally:
        db.close()
    await callback.answer()


@router.callback_query(F.data.startswith("adm:srefund_ok:"))
async def admin_refund_execute(callback: CallbackQuery, bot: Bot) -> None:
    if not _admin_only_callback(callback):
        return
    pay_id = int(callback.data.split(":")[-1])
    db = SessionLocal()
    try:
        payment = db.query(StarPayment).filter_by(id=pay_id).first()
        if not payment:
            await callback.answer("غير موجود", show_alert=True)
            return
        user = payment.user
        ok, detail = await refund_star_payment_record(bot, db, payment)
        if ok:
            await callback.answer("تم الاسترداد في تيليجرام", show_alert=True)
            await callback.message.edit_text(
                admin_refund_feedback(ok, detail, payment.stars_amount, user.telegram_id),
                parse_mode="Markdown",
            )
        else:
            msg = admin_refund_feedback(ok, detail, payment.stars_amount, user.telegram_id)
            await callback.answer(msg[:180], show_alert=True)
    finally:
        db.close()


@router.callback_query(F.data.startswith("adm:uban:"))
async def admin_user_ban_toggle(callback: CallbackQuery) -> None:
    if not _admin_only_callback(callback):
        return
    parts = callback.data.split(":")
    uid = int(parts[2])
    ban = parts[3] == "1"
    db = SessionLocal()
    try:
        user = db.query(User).filter_by(id=uid).first()
        if not user:
            await callback.answer("غير موجود", show_alert=True)
            return
        if is_admin(user.telegram_id, user.username):
            await callback.answer("لا يمكن حظر إداري", show_alert=True)
            return
        user.is_banned = ban
        db.commit()
        status = "🚫 محظور" if user.is_banned else "✅ نشط"
        text = (
            f"👤 مستخدم\n"
            f"المعرّف: {user.telegram_id}\n"
            f"@{user.username or '—'}\n"
            f"النقاط: {user.points}\n"
            f"الحالة: {status}"
        )
        await callback.message.edit_text(
            text,
            reply_markup=user_admin_profile_keyboard(user.id, user.is_banned),
        )
        await callback.answer("تم الحظر" if ban else "تم إلغاء الحظر", show_alert=True)
    finally:
        db.close()


@router.callback_query(F.data == "adm:ban_user")
async def admin_ban_user_start(callback: CallbackQuery, state: FSMContext) -> None:
    if not _admin_only_callback(callback):
        return
    await state.set_state(AdminBanUser.waiting_target)
    await callback.message.answer(
        "🚫 **حظر مستخدم**\nأرسل **معرّف تيليجرام** (رقم) أو **@يوزرنيم**.\n"
        "لإلغاء الحظر استخدم نفس الطريقة من ملف المستخدم أو أرسل المعرّف ثم اختر إلغاء الحظر.",
        parse_mode="Markdown",
    )
    await callback.answer()


@router.message(AdminBanUser.waiting_target, F.text)
async def admin_ban_user_apply(message: Message, state: FSMContext) -> None:
    if not _admin_only_message(message):
        return
    db = SessionLocal()
    try:
        user = _find_user_by_target(db, message.text)
        if not user:
            await message.answer("لم أجد مستخدمًا. يجب أن يكون قد فتح البوت مرة واحدة.")
            await state.clear()
            return
        if is_admin(user.telegram_id, user.username):
            await message.answer("لا يمكن حظر إداري.")
            await state.clear()
            return
        user.is_banned = True
        db.commit()
        await message.answer(
            f"🚫 تم حظر {user.telegram_id} @{user.username or '—'}.\n"
            "لإلغاء الحظر: /admin → المستخدمون → اختره → إلغاء الحظر.",
            reply_markup=user_admin_profile_keyboard(user.id, True),
        )
    finally:
        db.close()
    await state.clear()


@router.callback_query(F.data.startswith("adm:uadd:"))
async def admin_add_points_user(callback: CallbackQuery, state: FSMContext) -> None:
    if not _admin_only_callback(callback):
        return
    uid = int(callback.data.split(":")[-1])
    await state.set_state(AdminAddPoints.amount)
    await state.update_data(user_db_id=uid)
    await callback.message.answer("كم نقطة تريد إضافتها؟ (رقم موجب)")
    await callback.answer()


@router.message(AdminAddPoints.target, F.text)
async def admin_add_points_target(message: Message, state: FSMContext) -> None:
    if not _admin_only_message(message):
        return
    db = SessionLocal()
    try:
        user = _find_user_by_target(db, message.text)
        if not user:
            await message.answer("لم أجد مستخدمًا. تأكد من الرقم/اليوزر أو اطلب منه فتح البوت أولًا.")
            return
        await state.update_data(user_db_id=user.id)
        tg_id, username, points = user.telegram_id, user.username, user.points
    finally:
        db.close()
    await state.set_state(AdminAddPoints.amount)
    await message.answer(
        f"المستخدم: {tg_id} @{username or '—'}\n"
        f"الرصيد الحالي: {points}\n\nكم نقطة تُضاف؟"
    )


@router.message(AdminAddPoints.amount, F.text)
async def admin_add_points_amount(message: Message, state: FSMContext, bot: Bot) -> None:
    if not _admin_only_message(message):
        return
    try:
        amount = int(message.text.strip())
    except ValueError:
        await message.answer("أرسل رقمًا صحيحًا.")
        return
    if amount <= 0:
        await message.answer("استخدم رقمًا موجبًا.")
        return
    data = await state.get_data()
    db = SessionLocal()
    try:
        user = db.query(User).filter_by(id=data["user_db_id"]).first()
        if not user:
            await message.answer("المستخدم غير موجود.")
            await state.clear()
            return
        user.points += amount
        db.commit()
        await message.answer(
            f"✅ تمت إضافة {amount} نقطة.\n"
            f"@{user.username or user.telegram_id} — الرصيد الآن: **{user.points}**",
            parse_mode="Markdown",
        )
        try:
            await bot.send_message(
                user.telegram_id,
                f"🎁 تم إضافة {amount} نقطة لحسابك.\nرصيدك الآن: {user.points} نقطة.",
            )
        except Exception:
            pass
    finally:
        db.close()
    await state.clear()


@router.callback_query(F.data == "adm:broadcast")
async def admin_broadcast_start(callback: CallbackQuery, state: FSMContext) -> None:
    if not _admin_only_callback(callback):
        await callback.answer("غير مصرح", show_alert=True)
        return
    await state.set_state(AdminBroadcast.waiting_content)
    await callback.message.answer(
        "📣 **إذاعة للمستخدمين**\n\n"
        "أرسل **نصًا** أو **صورة** (مع أو بدون تعليق) سيصل لكل من سجّل في البوت.\n"
        "أرسل `/cancel` للإلغاء.",
        parse_mode="Markdown",
    )
    await callback.answer()


@router.callback_query(F.data == "adm:broadcast_cancel")
async def admin_broadcast_cancel(callback: CallbackQuery, state: FSMContext) -> None:
    if not _admin_only_callback(callback):
        return
    await state.clear()
    await callback.message.edit_text("تم إلغاء الإذاعة.", reply_markup=admin_main_inline())
    await callback.answer()


@router.message(AdminBroadcast.waiting_content)
async def admin_broadcast_preview(message: Message, state: FSMContext) -> None:
    if not _admin_only_message(message):
        return
    if message.text and message.text.strip().lower() == "/cancel":
        await state.clear()
        await message.answer("تم الإلغاء.", reply_markup=admin_main_inline())
        return

    photo_id = None
    text = None
    if message.photo:
        photo_id = message.photo[-1].file_id
        text = (message.caption or "").strip()
    elif message.text:
        text = message.text.strip()
    else:
        await message.answer("أرسل نصًا أو صورة فقط.")
        return

    if not photo_id and not text:
        await message.answer("الرسالة فاضية. أرسل نصًا أو صورة بتعليق.")
        return

    await state.update_data(
        bc_photo=photo_id,
        bc_text=text,
    )
    db = SessionLocal()
    try:
        total = db.query(User).count()
    finally:
        db.close()

    preview = text[:400] + ("…" if text and len(text) > 400 else "")
    kind = "🖼 صورة" if photo_id else "📝 نص"
    await message.answer(
        f"**معاينة الإذاعة** ({kind})\n\n"
        f"{preview or '—'}\n\n"
        f"سيُرسل إلى **{total}** مستخدم.\n"
        "تأكيد الإرسال؟",
        parse_mode="Markdown",
        reply_markup=broadcast_confirm_keyboard(),
    )


@router.callback_query(F.data == "adm:broadcast_send")
async def admin_broadcast_send(callback: CallbackQuery, state: FSMContext, bot: Bot) -> None:
    if not _admin_only_callback(callback):
        await callback.answer("غير مصرح", show_alert=True)
        return
    data = await state.get_data()
    photo_id = data.get("bc_photo")
    text = data.get("bc_text") or ""
    if not photo_id and not text.strip():
        await callback.answer("لا توجد رسالة. ابدأ من جديد.", show_alert=True)
        await state.clear()
        return

    await callback.message.edit_text("⏳ جاري الإرسال… قد يستغرق دقائق حسب عدد المستخدمين.")
    await callback.answer()

    db = SessionLocal()
    try:
        total, ok, failed = await broadcast_message(
            bot,
            db,
            text=text if not photo_id else None,
            photo_file_id=photo_id,
            caption=text if photo_id else None,
        )
    finally:
        db.close()
    await state.clear()
    await callback.message.answer(
        f"📣 **انتهت الإذاعة**\n"
        f"• المسجّلين: {total}\n"
        f"• وصلت: {ok}\n"
        f"• فشل (حظر / لم يفتح البوت): {failed}",
        parse_mode="Markdown",
        reply_markup=admin_main_inline(),
    )


@router.callback_query(F.data.startswith("adm:users:"))
async def admin_users(callback: CallbackQuery) -> None:
    if not _admin_only_callback(callback):
        return
    page = int(callback.data.split(":")[-1])
    per_page = 10
    db = SessionLocal()
    try:
        q = db.query(User).order_by(desc(User.created_at))
        total = q.count()
        users = q.offset(page * per_page).limit(per_page).all()
        lines = ["👥 المستخدمون"]
        for u in users:
            flag = " 🚫" if u.is_banned else ""
            lines.append(f"• {u.telegram_id} @{u.username or '—'} — {u.points} نقطة{flag}")
        from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

        nav = []
        if page > 0:
            nav.append(InlineKeyboardButton(text="◀️", callback_data=f"adm:users:{page - 1}"))
        if (page + 1) * per_page < total:
            nav.append(InlineKeyboardButton(text="▶️", callback_data=f"adm:users:{page + 1}"))
        rows = []
        for u in users:
            prefix = "🚫" if u.is_banned else "👤"
            label = f"{prefix} @{u.username}" if u.username else f"{prefix} {u.telegram_id}"
            rows.append(
                [InlineKeyboardButton(text=label, callback_data=f"adm:uprof:{u.id}")]
            )
        if nav:
            rows.append(nav)
        rows.append(
            [
                InlineKeyboardButton(text="💎 إضافة نقاط", callback_data="adm:addpoints"),
                InlineKeyboardButton(text="🚫 حظر بالمعرّف", callback_data="adm:ban_user"),
            ]
        )
        rows.append([InlineKeyboardButton(text="◀️ الإدارة", callback_data="adm:menu")])
        await callback.message.edit_text("\n".join(lines), reply_markup=InlineKeyboardMarkup(inline_keyboard=rows))
    finally:
        db.close()
    await callback.answer()


@router.callback_query(F.data == "adm:push_github")
async def admin_push_github(callback: CallbackQuery) -> None:
    if not _admin_only_callback(callback):
        await callback.answer("غير مصرح", show_alert=True)
        return
    from app.services.backup_export import build_backup_payload
    from app.services.github_seed_sync import github_backup_configured, push_seed_to_github

    if not github_backup_configured():
        await callback.answer(
            "أضف GITHUB_BACKUP_TOKEN على Render (صلاحية الكتابة على المستودع)",
            show_alert=True,
        )
        return
    db = SessionLocal()
    try:
        payload = build_backup_payload(db)
        n = len(payload.get("users") or [])
    finally:
        db.close()
    ok = push_seed_to_github(payload, force=True)
    if ok:
        await callback.message.answer(f"☁️ تم رفع النسخة الحالية لـ GitHub ({n} مستخدم).")
        await callback.answer("تم الرفع")
    else:
        await callback.answer("فشل الرفع — راجع السجلات", show_alert=True)


@router.callback_query(F.data == "adm:reload_seed")
async def admin_reload_seed(callback: CallbackQuery) -> None:
    if not _admin_only_callback(callback):
        await callback.answer("غير مصرح", show_alert=True)
        return
    db = SessionLocal()
    try:
        from app.services.github_seed_sync import fetch_seed_from_github
        from app.services.backup_export import import_backup_payload
        from app.services.startup_seed import persist_runtime_snapshot

        remote = fetch_seed_from_github()
        if remote:
            result = import_backup_payload(db, remote)
        else:
            from app.services.startup_seed import force_restore_bundled_seed

            result = force_restore_bundled_seed(db)
        if result is None:
            await callback.answer("لا توجد نسخة startup_seed على السيرفر", show_alert=True)
            return
        users_n, tasks_n, transfers_n = result
        persist_runtime_snapshot(db)
        await callback.message.answer(
            f"♻️ تم جلب آخر نسخة من GitHub (`startup_seed.json`).\n"
            f"المستخدمون: {users_n}\nالمهام: {tasks_n}\nطلبات التحويل: {transfers_n}",
            parse_mode="Markdown",
        )
    finally:
        db.close()
    await callback.answer("تمت الاستعادة")


@router.callback_query(F.data == "adm:backup")
async def admin_backup(callback: CallbackQuery) -> None:
    if not _admin_only_callback(callback):
        await callback.answer("غير مصرح", show_alert=True)
        return
    db = SessionLocal()
    try:
        data = backup_json_bytes(db)
        n_users = db.query(User).count()
    finally:
        db.close()
    name = f"bot_backup_{datetime.utcnow().strftime('%Y%m%d_%H%M')}.json"
    await callback.message.answer_document(
        BufferedInputFile(data, filename=name),
        caption=f"📥 نسخة احتياطية\nالمستخدمون: {n_users}\nاحفظ الملف قبل أي تحديث على Render.",
    )
    await callback.answer("تم إرسال النسخة")


@router.callback_query(F.data == "adm:restore")
async def admin_restore_start(callback: CallbackQuery, state: FSMContext) -> None:
    if not _admin_only_callback(callback):
        await callback.answer("غير مصرح", show_alert=True)
        return
    await state.set_state(AdminRestoreBackup.waiting_file)
    await callback.message.answer(
        "📤 أرسل ملف **bot_backup_….json** (النسخة الاحتياطية) كمستند.\n"
        "سيتم استبدال النقاط والإعدادات والمهام بمحتوى الملف.",
        parse_mode="Markdown",
    )
    await callback.answer()


@router.message(AdminRestoreBackup.waiting_file, F.document)
async def admin_restore_file(message: Message, state: FSMContext, bot: Bot) -> None:
    if not _admin_only_message(message):
        return
    doc = message.document
    if not doc or not (doc.file_name or "").endswith(".json"):
        await message.answer("أرسل ملف JSON فقط (.json)")
        return
    file = await bot.get_file(doc.file_id)
    raw = await bot.download_file(file.file_path)
    try:
        payload = json.loads(raw.read().decode("utf-8"))
    except Exception:
        await message.answer("ملف غير صالح.")
        return
    db = SessionLocal()
    try:
        users_n, tasks_n, transfers_n = import_backup_payload(db, payload)
        from app.services.startup_seed import persist_runtime_snapshot

        persist_runtime_snapshot(db)
    finally:
        db.close()
    await state.clear()
    await message.answer(
        f"✅ تمت الاستعادة.\nالمستخدمون: {users_n}\nالمهام: {tasks_n}\nالطلبات: {transfers_n}",
        reply_markup=admin_main_inline(),
    )


@router.callback_query(F.data == "adm:promos")
async def admin_promos(callback: CallbackQuery) -> None:
    if not _admin_only_callback(callback):
        return
    db = SessionLocal()
    try:
        items = db.query(PromoCode).order_by(PromoCode.created_at.desc()).all()
        await callback.message.edit_text(
            "🎁 أكواد البرومو — اختر للتعديل:",
            reply_markup=promos_admin_keyboard(items),
        )
    finally:
        db.close()
    await callback.answer()


@router.callback_query(F.data == "adm:promo_new")
async def admin_promo_new(callback: CallbackQuery, state: FSMContext) -> None:
    if not _admin_only_callback(callback):
        return
    await state.set_state(AdminAddPromo.code)
    await callback.message.answer(
        "أرسل **كود البرومو** (حروف وأرقام، بدون مسافات):\nمثال: `WELCOME50`",
        parse_mode="Markdown",
    )
    await callback.answer()


@router.message(AdminAddPromo.code, F.text)
async def admin_promo_code(message: Message, state: FSMContext) -> None:
    if not _admin_only_message(message):
        return
    code = normalize_promo_code(message.text)
    if not code:
        await message.answer("كود غير صالح.")
        return
    db = SessionLocal()
    try:
        if db.query(PromoCode).filter_by(code=code).first():
            await message.answer("هذا الكود موجود مسبقاً. اختر كوداً آخر.")
            return
    finally:
        db.close()
    await state.update_data(promo_code=code)
    await state.set_state(AdminAddPromo.points)
    await message.answer("كم **نقطة** يحصل عليها المستخدم؟ (رقم)", parse_mode="Markdown")


@router.message(AdminAddPromo.points, F.text)
async def admin_promo_points(message: Message, state: FSMContext) -> None:
    if not _admin_only_message(message):
        return
    try:
        points = int(message.text.strip())
    except ValueError:
        await message.answer("رقم فقط.")
        return
    if points <= 0:
        await message.answer("استخدم رقمًا موجبًا.")
        return
    await state.update_data(promo_points=points)
    await state.set_state(AdminAddPromo.max_uses)
    await message.answer(
        "أقصى عدد **استخدامات** للكود (0 = غير محدود):\nمثال: `100` أو `0`",
        parse_mode="Markdown",
    )


@router.message(AdminAddPromo.max_uses, F.text)
async def admin_promo_max_uses(message: Message, state: FSMContext) -> None:
    if not _admin_only_message(message):
        return
    try:
        max_uses = int(message.text.strip())
    except ValueError:
        await message.answer("رقم فقط.")
        return
    if max_uses < 0:
        await message.answer("استخدم 0 أو أكثر.")
        return
    data = await state.get_data()
    db = SessionLocal()
    try:
        db.add(
            PromoCode(
                code=data["promo_code"],
                points=data["promo_points"],
                max_uses=max_uses,
                used_count=0,
                active=True,
            )
        )
        db.commit()
        from app.services.snapshot_hook import snapshot_db

        snapshot_db()
        await message.answer(
            f"✅ تم إنشاء الكود `{data['promo_code']}` — **{data['promo_points']}** نقطة.",
            parse_mode="Markdown",
        )
    finally:
        db.close()
    await state.clear()


@router.callback_query(F.data.startswith("adm:promo:"))
async def admin_promo_detail(callback: CallbackQuery) -> None:
    if not _admin_only_callback(callback):
        return
    pid = int(callback.data.split(":")[-1])
    db = SessionLocal()
    try:
        p = db.query(PromoCode).filter_by(id=pid).first()
        if not p:
            await callback.answer("—", show_alert=True)
            return
        uses = f"{p.used_count}"
        if p.max_uses > 0:
            uses += f" / {p.max_uses}"
        else:
            uses += " / ∞"
        exp = p.expires_at.isoformat() if p.expires_at else "—"
        text = (
            f"كود: `{p.code}`\n"
            f"النقاط: {p.points}\n"
            f"الاستخدامات: {uses}\n"
            f"نشط: {'نعم' if p.active else 'لا'}\n"
            f"ينتهي: {exp}"
        )
        await callback.message.edit_text(
            text, reply_markup=promo_actions_keyboard(p.id, p.active), parse_mode="Markdown"
        )
    finally:
        db.close()
    await callback.answer()


@router.callback_query(F.data.startswith("adm:promo_toggle:"))
async def admin_promo_toggle(callback: CallbackQuery) -> None:
    if not _admin_only_callback(callback):
        return
    pid = int(callback.data.split(":")[-1])
    db = SessionLocal()
    try:
        p = db.query(PromoCode).filter_by(id=pid).first()
        if p:
            p.active = not p.active
            db.commit()
            await callback.message.edit_reply_markup(
                reply_markup=promo_actions_keyboard(p.id, p.active)
            )
    finally:
        db.close()
    await callback.answer("تم")


@router.callback_query(F.data.startswith("adm:promo_del:"))
async def admin_promo_del(callback: CallbackQuery) -> None:
    if not _admin_only_callback(callback):
        return
    pid = int(callback.data.split(":")[-1])
    db = SessionLocal()
    try:
        p = db.query(PromoCode).filter_by(id=pid).first()
        if p:
            db.query(PromoRedemption).filter_by(promo_id=p.id).delete()
            db.delete(p)
            db.commit()
        items = db.query(PromoCode).order_by(PromoCode.created_at.desc()).all()
        await callback.message.edit_text(
            "🎁 أكواد البرومو:",
            reply_markup=promos_admin_keyboard(items),
        )
    finally:
        db.close()
    await callback.answer("حُذف")


def _box_label(req: BoxRequest) -> str:
    if req.custom_title:
        return req.custom_title
    if req.box_game:
        return req.box_game.title
    return "—"


@router.callback_query(F.data.startswith("adm:boxes:"))
async def admin_boxes(callback: CallbackQuery) -> None:
    if not _admin_only_callback(callback):
        await callback.answer("غير مصرح", show_alert=True)
        return
    page = int(callback.data.split(":")[-1])
    per_page = 5
    db = SessionLocal()
    try:
        q = db.query(BoxRequest).order_by(desc(BoxRequest.created_at))
        total = q.count()
        items = q.offset(page * per_page).limit(per_page).all()
        if not items:
            text = "لا توجد طلبات صناديق."
            kb = admin_main_inline()
        else:
            pages = max(1, (total - 1) // per_page + 1)
            lines = [f"📦 طلبات الصناديق ({page + 1}/{pages})"]
            for r in items:
                lines.append(
                    f"\n#{r.id} | {r.status}\n"
                    f"👤 {r.user.telegram_id} @{r.user.username or '—'}\n"
                    f"🎮 {_box_label(r)}\n"
                    f"📧 {r.account_name}\n"
                    f"🔑 {r.account_password}"
                )
            text = "\n".join(lines)
            from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

            nav = []
            if page > 0:
                nav.append(InlineKeyboardButton(text="◀️", callback_data=f"adm:boxes:{page - 1}"))
            if (page + 1) * per_page < total:
                nav.append(InlineKeyboardButton(text="▶️", callback_data=f"adm:boxes:{page + 1}"))
            rows = [
                [InlineKeyboardButton(text=f"⚙️ صندوق #{r.id}", callback_data=f"adm:boxreq:{r.id}")]
                for r in items
            ]
            if nav:
                rows.append(nav)
            rows.append([InlineKeyboardButton(text="◀️ الإدارة", callback_data="adm:menu")])
            kb = InlineKeyboardMarkup(inline_keyboard=rows)
        await callback.message.edit_text(text, reply_markup=kb)
    finally:
        db.close()
    await callback.answer()


@router.callback_query(F.data.startswith("adm:boxreq:"))
async def admin_box_detail(callback: CallbackQuery) -> None:
    if not _admin_only_callback(callback):
        await callback.answer("غير مصرح", show_alert=True)
        return
    req_id = int(callback.data.split(":")[-1])
    db = SessionLocal()
    try:
        r = db.query(BoxRequest).filter_by(id=req_id).first()
        if not r:
            await callback.answer("غير موجود", show_alert=True)
            return
        text = (
            f"صندوق #{r.id}\n"
            f"الحالة: {r.status}\n"
            f"المستخدم: {r.user.telegram_id} @{r.user.username or '—'}\n"
            f"اللعبة: {_box_label(r)}\n"
            f"الحساب: {r.account_name}\n"
            f"كلمة المرور: {r.account_password}"
        )
        await callback.message.edit_text(text, reply_markup=box_status_keyboard(req_id))
    finally:
        db.close()
    await callback.answer()


@router.callback_query(F.data.startswith("adm:bst:"))
async def admin_box_status(callback: CallbackQuery) -> None:
    if not _admin_only_callback(callback):
        await callback.answer("غير مصرح", show_alert=True)
        return
    _, _, req_id, status = callback.data.split(":", 3)
    db = SessionLocal()
    try:
        r = db.query(BoxRequest).filter_by(id=int(req_id)).first()
        if r:
            r.status = status
            db.commit()
            await callback.answer(f"تم: {status}", show_alert=True)
            text = (
                f"صندوق #{r.id}\n"
                f"الحالة: {r.status}\n"
                f"المستخدم: {r.user.telegram_id}\n"
                f"الحساب: {r.account_name}"
            )
            await callback.message.edit_text(text, reply_markup=box_status_keyboard(r.id))
        else:
            await callback.answer("غير موجود", show_alert=True)
    finally:
        db.close()


def _play_pass_slots_line(db) -> str:
    from app.services.play_pass import play_pass_max_slots, play_pass_slots_remaining, play_pass_slots_used

    cap = play_pass_max_slots(db)
    if cap <= 0:
        return "🪑 الأماكن: غير محدود (0 = غير محدود)"
    used = play_pass_slots_used(db)
    rem = play_pass_slots_remaining(db) or 0
    return f"🪑 الأماكن: {used}/{cap} مستخدم — متبقي {rem}"


@router.callback_query(F.data.startswith("adm:playpass:"))
async def admin_playpass_list(callback: CallbackQuery) -> None:
    if not _admin_only_callback(callback):
        await callback.answer("غير مصرح", show_alert=True)
        return
    page = int(callback.data.split(":")[-1])
    per_page = 5
    db = SessionLocal()
    try:
        from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

        slots_line = _play_pass_slots_line(db)
        q = db.query(PlayPassRequest).order_by(desc(PlayPassRequest.created_at))
        total = q.count()
        items = q.offset(page * per_page).limit(per_page).all()
        has_prev = page > 0
        has_next = (page + 1) * per_page < total
        if not items:
            text = f"👨‍👩‍👧 Play Pass\n{slots_line}\n\nلا توجد طلبات."
            kb = playpass_admin_list_keyboard(page, has_prev, has_next)
        else:
            pages = max(1, (total - 1) // per_page + 1)
            lines = [f"👨‍👩‍👧 Play Pass ({page + 1}/{pages})", slots_line]
            for r in items:
                pay = f"{r.points_paid} نقطة" if r.points_paid else f"{r.stars_paid} نجوم"
                lines.append(
                    f"\n#{r.id} | {r.status}\n"
                    f"👤 {r.user.telegram_id} @{r.user.username or '—'}\n"
                    f"💳 {pay}\n"
                    f"📧 {r.account_name}\n"
                    f"🔑 {r.account_password}"
                )
            text = "\n".join(lines)
            rows = [
                [InlineKeyboardButton(text=f"⚙️ #{r.id}", callback_data=f"adm:ppreq:{r.id}")]
                for r in items
            ]
            footer = playpass_admin_list_keyboard(page, has_prev, has_next)
            kb = InlineKeyboardMarkup(inline_keyboard=rows + footer.inline_keyboard)
        await callback.message.edit_text(text, reply_markup=kb)
    finally:
        db.close()
    await callback.answer()


@router.callback_query(F.data == "adm:playpass_slots")
async def admin_playpass_slots(callback: CallbackQuery, state: FSMContext) -> None:
    if not _admin_only_callback(callback):
        return
    db = SessionLocal()
    try:
        from app.services.play_pass import play_pass_max_slots, play_pass_slots_used

        cap = play_pass_max_slots(db)
        used = play_pass_slots_used(db)
        cap_label = "غير محدود" if cap <= 0 else str(cap)
    finally:
        db.close()
    await state.set_state(AdminSetPlayPassSlots.waiting_slots)
    await callback.message.answer(
        f"🪑 Play Pass — الأماكن\n"
        f"المستخدم حالياً: {used}\n"
        f"الحد الأقصى: {cap_label}\n\n"
        "أرسل عدد الأماكن الكلي (مثلاً 5).\n"
        "أرسل **0** لجعلها غير محدودة.",
        parse_mode="Markdown",
    )
    await callback.answer()


@router.message(AdminSetPlayPassSlots.waiting_slots, F.text)
async def admin_playpass_slots_save(message: Message, state: FSMContext) -> None:
    if not _admin_only_message(message):
        return
    try:
        slots = int(message.text.strip())
    except ValueError:
        await message.answer("رقم فقط.")
        return
    if slots < 0:
        await message.answer("استخدم 0 أو أكثر.")
        return
    db = SessionLocal()
    try:
        set_setting(db, "play_pass_max_slots", str(slots))
        db.commit()
        from app.services.play_pass import play_pass_slots_remaining, play_pass_slots_used

        used = play_pass_slots_used(db)
        if slots <= 0:
            await message.answer("✅ Play Pass: أماكن غير محدودة.")
        else:
            rem = play_pass_slots_remaining(db) or 0
            await message.answer(f"✅ الحد: {slots} مكان — مستخدم {used} — متبقي {rem}.")
    finally:
        db.close()
    await state.clear()


def _play_pass_settings_text(db) -> str:
    from app.services.play_pass import play_pass_max_slots, play_pass_slots_remaining, play_pass_slots_used

    stars = get_setting(db, "play_pass_stars", "20")
    cap = play_pass_max_slots(db)
    used = play_pass_slots_used(db)
    if cap <= 0:
        cap_line = f"🪑 الأماكن: غير محدود — مستخدم {used}"
    else:
        rem = play_pass_slots_remaining(db) or 0
        cap_line = f"🪑 الأماكن: {used}/{cap} — متبقي {rem}"
    return f"⚙️ إعدادات Play Pass\n⭐ سعر النجوم: **{stars}**\n{cap_line}"


@router.callback_query(F.data == "adm:playpass_cfg")
async def admin_playpass_cfg(callback: CallbackQuery) -> None:
    if not _admin_only_callback(callback):
        return
    db = SessionLocal()
    try:
        text = _play_pass_settings_text(db)
    finally:
        db.close()
    await callback.message.edit_text(
        text,
        reply_markup=playpass_admin_settings_keyboard(),
        parse_mode="Markdown",
    )
    await callback.answer()


@router.callback_query(F.data == "adm:playpass_stars")
async def admin_playpass_stars(callback: CallbackQuery, state: FSMContext) -> None:
    if not _admin_only_callback(callback):
        return
    db = SessionLocal()
    try:
        stars = get_setting(db, "play_pass_stars", "20")
    finally:
        db.close()
    await state.set_state(AdminSetPlayPassStars.waiting_stars)
    await callback.message.answer(
        f"⭐ سعر Play Pass بالنجوم الحالي: **{stars}**\nأرسل الرقم الجديد:",
        parse_mode="Markdown",
    )
    await callback.answer()


@router.message(AdminSetPlayPassStars.waiting_stars, F.text)
async def admin_playpass_stars_save(message: Message, state: FSMContext) -> None:
    if not _admin_only_message(message):
        return
    try:
        stars = int(message.text.strip())
    except ValueError:
        await message.answer("رقم فقط.")
        return
    if stars < 1:
        await message.answer("استخدم 1 أو أكثر.")
        return
    db = SessionLocal()
    try:
        set_setting(db, "play_pass_stars", str(stars))
        db.commit()
        await message.answer(f"✅ Play Pass: {stars} نجوم لكل طلب.")
    finally:
        db.close()
    await state.clear()


@router.callback_query(F.data.startswith("adm:pp_slot:"))
async def admin_playpass_slot_delta(callback: CallbackQuery) -> None:
    if not _admin_only_callback(callback):
        return
    delta = int(callback.data.split(":")[-1])
    db = SessionLocal()
    try:
        from app.services.play_pass import adjust_play_pass_max_slots, play_pass_slots_used

        new_cap, err = adjust_play_pass_max_slots(db, delta)
        if err == "unlimited":
            await callback.answer("الأماكن غير محدودة — استخدم «تعيين عدد» أو ➕ مكان", show_alert=True)
            return
        used = play_pass_slots_used(db)
        if new_cap <= 0:
            cap_msg = "غير محدود"
        else:
            cap_msg = f"{used}/{new_cap}"
        text = _play_pass_settings_text(db)
        await callback.message.edit_text(
            text,
            reply_markup=playpass_admin_settings_keyboard(),
            parse_mode="Markdown",
        )
        await callback.answer(f"تم — الأماكن: {cap_msg}", show_alert=True)
    finally:
        db.close()


@router.callback_query(F.data.startswith("adm:ppreq:"))
async def admin_playpass_detail(callback: CallbackQuery) -> None:
    if not _admin_only_callback(callback):
        await callback.answer("غير مصرح", show_alert=True)
        return
    req_id = int(callback.data.split(":")[-1])
    db = SessionLocal()
    try:
        r = db.query(PlayPassRequest).filter_by(id=req_id).first()
        if not r:
            await callback.answer("غير موجود", show_alert=True)
            return
        pay = f"{r.points_paid} نقطة" if r.points_paid else f"{r.stars_paid} نجوم"
        text = (
            f"Play Pass #{r.id}\n"
            f"الحالة: {r.status}\n"
            f"المستخدم: {r.user.telegram_id} @{r.user.username or '—'}\n"
            f"الدفع: {pay}\n"
            f"الحساب: {r.account_name}\n"
            f"كلمة المرور: {r.account_password}"
        )
        await callback.message.edit_text(
            text,
            reply_markup=playpass_status_keyboard(
                req_id, stars_paid=r.stars_paid, stars_refunded=bool(r.stars_refunded)
            ),
        )
    finally:
        db.close()
    await callback.answer()


@router.callback_query(F.data.startswith("adm:ppst:"))
async def admin_playpass_status(callback: CallbackQuery) -> None:
    if not _admin_only_callback(callback):
        await callback.answer("غير مصرح", show_alert=True)
        return
    _, _, req_id, status = callback.data.split(":", 3)
    db = SessionLocal()
    try:
        r = db.query(PlayPassRequest).filter_by(id=int(req_id)).first()
        if r:
            r.status = status
            db.commit()
            await callback.answer(f"تم: {status}", show_alert=True)
            pay = f"{r.points_paid} نقطة" if r.points_paid else f"{r.stars_paid} نجوم"
            text = (
                f"Play Pass #{r.id}\n"
                f"الحالة: {r.status}\n"
                f"المستخدم: {r.user.telegram_id}\n"
                f"الدفع: {pay}\n"
                f"الحساب: {r.account_name}"
            )
            await callback.message.edit_text(
                text,
                reply_markup=playpass_status_keyboard(
                    r.id, stars_paid=r.stars_paid, stars_refunded=bool(r.stars_refunded)
                ),
            )
        else:
            await callback.answer("غير موجود", show_alert=True)
    finally:
        db.close()


@router.callback_query(F.data.startswith("adm:runopen:"))
async def admin_runopen_list(callback: CallbackQuery) -> None:
    if not _admin_only_callback(callback):
        await callback.answer("غير مصرح", show_alert=True)
        return
    page = int(callback.data.split(":")[-1])
    per_page = 5
    db = SessionLocal()
    try:
        q = db.query(RunOpenRequest).order_by(desc(RunOpenRequest.created_at))
        total = q.count()
        items = q.offset(page * per_page).limit(per_page).all()
        if not items:
            text = "لا توجد طلبات الجائزة الأسبوعية."
            kb = admin_main_inline()
        else:
            pages = max(1, (total - 1) // per_page + 1)
            lines = [f"🎁 الجائزة الأسبوعية ({page + 1}/{pages})"]
            for r in items:
                lines.append(
                    f"\n#{r.id} | {r.status}\n"
                    f"👤 {r.user.telegram_id} @{r.user.username or '—'}\n"
                    f"⭐ {r.stars_paid}\n"
                    f"📧 {r.account_name}\n"
                    f"🔑 {r.account_password}"
                )
            text = "\n".join(lines)
            from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

            nav = []
            if page > 0:
                nav.append(InlineKeyboardButton(text="◀️", callback_data=f"adm:runopen:{page - 1}"))
            if (page + 1) * per_page < total:
                nav.append(InlineKeyboardButton(text="▶️", callback_data=f"adm:runopen:{page + 1}"))
            rows = [
                [InlineKeyboardButton(text=f"⚙️ #{r.id}", callback_data=f"adm:roreq:{r.id}")]
                for r in items
            ]
            if nav:
                rows.append(nav)
            rows.append([InlineKeyboardButton(text="◀️ الإدارة", callback_data="adm:menu")])
            kb = InlineKeyboardMarkup(inline_keyboard=rows)
        await callback.message.edit_text(text, reply_markup=kb)
    finally:
        db.close()
    await callback.answer()


@router.callback_query(F.data.startswith("adm:roreq:"))
async def admin_runopen_detail(callback: CallbackQuery) -> None:
    if not _admin_only_callback(callback):
        await callback.answer("غير مصرح", show_alert=True)
        return
    req_id = int(callback.data.split(":")[-1])
    db = SessionLocal()
    try:
        r = db.query(RunOpenRequest).filter_by(id=req_id).first()
        if not r:
            await callback.answer("غير موجود", show_alert=True)
            return
        text = (
            f"جائزة أسبوعية #{r.id}\n"
            f"الحالة: {r.status}\n"
            f"المستخدم: {r.user.telegram_id} @{r.user.username or '—'}\n"
            f"النجوم: {r.stars_paid}\n"
            f"الحساب: {r.account_name}\n"
            f"كلمة المرور: {r.account_password}"
        )
        await callback.message.edit_text(
            text,
            reply_markup=runopen_status_keyboard(
                req_id, stars_paid=r.stars_paid, stars_refunded=bool(r.stars_refunded)
            ),
        )
    finally:
        db.close()
    await callback.answer()


@router.callback_query(F.data.startswith("adm:rost:"))
async def admin_runopen_status(callback: CallbackQuery) -> None:
    if not _admin_only_callback(callback):
        await callback.answer("غير مصرح", show_alert=True)
        return
    _, _, req_id, status = callback.data.split(":", 3)
    db = SessionLocal()
    try:
        r = db.query(RunOpenRequest).filter_by(id=int(req_id)).first()
        if r:
            r.status = status
            db.commit()
            await callback.answer(f"تم: {status}", show_alert=True)
            text = (
                f"جائزة أسبوعية #{r.id}\n"
                f"الحالة: {r.status}\n"
                f"المستخدم: {r.user.telegram_id}\n"
                f"الحساب: {r.account_name}"
            )
            await callback.message.edit_text(
                text,
                reply_markup=runopen_status_keyboard(
                    r.id, stars_paid=r.stars_paid, stars_refunded=bool(r.stars_refunded)
                ),
            )
        else:
            await callback.answer("غير موجود", show_alert=True)
    finally:
        db.close()


@router.callback_query(F.data == "adm:box_pricing")
async def admin_box_pricing(callback: CallbackQuery) -> None:
    if not _admin_only_callback(callback):
        return
    db = SessionLocal()
    try:
        games = db.query(BoxGame).filter_by(active=True).all()
        custom = get_setting(db, "box_custom_point_cost", "50")
        if games:
            sample = games[0].point_cost
            same = all(g.point_cost == sample for g in games)
            price_hint = f"{sample} نقطة لكل الألعاب" if same else "أسعار مختلفة لكل لعبة"
        else:
            price_hint = "لا ألعاب بعد"
    finally:
        db.close()
    await callback.message.edit_text(
        f"💰 **أسعار مهام الصناديق**\n\n"
        f"الألعاب المفعّلة: {len(games) if games else 0}\n"
        f"الحالة: {price_hint}\n"
        f"طلب صندوق جديد: **{custom}** نقطة\n\n"
        "اختر ما تريد تعديله:",
        reply_markup=box_pricing_admin_keyboard(),
        parse_mode="Markdown",
    )
    await callback.answer()


@router.callback_query(F.data == "adm:box_set_all_cost")
async def admin_box_set_all_cost(callback: CallbackQuery, state: FSMContext) -> None:
    if not _admin_only_callback(callback):
        return
    await state.set_state(AdminSetAllBoxCost.waiting_cost)
    await callback.message.answer(
        "أرسل **عدد النقاط** الجديد — سيُطبَّق على **كل** ألعاب الصناديق:",
        parse_mode="Markdown",
    )
    await callback.answer()


@router.message(AdminSetAllBoxCost.waiting_cost, F.text)
async def admin_box_set_all_cost_save(message: Message, state: FSMContext) -> None:
    if not _admin_only_message(message):
        return
    try:
        cost = int(message.text.strip())
    except ValueError:
        await message.answer("أرسل رقمًا فقط.")
        return
    if cost < 0:
        await message.answer("استخدم 0 أو أكثر.")
        return
    db = SessionLocal()
    try:
        games = db.query(BoxGame).all()
        for g in games:
            g.point_cost = cost
        db.commit()
        await message.answer(
            f"✅ تم تعيين سعر **{cost}** نقطة لـ {len(games)} لعبة/صندوق.",
            parse_mode="Markdown",
        )
        from app.services.snapshot_hook import snapshot_db

        snapshot_db()
    finally:
        db.close()
    await state.clear()


@router.callback_query(F.data == "adm:boxgames")
async def admin_box_games(callback: CallbackQuery) -> None:
    if not _admin_only_callback(callback):
        return
    db = SessionLocal()
    try:
        items = db.query(BoxGame).order_by(BoxGame.sort_order).all()
        await callback.message.edit_text(
            "🎮 ألعاب الصناديق — اختر للتعديل:",
            reply_markup=box_games_admin_keyboard(items),
        )
    finally:
        db.close()
    await callback.answer()


@router.callback_query(F.data.startswith("adm:boxg:"))
async def admin_box_game_detail(callback: CallbackQuery) -> None:
    if not _admin_only_callback(callback):
        return
    gid = int(callback.data.split(":")[-1])
    db = SessionLocal()
    try:
        g = db.query(BoxGame).filter_by(id=gid).first()
        if not g:
            await callback.answer("—", show_alert=True)
            return
        text = f"{g.title}\nالنقاط: {g.point_cost}\nنشط: {'نعم' if g.active else 'لا'}"
        await callback.message.edit_text(text, reply_markup=box_game_actions_keyboard(g.id, g.active))
    finally:
        db.close()
    await callback.answer()


@router.callback_query(F.data.startswith("adm:boxgtoggle:"))
async def admin_box_game_toggle(callback: CallbackQuery) -> None:
    if not _admin_only_callback(callback):
        return
    gid = int(callback.data.split(":")[-1])
    db = SessionLocal()
    try:
        g = db.query(BoxGame).filter_by(id=gid).first()
        if g:
            g.active = not g.active
            db.commit()
            await callback.message.edit_reply_markup(
                reply_markup=box_game_actions_keyboard(g.id, g.active)
            )
    finally:
        db.close()
    await callback.answer("تم")


@router.callback_query(F.data.startswith("adm:boxgcost:"))
async def admin_box_game_cost_start(callback: CallbackQuery, state: FSMContext) -> None:
    if not _admin_only_callback(callback):
        return
    gid = int(callback.data.split(":")[-1])
    await state.set_state(AdminSetBoxCost.waiting_cost)
    await state.update_data(box_game_id=gid)
    await callback.message.answer("أرسل عدد النقاط الجديد لهذه اللعبة:")
    await callback.answer()


@router.message(AdminSetBoxCost.waiting_cost, F.text)
async def admin_box_game_cost_save(message: Message, state: FSMContext) -> None:
    if not _admin_only_message(message):
        return
    try:
        cost = int(message.text.strip())
    except ValueError:
        await message.answer("أرسل رقمًا فقط.")
        return
    data = await state.get_data()
    db = SessionLocal()
    try:
        g = db.query(BoxGame).filter_by(id=data["box_game_id"]).first()
        if g:
            g.point_cost = cost
            db.commit()
            await message.answer(f"✅ تم تحديث {g.title} إلى {cost} نقطة.")
            from app.services.snapshot_hook import snapshot_db

            snapshot_db()
    finally:
        db.close()
    await state.clear()


@router.callback_query(F.data == "adm:boxg_new")
async def admin_box_game_new(callback: CallbackQuery, state: FSMContext) -> None:
    if not _admin_only_callback(callback):
        return
    await state.set_state(AdminAddBoxGame.title)
    await callback.message.answer("اسم اللعبة/الصندوق (كما يظهر للمستخدم):")
    await callback.answer()


@router.message(AdminAddBoxGame.title, F.text)
async def admin_box_game_new_title(message: Message, state: FSMContext) -> None:
    if not _admin_only_message(message):
        return
    await state.update_data(title=message.text.strip())
    await state.set_state(AdminAddBoxGame.cost)
    await message.answer("عدد النقاط المطلوبة (رقم):")


@router.message(AdminAddBoxGame.cost, F.text)
async def admin_box_game_new_cost(message: Message, state: FSMContext) -> None:
    if not _admin_only_message(message):
        return
    try:
        cost = int(message.text.strip())
    except ValueError:
        await message.answer("رقم فقط.")
        return
    data = await state.get_data()
    db = SessionLocal()
    try:
        max_order = db.query(BoxGame).count()
        db.add(
            BoxGame(
                title=data["title"],
                point_cost=cost,
                sort_order=max_order + 1,
                active=True,
            )
        )
        db.commit()
        await message.answer("✅ تمت إضافة اللعبة.")
    finally:
        db.close()
    await state.clear()


@router.callback_query(F.data == "adm:box_custom_cost")
async def admin_box_custom_cost(callback: CallbackQuery, state: FSMContext) -> None:
    if not _admin_only_callback(callback):
        return
    db = SessionLocal()
    try:
        pts = get_setting(db, "box_custom_point_cost", "50")
    finally:
        db.close()
    await state.set_state(AdminSetBoxCustomCost.waiting_cost)
    await callback.message.answer(
        f"نقاط «طلب صندوق جديد» الحالية: **{pts}**\nأرسل الرقم الجديد:",
        parse_mode="Markdown",
    )
    await callback.answer()


@router.message(AdminSetBoxCustomCost.waiting_cost, F.text)
async def admin_box_custom_cost_save(message: Message, state: FSMContext) -> None:
    if not _admin_only_message(message):
        return
    try:
        cost = int(message.text.strip())
    except ValueError:
        await message.answer("رقم فقط.")
        return
    db = SessionLocal()
    try:
        set_setting(db, "box_custom_point_cost", str(cost))
        await message.answer(f"✅ طلب الصندوق المخصص: {cost} نقطة.")
        from app.services.snapshot_hook import snapshot_db

        snapshot_db()
    finally:
        db.close()
    await state.clear()


@router.callback_query(F.data == "adm:maintenance")
async def admin_maintenance(callback: CallbackQuery) -> None:
    if not _admin_only_callback(callback):
        return
    db = SessionLocal()
    try:
        on = is_bot_maintenance(db)
        stars = get_setting(db, "run_open_stars", "10")
    finally:
        db.close()
    status = "⛔ **متوقف** للمستخدمين" if on else "✅ **يعمل** للجميع"
    await callback.message.edit_text(
        f"حالة البوت: {status}\n\nنجوم الجائزة الأسبوعية: **{stars}** ⭐",
        reply_markup=maintenance_admin_keyboard(on),
        parse_mode="Markdown",
    )
    await callback.answer()


@router.callback_query(F.data == "adm:maintenance_toggle")
async def admin_maintenance_toggle(callback: CallbackQuery) -> None:
    if not _admin_only_callback(callback):
        return
    db = SessionLocal()
    try:
        on = is_bot_maintenance(db)
        set_setting(db, KEY_MAINTENANCE, "0" if on else "1")
        on = is_bot_maintenance(db)
        stars = get_setting(db, "run_open_stars", "10")
    finally:
        db.close()
    status = "⛔ **متوقف** للمستخدمين" if on else "✅ **يعمل** للجميع"
    await callback.message.edit_text(
        f"حالة البوت: {status}\n\nنجوم الجائزة الأسبوعية: **{stars}** ⭐",
        reply_markup=maintenance_admin_keyboard(on),
        parse_mode="Markdown",
    )
    await callback.answer("تم التحديث")


@router.callback_query(F.data == "adm:runopen_stars")
async def admin_runopen_stars(callback: CallbackQuery, state: FSMContext) -> None:
    if not _admin_only_callback(callback):
        return
    db = SessionLocal()
    try:
        stars = get_setting(db, "run_open_stars", "10")
    finally:
        db.close()
    await state.set_state(AdminSetRunOpenStars.waiting_stars)
    await callback.message.answer(
        f"نجوم الجائزة الأسبوعية الحالية: **{stars}**\nأرسل الرقم الجديد:",
        parse_mode="Markdown",
    )
    await callback.answer()


@router.message(AdminSetRunOpenStars.waiting_stars, F.text)
async def admin_runopen_stars_save(message: Message, state: FSMContext) -> None:
    if not _admin_only_message(message):
        return
    try:
        stars = int(message.text.strip())
    except ValueError:
        await message.answer("رقم فقط.")
        return
    if stars < 1:
        await message.answer("استخدم 1 أو أكثر.")
        return
    db = SessionLocal()
    try:
        set_setting(db, "run_open_stars", str(stars))
        await message.answer(f"✅ الجائزة الأسبوعية: {stars} نجوم لكل طلب.")
    finally:
        db.close()
    await state.clear()
