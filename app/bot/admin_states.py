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


class AdminMandatorySub(StatesGroup):
    chat_id = State()
    invite_link = State()


class AdminMessageUser(StatesGroup):
    waiting_text = State()


class AdminRestoreBackup(StatesGroup):
    waiting_file = State()
