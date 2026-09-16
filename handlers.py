from __future__ import annotations

import html
from datetime import datetime

from aiogram import F, Router
from aiogram.filters import Command, CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Message

import db
from config import REMIND_MINUTES_BEFORE
from timeparser import fmt_dt, parse_deadline, parse_remind, split_task_and_deadline

router = Router()


class AddTask(StatesGroup):
    text = State()
    deadline = State()
    remind = State()


def _main_menu() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="➕ Новая задача", callback_data="add_task")],
            [InlineKeyboardButton(text="📋 Мои задачи", callback_data="list_tasks")],
        ]
    )


def _tasks_render(tasks: list[dict]) -> tuple[str, InlineKeyboardMarkup]:
    lines = []
    buttons: list[list[InlineKeyboardButton]] = []
    for i, t in enumerate(tasks, 1):
        dt = datetime.fromisoformat(t["deadline"])
        overdue = datetime.now() >= dt
        mark = "🔴" if overdue else "🕐"
        lines.append(f"{mark} {i}. <b>{html.escape(t['text'])}</b>\n      ⏰ {fmt_dt(dt)}")
        buttons.append(
            [
                InlineKeyboardButton(
                    text="✅ Выполнена", callback_data=f"done:{t['id']}"
                ),
                InlineKeyboardButton(text="🗑 Удалить", callback_data=f"del:{t['id']}"),
            ]
        )
    buttons.append([InlineKeyboardButton(text="🔙 Меню", callback_data="main_menu")])
    text = "📋 <b>Твои задачи:</b>\n\n" + "\n\n".join(lines)
    return text, InlineKeyboardMarkup(inline_keyboard=buttons)


def _remind_markup() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="🕐 В срок (0)", callback_data="remind:0"),
                InlineKeyboardButton(text="За 10 мин", callback_data="remind:10"),
            ],
            [
                InlineKeyboardButton(text="За 30 мин", callback_data="remind:30"),
                InlineKeyboardButton(text="За 1 час", callback_data="remind:60"),
            ],
            [
                InlineKeyboardButton(text="За 2 часа", callback_data="remind:120"),
                InlineKeyboardButton(text="За 6 часов", callback_data="remind:360"),
            ],
        ]
    )


async def _send(
    target: Message | CallbackQuery,
    text: str,
    **kwargs,
) -> None:
    if isinstance(target, CallbackQuery):
        await target.message.answer(text, **kwargs)
    else:
        await target.answer(text, **kwargs)


async def _save_task(
    target: Message,
    user_id: int,
    task_text: str,
    deadline: datetime,
    remind_before: int | None = None,
    warn_past: bool = False,
) -> None:
    if remind_before is None:
        remind_before = REMIND_MINUTES_BEFORE
    past = deadline <= datetime.now()
    await db.add_task(user_id, task_text, deadline.isoformat(), remind_before)
    frames = [f"✅ Задача добавлена:\n<b>{html.escape(task_text)}</b>"]
    if past and warn_past:
        frames.insert(0, "⚠️ Внимание: срок уже прошёл или наступил!")
    frames.append(f"⏰ Срок: {fmt_dt(deadline)}")
    if remind_before <= 0:
        frames.append("🔔 Напомню в момент срока.")
    else:
        hours, mins = divmod(remind_before, 60)
        label = " ".join(
            str(x)
            for x in (
                f"{hours} ч" if hours else "",
                f"{mins} мин" if mins else "",
            )
            if x
        )
        frames.append(f"🔔 Напомню за {label} до срока.")
    await _send(target, "\n".join(frames), reply_markup=_main_menu())


async def _ask_remind(
    target: Message, state: FSMContext, task_text: str, deadline: datetime
) -> None:
    await state.update_data(task_text=task_text, deadline=deadline.isoformat())
    await state.set_state(AddTask.remind)
    await target.answer(
        f"⏰ Дедлайн: <b>{html.escape(task_text)}</b> — {fmt_dt(deadline)}\n\n"
        "🔔 <b>За сколько напомнить до срока?</b>",
        reply_markup=_remind_markup(),
    )


@router.message(CommandStart())
async def cmd_start(message: Message) -> None:
    await message.answer(
        "👋 Привет! Я твой помощник по задачам.\n\n"
        "Что умею:\n"
        "• <b>Добавлять задачи</b> с дедлайном\n"
        "• <b>Напоминать</b> когда и за сколько попросишь\n"
        "• Показывать и закрывать задачи\n\n"
        "Пример: <code>/add Отчёт до 18:00</code> или <code>/add Купить цветы завтра 12:00</code>",
        reply_markup=_main_menu(),
    )


@router.message(Command("help"))
async def cmd_help(message: Message) -> None:
    await cmd_start(message)


@router.message(Command("add"))
async def cmd_add(message: Message, state: FSMContext) -> None:
    parts = message.text.split(" ", 1)
    raw = parts[1].strip() if len(parts) > 1 else ""

    if not raw:
        await state.set_state(AddTask.text)
        await message.answer("✍️ О чём задача? Напиши текст или отправь /cancel.")
        return

    task_text, deadline = split_task_and_deadline(raw)
    if deadline is None:
        await state.set_state(AddTask.deadline)
        await state.update_data(task_text=task_text)
        await message.answer(
            f"⏰ Задача: <b>{html.escape(task_text)}</b>\n"
            "Не нашёл время. Когда дедлайн?\n"
            "Например: <i>«завтра 18:00»</i>, <i>«20.09 18:00»</i>, <i>«через 2 часа»</i>",
        )
        return

    await _ask_remind(message, state, task_text, deadline)


