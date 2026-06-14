# CONTEXT.md — IoT Simulator Quick Snapshot

> Đọc file này TRƯỚC KHI code. 1 file, biết ngay stack + port + command + boundary.
> Behavioral contract chi tiết → `AGENTS.md`. Pattern code chi tiết → `.cursor/rules/`.

---

## 1. What this repo is

Mô-đun **giả lập wearable smartwatch** trong hệ HealthGuard (5 repo). Phát telemetry vital/motion/sleep dựa trên **dữ liệu y sinh thực tế** (không random.gauss), inject fall event, push lên `health_system/backend` qua HTTP.

Repo này **không** lưu DB · **không** train model · **không** xử lý alert business logic.

---

## 2. Tech stack (verified 2026-05-21)

### Backend (Python 3.11)

| Lib | Version | Purpose |
|---|---|---|
| `fastapi` | ≥0.104 | HTTP + WS framework |
| `uvicorn` | ≥0.24 | ASGI server |
| `pydantic` | ≥2.5 | Schema validation (v2 syntax) |
| `pydantic-settings` | ≥2.1 | Config from env |
| `sqlalchemy` | ≥2.0 | ORM + raw SQL |
| `asyncpg` | ≥0.29 | Async Postgres driver |
| `psycopg2-binary` | ≥2.9 | Sync Postgres driver |
| `httpx` | ≥0.25 | Outbound HTTP (BE publisher, model API) |
| `aiohttp` | ≥3.9 | (legacy, prefer httpx) |
| `pandas` | ≥2.0 | ETL + dataset registry |
| `pyarrow` | ≥14.0 | Parquet engine |
| `numpy` | ≥1.24 | Numerics cho generator |
| `pyyaml` | ≥6.0 | Config files |
| `python-dotenv` | ≥1.0 | `.env` loader |

### Frontend (TypeScript 5.7+)

| Lib | Version | Purpose |
|---|---|---|
| `react` + `react-dom` | 18.3 | Core |
| `react-router-dom` | 6.30 | Routing |
| `vite` | 5.4 | Build tool |
| `@tanstack/react-query` | 5.80 | Server state |
| `@tanstack/react-query-persist-client` | 5.100 | Cache persist (cold reload) |
| `@tanstack/query-sync-storage-persister` | 5.100 | Storage backend |
| `@tanstack/react-table` | 8.21 | Data table |
| `@tanstack/react-virtual` | 3.10 | Virtualization (long list) |
| `zustand` | 5.0 | Client cross-component state |
| `axios` | 1.9 | HTTP client |
| `sonner` | 2.0 | Toast notification |
| `echarts` + `echarts-for-react` | 5.6 / 3.0 | Chart |
| `lucide-react` | 0.523 | Icon |
| `mermaid` | 11.15 | Diagram |

### Test

| Lib | Purpose |
|---|---|
| `pytest` + `pytest-asyncio` | BE test (async support) |
| `vitest` 4.1 | FE unit/integration |
| `@testing-library/react` 16.3 | FE component test |
| `jsdom` 29 | Browser env cho vitest |

### Styling

- **Vanilla CSS** ở `simulator-web/src/index.css` (KHÔNG Tailwind, KHÔNG CSS-in-JS).

### Datasets (8 core)

| Dataset | Domain | Provenance tag |
|---|---|---|
| PPG-DaLiA | Wearable HR + accel | `real:PPGDaLiA` |
| PAMAP2 | Activity (accel/gyro) | `real:PAMAP2` |
| PIF_v3 | Fall bridge (post-fall vitals) | `real:PIFv3` |
| UP-Fall | Fall motion patterns | `real:UPFall` |
| Sleep-EDF | Hypnogram 5-cycle | `real:SleepEDF` |
| WESAD | Stress HR distribution | `real:WESAD` |
| VitalDB | Clinical SpO2 + BP | `real:VitalDB` |
| BIDMC | Respiration rate | `real:BIDMC` |

> Dataset thô **gitignored**. Distribution qua `datasets/DOWNLOAD_GUIDE.md`.

---

## 3. Ports & URLs (dev)

| Service | URL | Repo |
|---|---|---|
| **Simulator BE** | `http://localhost:8090` (prefix `/api/v1/sim/*`) | this repo |
| **Simulator Web** | `http://localhost:5173` | `simulator-web/` |
| **HealthGuard Backend** | `http://localhost:8002` (`HEALTH_BACKEND_URL`) | `health_system/backend` |
| **Model API** | `http://localhost:8001` | `healthguard-model-api` |
| **Admin BE** | `http://localhost:5000` | `HealthGuard/backend` |
| **Postgres (TimescaleDB shared)** | `localhost:5432` | container `timescaledb` — DB `healthguard` |

> Windows: `127.0.0.1` thay `localhost` để tránh IPv6 fallback ~2s.

