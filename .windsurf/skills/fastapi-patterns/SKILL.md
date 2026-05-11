---
name: fastapi-patterns
description: Use when writing or modifying FastAPI backend code in VSmartwatch (health_system/backend, healthguard-model-api, Iot_Simulator_clean/api_server). Reference patterns for router/service/repository layering, Pydantic v2, async DB, internal-secret auth, error handling, sanitized responses, and pytest.
---

# FastAPI Patterns — VSmartwatch Python Backends

> Apply when working in: `health_system/backend/`, `healthguard-model-api/`, `Iot_Simulator_clean/api_server/`. Stack: Python 3.11 + FastAPI + Pydantic v2 + asyncpg/SQLAlchemy + JWT/internal-secret auth.

## Project layering

```
app/
├── main.py             # FastAPI() init, router include, middleware, exception handlers
├── routers/            # endpoints (1 file/domain)
├── services/           # business logic
├── repositories/       # data access (DB queries)
├── models/             # Pydantic v2 schemas (request/response)
├── dependencies.py     # FastAPI Depends() factories
├── config.py           # pydantic-settings
├── exceptions.py       # custom exception classes
└── utils/

tests/                  # pytest
```

## main.py — wire it once

```python
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager

from app.config import settings
from app.routers import auth, fall, sleep, vitals
from app.exceptions import AppError, app_error_handler, generic_error_handler

@asynccontextmanager
async def lifespan(app: FastAPI):
    # startup: init pool, load model, etc.
    await init_db_pool()
    yield
    # shutdown: clean up
    await close_db_pool()

app = FastAPI(title="HealthGuard Mobile API", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.allowed_origins,  # explicit list, never ["*"]
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE"],
    allow_headers=["*"],
)

app.add_exception_handler(AppError, app_error_handler)
app.add_exception_handler(Exception, generic_error_handler)

app.include_router(auth.router, prefix="/api/mobile/auth", tags=["auth"])
app.include_router(fall.router, prefix="/api/mobile/fall", tags=["fall"])
# ...
```

## Routing — one router per domain

```python
# app/routers/fall.py
from fastapi import APIRouter, Depends, status
from app.models.fall import FallPredictRequest, FallPredictResponse
from app.services.fall_service import FallService
from app.dependencies import get_fall_service, verify_internal_secret

router = APIRouter()

@router.post(
    "/predict",
    response_model=FallPredictResponse,
    status_code=status.HTTP_200_OK,
)
async def predict_fall(
    payload: FallPredictRequest,
    service: FallService = Depends(get_fall_service),
    _auth: None = Depends(verify_internal_secret),
) -> FallPredictResponse:
    return await service.predict(payload)
```

**Rules:**
- Always `response_model` (auto-validate + sanitize output)
- Inject service via `Depends` (testable + lifecycle managed)
- Auth as a dependency, not in body of handler

## Pydantic v2 schemas

```python
# app/models/fall.py
from pydantic import BaseModel, ConfigDict, Field, field_validator
from datetime import datetime

class FallPredictRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")  # reject unknown fields
    
    user_id: str = Field(min_length=1)
    accel: list[float] = Field(min_length=3, max_length=3)
    gyro: list[float] = Field(min_length=3, max_length=3)
    timestamp: datetime
    
    @field_validator("accel", "gyro")
    @classmethod
    def reasonable_magnitude(cls, v: list[float]) -> list[float]:
        if any(abs(x) > 100 for x in v):
            raise ValueError("Sensor reading out of plausible range")
        return v

class FallPredictResponse(BaseModel):
    is_fall: bool
    confidence: float = Field(ge=0.0, le=1.0)
    risk_level: str  # 'low' | 'medium' | 'high'
```

**Naming:** `*Request` / `*Response` — never reuse DB models for API.

## Service — business logic, no HTTP awareness

