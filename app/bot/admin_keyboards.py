from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

ADMIN_BTN_AR = "🛠 لوحة الإدارة"
ADMIN_BTN_EN = "🛠 Admin panel"


def admin_main_inline() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="📥 طلبات التحويل", callback_data="adm:transfers:0")],
            [
                InlineKeyboardButton(text="📦 طلبات الصناديق", callback_data="adm:boxes:0"),
                InlineKeyboardButton(text="🔓 فتح التشغيل", callback_data="adm:runopen:0"),
            ],
            [
                InlineKeyboardButton(text="💰 أسعار الصناديق", callback_data="adm:box_pricing"),
                InlineKeyboardButton(text="⛔ إيقاف البوت", callback_data="adm:maintenance"),
            ],
            [InlineKeyboardButton(text="🎮 قائمة ألعاب الصناديق", callback_data="adm:boxgames")],
            [InlineKeyboardButton(text="🌍 الدول والنقاط", callback_data="adm:countries")],
            [
                InlineKeyboardButton(text="📋 المهام", callback_data="adm:tasks"),
                InlineKeyboardButton(text="➕ مهمة جديدة", callback_data="adm:task_new"),
            ],
            [
                InlineKeyboardButton(text="⚙️ نقاط الإحالة", callback_data="adm:referral"),
                InlineKeyboardButton(text="👥 المستخدمون", callback_data="adm:users:0"),
            ],
            [
                InlineKeyboardButton(text="🎁 أكواد البرومو", callback_data="adm:promos"),
                InlineKeyboardButton(text="➕ برومو جديد", callback_data="adm:promo_new"),
            ],
            [InlineKeyboardButton(text="💎 إضافة نقاط لمستخدم", callback_data="adm:addpoints")],
            [InlineKeyboardButton(text="📢 اشتراك إجباري", callback_data="adm:msub")],
            [
                InlineKeyboardButton(text="📥 نسخة احتياطية", callback_data="adm:backup"),
                InlineKeyboardButton(text="📤 استعادة نسخة", callback_data="adm:restore"),
            ],
            [
                InlineKeyboardButton(
                    text="♻️ استعادة نسخة GitHub (قديمة)",
                    callback_data="adm:reload_seed",
                )
            ],
            [InlineKeyboardButton(text="❌ إغلاق", callback_data="adm:close")],
        ]
    )


def transfer_status_keyboard(req_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="⏳ pending", callback_data=f"adm:st:{req_id}:pending"),
                InlineKeyboardButton(text="🔄 processing", callback_data=f"adm:st:{req_id}:processing"),
            ],
            [
                InlineKeyboardButton(text="✅ done", callback_data=f"adm:st:{req_id}:done"),
                InlineKeyboardButton(text="❌ rejected", callback_data=f"adm:st:{req_id}:rejected"),
            ],
            [InlineKeyboardButton(text="💬 مراسلة المستخدم", callback_data=f"adm:umsg:{req_id}")],
            [InlineKeyboardButton(text="◀️ قائمة الإدارة", callback_data="adm:menu")],
        ]
    )


def countries_admin_keyboard(countries: list) -> InlineKeyboardMarkup:
    rows = []
    for c in countries:
        status = "✅" if c.active else "⛔"
        rows.append(
            [
                InlineKeyboardButton(
                    text=f"{status} {c.name_ar} ({c.point_cost} نقطة)",
                    callback_data=f"adm:country:{c.id}",
                )
            ]
        )
    rows.append([InlineKeyboardButton(text="◀️ قائمة الإدارة", callback_data="adm:menu")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def country_actions_keyboard(country_id: int, active: bool) -> InlineKeyboardMarkup:
    toggle = "إيقاف" if active else "تفعيل"
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="✏️ تغيير النقاط", callback_data=f"adm:ccost:{country_id}")],
            [
                InlineKeyboardButton(
                    text=f"{'⛔' if active else '✅'} {toggle}",
                    callback_data=f"adm:ctoggle:{country_id}",
                )
            ],
            [InlineKeyboardButton(text="◀️ الدول", callback_data="adm:countries")],
        ]
    )


def tasks_admin_keyboard(tasks: list) -> InlineKeyboardMarkup:
    rows = []
    for task in tasks:
        st = "✅" if task.active else "⛔"
        rows.append(
            [
                InlineKeyboardButton(
                    text=f"{st} {task.title_ar}",
                    callback_data=f"adm:task:{task.id}",
                )
            ]
        )
    rows.append(
        [
            InlineKeyboardButton(text="➕ مهمة", callback_data="adm:task_new"),
            InlineKeyboardButton(text="◀️ الإدارة", callback_data="adm:menu"),
        ]
    )
    return InlineKeyboardMarkup(inline_keyboard=rows)


def mandatory_sub_admin_keyboard(enabled: bool) -> InlineKeyboardMarkup:
    toggle = "إيقاف الاشتراك الإجباري" if enabled else "تفعيل الاشتراك الإجباري"
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="🆔 تعيين Chat ID للقناة", callback_data="adm:msub_chat")],
            [InlineKeyboardButton(text="🔗 تعيين رابط القناة", callback_data="adm:msub_link")],
            [
                InlineKeyboardButton(
                    text=f"{'⛔' if enabled else '✅'} {toggle}",
                    callback_data="adm:msub_toggle",
                )
            ],
            [InlineKeyboardButton(text="◀️ قائمة الإدارة", callback_data="adm:menu")],
        ]
    )


