from aiogram.fsm.state import State, StatesGroup


class TopUpStates(StatesGroup):
    waiting_amount = State()


class WithdrawStates(StatesGroup):
    payment_link = State()
    email = State()


class PromoStates(StatesGroup):
    waiting_code = State()
