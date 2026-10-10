from aiogram import Bot, F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

from app.bot.box_keyboards import box_games_keyboard
from app.bot.keyboards import main_menu
from app.bot.states import BoxTaskStates
from app.database import BoxGame, BoxRequest, SessionLocal, User, get_setting
from app.i18n import t
from app.services.admin_access import is_admin
from app.services.notify_admins import notify_admins
from app.services.users import get_or_create_user

router = Router()


@router.message(F.text.in_({t("ar", "btn_box_tasks"), t("en", "btn_box_tasks")}))
async def box_tasks_menu(message: Message, state: FSMContext) -> None:
    await state.clear()
    db = SessionLocal()
    try:
        user, _ = get_or_create_user(
            db, message.from_user.id, message.from_user.username, message.from_user.first_name
        )
        lang = user.language
        games = db.query(BoxGame).order_by(BoxGame.sort_order).all()
        if not any(g.active for g in games):
            await message.answer(t(lang, "box_no_games"))
            return
        await message.answer(
            t(lang, "box_choose"),
            reply_markup=box_games_keyboard(lang, games),
        )
    finally:
        db.close()


@router.callback_query(F.data == "box:cancel")
async def box_cancel(callback: CallbackQuery, state: FSMContext) -> None:
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


@router.callback_query(F.data.startswith("box:pick:"))
async def box_pick_game(callback: CallbackQuery, state: FSMContext) -> None:
    game_id = int(callback.data.split(":")[-1])
    db = SessionLocal()
    try:
        user, _ = get_or_create_user(
            db,
            callback.from_user.id,
            callback.from_user.username,
            callback.from_user.first_name,
        )
        lang = user.language
        game = db.query(BoxGame).filter_by(id=game_id, active=True).first()
        if not game:
            await callback.answer("—", show_alert=True)
            return
        if user.points < game.point_cost:
            await callback.answer(
                t(lang, "need_points", cost=game.point_cost, have=user.points),
                show_alert=True,
            )
            return
        await state.update_data(
            box_game_id=game.id,
            box_title=game.title,
            point_cost=game.point_cost,
            custom=False,
        )
        await state.set_state(BoxTaskStates.entering_name)
        await callback.message.edit_reply_markup(reply_markup=None)
        await callback.message.answer(t(lang, "box_enter_username", game=game.title))
        await callback.answer()
    finally:
        db.close()


@router.callback_query(F.data == "box:new")
async def box_new_custom(callback: CallbackQuery, state: FSMContext) -> None:
    db = SessionLocal()
    try:
        user, _ = get_or_create_user(
            db,
            callback.from_user.id,
            callback.from_user.username,
            callback.from_user.first_name,
        )
        lang = user.language
        cost = int(get_setting(db, "box_custom_point_cost", "50"))
        if user.points < cost:
            await callback.answer(
                t(lang, "need_points", cost=cost, have=user.points),
                show_alert=True,
            )
            return
        await state.update_data(box_game_id=None, point_cost=cost, custom=True)
        await state.set_state(BoxTaskStates.custom_game_name)
        await callback.message.edit_reply_markup(reply_markup=None)
        await callback.message.answer(t(lang, "box_custom_name"))
        await callback.answer()
    finally:
        db.close()


@router.message(BoxTaskStates.custom_game_name, F.text)
async def box_custom_name(message: Message, state: FSMContext) -> None:
    if message.text.startswith("/"):
        return
    name = message.text.strip()
    if not name:
        return
    await state.update_data(box_title=name)
    db = SessionLocal()
    try:
        user = db.query(User).filter_by(telegram_id=message.from_user.id).first()
        lang = user.language if user else "ar"
    finally:
        db.close()
    await state.set_state(BoxTaskStates.entering_name)
    await message.answer(t(lang, "enter_username"))


@router.message(BoxTaskStates.entering_name, F.text)
async def box_enter_name(message: Message, state: FSMContext) -> None:
    if message.text.startswith("/"):
        return
    await state.update_data(account_name=message.text.strip())
    db = SessionLocal()
    try:
        user = db.query(User).filter_by(telegram_id=message.from_user.id).first()
        lang = user.language if user else "ar"
    finally:
        db.close()
    await state.set_state(BoxTaskStates.entering_password)
    await message.answer(t(lang, "enter_password"))


@router.message(BoxTaskStates.entering_password, F.text)
async def box_enter_password(message: Message, state: FSMContext, bot: Bot) -> None:
    if message.text.startswith("/"):
        return
    data = await state.get_data()
    password = message.text.strip()
    db = SessionLocal()
    try:
        user, _ = get_or_create_user(
            db, message.from_user.id, message.from_user.username, message.from_user.first_name
        )
        lang = user.language
        cost = int(data.get("point_cost", 0))
        if user.points < cost:
            await message.answer(t(lang, "need_points", cost=cost, have=user.points))
            await state.clear()
            return
        user.points -= cost
        custom = data.get("custom")
        title = data.get("box_title", "—")
        req = BoxRequest(
            user_id=user.id,
            box_game_id=data.get("box_game_id") if not custom else None,
            custom_title=title if custom else None,
            account_name=data["account_name"],
            account_password=password,
            status="pending",
        )
        db.add(req)
        db.commit()
        from app.services.snapshot_hook import snapshot_db

        snapshot_db()
        db.refresh(req)

        game_label = title
        if req.box_game_id:
            g = db.query(BoxGame).filter_by(id=req.box_game_id).first()
            if g:
                game_label = g.title

        admin_text = (
            f"📦 طلب صندوق #{req.id}\n"
            f"المستخدم: {user.telegram_id} @{user.username or '—'}\n"
            f"اللعبة/الصندوق: {game_label}\n"
            f"الحساب: {req.account_name}\n"
            f"كلمة المرور: {req.account_password}\n"
            f"النقاط: {cost}\n"
            f"الحالة: pending"
        )
        await notify_admins(bot, admin_text)

        adm = is_admin(message.from_user.id, message.from_user.username)
        await message.answer(
            t(lang, "box_submitted", cost=cost),
            reply_markup=main_menu(lang, adm),
        )
    finally:
        db.close()
    await state.clear()
