from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from app.i18n import t


def visa_pay_keyboard(lang: str, points: int, stars: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text=t(lang, "visa_pay_points", points=points), callback_data="visa:points")],
            [InlineKeyboardButton(text=t(lang, "visa_pay_stars", stars=stars), callback_data="visa:stars")],
            [InlineKeyboardButton(text=t(lang, "visa_cancel"), callback_data="visa:cancel")],
        ]
    )
