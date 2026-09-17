import asyncio
import html
import logging
from datetime import datetime, timedelta

from aiogram import Bot
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup, WebAppInfo

import db
from config import REMIND_MINUTES_BEFORE, WEBAPP_URL
from timeparser import fmt_dt

logger = logging.getLogger(__name__)


def _fmt_duration(mins: int) -> str:
    mins = max(1, mins)
    hours, rest = divmod(mins, 60)
    if hours and rest:
        return f"{hours} ч {rest} мин"
    if hours:
        return f"{hours} ч"
    return f"{rest} мин"


def _reminder_markup() -> InlineKeyboardMarkup | None:
    if not WEBAPP_URL:
        return None
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="📅 Открыть календарь",
                    web_app=WebAppInfo(url=WEBAPP_URL),
                )
            ]
        ]
    )


def _format_reminder(text: str, deadline: datetime, remind_before: int) -> str:
    past = datetime.now() >= deadline
    task_line = f"📌 <b>{html.escape(text)}</b>"
    deadline_line = f"🗓 Срок: <b>{fmt_dt(deadline)}</b>"

    if past:
        header = "🚨🚨 <b>ДЕДЛАЙН НАСТУПИЛ!</b> 🚨🚨"
        body = "\n\n".join([header, task_line, deadline_line])
    else:
        header = "🔔⏰ <b>НАПОМИНАНИЕ О ЗАДАЧЕ</b> 🔔⏰"
        left = f"⏳ Осталось: <b>{_fmt_duration(remind_before)}</b>"
        body = "\n\n".join([header, task_line, left, deadline_line])

    return body + "\n\n━━━━━━━━━━━━━━━━━"


async def _send_reminder(bot: Bot, task: dict) -> None:
    deadline = datetime.fromisoformat(task["deadline"])
    text = _format_reminder(
        task["text"], deadline, task.get("remind_before") or REMIND_MINUTES_BEFORE
    )

    try:
        await bot.send_message(
            chat_id=task["user_id"],
            text=text,
            parse_mode="HTML",
            reply_markup=_reminder_markup(),
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
                remind_at = deadline - timedelta(
                    minutes=task.get("remind_before") or REMIND_MINUTES_BEFORE
                )
                if now >= remind_at:
                    await _send_reminder(bot, task)
                    await db.mark_reminded(task["id"])
        except asyncio.CancelledError:
            raise
        except Exception:
            logger.exception("scheduler tick error")
        await asyncio.sleep(20)