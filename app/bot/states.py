from aiogram.fsm.state import State, StatesGroup


class TransferStates(StatesGroup):
    choosing_country = State()
    entering_username = State()
    entering_password = State()
