from __future__ import annotations

from aiogram import F, Router
from aiogram.filters import Command, CommandStart
from aiogram.types import (
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    Message,
    WebAppInfo,
)

from config import WEBAPP_URL

router = Router()


def _menu() -> InlineKeyboardMarkup:
    rows: list[list[InlineKeyboardButton]] = []
    if WEBAPP_URL:
        rows.append(
            [InlineKeyboardButton(text="📅 Календарь", web_app=WebAppInfo(url=WEBAPP_URL))]
        )
    return InlineKeyboardMarkup(inline_keyboard=rows)


@router.message(CommandStart())
async def cmd_start(message: Message) -> None:
    await message.answer(
        "👋 Привет! Я твой помощник по задачам.\n\n"
        "📱 <b>Планируй задачи в приложении</b> — нажми «📅 Календарь».\n"
        "🔔 Сюда в чат я присылаю только <b>напоминания</b> о сроках.",
        reply_markup=_menu(),
    )


@router.message(Command("help"))
async def cmd_help(message: Message) -> None:
    await cmd_start(message)


@router.message(Command("app"))
async def cmd_app(message: Message) -> None:
    await message.answer("📅 Открой календарь с задачами:", reply_markup=_menu())


@router.message(F.text)
async def on_any_text(message: Message) -> None:
    await message.answer(
        "🙅‍♂️ Задачи создаются только в приложении.\n\n"
        "Открой <b>«📅 Календарь»</b> в меню и добавь задачу там.\n"
        "В этот чат я присылаю только напоминания.",
        reply_markup=_menu(),
    )