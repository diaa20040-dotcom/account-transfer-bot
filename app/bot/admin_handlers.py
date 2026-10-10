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
    countries_admin_keyboard,
    country_actions_keyboard,
    task_actions_keyboard,
    tasks_admin_keyboard,
    transfer_status_keyboard,
    mandatory_sub_admin_keyboard,
)
from app.bot.admin_states import (
    AdminAddPoints,
    AdminAddTask,
    AdminSetCountryCost,
    AdminSetReferral,
    AdminMandatorySub,
    AdminMessageUser,
    AdminRestoreBackup,
)
from app.bot.keyboards import main_menu
from app.database import Country, SessionLocal, Task, TransferRequest, User, get_setting, set_setting
from app.services.admin_access import is_admin, persist_admin
from app.services.mandatory_sub import (
    KEY_CHAT_ID,
    KEY_ENABLED,
    KEY_INVITE_LINK,
    get_mandatory_sub_config,
)
from app.services.backup_export import backup_json_bytes, import_backup_payload
from app.services.user_notify import notify_transfer_status, send_admin_message_to_user
from app.services.users import get_or_create_user
import json
from datetime import datetime

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


@router.callback_query(F.data.startswith("adm:umsg:"))
async def admin_message_user_start(callback: CallbackQuery, state: FSMContext) -> None:
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
        await state.update_data(msg_req_id=req_id, msg_target_tid=r.user.telegram_id)
        await state.set_state(AdminMessageUser.waiting_text)
        await callback.message.answer(
            f"💬 اكتب الرسالة المرسلة للمستخدم (طلب #{req_id}):\n"
            f"المستخدم: `{r.user.telegram_id}` @{r.user.username or '—'}\n"
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
        ok = await send_admin_message_to_user(bot, user, int(req_id or 0), message.text.strip())
        if ok:
            await message.answer(f"✅ تم إرسال الرسالة للمستخدم (طلب #{req_id}).")
        else:
            await message.answer(
                "❌ تعذّر الإرسال. ربما المستخدم حظر البوت أو لم يضغط Start."
            )
    finally:
        db.close()
    await state.clear()


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
            lines.append(f"• {u.telegram_id} @{u.username or '—'} — {u.points} نقطة")
        from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

        nav = []
        if page > 0:
            nav.append(InlineKeyboardButton(text="◀️", callback_data=f"adm:users:{page - 1}"))
        if (page + 1) * per_page < total:
            nav.append(InlineKeyboardButton(text="▶️", callback_data=f"adm:users:{page + 1}"))
        rows = []
        for u in users:
            label = f"➕ @{u.username}" if u.username else f"➕ {u.telegram_id}"
            rows.append(
                [InlineKeyboardButton(text=label, callback_data=f"adm:uadd:{u.id}")]
            )
        if nav:
            rows.append(nav)
        rows.append(
            [
                InlineKeyboardButton(text="💎 إضافة نقاط", callback_data="adm:addpoints"),
                InlineKeyboardButton(text="◀️ الإدارة", callback_data="adm:menu"),
            ]
        )
        await callback.message.edit_text("\n".join(lines), reply_markup=InlineKeyboardMarkup(inline_keyboard=rows))
    finally:
        db.close()
    await callback.answer()


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
        users_n, tasks_n = import_backup_payload(db, payload)
    finally:
        db.close()
    await state.clear()
    await message.answer(
        f"✅ تمت الاستعادة.\nالمستخدمون: {users_n}\nالمهام: {tasks_n}",
        reply_markup=admin_main_inline(),
    )