---

## 4. Schema versioning (frozen contract)

Payload publish lên BE:

| Schema | Frequency |
|---|---|
| `sim_vitals_v1` | ~1 Hz per device |
| `sim_motion_v1` | 50 Hz windowed |
| `sim_sleep_v1` | per session |
| `sim_event_v1` | event-based (fall) |

**Đổi schema = bump version + cross-repo PR.** Không rename/remove field implicit.

---

## 5. Hard Medical Boundaries (non-negotiable)

| Field | Floor | Ceiling | Source |
|---|---|---|---|
| `heart_rate` (bpm) | 30 | 220 | AHA 2020 |
| `spo2` (%) | 0 | 100 | WHO 2011 |
| `blood_pressure_sys` (mmHg) | 60 | 250 | ACC/AHA 2017 |
| `blood_pressure_dia` (mmHg) | 40 | 180 | ACC/AHA 2017 |
| `respiratory_rate` (rpm) | 4 | 60 | NEWS2 / ERS |
| `temperature` (°C) | 32 | 42 | Harrison's |

Mọi vital phát ra **PHẢI clamp**. Provenance tag (`*_source = "real:X"` hoặc `"mock"`) **bắt buộc**.

---

## 6. Quick commands

```pwsh
# Start everything (Windows)
.\start_all.bat

# Backend only
uvicorn api_server.main:app --port 8090 --reload

# Frontend only
cd simulator-web; npm run dev

# Test DB (shared TimescaleDB — đã chạy)
docker ps --filter name=timescaledb
docker exec timescaledb psql -U postgres -d healthguard -c "SELECT version();"

# BE test
pytest                                        # full
pytest tests/<module> -k <name> -v            # focused
pytest --cov=api_server --cov=simulator_core  # coverage

# BE lint (nếu config sẵn)
ruff check api_server simulator_core
black --check api_server simulator_core

# FE test
cd simulator-web
npm test                       # vitest
npm run test:watch
npm run lint
npm run build                  # smoke

# E2E smoke
pwsh -File scripts/e2e_fall_lab_smoke.ps1
```

---

## 7. Conventions (1-line summary)

- **Branch:** `<type>/<short-desc>` kebab-case · trunk = `develop`
- **Commit:** `<type>(<scope>): <mô tả tiếng Việt>` — type EN, body VN
- **Python:** `snake_case` func/var, `UpperCamelCase` class
- **TS:** `camelCase` func/var, `PascalCase` interface/type
- **BE Pydantic DTO field:** `camelCase` (match FE consumer)
- **API path:** `/api/v1/sim/<resource>`
- **WS path:** `/ws/<channel>/{id}`
- **Env var:** `UPPER_SNAKE_CASE`
- **File limit:** ≤ 300 lines (test relax đến 500)

---

## 8. Where to look

| Need to know | File |
|---|---|
| Behavioral contract (em hành xử thế nào) | `AGENTS.md` |
| FastAPI patterns chi tiết | `.cursor/rules/21-fastapi-backend.mdc` |
| React+Vite patterns chi tiết | `.cursor/rules/22-react-frontend.mdc` |
| Dataset pipeline + ETL | `.cursor/rules/23-dataset-pipeline.mdc` |
| Medical realism rules | `.cursor/rules/24-medical-realism.mdc` |
| Cross-repo contracts | `.cursor/rules/25-cross-repo-contracts.mdc` |
| Tech library cheatsheet | `.cursor/rules/70-tech-stack-cheatsheet.mdc` |
| Common pitfalls (15 nhóm) | `.cursor/rules/80-common-pitfalls.mdc` |
| Workflow `/auto`, `/check`, `/brainstorm` | `.cursor/rules/workflow-*.mdc` |
| Field-level public reference | `docs/FEATURE_SPEC.md` |
| Datasets download | `datasets/DOWNLOAD_GUIDE.md` |
| SQL canonical | `../PM_REVIEW/SQL SCRIPTS/init_full_setup.sql` |

---

## 9. Decisions đã chốt — không re-litigate

- Python 3.11 + FastAPI cho BE (không Flask, không Django)
- Pydantic v2 cho schema validation
- pandas + pyarrow cho ETL (không Polars)
- DatasetRegistry hash-index O(1) (không list scan)
- HTTP push lên BE (không MQTT broker)
- React + Vite + TS (không Next.js)
- React Query cho server state, Zustand cho client state (không Redux)
- Vanilla CSS (không Tailwind)
- Vitest + RTL cho FE, pytest cho BE
- WebSocket fan-out per session cho realtime (không SSE)
- Không train model trong repo này — chỉ inference qua HTTP đến `model-api`

---

**Last verified:** 2026-05-21 với codebase actual (`requirements.txt`, `simulator-web/package.json`, `api_server/main.py`).
