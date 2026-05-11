---
trigger: always_on
---

# FastAPI Rules — Python Backend

Áp dụng cho FastAPI repos: `health_system/backend`, `healthguard-model-api`, `Iot_Simulator_clean/api_server`.

## Project structure

Convention:

```
app/  (hoặc tên tương đương)
├── main.py             # FastAPI() init, router include, middleware
├── routers/            # endpoints (1 file/module)
├── services/           # business logic
├── models/             # Pydantic schemas (request/response)
├── repositories/       # data access (DB queries)
├── dependencies.py     # FastAPI Depends() factories
├── config.py           # pydantic-settings (env vars)
└── utils/

tests/                  # pytest
migrations/             # alembic or raw SQL scripts
```

## Routing

- **One router per logical domain.** `routers/fall.py`, `routers/sleep.py`, `routers/auth.py`.
- **Prefix + tag:** `router = APIRouter(prefix="/fall", tags=["fall"])`.
- **Dependency injection** cho auth/DB session/service:

```python
@router.post("/predict")
async def predict_fall(
    payload: FallPredictRequest,
    service: FallService = Depends(get_fall_service),
    _auth: None = Depends(verify_internal_secret),
) -> FallPredictResponse:
    return await service.predict(payload)
```

- **Return Pydantic model** — không return dict.

## Pydantic

- **v2 syntax** (`model_config = ConfigDict(...)`, `field_validator`).
- **Request schema** suffix `Request`, response `Response`.
- **Don't reuse DB model as API schema** — separate concerns.

## Services

- **Business logic ở service**, không trong router.
- **Service không biết về HTTP** — không nhận `Request`, không return `JSONResponse`.
- **Async by default** trừ khi pure CPU.

## Error handling

- **Custom exception classes** trong `app/exceptions.py`:

```python
class PredictionError(Exception): ...
class ModelLoadError(PredictionError): ...
```

- **Exception handler** trong `main.py`:

```python
@app.exception_handler(PredictionError)
async def handle_prediction_error(request, exc):
    return JSONResponse(status_code=500, content={"error": "Prediction failed"})
    # NEVER leak str(exc) — internal info leak (xem 40-security-guardrails)
```

- **HTTPException** chỉ cho client errors (4xx).

## Database

### `health_system/backend`
- DB layer pattern: SQLAlchemy hoặc raw SQL với asyncpg. Verify thực tế trong `app/repositories/`.

### `healthguard-model-api`
- Stateless, không DB. ML model load 1 lần khi startup (cache).

### `Iot_Simulator_clean`
- Pre-model trigger có rule engine (config-driven). Verify schema trong `pre_model_trigger/health_rules/rules_config.json`.

## Logging

```python
import logging
logger = logging.getLogger(__name__)

logger.info("Predicted fall", extra={"request_id": req_id, "user_id": user_id})
# Cấm: logger.info(f"password={password}") — leak PHI
```

## Background tasks

- **Light task:** `BackgroundTasks` của FastAPI (chạy sau response).
- **Heavy/scheduled:** Celery hoặc APScheduler. Verify codebase dùng cái nào trước khi thêm.

## Config

`pydantic-settings`:

```python
class Settings(BaseSettings):
    db_url: str
    jwt_secret: str
    internal_secret: str
    model_config = SettingsConfigDict(env_file=".env")
```

`.env*` gitignored, `.env.example` checked-in với placeholder.

## Testing

```python
# tests/test_fall_router.py
from fastapi.testclient import TestClient

def test_predict_fall_unauthorized(client: TestClient):
    resp = client.post("/fall/predict", json={...})
    assert resp.status_code == 401
```

- Use `TestClient` cho API contract.
- Mock external dependencies (model API, DB) bằng `unittest.mock` hoặc fixture.
- Run: `pytest tests/test_fall_router.py::test_predict_fall_unauthorized` trước full suite.

## Anti-patterns flag tự động

- Mutable default arg (`def f(x=[])`)
- `except Exception:` không log + không re-raise
- Hardcode secret/URL/credential
- Sync I/O trong async function (use `asyncio.to_thread` hoặc sync endpoint)
- Global mutable state (db connection, model) không thread-safe
- `print()` trong production code

## Commands

- `pip install -r requirements.txt`
- `uvicorn app.main:app --reload --port <port>` (dev)
- `pytest tests/<file>::<test>` (specific) trước `pytest` (full)
- `black .` + `isort .` trước commit (check `pyproject.toml`)
- `mypy app/` cho type check (nếu repo có mypy config)
