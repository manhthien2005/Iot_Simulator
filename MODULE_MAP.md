# MODULE_MAP.md — IoT Simulator Module Layout

> Mỗi folder làm gì, entry point ở đâu, dependency direction ra sao. Đọc trước khi edit.

---

## Top-level layout

```
Iot_Simulator_clean/
├── api_server/             FastAPI HTTP/WS boundary
├── simulator_core/         Domain logic — generator, dataset, persona, session
├── transport/              Outbound HTTP publisher → health_system BE
├── pre_model_trigger/      Risk dispatch primitives (fall/sleep)
├── etl_pipeline/           Raw dataset → normalized parquet
├── dataset_adapters/       Per-dataset transform adapter
├── normalized_artifacts/   Parquet output (gitignored, rebuild local)
├── datasets/               Raw input (gitignored, distributed via Drive)
├── simulator-web/          React + Vite + TS frontend
├── scripts/                E2E smoke + utility scripts
├── tests/                  Local test (gitignored, không commit)
├── demo/                   Demo data + walkthrough
└── docs/                   Documentation (FEATURE_SPEC.md commit, rest gitignored)
```

---

## `api_server/` — HTTP boundary

**Vai trò:** FastAPI route registration, middleware, dependency injection, Pydantic schema, WebSocket handler.

**Entry point:** `api_server/main.py` — app factory + lifespan + router include với prefix `/api/v1/sim/*`.

```
api_server/
├── main.py                   App factory + lifespan + CORS + router include
├── schemas.py                Tất cả Pydantic model (HTTP boundary contract)
├── dependencies.py           SimulatorRuntime singleton + DI registry
├── runtime_state.py          Cross-cutting state cho /health payload v2
├── runtime_persistence.py    Mutable runtime config persist (api_server/config/runtime.json)
├── backend_admin_client.py   Health check ping → admin BE
├── sim_admin_service.py      DB query helper cho /admin/* endpoint
├── db.py                     SQLAlchemy session + get_db()
├── middleware/
│   ├── auth.py               require_admin_key dependency
│   └── rate_limit.py         RateLimitMiddleware (LIFO order)
├── routers/                  Per-resource HTTP route
│   ├── devices.py            /devices/* + /admin/db-devices/* + personalization proxy
│   ├── sessions.py           /sessions/* (start/stop/runner)
│   ├── scenarios.py          /scenarios/* (apply, sleep backfill)
│   ├── vitals.py             /vitals/* (latest sample query)
│   ├── events.py             /events/* (fall inject, alert query)
│   ├── analytics.py          /analytics/* (risk inject, summary)
│   ├── verification.py       /verification/* (pipeline trace)
│   ├── registry.py           /registry/* (dataset catalogue)
│   ├── dashboard.py          /dashboard/* (summary stat)
│   └── settings.py           /settings/* (runtime config + feature flag)
├── services/
│   └── sleep_service.py      Sleep AI scoring + heuristic fallback
└── ws/
    ├── log_stream.py         /ws/logs/{session_id} fan-out
    └── flow_stream.py        /ws/flow/{session_id} fan-out (sequence diagram)
```

**Dependency direction:**
- `api_server/` import từ `simulator_core/`, `transport/`, `pre_model_trigger/`. ✅
- `api_server/` KHÔNG import được import bởi `simulator_core/`. ❌

**Khi edit:**
- Route mới → tạo router file trong `routers/` + include trong `main.py:94-103`.
- Schema mới → thêm vào `schemas.py` (1 file lớn, OK theo convention codebase).
- Auth admin → wrap router với `dependencies=[Depends(require_admin_key)]`.

---

## `simulator_core/` — Domain logic

**Vai trò:** Tick generator, dataset registry, persona, session state machine, AI client. KHÔNG biết HTTP layer.

```
simulator_core/
├── generators.py             Combined tick generator (vital + motion + sleep) — main entry
├── vitals_generator.py       Vital signs generator (HR, SpO2, BP, RR, temp)
├── motion_generator.py       Motion window 50 Hz (accel + gyro + fall pattern)
├── sleep_vitals_enricher.py  Sleep session payload (19 features, 4 scenario)
├── dataset_registry.py       Hash-index O(1) lookup across all parquet
├── persona_engine.py         Per-device persona (age, weight, baseline curve)
├── mock_personas.py          Built-in persona fixture
├── session.py                Session FSM (idle → running → stopped)
├── sleep_ai_client.py        HTTP client → model-api /sleep/predict
└── fall_ai_client.py         HTTP client → BE /fall/predict (proxied to model-api)
```

**Dependency direction:**
- `simulator_core/` import từ `dataset_adapters/`, `etl_pipeline/` (registry). ✅
- KHÔNG import `api_server/`, `transport/`, `pre_model_trigger/`. ❌

**Khi edit:**
- Generator mới → file riêng + wire vào `generators.py`.
- Dataset adapter mới → `dataset_adapters/<name>_adapter.py` + register trong `dataset_registry.py`.
- Provenance tag bắt buộc cho field từ dataset (xem `24-medical-realism.mdc`).

---

## `transport/` — Outbound publisher

**Vai trò:** HTTP POST batch telemetry lên `health_system/backend`. Backoff, retry, header auth.

```
transport/
├── http_publisher.py         Main publisher — vitals/motion/sleep/event endpoint
└── (mqtt_publisher.py)       Legacy stub, không dùng
```

**Dependency direction:**
- `transport/` import từ `simulator_core/` (lấy domain object để serialize). ✅
- KHÔNG import `api_server/`. ❌