```python
# app/services/fall_service.py
import logging
from app.models.fall import FallPredictRequest, FallPredictResponse
from app.repositories.model_repository import ModelRepository
from app.exceptions import PredictionError

logger = logging.getLogger(__name__)

class FallService:
    def __init__(self, model_repo: ModelRepository):
        self._model_repo = model_repo
    
    async def predict(self, req: FallPredictRequest) -> FallPredictResponse:
        try:
            model = await self._model_repo.get_fall_model()
            features = self._build_features(req)
            confidence = float(model.predict_proba([features])[0][1])
            
            logger.info("Fall prediction", extra={"user_id": req.user_id, "confidence": confidence})
            
            return FallPredictResponse(
                is_fall=confidence > 0.7,
                confidence=confidence,
                risk_level=self._classify_risk(confidence),
            )
        except Exception as e:
            logger.exception("Prediction failed")  # log details internally
            raise PredictionError("Failed to predict fall") from e  # generic error to caller
```

**Service does NOT:** receive `Request`, return `JSONResponse`, know about HTTP status codes.

## Custom exceptions + sanitized handlers

```python
# app/exceptions.py
from fastapi import Request
from fastapi.responses import JSONResponse
import logging

logger = logging.getLogger(__name__)

class AppError(Exception):
    status_code: int = 500
    code: str = "INTERNAL"
    public_message: str = "Internal server error"
    
    def __init__(self, internal_message: str = "", details: dict | None = None):
        super().__init__(internal_message)
        self.details = details or {}

class ValidationError(AppError):
    status_code = 400
    code = "VALIDATION"
    public_message = "Invalid input"

class UnauthenticatedError(AppError):
    status_code = 401
    code = "UNAUTH"
    public_message = "Authentication required"

class NotFoundError(AppError):
    status_code = 404
    code = "NOT_FOUND"
    public_message = "Resource not found"

class PredictionError(AppError):
    status_code = 500
    code = "PREDICTION_FAILED"
    public_message = "Prediction failed"

async def app_error_handler(request: Request, exc: AppError) -> JSONResponse:
    logger.warning("App error", extra={"code": exc.code, "path": request.url.path, "internal": str(exc)})
    return JSONResponse(
        status_code=exc.status_code,
        content={"error": {"code": exc.code, "message": exc.public_message, "details": exc.details}},
    )

async def generic_error_handler(request: Request, exc: Exception) -> JSONResponse:
    # NEVER leak str(exc) — security risk (PHI / stack trace)
    logger.exception("Unhandled error", extra={"path": request.url.path})
    return JSONResponse(
        status_code=500,
        content={"error": {"code": "INTERNAL", "message": "Internal server error"}},
    )
```

**Iron rule:** never include `str(exc)` in client response.

## Dependencies — auth + DB session

```python
# app/dependencies.py
from fastapi import Depends, Header, HTTPException, status
from app.config import settings

async def verify_internal_secret(x_internal_secret: str = Header(...)) -> None:
    """For service-to-service calls (model-api ← health_system, IoT sim → backend)."""
    if x_internal_secret != settings.internal_secret:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, detail="Invalid internal secret")

async def get_current_user(authorization: str = Header(...)) -> User:
    """For mobile-facing endpoints (JWT user)."""
    if not authorization.startswith("Bearer "):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, detail="Missing token")
    token = authorization[7:]
    try:
        payload = jwt.decode(token, settings.jwt_secret, algorithms=["HS256"], issuer="healthguard-mobile")
    except jwt.PyJWTError:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, detail="Invalid token")
    return User(id=payload["sub"], email=payload.get("email"))
```

## Config — pydantic-settings

```python
# app/config.py
from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")
    
    db_url: str
    jwt_secret: str
    internal_secret: str
    allowed_origins: list[str] = ["http://localhost:5173"]
    log_level: str = "INFO"
    model_path: str = "/app/models/fall_v2.pkl"

settings = Settings()  # fails fast if env invalid
```

`.env` gitignored, `.env.example` checked-in with placeholders.

## Repository pattern — DB access

