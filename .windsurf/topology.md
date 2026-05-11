# VSmartwatch Cross-Repo Topology — Reference

Tài liệu này là **reference detailed** cho `shared/rules/11-cross-repo-topology.md` (rule always-on).
Đọc khi cần deep-dive về integration.

## Repo overview

| Repo | Vai trò | Stack | Port (dev) | Trunk |
|---|---|---|---|---|
| HealthGuard | Admin web (BE + FE) | Express + Prisma + Vite/React | 5000 (BE), 5173 (FE) | `deploy` |
| health_system | Mobile (UI) + Backend | Flutter 3.11 + FastAPI Python 3.11 | 8000 (BE) | `develop` |
| Iot_Simulator_clean | IoT simulation | Python FastAPI + simulator-web | 8002 | `develop` |
| healthguard-model-api | ML Model API | Python FastAPI | 8001 | `master` |
| PM_REVIEW | Docs + SQL + custom skills | Markdown + SQL | n/a | `main` |

## Data flow diagram

```
                ┌────────────────────────────┐
                │  Smartwatch (BLE device)   │
                └───────────────┬────────────┘
                                │ BLE
                ┌───────────────▼────────────┐
                │  Mobile App (Flutter)      │
                │  health_system/lib/        │
                └───────┬──────────────┬─────┘
                        │ HTTPS        │ FCM (push)
                        │              │
                ┌───────▼──────┐  ┌───▼───────────────┐
                │  Mobile BE   │  │  Firebase Cloud   │
                │  health_     │  │  Messaging        │
                │  system/     │  └───────────────────┘
                │  backend/    │
                └──┬───────┬───┘
                   │       │
       ┌───────────┘       └─────────────┐
       │                                  │
       │ HTTP                             │ HTTP (internal secret)
       │                                  │
┌──────▼──────────┐              ┌────────▼────────────┐
│  Shared         │              │  Model API          │
│  Postgres DB    │              │  healthguard-       │
│  (PM_REVIEW/    │              │  model-api/         │
│   SQL canonical)│              └─────────────────────┘
└──────┬──────────┘                       ▲
       │                                  │
       │ Prisma                           │ HTTP
       │                                  │
┌──────▼──────────────┐          ┌────────┴─────────────┐
│  Admin BE           │          │  IoT Simulator       │
│  HealthGuard/       │          │  Iot_Simulator_      │
│  backend/           │          │  clean/api_server/   │
└──────┬──────────────┘          └──────────────────────┘
       │ HTTPS                             ▲
       │                                   │ HTTP (sensor publish)
┌──────▼──────────────┐                    │
│  Admin Frontend     │                    │
│  HealthGuard/       │             ┌──────┴───────────┐
│  frontend/ (Vite)   │             │  Simulator Web   │
└─────────────────────┘             │  (control UI)    │
                                    └──────────────────┘
```

## API contract details

### Mobile Backend (`health_system/backend`)

**Base URL (dev):** `http://localhost:8000/api/mobile`

| Endpoint | Method | Purpose | Consumer |
|---|---|---|---|
| `/auth/login` | POST | User login | Mobile app |
| `/auth/refresh` | POST | Refresh access token | Mobile app |
| `/vitals/timeseries` | GET | Vitals chart data | Mobile app |
| `/fall-events/{id}/confirm` | POST | Confirm safe after fall | Mobile app |
| `/fall-events/{id}/trigger-sos` | POST | Trigger SOS | Mobile app |
| `/internal/sensor-data` | POST | IoT publish vitals | IoT sim |

**Auth:** JWT (`iss=healthguard-mobile`) qua `Authorization: Bearer <token>`.
**Internal auth:** header `X-Internal-Secret` cho `/internal/*`.

### Model API (`healthguard-model-api`)

**Base URL (dev):** `http://localhost:8001/api/v1`

