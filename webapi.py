from __future__ import annotations

import logging
from datetime import datetime

from aiohttp import web

import db
from config import REMIND_MINUTES_BEFORE, WEBAPP_PORT, WEBAPP_SECRET

logger = logging.getLogger(__name__)

routes = web.RouteTableDef()

MAX_TASK_TEXT = 300
MAX_REMIND_MIN = 10080  # 7 дней — верхний предел «напомнить до»


def _authorized(request: web.Request) -> bool:
    return bool(WEBAPP_SECRET) and request.headers.get("X-App-Secret") == WEBAPP_SECRET


def _bad(msg: str, status: int = 400) -> web.Response:
    return web.json_response({"error": msg}, status=status)


async def _read_user_id(body: dict) -> int | None:
    uid = body.get("user_id")
    if isinstance(uid, bool) or not isinstance(uid, (int, str)):
        return None
    if isinstance(uid, str) and not uid.isdigit():
        return None
    return int(uid)


@routes.get("/health")
async def health(_: web.Request) -> web.Response:
    return web.json_response({"ok": True})


@routes.get("/api/tasks")
async def api_tasks(request: web.Request) -> web.Response:
    if not _authorized(request):
        return _bad("forbidden", 403)
    user_id = request.query.get("user_id", "")
    if not user_id.isdigit():
        return _bad("bad user_id")

    tasks = await db.get_user_tasks(int(user_id))
    payload = [
        {
            "id": t["id"],
            "text": t["text"],
            "deadline": t["deadline"],
            "done": bool(t["done"]),
            "reminded": bool(t["reminded"]),
            "remind_before": int(t.get("remind_before") or REMIND_MINUTES_BEFORE),
        }
        for t in tasks
    ]
    return web.json_response(payload)


@routes.post("/api/tasks/create")
async def api_create(request: web.Request) -> web.Response:
    if not _authorized(request):
        return _bad("forbidden", 403)
    try:
        body = await request.json()
    except Exception:
        return _bad("bad json")
    if not isinstance(body, dict):
        return _bad("bad body")

    user_id = await _read_user_id(body)
    if user_id is None:
        return _bad("bad user_id")

    text = str(body.get("text", "") or "").strip()
    if not text:
        return _bad("bad text")
    text = text[:MAX_TASK_TEXT]

    try:
        deadline = datetime.fromisoformat(body.get("deadline", ""))
    except (TypeError, ValueError):
        return _bad("bad deadline")

    remind_before = body.get("remind_before", REMIND_MINUTES_BEFORE)
    if isinstance(remind_before, bool):
        remind_before = REMIND_MINUTES_BEFORE
    try:
        remind_before = int(remind_before)
    except (TypeError, ValueError):
        remind_before = REMIND_MINUTES_BEFORE
    if remind_before < 0 or remind_before > MAX_REMIND_MIN:
        remind_before = REMIND_MINUTES_BEFORE

    task_id = await db.add_task(user_id, text, deadline.isoformat(), remind_before)
    return web.json_response(
        {
            "id": task_id,
            "text": text,
            "deadline": deadline.isoformat(),
            "done": False,
            "reminded": False,
            "remind_before": int(remind_before),
        },
        status=201,
    )


@routes.post("/api/tasks/update")
async def api_update(request: web.Request) -> web.Response:
    if not _authorized(request):
        return _bad("forbidden", 403)
    try:
        body = await request.json()
    except Exception:
        return _bad("bad json")
    if not isinstance(body, dict):
        return _bad("bad body")

    user_id = await _read_user_id(body)
    task_id = body.get("id")
    if user_id is None or task_id is None or isinstance(task_id, bool):
        return _bad("bad ids")
    try:
        task_id = int(task_id)
    except (TypeError, ValueError):
        return _bad("bad id")

    if body.get("delete"):
        ok = await db.delete_task_by_user(task_id, user_id)
        return web.json_response({"ok": bool(ok)})

    done = body.get("done")
    if done is None:
        return _bad("nothing to update")
    ok = await db.update_task_done(task_id, user_id, bool(done))
    return web.json_response({"ok": bool(ok)})


async def run_webapi() -> None:
    app = web.Application()
    app.add_routes(routes)
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, "0.0.0.0", WEBAPP_PORT)
    await site.start()
    logger.info("Web API listening on 0.0.0.0:%d", WEBAPP_PORT)