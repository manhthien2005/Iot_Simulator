---
trigger: model_decision
description: Project metadata (5 repos, paths, trunks, domain context) for VSmartwatch HealthGuard. Apply when user references repo names, paths, stack info, UC requirements, or asks about cross-repo features.
---

# Project Context — VSmartwatch HealthGuard

Hệ thống smartwatch giám sát sức khỏe người cao tuổi. Đồ án 2 (capstone) của anh, solo dev.

## 5 Repo chính

| Repo | Path | Vai trò | Stack | Trunk |
|---|---|---|---|---|
| `HealthGuard` | `d:\DoAn2\VSmartwatch\HealthGuard` | Admin web | Express + Prisma + Vite frontend | `develop` |
| `health_system` | `d:\DoAn2\VSmartwatch\health_system` | Mobile + Backend | Flutter 3.11 / FastAPI Python 3.11 | `develop` |
| `Iot_Simulator_clean` | `d:\DoAn2\VSmartwatch\Iot_Simulator_clean` | IoT giả lập | Python FastAPI + simulator-web | `develop` |
| `healthguard-model-api` | `d:\DoAn2\VSmartwatch\healthguard-model-api` | Model API | Python FastAPI + ML models | `master` |
| `PM_REVIEW` | `d:\DoAn2\VSmartwatch\PM_REVIEW` | Docs + SQL + custom skills | Markdown + SQL | `main` |

## Domain context

- **End user:** Người cao tuổi đeo smartwatch + người thân theo dõi qua mobile app + admin/clinician xem qua web.
- **Core features:**
  - Vital signs monitoring (heart rate, SpO2, sleep, activity)
  - Fall detection + SOS escalation (real-time alert)
  - Risk analysis (sleep risk, fall risk) qua ML model
  - Emergency response (SOS confirm/cancel flow với countdown)
  - Family sharing (linked accounts, profile switcher)
  - Health monitoring dashboard (admin)

## Module map (cross-repo)

Mỗi feature trải qua nhiều repo. Khi sửa 1 feature, kiểm tra cả pipeline:

| Feature | Mobile (health_system) | Admin (HealthGuard) | IoT (sim) | Model API |
|---|---|---|---|---|
| Fall detection | UI + service + FCM | View alert + manage | Trigger event | Predict risk |
| Vital monitoring | Chart + sync | Dashboard + alert | Publish telemetry | — |
| Sleep risk | Analysis screen | Report | — | Sleep model |
| SOS | Confirm + countdown | Receive + dispatch | — | — |
| Auth | Login screen | Admin login + token | Internal secret | — |
| Family share | Linked contact | View relationships | — | — |

## Spec source-of-truth

- **SRS + UC + DB schema + JIRA backlog**: tất cả ở `PM_REVIEW/`
- **MASTER_INDEX**: `PM_REVIEW/MASTER_INDEX.md` — GPS map của project
- **SRS Index**: `PM_REVIEW/Resources/SRS_INDEX.md`
- **SQL schema**: `PM_REVIEW/SQL SCRIPTS/`
- **Use Cases**: `PM_REVIEW/Resources/UC/{Module}/UC{XXX}.md` (26 UCs)
- **JIRA backlog**: `PM_REVIEW/Resources/TASK/JIRA/Sprint-{N}/`
- Khi cần verify yêu cầu → đọc UC trước, không guess.

## Khi anh request feature/bug fix

Phân loại trước khi action:

### Domain feature / behavior bug (mobile UI, BE business logic, end-user flow)
1. **Locate UC** trong `PM_REVIEW/Resources/UC/` — nếu chưa có UC, hỏi anh muốn dùng UC nào hoặc tạo mới.
2. **Check cross-repo impact** — feature này chạm mấy repo? (xem topology.md)
3. **Identify acceptance criteria** từ UC + JIRA story tương ứng.
4. **Chỉ sau đó** mới đề xuất implementation plan.

### Infra / tooling / test harness / CI bug (workflow, hook, sync script, gitignore, lint config)
1. **Locate ADR** trong `PM_REVIEW/ADR/` nếu có decision liên quan.
2. **Check workflow** trong `.windsurf/workflows/` để biết convention.
3. **Skip UC requirement** — UC là cho domain behavior, không phải infra.
4. Direct fix nếu trivial (typo, paths, version bump). Plan nếu structural change.

## Repo-specific overlays

Mỗi repo còn có thêm rules đặc thù trong `.windsurf/rules/` (số 21-25). Đọc cả overlay khi work trong repo đó.