def box_status_keyboard(req_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="⏳ pending", callback_data=f"adm:bst:{req_id}:pending"),
                InlineKeyboardButton(text="🔄 processing", callback_data=f"adm:bst:{req_id}:processing"),
            ],
            [
                InlineKeyboardButton(text="✅ done", callback_data=f"adm:bst:{req_id}:done"),
                InlineKeyboardButton(text="❌ rejected", callback_data=f"adm:bst:{req_id}:rejected"),
            ],
            [InlineKeyboardButton(text="◀️ قائمة الإدارة", callback_data="adm:menu")],
        ]
    )


def runopen_status_keyboard(req_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="⏳ pending", callback_data=f"adm:rost:{req_id}:pending"),
                InlineKeyboardButton(text="🔄 processing", callback_data=f"adm:rost:{req_id}:processing"),
            ],
            [
                InlineKeyboardButton(text="✅ done", callback_data=f"adm:rost:{req_id}:done"),
                InlineKeyboardButton(text="❌ rejected", callback_data=f"adm:rost:{req_id}:rejected"),
            ],
            [InlineKeyboardButton(text="◀️ قائمة الإدارة", callback_data="adm:menu")],
        ]
    )


def box_pricing_admin_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="✏️ سعر كل الألعاب (مرة واحدة)",
                    callback_data="adm:box_set_all_cost",
                )
            ],
            [
                InlineKeyboardButton(
                    text="🎮 تعديل سعر كل لعبة",
                    callback_data="adm:boxgames",
                )
            ],
            [
                InlineKeyboardButton(
                    text="📩 سعر «طلب صندوق جديد»",
                    callback_data="adm:box_custom_cost",
                )
            ],
            [InlineKeyboardButton(text="◀️ الإدارة", callback_data="adm:menu")],
        ]
    )


def box_games_admin_keyboard(games: list) -> InlineKeyboardMarkup:
    rows = []
    for g in games:
        st = "✅" if g.active else "⛔"
        rows.append(
            [
                InlineKeyboardButton(
                    text=f"{st} {g.title} ({g.point_cost})",
                    callback_data=f"adm:boxg:{g.id}",
                )
            ]
        )
    rows.append(
        [
            InlineKeyboardButton(text="➕ لعبة", callback_data="adm:boxg_new"),
            InlineKeyboardButton(text="✏️ طلب مخصص", callback_data="adm:box_custom_cost"),
        ]
    )
    rows.append([InlineKeyboardButton(text="◀️ الإدارة", callback_data="adm:menu")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def box_game_actions_keyboard(game_id: int, active: bool) -> InlineKeyboardMarkup:
    toggle = "إيقاف" if active else "تفعيل"
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="✏️ تغيير النقاط", callback_data=f"adm:boxgcost:{game_id}")],
            [
                InlineKeyboardButton(
                    text=f"{'⛔' if active else '✅'} {toggle}",
                    callback_data=f"adm:boxgtoggle:{game_id}",
                )
            ],
            [InlineKeyboardButton(text="◀️ الألعاب", callback_data="adm:boxgames")],
        ]
    )


def promos_admin_keyboard(promos: list) -> InlineKeyboardMarkup:
    rows = []
    for p in promos:
        st = "✅" if p.active else "⛔"
        uses = f"{p.used_count}"
        if p.max_uses > 0:
            uses += f"/{p.max_uses}"
        rows.append(
            [
                InlineKeyboardButton(
                    text=f"{st} {p.code} +{p.points} ({uses})",
                    callback_data=f"adm:promo:{p.id}",
                )
            ]
        )
    rows.append(
        [
            InlineKeyboardButton(text="➕ برومو", callback_data="adm:promo_new"),
            InlineKeyboardButton(text="◀️ الإدارة", callback_data="adm:menu"),
        ]
    )
    return InlineKeyboardMarkup(inline_keyboard=rows)


def promo_actions_keyboard(promo_id: int, active: bool) -> InlineKeyboardMarkup:
    toggle = "إيقاف" if active else "تفعيل"
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text=f"{'⛔' if active else '✅'} {toggle}",
                    callback_data=f"adm:promo_toggle:{promo_id}",
                ),
                InlineKeyboardButton(text="🗑 حذف", callback_data=f"adm:promo_del:{promo_id}"),
            ],
            [InlineKeyboardButton(text="◀️ البرومو", callback_data="adm:promos")],
        ]
    )


def maintenance_admin_keyboard(enabled: bool) -> InlineKeyboardMarkup:
    label = "▶️ تشغيل البوت" if enabled else "⛔ إيقاف البوت للمستخدمين"
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text=label, callback_data="adm:maintenance_toggle")],
            [
                InlineKeyboardButton(text="⭐ نجوم فتح التشغيل", callback_data="adm:runopen_stars"),
            ],
            [InlineKeyboardButton(text="◀️ الإدارة", callback_data="adm:menu")],
        ]
    )


def task_actions_keyboard(task_id: int, active: bool) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="تبديل التفعيل",
                    callback_data=f"adm:ttoggle:{task_id}",
                ),
                InlineKeyboardButton(text="🗑 حذف", callback_data=f"adm:tdel:{task_id}"),
            ],
            [InlineKeyboardButton(text="◀️ المهام", callback_data="adm:tasks")],
        ]
    )
