from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup, KeyboardButton, ReplyKeyboardMarkup

from app.bot.withdraw_products import WITHDRAW_PRODUCTS, product_title
from app.i18n import t


def main_menu(lang: str) -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text=t(lang, "btn_available"))],
            [
                KeyboardButton(text=t(lang, "btn_referral")),
                KeyboardButton(text=t(lang, "btn_points")),
            ],
            [KeyboardButton(text=t(lang, "btn_topup"))],
        ],
        resize_keyboard=True,
    )


def withdraw_options_keyboard(lang: str) -> InlineKeyboardMarkup:
    rows = []
    for key in WITHDRAW_PRODUCTS:
        cost = WITHDRAW_PRODUCTS[key]["cost"]
        title = product_title(key, lang)
        rows.append(
            [
                InlineKeyboardButton(
                    text=f"{title} · {cost} 💎",
                    callback_data=f"wd:{key}",
                )
            ]
        )
    rows.append([InlineKeyboardButton(text=t(lang, "back"), callback_data="wd:cancel")])
    return InlineKeyboardMarkup(inline_keyboard=rows)
