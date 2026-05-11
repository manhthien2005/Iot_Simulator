---
trigger: always_on
---

# Cross-Repo Topology — Data Flow

Hệ thống VSmartwatch là **distributed** — 4 repo runtime + 1 repo docs. Khi sửa code, luôn nghĩ tới downstream/upstream.

## High-level data flow

```
┌─────────────────┐         ┌──────────────────┐
│  Smartwatch     │  BLE    │  Mobile App      │
│  (real device   │ ──────▶ │  (health_system/ │
│  or IoT sim)    │         │   lib/)          │
└────────┬────────┘         └────────┬─────────┘
         │                           │ HTTPS
         │ HTTP publish              │
         ▼                           ▼
┌─────────────────┐         ┌──────────────────┐
│  IoT Simulator  │  HTTP   │  Backend API     │
│  (Iot_Sim/      │ ──────▶ │  (health_system/ │
│   api_server)   │ trigger │   backend/)      │
└─────────────────┘         └────────┬─────────┘
                                     │
                              ┌──────┴──────┐
                              ▼             ▼
                    ┌─────────────────┐  ┌─────────────────┐
                    │  Admin Backend  │  │  Model API      │
                    │  (HealthGuard/  │  │  (healthguard-  │
                    │   backend/)     │  │   model-api/)   │
                    └────────┬────────┘  └─────────────────┘
                             │ HTTPS
                             ▼
                    ┌─────────────────┐
                    │  Admin Web UI   │
                    │  (HealthGuard/  │
                    │   frontend/)    │
                    └─────────────────┘
```

## Boundary contracts

| From | To | Protocol | Auth | Spec location |
|---|---|---|---|---|
| Mobile → Backend (health_system) | REST `/api/mobile/*` | JWT user | `health_system/backend/app/routers/` |
| Backend → Model API | REST `/api/v1/{fall,sleep,health}` | Internal secret header | `healthguard-model-api/app/routers/` |
| IoT sim → Backend | REST `/api/internal/*` | Internal auth header | `Iot_Simulator_clean/transport/http_publisher.py` |
| Admin Web → Admin Backend | REST `/api/admin/*` | JWT admin | `HealthGuard/backend/src/` |
| Admin Backend → Mobile Backend | (when shared DB) shared Postgres | — | `PM_REVIEW/SQL SCRIPTS/` |
| All → Postgres | `prisma` (admin) / SQLAlchemy or raw (mobile BE) | DB credentials | `PM_REVIEW/SQL SCRIPTS/init_full_setup.sql` |

## Risk hot-spots khi sửa code

### Sửa `health_system/backend/app/routers/`
**Impact:** Mobile app + IoT sim (nếu trigger endpoint thay đổi)
- Check `health_system/lib/` repositories có gọi endpoint này không
- Check `Iot_Simulator_clean/transport/http_publisher.py` payload format

### Sửa `healthguard-model-api/app/routers/`
**Impact:** Backend (health_system + HealthGuard) gọi model API
- Check `health_system/backend/app/services/` có client gọi model API không
- Update version trong `app/services/prediction_contract.py` nếu breaking

### Sửa Prisma schema (`HealthGuard/backend/prisma/schema.prisma`)
**Impact:** Postgres DB → cả 2 backend đều dùng
- Sync SQL với `PM_REVIEW/SQL SCRIPTS/` — đó là source of truth canonical
- Mobile backend cũng query cùng DB → check FastAPI models tương ứng

### Sửa SQL trong `PM_REVIEW/SQL SCRIPTS/`
**Impact:** Cả hệ thống
- Đây là canonical schema. Migrate cẩn thận.
- Cập nhật Prisma schema (admin) + FastAPI models (mobile BE) đồng thời.

### Sửa UC trong `PM_REVIEW/Resources/UC/`
**Impact:** Test cases + JIRA stories + implementations
- Trigger `UC_AUDIT` skill để check inconsistency.

## Localhost dev ports (convention)

| Service | Port | Repo |
|---|---|---|
| Admin Backend | 5000 | HealthGuard/backend |
| Admin Frontend (Vite) | 5173 | HealthGuard/frontend |
| Mobile Backend (FastAPI) | 8000 | health_system/backend |
| Model API | 8001 | healthguard-model-api |
| IoT Sim API | 8002 | Iot_Simulator_clean/api_server |
| Postgres | 5432 | (shared) |

> **Note:** Verify thực tế trong `.env`/`.env.dev` của từng repo trước khi dùng.

## Khi cần thay đổi cross-repo

1. **Identify ripple effect** — list tất cả repo bị ảnh hưởng.
2. **Update spec trước** — sửa UC/SRS/SQL trong PM_REVIEW.
3. **Update producer** — sửa endpoint/payload server-side.
4. **Update consumer** — sửa client(s) gọi endpoint đó.
5. **Cross-repo test** — chạy E2E smoke test (xem `Iot_Simulator_clean/scripts/e2e_*.ps1`).
6. **Document deviation** trong commit message.
