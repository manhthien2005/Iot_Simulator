from __future__ import annotations

import asyncio
from typing import Any

from fastapi import WebSocket, WebSocketDisconnect

from Iot_Simulator.api_server.dependencies import get_runtime


async def handle_ws_logs(websocket: WebSocket, session_id: str) -> None:
    runtime = get_runtime()
    await websocket.accept()
    queue = runtime.logs.subscribe(session_id)
    try:
        for entry in runtime.logs.history(session_id):
            await websocket.send_json(entry)
        while True:
            try:
                entry: dict[str, Any] = await asyncio.wait_for(queue.get(), timeout=10.0)
                await websocket.send_json(entry)
            except asyncio.TimeoutError:
                await websocket.send_json({"level": "INFO", "session_id": session_id, "device_id": "system", "message": "keepalive", "ts": runtime.sessions.get(session_id).last_tick_at if session_id in runtime.sessions else None})
    except WebSocketDisconnect:
        pass
    finally:
        runtime.logs.unsubscribe(session_id, queue)