@router.message(Command("tasks"))
async def cmd_tasks(message: Message) -> None:
    await _send_tasks(message, message.from_user.id)


@router.message(Command("cancel"))
async def cmd_cancel(message: Message, state: FSMContext) -> None:
    current = await state.get_state()
    if current is not None:
        await state.clear()
        await message.answer("Отменено.", reply_markup=_main_menu())
    else:
        await message.answer("Нечего отменять 🙂", reply_markup=_main_menu())


@router.message(AddTask.text)
async def on_task_text(message: Message, state: FSMContext) -> None:
    await state.update_data(task_text=message.text.strip())
    await state.set_state(AddTask.deadline)
    await message.answer(
        "⏰ Когда дедлайн?\nНапример: <i>«завтра 18:00»</i>, <i>«20.09 18:00»</i>, "
        "<i>«через 2 часа»</i>\nОтправь /cancel, чтобы отменить.",
    )


@router.message(AddTask.deadline)
async def on_deadline(message: Message, state: FSMContext) -> None:
    data = await state.get_data()
    deadline = parse_deadline(message.text)
    if deadline is None:
        await message.answer(
            "😅 Не понял время. Попробуй ещё раз, например: <i>«завтра 18:00»</i> "
            "или отправь /cancel."
        )
        return
    await _ask_remind(message, state, data["task_text"], deadline)


@router.message(AddTask.remind)
async def on_remind(message: Message, state: FSMContext) -> None:
    data = await state.get_data()
    minutes = parse_remind(message.text)
    if minutes is None:
        await message.answer(
            "😅 Не понял. Напиши число минут (например: <b>15</b>), "
            "<i>«за 2 часа»</i> или выбери кнопку.",
            reply_markup=_remind_markup(),
        )
        return
    await state.clear()
    await _save_task(
        message,
        message.from_user.id,
        data["task_text"],
        datetime.fromisoformat(data["deadline"]),
        remind_before=minutes,
        warn_past=True,
    )


@router.callback_query(F.data.startswith("remind:"))
async def cb_remind(callback: CallbackQuery, state: FSMContext) -> None:
    minutes = int(callback.data.split(":", 1)[1])
    data = await state.get_data()
    await state.clear()
    await _save_task(
        callback,
        callback.from_user.id,
        data["task_text"],
        datetime.fromisoformat(data["deadline"]),
        remind_before=minutes,
        warn_past=True,
    )
    await callback.answer()


@router.callback_query(F.data == "add_task")
async def cb_add_task(callback: CallbackQuery, state: FSMContext) -> None:
    await state.set_state(AddTask.text)
    await callback.message.answer("✍️ О чём задача? Напиши текст или отправь /cancel.")
    await callback.answer()


@router.callback_query(F.data == "list_tasks")
async def cb_list_tasks(callback: CallbackQuery) -> None:
    await _send_tasks(callback, callback.from_user.id)
    await callback.answer()


@router.callback_query(F.data == "main_menu")
async def cb_main_menu(callback: CallbackQuery) -> None:
    await callback.message.edit_text("Меню:", reply_markup=_main_menu())
    await callback.answer()


@router.callback_query(F.data.startswith("done:"))
async def cb_done(callback: CallbackQuery) -> None:
    task = await db.get_task(int(callback.data.split(":", 1)[1]))
    if task is None or task["user_id"] != callback.from_user.id:
        await callback.answer("Задача не найдена", show_alert=True)
        return
    await db.mark_done(task["id"])
    await callback.answer("✅ Задача выполнена!")
    remaining = await db.get_active_tasks(callback.from_user.id)
    if remaining:
        text, markup = _tasks_render(remaining)
        await callback.message.edit_text(text, reply_markup=markup)
    else:
        await callback.message.edit_text(
            "🏁 Все задачи выполнены. Отличная работа!",
            reply_markup=_main_menu(),
        )


@router.callback_query(F.data.startswith("del:"))
async def cb_delete(callback: CallbackQuery) -> None:
    task = await db.get_task(int(callback.data.split(":", 1)[1]))
    if task is None or task["user_id"] != callback.from_user.id:
        await callback.answer("Задача не найдена", show_alert=True)
        return
    await db.delete_task(task["id"])
    await callback.answer("🗑 Задача удалена.")
    remaining = await db.get_active_tasks(callback.from_user.id)
    if remaining:
        text, markup = _tasks_render(remaining)
        await callback.message.edit_text(text, reply_markup=markup)
    else:
        await callback.message.edit_text(
            "📭 Задач больше нет.", reply_markup=_main_menu()
        )


async def _send_tasks(target: Message | CallbackQuery, user_id: int) -> None:
    tasks = await db.get_active_tasks(user_id)
    if not tasks:
        text = "📭 Задач пока нет. Добавь первую!"
        markup = _main_menu()
    else:
        text, markup = _tasks_render(tasks)
    await _send(target, text, reply_markup=markup)