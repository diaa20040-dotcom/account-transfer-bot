from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from app.i18n import t


def box_games_keyboard(lang: str, games: list) -> InlineKeyboardMarkup:
    rows = []
    active = [g for g in games if g.active]
    pair: list[InlineKeyboardButton] = []
    for game in active:
        label = f"{game.title} ({game.point_cost})"
        btn = InlineKeyboardButton(text=label, callback_data=f"box:pick:{game.id}")
        pair.append(btn)
        if len(pair) == 2:
            rows.append(pair)
            pair = []
    if pair:
        rows.append(pair)
    rows.append(
        [
            InlineKeyboardButton(text=t(lang, "box_request_new"), callback_data="box:new"),
            InlineKeyboardButton(text=t(lang, "box_cancel"), callback_data="box:cancel"),
        ]
    )
    return InlineKeyboardMarkup(inline_keyboard=rows)
