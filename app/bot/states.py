from aiogram.fsm.state import State, StatesGroup


class SellStarsStates(StatesGroup):
    waiting_amount = State()
