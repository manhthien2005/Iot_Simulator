from __future__ import annotations

import logging
import os
from contextlib import asynccontextmanager
from pathlib import Path
from typing import AsyncIterator

from dotenv import load_dotenv
from fastapi import FastAPI, WebSocket
from fastapi.middleware.cors import CORSMiddleware

_ENV_CANDIDATES = [
    Path(__file__).resolve().parents[1] / ".env",
    Path(__file__).resolve().parents[2] / ".env",
]
for _env_path in _ENV_CANDIDATES:
    if _env_path.exists():
        load_dotenv(_env_path, override=False)
        break

try:
    from Iot_Simulator.api_server.middleware.rate_limit import RateLimitMiddleware
    from Iot_Simulator.api_server.dependencies import SimulatorRuntime, get_runtime, set_runtime
    from Iot_Simulator.api_server.routers.analytics import router as analytics_router
    from Iot_Simulator.api_server.routers.dashboard import router as dashboard_router
    from Iot_Simulator.api_server.routers.devices import router as devices_router
    from Iot_Simulator.api_server.routers.events import router as events_router
    from Iot_Simulator.api_server.routers.registry import router as registry_router
    from Iot_Simulator.api_server.routers.scenarios import router as scenarios_router
    from Iot_Simulator.api_server.routers.sessions import router as sessions_router
    from Iot_Simulator.api_server.routers.settings import router as settings_router
    from Iot_Simulator.api_server.routers.verification import router as verification_router
    from Iot_Simulator.api_server.routers.vitals import router as vitals_router
    from Iot_Simulator.api_server.ws.log_stream import handle_ws_logs
except ModuleNotFoundError:
    from api_server.middleware.rate_limit import RateLimitMiddleware
    from api_server.dependencies import SimulatorRuntime, get_runtime, set_runtime
    from api_server.routers.analytics import router as analytics_router
    from api_server.routers.dashboard import router as dashboard_router
    from api_server.routers.devices import router as devices_router
    from api_server.routers.events import router as events_router
    from api_server.routers.registry import router as registry_router
    from api_server.routers.scenarios import router as scenarios_router
    from api_server.routers.sessions import router as sessions_router
    from api_server.routers.settings import router as settings_router
    from api_server.routers.verification import router as verification_router
    from api_server.routers.vitals import router as vitals_router
    from api_server.ws.log_stream import handle_ws_logs


logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Startup / shutdown lifecycle — initialises the runtime singleton
    and stores it on ``app.state`` so tests can access or replace it."""
    runtime = SimulatorRuntime()
    set_runtime(runtime)
    app.state.runtime = runtime
    runtime.start_background_tick()
    recovered = runtime.recover_active_sessions()
    if recovered:
        logger.info("Auto-recovered %d active device session(s) on startup", recovered)
    else:
        logger.info("No active DB devices to recover on startup")
    yield
    runtime.shutdown()


app = FastAPI(title="IoT Simulator API", version="1.0.0", lifespan=lifespan)

ALLOWED_ORIGINS = os.getenv("ALLOWED_ORIGINS", "http://localhost:5173,http://localhost:5174").split(",")

# NOTE: Starlette processes middlewares in LIFO order (last-added = outermost).
# CORSMiddleware MUST be outermost so that even rate-limited 429 responses
# carry correct CORS headers; otherwise the browser treats them as opaque
# network errors and the frontend shows "API Simulator không khả dụng".
app.add_middleware(RateLimitMiddleware)
app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_origin_regex=r"http://localhost:\d+",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(devices_router, prefix="/api/sim")
app.include_router(dashboard_router, prefix="/api/sim")
app.include_router(registry_router, prefix="/api/sim")
app.include_router(scenarios_router, prefix="/api/sim")
app.include_router(sessions_router, prefix="/api/sim")
app.include_router(vitals_router, prefix="/api/sim")
app.include_router(events_router, prefix="/api/sim")
app.include_router(verification_router, prefix="/api/sim")
app.include_router(analytics_router, prefix="/api/sim")
app.include_router(settings_router, prefix="/api/sim")


@app.get("/api/sim/health")
def health() -> dict[str, str]:
    runtime = get_runtime()
    return runtime.health_payload()


@app.websocket("/ws/logs/{session_id}")
async def ws_logs(websocket: WebSocket, session_id: str) -> None:
    await handle_ws_logs(websocket, session_id)
