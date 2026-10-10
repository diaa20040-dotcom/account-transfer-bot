from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from app.i18n import t


def mandatory_sub_keyboard(lang: str, invite_link: str | None) -> InlineKeyboardMarkup:
    rows = []
    if invite_link:
        rows.append([InlineKeyboardButton(text=t(lang, "mandatory_sub_join"), url=invite_link)])
    rows.append(
        [InlineKeyboardButton(text=t(lang, "mandatory_sub_verify_btn"), callback_data="verify_mandatory")]
    )
    return InlineKeyboardMarkup(inline_keyboard=rows)
