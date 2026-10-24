from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from app.i18n import t
from app.services.mandatory_sub import MandatoryTarget


def mandatory_sub_keyboard(lang: str, targets: list[MandatoryTarget]) -> InlineKeyboardMarkup:
    rows = []
    for target in targets:
        if target.invite_link:
            label = target.label_ar if lang == "ar" else target.label_en
            rows.append([InlineKeyboardButton(text=label, url=target.invite_link)])
    if not rows and targets:
        for target in targets:
            cid = target.chat_id
            url = cid if cid.startswith("http") else f"https://t.me/{cid.lstrip('@')}"
            rows.append([InlineKeyboardButton(text=target.label_ar, url=url)])
    rows.append(
        [
            InlineKeyboardButton(
                text=t(lang, "mandatory_sub_verify_btn"),
                callback_data="verify_mandatory",
            )
        ]
    )
    return InlineKeyboardMarkup(inline_keyboard=rows)
