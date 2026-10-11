from aiogram.fsm.state import State, StatesGroup


class TransferStates(StatesGroup):
    choosing_country = State()
    entering_username = State()
    entering_password = State()


class TopUpStates(StatesGroup):
    amount = State()


class BoxTaskStates(StatesGroup):
    entering_name = State()
    entering_password = State()
    custom_game_name = State()


class RunOpenStates(StatesGroup):
    entering_name = State()
    entering_password = State()


class PlayPassStates(StatesGroup):
    entering_name = State()
    entering_password = State()


class PromoStates(StatesGroup):
    entering_code = State()
