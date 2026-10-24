from aiogram.fsm.state import State, StatesGroup


class AdminAddTask(StatesGroup):
    title_ar = State()
    title_en = State()
    chat_id = State()
    reward = State()
    invite_link = State()


class AdminSetReferral(StatesGroup):
    waiting_points = State()


class AdminSetCountryCost(StatesGroup):
    waiting_cost = State()


class AdminAddPoints(StatesGroup):
    target = State()
    amount = State()


class AdminSubtractPoints(StatesGroup):
    target = State()
    amount = State()


class AdminMandatorySub(StatesGroup):
    chat_id = State()
    invite_link = State()


class AdminMessageUser(StatesGroup):
    waiting_text = State()


class AdminDiscussion(StatesGroup):
    active = State()


class AdminRestoreBackup(StatesGroup):
    waiting_file = State()


class AdminSetBoxCost(StatesGroup):
    waiting_cost = State()


class AdminSetAllBoxCost(StatesGroup):
    waiting_cost = State()


class AdminSetRunOpenStars(StatesGroup):
    waiting_stars = State()


class AdminSetPlayPassSlots(StatesGroup):
    waiting_slots = State()


class AdminSetPlayPassStars(StatesGroup):
    waiting_stars = State()


class AdminBanUser(StatesGroup):
    waiting_target = State()


class AdminSetBoxCustomCost(StatesGroup):
    waiting_cost = State()


class AdminAddBoxGame(StatesGroup):
    title = State()
    cost = State()


class AdminAddPromo(StatesGroup):
    code = State()
    points = State()
    max_uses = State()


class AdminBroadcast(StatesGroup):
    waiting_content = State()


class AdminStarsRefund(StatesGroup):
    waiting_user = State()
    waiting_charge_id = State()


class AdminAddVisaStock(StatesGroup):
    waiting_content = State()


class AdminSetVisaPrice(StatesGroup):
    waiting_points = State()
    waiting_stars = State()
