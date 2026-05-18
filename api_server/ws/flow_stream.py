from __future__ import annotations

import asyncio

from fastapi import WebSocket, WebSocketDisconnect

from api_server.dependencies import get_runtime


async def handle_ws_flow(websocket: WebSocket, session_id: str) -> None:
    """ADR-024 Phase 7 S14 — real-time flow events for the sequence diagram.

    Mirrors :func:`api_server.ws.log_stream.handle_ws_logs` but carries
    structured *flow* events (vitals_ingest, imu_predict, alert_push, …)
    instead of human-readable log lines.

    * Replays no history on connect — the sequence diagram always shows
      the live run, not an archived one.
    * Keepalive ping every 10 s so the browser WebSocket doesn't time out.
    """
    runtime = get_runtime()
    await websocket.accept()
    queue: asyncio.Queue[dict] = runtime.subscribe_flow_events(session_id)
    try:
        while True:
            try:
                event = await asyncio.wait_for(queue.get(), timeout=10.0)
                await websocket.send_json(event)
            except asyncio.TimeoutError:
                await websocket.send_json(
                    {"type": "keepalive", "session_id": session_id}
                )
    except WebSocketDisconnect:
        pass
    finally:
        runtime.unsubscribe_flow_events(session_id, queue)
