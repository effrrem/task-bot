from __future__ import annotations

import logging

from aiohttp import web

import db
from config import WEBAPP_PORT, WEBAPP_SECRET

logger = logging.getLogger(__name__)

routes = web.RouteTableDef()


@routes.get("/health")
async def health(_: web.Request) -> web.Response:
    return web.json_response({"ok": True})


@routes.get("/api/tasks")
async def api_tasks(request: web.Request) -> web.Response:
    if not WEBAPP_SECRET or request.headers.get("X-App-Secret") != WEBAPP_SECRET:
        return web.json_response({"error": "forbidden"}, status=403)

    user_id = request.query.get("user_id", "")
    if not user_id.isdigit():
        return web.json_response({"error": "bad user_id"}, status=400)

    tasks = await db.get_user_tasks(int(user_id))
    payload = [
        {
            "id": t["id"],
            "text": t["text"],
            "deadline": t["deadline"],
            "done": bool(t["done"]),
            "reminded": bool(t["reminded"]),
        }
        for t in tasks
    ]
    return web.json_response(payload)


async def run_webapi() -> None:
    app = web.Application()
    app.add_routes(routes)
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, "0.0.0.0", WEBAPP_PORT)
    await site.start()
    logger.info("Web API listening on 0.0.0.0:%d", WEBAPP_PORT)