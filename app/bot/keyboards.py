from aiogram.types import KeyboardButton, ReplyKeyboardMarkup

from app.bot.admin_keyboards import ADMIN_BTN_AR, ADMIN_BTN_EN
from app.i18n import t


def main_menu(lang: str, is_admin: bool = False) -> ReplyKeyboardMarkup:
    rows = [
        [KeyboardButton(text=t(lang, "btn_visa"))],
        [
            KeyboardButton(text=t(lang, "btn_referral")),
            KeyboardButton(text=t(lang, "btn_points")),
        ],
        [KeyboardButton(text=t(lang, "btn_language"))],
    ]
    if is_admin:
        rows.append([KeyboardButton(text=ADMIN_BTN_AR if lang == "ar" else ADMIN_BTN_EN)])
    return ReplyKeyboardMarkup(keyboard=rows, resize_keyboard=True)
