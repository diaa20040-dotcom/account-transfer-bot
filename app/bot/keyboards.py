from aiogram.types import KeyboardButton, ReplyKeyboardMarkup

from app.i18n import t


def main_menu(lang: str) -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text=t(lang, "btn_sell_stars"))]],
        resize_keyboard=True,
    )
