from __future__ import annotations

# Load repo-local environment before importing the API stack.
import os
from pathlib import Path

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

from Iot_Simulator.api_server.dependencies import get_runtime
from Iot_Simulator.api_server.routers.analytics import router as analytics_router
from Iot_Simulator.api_server.routers.dashboard import router as dashboard_router
from Iot_Simulator.api_server.routers.devices import router as devices_router
from Iot_Simulator.api_server.routers.events import router as events_router
from Iot_Simulator.api_server.routers.registry import router as registry_router
from Iot_Simulator.api_server.routers.scenarios import router as scenarios_router
from Iot_Simulator.api_server.routers.sessions import router as sessions_router
from Iot_Simulator.api_server.routers.verification import router as verification_router
from Iot_Simulator.api_server.routers.vitals import router as vitals_router
from Iot_Simulator.api_server.ws.log_stream import handle_ws_logs

app = FastAPI(title="IoT Simulator API", version="1.0.0")

ALLOWED_ORIGINS = os.getenv("ALLOWED_ORIGINS", "http://localhost:5173").split(",")

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
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


@app.get("/api/sim/health")
def health() -> dict[str, str]:
    runtime = get_runtime()
    return runtime.health_payload()


@app.websocket("/ws/logs/{session_id}")
async def ws_logs(websocket: WebSocket, session_id: str) -> None:
    await handle_ws_logs(websocket, session_id)
