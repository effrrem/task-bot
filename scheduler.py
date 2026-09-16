import asyncio
import logging
from datetime import datetime, timedelta

from aiogram import Bot

import db
from config import REMIND_MINUTES_BEFORE
from timeparser import fmt_dt

logger = logging.getLogger(__name__)


def _format_reminder(text: str, deadline: datetime, past: bool = False) -> str:
    header = "🔴 Дедлайн наступил!" if past else "⏰ Напоминание"
    return (
        f"<b>{header}</b>\n\n"
        f"📝 {text}\n"
        f"⏰ Срок: {fmt_dt(deadline)}"
    )


async def _send_reminder(bot: Bot, task: dict) -> None:
    deadline = datetime.fromisoformat(task["deadline"])
    past = datetime.now() >= deadline
    text = _format_reminder(task["text"], deadline, past)

    try:
        await bot.send_message(
            chat_id=task["user_id"],
            text=text,
        )
    except Exception:
        logger.exception("Failed to send reminder for task %s", task["id"])


async def run_scheduler(bot: Bot) -> None:
    logger.info("Scheduler started (remind %d min before)", REMIND_MINUTES_BEFORE)
    while True:
        try:
            now = datetime.now()
            tasks = await db.get_all_pending()
            for task in tasks:
                deadline = datetime.fromisoformat(task["deadline"])
                remind_at = deadline - timedelta(minutes=REMIND_MINUTES_BEFORE)
                if now >= remind_at:
                    await _send_reminder(bot, task)
                    await db.mark_reminded(task["id"])
        except asyncio.CancelledError:
            raise
        except Exception:
            logger.exception("scheduler tick error")
        await asyncio.sleep(20)