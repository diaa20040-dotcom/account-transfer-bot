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


def playpass_status_keyboard(
    req_id: int, stars_paid: int = 0, stars_refunded: bool = False
) -> InlineKeyboardMarkup:
    rows = [
        [
            InlineKeyboardButton(text="⏳ pending", callback_data=f"adm:ppst:{req_id}:pending"),
            InlineKeyboardButton(text="🔄 processing", callback_data=f"adm:ppst:{req_id}:processing"),
        ],
        [
            InlineKeyboardButton(text="✅ done", callback_data=f"adm:ppst:{req_id}:done"),
            InlineKeyboardButton(text="❌ rejected", callback_data=f"adm:ppst:{req_id}:rejected"),
        ],
    ]
    if stars_paid > 0 and not stars_refunded:
        rows.append(
            [InlineKeyboardButton(text="↩️ استرداد النجوم", callback_data=f"adm:oref:play_pass:{req_id}")]
        )
    elif stars_refunded:
        rows.append(
            [InlineKeyboardButton(text="✅ تم استرداد النجوم", callback_data=f"adm:ppreq:{req_id}")]
        )
    rows.append(
        [
            InlineKeyboardButton(text="💬 رسالة", callback_data=f"adm:umsg:play_pass:{req_id}"),
            InlineKeyboardButton(text="🗣️ مناقشة", callback_data=f"adm:udisc:play_pass:{req_id}"),
        ]
    )
    rows.append([InlineKeyboardButton(text="◀️ قائمة الإدارة", callback_data="adm:menu")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def playpass_admin_list_keyboard(page: int, has_prev: bool, has_next: bool) -> InlineKeyboardMarkup:
    nav = []
    if has_prev:
        nav.append(InlineKeyboardButton(text="◀️", callback_data=f"adm:playpass:{page - 1}"))
    if has_next:
        nav.append(InlineKeyboardButton(text="▶️", callback_data=f"adm:playpass:{page + 1}"))
    rows = [
        [InlineKeyboardButton(text="⚙️ إعدادات Play Pass", callback_data="adm:playpass_cfg")],
    ]
    if nav:
        rows.append(nav)
    rows.append([InlineKeyboardButton(text="◀️ الإدارة", callback_data="adm:menu")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def playpass_admin_settings_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="⭐ تعديل سعر النجوم", callback_data="adm:playpass_stars")],
            [
                InlineKeyboardButton(text="➕ مكان", callback_data="adm:pp_slot:1"),
                InlineKeyboardButton(text="➖ مكان", callback_data="adm:pp_slot:-1"),
            ],
            [InlineKeyboardButton(text="🔢 تعيين عدد الأماكن", callback_data="adm:playpass_slots")],
            [InlineKeyboardButton(text="◀️ طلبات Play Pass", callback_data="adm:playpass:0")],
        ]
    )


def user_admin_profile_keyboard(user_id: int, is_banned: bool) -> InlineKeyboardMarkup:
    ban_btn = (
        InlineKeyboardButton(text="✅ إلغاء الحظر", callback_data=f"adm:uban:{user_id}:0")
        if is_banned
        else InlineKeyboardButton(text="🚫 حظر", callback_data=f"adm:uban:{user_id}:1")
    )
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="➕ إضافة نقاط", callback_data=f"adm:uadd:{user_id}"),
                InlineKeyboardButton(text="➖ خصم نقاط", callback_data=f"adm:usub:{user_id}"),
            ],
            [ban_btn],
            [InlineKeyboardButton(text="◀️ المستخدمون", callback_data="adm:users:0")],
        ]
    )
