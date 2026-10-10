from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

ADMIN_BTN_AR = "🛠 لوحة الإدارة"
ADMIN_BTN_EN = "🛠 Admin panel"


def admin_main_inline() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="📥 طلبات التحويل", callback_data="adm:transfers:0")],
            [InlineKeyboardButton(text="🌍 الدول والنقاط", callback_data="adm:countries")],
            [
                InlineKeyboardButton(text="📋 المهام", callback_data="adm:tasks"),
                InlineKeyboardButton(text="➕ مهمة جديدة", callback_data="adm:task_new"),
            ],
            [
                InlineKeyboardButton(text="⚙️ نقاط الإحالة", callback_data="adm:referral"),
                InlineKeyboardButton(text="👥 المستخدمون", callback_data="adm:users:0"),
            ],
            [InlineKeyboardButton(text="💎 إضافة نقاط لمستخدم", callback_data="adm:addpoints")],
            [InlineKeyboardButton(text="📢 اشتراك إجباري", callback_data="adm:msub")],
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