| Endpoint | Method | Purpose | Consumer |
|---|---|---|---|
| `/fall/predict` | POST | Fall risk prediction | Backend services |
| `/sleep/predict` | POST | Sleep risk prediction | Backend services |
| `/health/predict` | POST | General health risk | Backend services |

**Auth:** Internal secret header. **Không có user JWT** — model API stateless, không biết user.

**Request shape:** xem `healthguard-model-api/app/models/` cho Pydantic schemas.

### Admin Backend (`HealthGuard/backend`)

**Base URL (dev):** `http://localhost:5000/api/admin`

| Endpoint | Method | Purpose | Consumer |
|---|---|---|---|
| `/auth/sessions` | POST | Admin login | Admin frontend |
| `/devices` | GET/POST | Device management | Admin frontend |
| `/users` | GET | User listing | Admin frontend |
| `/dashboard` | GET | Dashboard stats | Admin frontend |
| `/emergencies` | GET | Emergency events | Admin frontend |
| WebSocket | n/a | Realtime vital updates | Admin frontend |

**Auth:** JWT (`iss=healthguard-admin`) qua `Authorization: Bearer <token>`.

### IoT Simulator (`Iot_Simulator_clean/api_server`)

**Base URL (dev):** `http://localhost:8002`

| Endpoint | Method | Purpose | Consumer |
|---|---|---|---|
| `/simulate/start` | POST | Start sim profile | Simulator Web UI |
| `/simulate/stop` | POST | Stop sim | Simulator Web UI |
| `/simulate/profiles` | GET | List profiles | Simulator Web UI |
| `/simulate/devices` | GET/POST | Manage virtual devices | Simulator Web UI |

**Auth:** Local dev — không strict auth.

## Database

**Canonical schema:** `PM_REVIEW/SQL SCRIPTS/init_full_setup.sql`

**Shared by:**
- Admin BE: via Prisma (`HealthGuard/backend/prisma/schema.prisma`)
- Mobile BE: via SQLAlchemy hoặc raw asyncpg (verify trong `health_system/backend/app/`)

**Migration discipline:**
- Update canonical SQL trong PM_REVIEW
- Generate Prisma migration (admin)
- Update SQLAlchemy model (mobile BE)
- Run migration trên dev DB
- Sync trên production DB sau khi verify

## Cross-repo testing

E2E smoke test ở `Iot_Simulator_clean/scripts/e2e_*.ps1`:
- `e2e_fall_lab_smoke.ps1` — simulate fall → trigger SOS → verify alert → confirm/cancel flow

Khi sửa cross-repo feature, **chạy E2E** trước khi push.

## When you change something

### Change endpoint contract
1. Update spec trong UC (`PM_REVIEW/Resources/UC/{Module}/UCxxx.md`)
2. Update producer (BE endpoint)
3. Update consumer(s) (mobile app, admin frontend, IoT sim)
4. Update Pydantic/Prisma schema nếu cần
5. Run unit test cho endpoint
6. Run E2E smoke test

### Change DB schema
1. Update canonical `PM_REVIEW/SQL SCRIPTS/init_full_setup.sql`
2. Write migration script `YYYYMMDD_<desc>.sql`
3. Update Prisma schema + run `prisma migrate dev`
4. Update SQLAlchemy model (mobile BE)
5. Test query both backends still work
6. Document deviation trong commit

### Change UC
1. Update UC file
2. Invoke skill `UC_AUDIT` để check inconsistency
3. Update JIRA Story acceptance criteria nếu cần
4. Re-generate test cases (`TEST_CASE_GEN`)

## Common pitfalls

- **Forget update consumer** khi đổi producer → 4xx/5xx tại runtime
- **DB schema drift** giữa Prisma và canonical SQL → query fail trên 1 backend
- **Internal secret mismatch** giữa caller và callee → 401 internal
- **JWT iss mismatch** — admin token gửi cho mobile endpoint → 403
- **CORS issue** khi đổi origin admin FE
- **Localhost port conflict** khi run nhiều service cùng lúc
