from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup, KeyboardButton, ReplyKeyboardMarkup

from app.bot.admin_keyboards import ADMIN_BTN_AR, ADMIN_BTN_EN
from app.bot.withdraw_products import WITHDRAW_PRODUCTS, product_title
from app.i18n import t


def main_menu(lang: str, admin: bool = False) -> ReplyKeyboardMarkup:
    rows = [
        [KeyboardButton(text=t(lang, "btn_available"))],
        [
            KeyboardButton(text=t(lang, "btn_referral")),
            KeyboardButton(text=t(lang, "btn_points")),
        ],
        [KeyboardButton(text=t(lang, "btn_promo")), KeyboardButton(text=t(lang, "btn_topup"))],
    ]
    if admin:
        rows.append([KeyboardButton(text=ADMIN_BTN_AR if lang == "ar" else ADMIN_BTN_EN)])
    return ReplyKeyboardMarkup(keyboard=rows, resize_keyboard=True)


def withdraw_options_keyboard(lang: str) -> InlineKeyboardMarkup:
    rows = []
    for key in ("link_01", "link_005"):
        if key not in WITHDRAW_PRODUCTS:
            continue
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
