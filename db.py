from __future__ import annotations

from pathlib import Path

import aiosqlite

from config import REMIND_MINUTES_BEFORE

DB_PATH = str(Path(__file__).resolve().parent / "tasks.db")


async def _conn() -> aiosqlite.Connection:
    return await aiosqlite.connect(DB_PATH)


async def init() -> None:
    db = await _conn()
    try:
        await db.execute(
            """
            CREATE TABLE IF NOT EXISTS tasks (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                text TEXT NOT NULL,
                deadline TEXT NOT NULL,
                done INTEGER NOT NULL DEFAULT 0,
                reminded INTEGER NOT NULL DEFAULT 0,
                remind_before INTEGER NOT NULL DEFAULT 10,
                created_at TEXT NOT NULL
            )
            """
        )
        cur = await db.execute("PRAGMA table_info(tasks)")
        cols = {row[1] for row in await cur.fetchall()}
        if "remind_before" not in cols:
            await db.execute(
                "ALTER TABLE tasks ADD COLUMN remind_before INTEGER "
                f"NOT NULL DEFAULT {int(REMIND_MINUTES_BEFORE)}"
            )
        await db.commit()
    finally:
        await db.close()


async def add_task(
    user_id: int, text: str, deadline: str, remind_before: int | None = None
) -> int:
    if remind_before is None:
        remind_before = REMIND_MINUTES_BEFORE
    db = await _conn()
    try:
        cur = await db.execute(
            "INSERT INTO tasks (user_id, text, deadline, remind_before, created_at) "
            "VALUES (?, ?, ?, ?, ?)",
            (user_id, text, deadline, int(remind_before), deadline),
        )
        await db.commit()
        return cur.lastrowid
    finally:
        await db.close()


async def get_user_tasks(user_id: int) -> list[dict]:
    db = await _conn()
    try:
        db.row_factory = aiosqlite.Row
        cur = await db.execute(
            "SELECT * FROM tasks WHERE user_id = ? ORDER BY deadline", (user_id,)
        )
        rows = await cur.fetchall()
        return [dict(r) for r in rows]
    finally:
        await db.close()


async def get_task(task_id: int) -> dict | None:
    db = await _conn()
    try:
        db.row_factory = aiosqlite.Row
        cur = await db.execute("SELECT * FROM tasks WHERE id = ?", (task_id,))
        row = await cur.fetchone()
        return dict(row) if row else None
    finally:
        await db.close()


async def get_active_tasks(user_id: int) -> list[dict]:
    db = await _conn()
    try:
        db.row_factory = aiosqlite.Row
        cur = await db.execute(
            "SELECT * FROM tasks WHERE user_id = ? AND done = 0 ORDER BY deadline",
            (user_id,),
        )
        rows = await cur.fetchall()
        return [dict(r) for r in rows]
    finally:
        await db.close()


async def get_all_pending() -> list[dict]:
    db = await _conn()
    try:
        db.row_factory = aiosqlite.Row
        cur = await db.execute(
            "SELECT * FROM tasks WHERE done = 0 AND reminded = 0 ORDER BY deadline"
        )
        rows = await cur.fetchall()
        return [dict(r) for r in rows]
    finally:
        await db.close()


async def mark_reminded(task_id: int) -> None:
    db = await _conn()
    try:
        await db.execute("UPDATE tasks SET reminded = 1 WHERE id = ?", (task_id,))
        await db.commit()
    finally:
        await db.close()


async def mark_done(task_id: int) -> None:
    db = await _conn()
    try:
        await db.execute("UPDATE tasks SET done = 1 WHERE id = ?", (task_id,))
        await db.commit()
    finally:
        await db.close()


async def update_task_done(task_id: int, user_id: int, done: bool) -> bool:
    db = await _conn()
    try:
        cur = await db.execute(
            "UPDATE tasks SET done = ? WHERE id = ? AND user_id = ?",
            (int(done), task_id, user_id),
        )
        await db.commit()
        return (cur.rowcount or 0) > 0
    finally:
        await db.close()


async def delete_task_by_user(task_id: int, user_id: int) -> bool:
    db = await _conn()
    try:
        cur = await db.execute(
            "DELETE FROM tasks WHERE id = ? AND user_id = ?",
            (task_id, user_id),
        )
        await db.commit()
        return (cur.rowcount or 0) > 0
    finally:
        await db.close()


async def delete_task(task_id: int) -> None:
    db = await _conn()
    try:
        await db.execute("DELETE FROM tasks WHERE id = ?", (task_id,))
        await db.commit()
    finally:
        await db.close()