**Khi edit:**
- Endpoint mới → method mới trong `HttpPublisher`.
- Header auth: `X-Internal-Service` + `X-Internal-Secret` từ env.
- Timeout explicit (default 5s).

---

## `pre_model_trigger/` — Risk dispatch primitives

**Vai trò:** Pre-trigger gate cho fall/sleep risk evaluation. Hard rule + soft rule. Bypass model-api nếu rule không trigger (Phase 2).

```
pre_model_trigger/
├── fall/
│   ├── fall_pre_trigger.py   IMPACT_PEAK_3G + soft trigger evaluation
│   └── README.md
├── health_rules/
│   ├── rule_engine.py        Threshold-based health rule
│   └── README.md
├── mobile_telemetry_client.py  Internal client → mobile BE
└── healthguard_client.py     Legacy client (Phase 0/1)
```

**Dependency direction:**
- Import từ `simulator_core/` (motion window, vital tick). ✅
- Có thể import nhau giữa các submodule. ✅

**Khi edit:**
- Rule mới → thêm vào `health_rules/rule_engine.py`.
- Trigger mode (`off`/`shadow`/`active`) qua env `PRE_MODEL_TRIGGER_ENABLED` + `PRE_MODEL_TRIGGER_ENABLE_MODEL_CALLS`.

---

## `etl_pipeline/` + `dataset_adapters/` — Dataset

**Vai trò:** Raw dataset (CSV/EDF/MAT) → canonical parquet → registry.

```
etl_pipeline/
├── normalize.py              Main ETL entry — chạy mỗi dataset
└── etl_<dataset>.py          Per-dataset ETL script

dataset_adapters/
└── <dataset>_adapter.py      Per-dataset transform (unit conversion, downsample)
```

**Khi edit:**
- Dataset mới → workflow `/dataset` (xem `.cursor/rules/workflow-dataset.mdc`).
- Canonical schema xem `23-dataset-pipeline.mdc`.

---

## `simulator-web/` — Frontend

**Vai trò:** React + Vite + TS dashboard cho operator.

```
simulator-web/
├── src/
│   ├── components/
│   │   ├── domain/           Domain-specific (session, settings, diagnostics, demo_mode)
│   │   ├── layout/           Sidebar, Header, AppShell
│   │   └── ui/               Reusable (Card, Badge, Spinner)
│   ├── pages/                Route-level page (SessionRunnerPage, SettingsPage, ...)
│   ├── hooks/                Custom hook (useFlowStream, usePersonalization)
│   ├── services/             API client (axios) — *Api.ts files
│   ├── types/                TS interface (mirror BE Pydantic)
│   ├── config/               Runtime defaults
│   └── store/                Zustand store (sessionStore.ts)
├── package.json              Stack: React 18, Vite 5, TanStack Query/Table, Zustand, axios, sonner, echarts
├── vite.config.ts            Build config + path alias @/
└── tsconfig*.json            Strict mode
```

**Stack quick reference:** xem `70-tech-stack-cheatsheet.mdc` mục Frontend stack.

---

## `scripts/` — E2E + utility

```
scripts/
└── e2e_fall_lab_smoke.ps1    Cross-repo smoke: simulator → BE → alert flow
```

PowerShell scripts (Windows-first). Run qua `pwsh -File scripts/<name>.ps1`.

---

## Layer dependency rules (strict)

```
┌──────────────────────────────────────────────────────────┐
│  api_server/  (HTTP boundary)                            │
│      ↓ depends on                                        │
│  simulator_core/  (domain)         pre_model_trigger/   │
│      ↓                                  ↓                │
│  dataset_adapters/    transport/   (outbound HTTP)       │
│      ↓                                                   │
│  etl_pipeline/  (parquet generation)                     │
└──────────────────────────────────────────────────────────┘
```

**Vi phạm common:**
- 🔴 `simulator_core/` import `api_server/` → circular, refuse.
- 🔴 Router chứa business logic dài → push xuống `services/` hoặc `simulator_core/`.
- 🔴 Generator gọi httpx trực tiếp → push qua `transport/`.
- 🟡 FE `pages/` gọi axios trực tiếp → push qua `services/*Api.ts`.

---

## Quick "tôi muốn edit X, edit ở đâu?"

| Muốn làm | File / folder |
|---|---|
| Thêm endpoint mới | `api_server/routers/<resource>.py` |
| Thêm Pydantic schema | `api_server/schemas.py` |
| Thêm scenario built-in | `simulator_core/persona_engine.py` + generator wire |
| Thêm dataset mới | `etl_pipeline/etl_<name>.py` + `dataset_adapters/<name>_adapter.py` + `simulator_core/dataset_registry.py` |
| Đổi Hard Boundary | `simulator_core/vitals_generator.py` (top constant) |
| Sửa publisher payload | `transport/http_publisher.py` + `api_server/schemas.py` mirror |
| Thêm rule risk | `pre_model_trigger/health_rules/rule_engine.py` |
| Thêm FE page | `simulator-web/src/pages/<Name>Page.tsx` + route trong router |
| Thêm FE component | `simulator-web/src/components/domain/<feature>/` |
| Thêm WS channel | `api_server/ws/<channel>_stream.py` + register `main.py` |
| Sửa runtime config | `api_server/runtime_persistence.py` + schema `RuntimeConfig` |
| Cross-repo schema bump | Producer `schemas.py` + `transport/` → consumer BE schema (cross-repo PR) |

---

**Last verified:** 2026-05-21 (codebase scan: `api_server/`, `simulator_core/`, `simulator-web/src/`).
