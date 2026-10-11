from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from app.i18n import t


def play_pass_pay_keyboard(lang: str, points: int, stars: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text=t(lang, "play_pass_pay_points", points=points),
                    callback_data="pp:points",
                )
            ],
            [
                InlineKeyboardButton(
                    text=t(lang, "play_pass_pay_stars", stars=stars),
                    callback_data="pp:stars",
                )
            ],
            [InlineKeyboardButton(text=t(lang, "play_pass_cancel"), callback_data="pp:cancel")],
        ]
    )


def playpass_status_keyboard(req_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="⏳ pending", callback_data=f"adm:ppst:{req_id}:pending"),
                InlineKeyboardButton(text="🔄 processing", callback_data=f"adm:ppst:{req_id}:processing"),
            ],
            [
                InlineKeyboardButton(text="✅ done", callback_data=f"adm:ppst:{req_id}:done"),
                InlineKeyboardButton(text="❌ rejected", callback_data=f"adm:ppst:{req_id}:rejected"),
            ],
            [InlineKeyboardButton(text="◀️ قائمة الإدارة", callback_data="adm:menu")],
        ]
    )
