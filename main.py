import asyncio
import logging

import uvicorn
from aiogram import Bot, Dispatcher
from aiogram.fsm.storage.memory import MemoryStorage
from fastapi import FastAPI

from app.bot.admin_handlers import router as admin_router
from app.bot.group_guard import router as group_guard_router
from app.bot.handlers import router as user_router
from app.bot.payments_handlers import router as payments_router
from app.bot.middlewares import MandatorySubMiddleware, PrivateChatsOnlyMiddleware
from app.config import settings
from app.database import init_db
from app.services.admin_notify import set_admin_ids

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def create_health_app() -> FastAPI:
    app = FastAPI(title="Transfer Bot")

    @app.get("/health")
    async def health():
        return {"status": "ok"}

    return app


def create_http_app() -> FastAPI:
    if settings.enable_web_admin:
        from app.admin.app import create_admin_app

        return create_admin_app()
    return create_health_app()


async def resolve_admin_ids(bot: Bot) -> list[int]:
    ids: set[int] = set(settings.admin_ids)
    for username in settings.admin_usernames:
        try:
            chat = await bot.get_chat(f"@{username}")
            ids.add(chat.id)
            logger.info("Admin resolved @%s -> %s", username, chat.id)
        except Exception as exc:
            logger.warning("Could not resolve admin @%s: %s", username, exc)
    return list(ids)


async def run_bot() -> None:
    bot = Bot(token=settings.bot_token)
    dp = Dispatcher(storage=MemoryStorage())
    dp.message.middleware(PrivateChatsOnlyMiddleware())
    dp.callback_query.middleware(PrivateChatsOnlyMiddleware())
    dp.message.middleware(MandatorySubMiddleware())
    dp.callback_query.middleware(MandatorySubMiddleware())
    dp.include_router(group_guard_router)
    dp.include_router(admin_router)
    dp.include_router(payments_router)
    dp.include_router(user_router)
    me = await bot.get_me()
    logger.info("Bot started as @%s", me.username)
    set_admin_ids(await resolve_admin_ids(bot))
    await dp.start_polling(bot)


async def main() -> None:
    init_db()
    mode = "bot + web admin" if settings.enable_web_admin else "bot + /health only"
    logger.info("Starting (%s) on port %s", mode, settings.port)
    config = uvicorn.Config(
        create_http_app(),
        host=settings.host,
        port=settings.port,
        log_level="warning",
        access_log=False,
        loop="asyncio",
    )
    server = uvicorn.Server(config)
    bot_task = asyncio.create_task(run_bot())
    try:
        await server.serve()
    finally:
        bot_task.cancel()


if __name__ == "__main__":
    asyncio.run(main())
