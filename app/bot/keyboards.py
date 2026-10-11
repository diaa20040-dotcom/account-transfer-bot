from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup, KeyboardButton, ReplyKeyboardMarkup

from app.bot.admin_keyboards import ADMIN_BTN_AR, ADMIN_BTN_EN
from app.i18n import t


def main_menu(lang: str, is_admin: bool = False) -> ReplyKeyboardMarkup:
    rows = [
        [KeyboardButton(text=t(lang, "btn_transfer"))],
        [KeyboardButton(text=t(lang, "btn_box_tasks"))],
        [
            KeyboardButton(text=t(lang, "btn_tasks")),
            KeyboardButton(text=t(lang, "btn_referral")),
        ],
        [KeyboardButton(text=t(lang, "btn_run_open"))],
        [KeyboardButton(text=t(lang, "btn_play_pass"))],
        [
            KeyboardButton(text=t(lang, "btn_points")),
            KeyboardButton(text=t(lang, "btn_topup")),
        ],
        [KeyboardButton(text=t(lang, "btn_promo"))],
        [KeyboardButton(text=t(lang, "btn_language"))],
    ]
    if is_admin:
        rows.append([KeyboardButton(text=ADMIN_BTN_AR if lang == "ar" else ADMIN_BTN_EN)])
    return ReplyKeyboardMarkup(keyboard=rows, resize_keyboard=True)


def countries_keyboard(lang: str, countries: list) -> InlineKeyboardMarkup:
    rows = []
    for c in countries:
        name = c.name_ar if lang == "ar" else c.name_en
        rows.append(
            [
                InlineKeyboardButton(
                    text=t(lang, "country_cost", name=name, cost=c.point_cost),
                    callback_data=f"country:{c.id}",
                )
            ]
        )
    rows.append([InlineKeyboardButton(text=t(lang, "back"), callback_data="cancel_transfer")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def tasks_keyboard(lang: str, tasks: list) -> InlineKeyboardMarkup:
    rows = []
    for task in tasks:
        title = task.title_ar if lang == "ar" else task.title_en
        rows.append(
            [
                InlineKeyboardButton(
                    text=t(lang, "task_verify", title=title),
                    callback_data=f"verify_task:{task.id}",
                )
            ]
        )
        if task.invite_link:
            rows.append([InlineKeyboardButton(text=f"🔗 {title}", url=task.invite_link)])
    if not rows:
        rows.append([InlineKeyboardButton(text=t(lang, "back"), callback_data="noop")])
    return InlineKeyboardMarkup(inline_keyboard=rows)