```python
# app/repositories/fall_event_repository.py
import asyncpg
from app.models.fall import FallEvent

class FallEventRepository:
    def __init__(self, pool: asyncpg.Pool):
        self._pool = pool
    
    async def insert(self, event: FallEvent) -> str:
        async with self._pool.acquire() as conn:
            row = await conn.fetchrow(
                """
                INSERT INTO fall_events (user_id, device_id, confidence, detected_at)
                VALUES ($1, $2, $3, $4)
                RETURNING id
                """,
                event.user_id, event.device_id, event.confidence, event.detected_at,
            )
            return row["id"]
    
    async def recent_for_user(self, user_id: str, limit: int = 20) -> list[FallEvent]:
        async with self._pool.acquire() as conn:
            rows = await conn.fetch(
                "SELECT id, user_id, device_id, confidence, detected_at FROM fall_events "
                "WHERE user_id = $1 ORDER BY detected_at DESC LIMIT $2",
                user_id, limit,
            )
            return [FallEvent.model_validate(dict(r)) for r in rows]
```

**Always parameterized** ($1, $2). Never f-string SQL.

## Logging — structured, no PHI

```python
import logging
logger = logging.getLogger(__name__)

# Good
logger.info("Predicted fall", extra={"user_id": user_id, "confidence": conf, "request_id": req_id})

# Bad — logs PHI raw
# logger.info(f"Patient {email} blood pressure {bp}")  # NEVER
```

For health vitals → mask or only log aggregates (count, range), not raw values.

## Background tasks

```python
from fastapi import BackgroundTasks

@router.post("/fall/notify")
async def notify_after_fall(payload: FallEvent, bg: BackgroundTasks):
    bg.add_task(send_fcm_to_emergency_contacts, payload)
    return {"status": "queued"}
```

For heavier/scheduled work: APScheduler or external queue (Celery, Redis).

## Testing (pytest)

```python
# tests/test_fall_router.py
from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)

def test_predict_fall_unauthorized():
    resp = client.post("/api/mobile/fall/predict", json={"user_id": "u1", "accel": [0, 0, 9.8], "gyro": [0, 0, 0], "timestamp": "2026-01-01T00:00:00Z"})
    assert resp.status_code == 401

def test_predict_fall_validates_payload(internal_secret_header):
    resp = client.post(
        "/api/mobile/fall/predict",
        json={"user_id": "u1", "accel": [9999, 0, 0], "gyro": [0, 0, 0], "timestamp": "2026-01-01T00:00:00Z"},
        headers=internal_secret_header,
    )
    assert resp.status_code == 422  # Pydantic validation kicked in
```

Run: `pytest tests/test_fall_router.py::test_predict_fall_unauthorized` (focused) trước `pytest` (full).

## Common gotchas

| Issue | Fix |
|---|---|
| `def f(x=[])` mutable default | Use `def f(x: list \| None = None)` |
| `except Exception:` không log | At minimum `logger.exception(...)` then re-raise or wrap |
| Sync I/O trong async function | `await asyncio.to_thread(blocking_call)` or sync endpoint |
| `print()` in production | Use `logger`, structured |
| Global mutable state | Use lifespan or Depends factory |
| `str(exc)` in client response | Generic public message; log internal details |
| Pydantic v1 syntax | Use v2: `model_config = ConfigDict(...)`, `field_validator` |
| Hardcoded secret | Through `Settings` (pydantic-settings + env) |
| CORS `["*"]` in production | Explicit allowlist from env |

## Quick commands

```pwsh
# health_system/backend
cd d:\DoAn2\VSmartwatch\health_system\backend
uvicorn app.main:app --reload --port 8000
pytest tests/test_fall.py::test_predict_unauthorized
pytest                           # full
black . && isort .               # before commit
mypy app/                        # if mypy configured

# healthguard-model-api
cd d:\DoAn2\VSmartwatch\healthguard-model-api
uvicorn app.main:app --reload --port 8001

# Iot_Simulator_clean
cd d:\DoAn2\VSmartwatch\Iot_Simulator_clean
uvicorn api_server.main:app --reload --port 8002
```

## Anti-patterns auto-flag

- Mutable default arg (`def f(x=[])`)
- `except Exception:` không log + không re-raise
- Hardcoded secret/URL/credential
- Sync I/O trong async function
- Global mutable state (DB pool, model) không thread-safe
- `print()` thay logger
- `str(exc)` leaked to client response
- Pydantic v1 syntax (`@validator`, `class Config`)
- CORS `["*"]` in production config
