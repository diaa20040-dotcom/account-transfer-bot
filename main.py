import asyncio
import logging
from contextlib import asynccontextmanager
from typing import AsyncIterator

import uvicorn
from aiogram import Bot, Dispatcher
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import Update
from fastapi import FastAPI, Header, HTTPException, Request

from app.bot.admin_handlers import router as admin_router
from app.bot.box_handlers import router as box_router
from app.bot.group_guard import router as group_guard_router
from app.bot.handlers import router as user_router
from app.bot.payments_handlers import router as payments_router
from app.bot.promo_handlers import router as promo_router
from app.bot.run_open_handlers import router as run_open_router
from app.bot.middlewares import (
    MaintenanceMiddleware,
    MandatorySubMiddleware,
    PrivateChatsOnlyMiddleware,
)
from app.config import settings
from app.database import init_db
from app.services.admin_notify import set_admin_ids

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

_bot_polling_alive = False


def build_dispatcher() -> Dispatcher:
    dp = Dispatcher(storage=MemoryStorage())
    dp.message.middleware(PrivateChatsOnlyMiddleware())
    dp.callback_query.middleware(PrivateChatsOnlyMiddleware())
    dp.message.middleware(MandatorySubMiddleware())
    dp.callback_query.middleware(MandatorySubMiddleware())
    dp.message.middleware(MaintenanceMiddleware())
    dp.callback_query.middleware(MaintenanceMiddleware())
    dp.include_router(group_guard_router)
    dp.include_router(admin_router)
    dp.include_router(payments_router)
    dp.include_router(box_router)
    dp.include_router(run_open_router)
    dp.include_router(promo_router)
    dp.include_router(user_router)
    return dp


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


def use_webhook_mode() -> bool:
    return bool(settings.public_url.strip())


def webhook_url() -> str:
    base = settings.public_url.strip().rstrip("/")
    path = settings.webhook_path if settings.webhook_path.startswith("/") else f"/{settings.webhook_path}"
    return f"{base}{path}"


async def run_polling_with_restart(bot: Bot, dp: Dispatcher) -> None:
    global _bot_polling_alive
    delay = 5
    while True:
        try:
            _bot_polling_alive = True
            me = await bot.get_me()
            logger.info("Polling started as @%s", me.username)
            set_admin_ids(await resolve_admin_ids(bot))
            await dp.start_polling(bot)
        except asyncio.CancelledError:
            _bot_polling_alive = False
            raise
        except Exception:
            _bot_polling_alive = False
            logger.exception("Bot polling stopped; retry in %ss", delay)
            await asyncio.sleep(delay)
            delay = min(delay * 2, 60)


async def ensure_telegram_webhook(bot: Bot, dp: Dispatcher) -> None:
    if not use_webhook_mode():
        return
    url = webhook_url()
    try:
        info = await bot.get_webhook_info()
        if info.url != url:
            await bot.set_webhook(
                url,
                secret_token=settings.webhook_secret or None,
                allowed_updates=dp.resolve_used_update_types(),
                drop_pending_updates=False,
            )
            logger.info("Webhook re-registered at %s", url)
    except Exception:
        logger.exception("ensure_telegram_webhook failed")


def register_routes(app: FastAPI, bot: Bot, dp: Dispatcher) -> None:
    @app.get("/health")
    async def health():
        await ensure_telegram_webhook(bot, dp)
        mode = "webhook" if use_webhook_mode() else "polling"
        hooked = False
        if use_webhook_mode():
            try:
                info = await bot.get_webhook_info()
                hooked = info.url == webhook_url()
            except Exception:
                hooked = False
        from app.config import settings

        db_kind = "postgres" if "postgres" in settings.database_url.lower() else "sqlite"
        return {
            "status": "ok",
            "bot_mode": mode,
            "database": db_kind,
            "polling_alive": _bot_polling_alive,
            "webhook_ok": hooked,
        }

    if use_webhook_mode():

        @app.post(settings.webhook_path)
        async def telegram_webhook(
            request: Request,
            x_telegram_bot_api_secret_token: str | None = Header(default=None),
        ):
            if settings.webhook_secret:
                if x_telegram_bot_api_secret_token != settings.webhook_secret:
                    raise HTTPException(status_code=403, detail="invalid webhook secret")
            try:
                payload = await request.json()
                update = Update.model_validate(payload)
                await dp.feed_update(bot, update)
            except Exception:
                logger.exception("Webhook update handling failed")
            return {"ok": True}


def create_http_app(bot: Bot, dp: Dispatcher, lifespan) -> FastAPI:
    if settings.enable_web_admin:
        from app.admin.app import create_admin_app

        app = create_admin_app()
    else:
        app = FastAPI(title="Transfer Bot", lifespan=lifespan)
    register_routes(app, bot, dp)
    return app


async def main() -> None:
    init_db()
    bot = Bot(token=settings.bot_token)
    dp = build_dispatcher()

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        polling_task: asyncio.Task | None = None
        me = await bot.get_me()
        logger.info("Bot ready as @%s", me.username)
        set_admin_ids(await resolve_admin_ids(bot))

        if use_webhook_mode():
            await ensure_telegram_webhook(bot, dp)
            logger.info("Webhook mode: %s", webhook_url())
        else:
            polling_task = asyncio.create_task(run_polling_with_restart(bot, dp))
            logger.info("Polling mode (set RENDER_EXTERNAL_URL on cloud hosts)")

        yield

        # Do not delete webhook on shutdown — Render redeploys would leave the bot offline.
        if polling_task:
            polling_task.cancel()
            try:
                await polling_task
            except asyncio.CancelledError:
                pass
        from app.database import SessionLocal
        from app.services.startup_seed import persist_runtime_snapshot

        snap_db = SessionLocal()
        try:
            persist_runtime_snapshot(snap_db)
        finally:
            snap_db.close()
        await bot.session.close()

    app = create_http_app(bot, dp, lifespan)
    app.state.bot = bot
    app.state.dp = dp

    mode = "webhook" if use_webhook_mode() else "polling"
    web = "bot + web admin" if settings.enable_web_admin else "bot + /health"
    logger.info("Starting (%s, %s) on port %s", web, mode, settings.port)

    config = uvicorn.Config(
        app,
        host=settings.host,
        port=settings.port,
        log_level="info",
        access_log=False,
        loop="asyncio",
    )
    server = uvicorn.Server(config)
    await server.serve()


if __name__ == "__main__":
    asyncio.run(main())
