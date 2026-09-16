import asyncio
import logging

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.client.session.aiohttp import AiohttpSession
from aiogram.client.telegram import TelegramAPIServer
from aiogram.enums import ParseMode

import handlers
from config import BOT_TOKEN, TG_PROXY_BASE, TG_PROXY_KEY
from db import init as init_db
from scheduler import run_scheduler
from webapi import run_webapi

logger = logging.getLogger(__name__)


def _make_session() -> AiohttpSession:
    if TG_PROXY_BASE and TG_PROXY_KEY:
        api = TelegramAPIServer.from_base(f"{TG_PROXY_BASE}/{TG_PROXY_KEY}")
        logger.info("Using Telegram API proxy: %s", TG_PROXY_BASE)
    else:
        api = TelegramAPIServer.from_base("https://api.telegram.org")
    return AiohttpSession(api=api, timeout=60)


async def _start_with_retry(bot: Bot, dp: Dispatcher) -> None:
    for attempt in range(1, 11):
        try:
            logger.info("Attempt %d: connecting to Telegram API...", attempt)
            await bot.delete_webhook(drop_pending_updates=True)
            logger.info("Webhook cleared, starting polling...")
            await dp.start_polling(bot)
            return
        except Exception as e:
            wait = min(attempt * 5, 60)
            logger.warning(
                "Attempt %d failed: %s — retrying in %ds", attempt, e, wait
            )
            await asyncio.sleep(wait)
    logger.error("Could not connect after 10 attempts, exiting.")
    raise SystemExit(1)


async def main() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
    await init_db()

    bot = Bot(
        token=BOT_TOKEN,
        session=_make_session(),
        default=DefaultBotProperties(parse_mode=ParseMode.HTML),
    )
    dp = Dispatcher()
    dp.include_router(handlers.router)

    scheduler_task = asyncio.create_task(run_scheduler(bot))
    webapi_task = asyncio.create_task(run_webapi())

    try:
        await _start_with_retry(bot, dp)
    finally:
        scheduler_task.cancel()
        webapi_task.cancel()
        await bot.session.close()


if __name__ == "__main__":
    asyncio.run(main())