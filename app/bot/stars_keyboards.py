from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from app.i18n import t

TOPUP_PRESETS = (10, 25, 50, 100, 250, 500)


def topup_amounts_keyboard(lang: str) -> InlineKeyboardMarkup:
    rows = []
    row = []
    for n in TOPUP_PRESETS:
        row.append(
            InlineKeyboardButton(
                text=t(lang, "topup_stars_btn", stars=n),
                callback_data=f"topup:{n}",
            )
        )
        if len(row) == 2:
            rows.append(row)
            row = []
    if row:
        rows.append(row)
    rows.append(
        [InlineKeyboardButton(text=t(lang, "topup_custom_btn"), callback_data="topup:custom")]
    )
    return InlineKeyboardMarkup(inline_keyboard=rows)
