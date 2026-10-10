from aiogram import Bot

from app.services.admin_notify import get_admin_ids


async def notify_admins(bot: Bot, text: str) -> None:
    for admin_id in get_admin_ids():
        try:
            await bot.send_message(admin_id, text)
        except Exception:
            pass
