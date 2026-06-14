# GLOSSARY.md — IoT Simulator Terminology

> Domain term y khoa + project-specific term. Tránh dịch sai, lẫn lộn FE/BE label.

---

## A. Medical / clinical term

| Term | Vietnamese | Definition | Source |
|---|---|---|---|
| **Bradycardia** | Nhịp tim chậm | HR < 60 bpm at rest | AHA |
| **Tachycardia** | Nhịp tim nhanh | HR > 100 bpm at rest | AHA |
| **Hypoxia** | Thiếu oxy máu | SpO2 < 90% | WHO |
| **Hypoxemia** | Same as hypoxia (formal) | SpO2 < 90% | WHO |
| **Hypertension** | Tăng huyết áp | Sys ≥ 130 hoặc Dia ≥ 80 | ACC/AHA 2017 |
| **Hypotension** | Tụt huyết áp | Sys < 90 | Clinical |
| **Apnea** | Ngưng thở | RR < 4 rpm hoặc pause > 10s | NEWS2 |
| **Dyspnea** | Khó thở | RR > 25 rpm hoặc subjective | ERS |
| **Hyperthermia** | Sốt cao | Temp > 38°C | Harrison's |
| **Hypothermia** | Hạ thân nhiệt | Temp < 35°C | Harrison's |
| **NEWS2** | National Early Warning Score 2 | UK clinical score, 0-20 risk scale | UK NHS |
| **NEWS2-Lite** | NEWS2 simplified | Subset cho wearable (HR + SpO2 + RR + temp) | Internal |
| **Hypnogram** | Sơ đồ giấc ngủ | Stage timeline (W/N1/N2/N3/REM) | Sleep medicine |
| **REM** | Giấc ngủ động mắt nhanh | Rapid Eye Movement stage | Sleep medicine |
| **Sleep efficiency** | Hiệu suất giấc ngủ | total_sleep_min / time_in_bed_min × 100 | Sleep medicine |
| **PPG** | Photoplethysmography | Optical HR sensing (smartwatch) | Sensor tech |
| **HRV** | Heart Rate Variability | Time variation between beat | Cardiology |
| **MAP** | Mean Arterial Pressure | dia + (sys − dia) / 3 | Cardiology |
| **Pulse pressure** | Áp suất xung | sys − dia | Cardiology |
| **Stroke** | Đột quỵ | Brain blood flow disruption | Neurology |
| **Fight-or-flight** | Phản ứng căng thẳng | Sympathetic nervous activation, HR/BP spike | Physiology |
| **ADL** | Activities of Daily Living | Walking, sitting, sleeping, ... | Geriatrics |
| **PSG** | Polysomnography | Full sleep study with EEG | Sleep medicine |

---

## B. Project-specific term

| Term | Vietnamese | Definition |
|---|---|---|
| **Simulator** | Giả lập | Repo này — phát telemetry thay smartwatch thật |
| **Telemetry** | Dữ liệu sinh hiệu | Vital + motion + sleep payload publish lên BE |
| **Tick** | Mỗi lần sinh sample | Generator phát 1 record (~1 Hz cho vital, 50 Hz cho motion) |
| **Session** | Phiên giả lập | 1 instance device đang chạy (idle/running/stopped) |
| **Scenario** | Kịch bản | Built-in vital pattern (`normal_rest`, `tachycardia_warning`, ...) |
| **Persona** | Hồ sơ giả định | Per-device baseline (age, weight, gender, seed) |
| **Sustainability** | Duration tối thiểu | Scenario phải duy trì ≥ 60s, không flicker 1 tick |
| **Provenance** | Nguồn gốc dữ liệu | Tag `real:<Dataset>` hoặc `mock` mỗi field |
| **Hard Boundary** | Khung cứng y tế | Floor/ceiling clamp theo AHA/WHO (không vượt được) |
| **Warning threshold** | Ngưỡng cảnh báo | Vùng "không bình thường" — BE flag nhưng simulator vẫn emit |
| **Critical threshold** | Ngưỡng nguy hiểm | Vùng cấp cứu — BE trigger alert |
| **Fallback** | Đường dự phòng | Khi dataset offline, generator dùng default constant + tag `mock` |
| **Replay mode** | Chế độ replay | Source `replay` — phát nguyên row từ dataset, không synthesis |
| **Synthetic mode** | Chế độ tổng hợp | Source `synthetic` — generator + persona, có thể có dataset baseline |
| **Assisted mode** | Chế độ trợ giúp | Source `assisted` — synthetic + dataset overlay (vd stress delta) |
| **Backfill** | Bơm lịch sử | Inject N ngày sleep history qua `/scenarios/sleep/backfill` |
| **FSM** | State machine thiết bị | Device state (`draft`/`provisioned`/`bound`/`streaming`/`fall_countdown`/...) |
| **FallState** | Trạng thái fall | Pipeline state cho fall event (`idle`/`fall_detected`/`fall_countdown`/`sos_active`/`fall_resolved`) |
| **Fall variant** | Biến thể té ngã | Loại ngã (`forward`, `backward`, `lateral`, `false_fall`, `fall_brief`, ...) |
| **Countdown** | Đếm ngược SOS | Operator-cancellable window (10–30s) trước khi escalate alert |
| **Pre-trigger** | Gate trước model | Hard rule (IMPACT_PEAK_3G) + soft rule check trước khi gọi model-api |
| **Trigger mode** | Chế độ trigger | `off`/`shadow`/`active` — kiểm soát có gọi model-api không |
| **Personalization** | Cá nhân hóa | BE feature: baseline per-user + adaptive threshold + trend slope |
| **Baseline status** | Trạng thái baseline | `disabled`/`learning`/`active` của personalization |

---

## C. Schema / payload term

| Term | Definition |
|---|---|
| `sim_vitals_v1` | Schema version 1 cho vital tick payload |
| `sim_motion_v1` | Schema version 1 cho motion window 50 Hz |
| `sim_sleep_v1` | Schema version 1 cho sleep session payload |
| `sim_event_v1` | Schema version 1 cho fall event |
| **DTO** | Data Transfer Object — Pydantic model field camelCase (match FE) |
| **Internal model** | Domain object trong `simulator_core/` — field snake_case |
| **Provenance tag** | Field `<base>_source` ∈ {`real:<Dataset>`, `mock`} |
| **Severity** | `normal` / `warning` / `critical` / `invalid` — derived ở BE |
| **Risk band** | `LOW` / `MEDIUM` / `HIGH` / `CRITICAL` — model-api output |
| **AI prediction label** | `normal` / `possible_fall` / `likely_fall` / `critical_fall` |
| **Bind status** | `unbound` / `bindable` / `bound` — sim device ↔ DB device link |
| **Activity label** | `resting` / `walking` / `running` / `falling` / `recovery` / `sleeping` / `unknown` |
| **Realism mode** | `fallback` / `real` / `edf` — sleep enricher mode |

---

## D. Cross-repo / system term

| Term | Definition |
|---|---|
| **HealthGuard** | Tên hệ thống tổng (5 repo) |
| **VSmartwatch** | Brand wearable — workspace root |
| **Mobile BE** | `health_system/backend` (port 8002) — main consumer |
| **Admin BE** | `HealthGuard/backend` (port 5000) |
| **Model API** | `healthguard-model-api` (port 8001) — ML inference |
| **PM_REVIEW** | Repo docs + SQL canonical |
| **Internal secret** | `X-Internal-Secret` header — service-to-service auth |
| **Internal service** | `X-Internal-Service: iot-simulator` — caller identifier |
| **Sim admin key** | `X-Sim-Admin-Key` header — protect simulator admin endpoint |
| **Internal Service header** | `X-Internal-Service` (vd `iot-simulator`) — caller side |
| **X-Target-Profile-Id** | Header proxy personalization endpoint — đại diện user_id |
| **Canonical SQL** | `PM_REVIEW/SQL SCRIPTS/init_full_setup.sql` — DB source of truth |
| **Cross-repo PR sequence** | Producer → consumer → E2E smoke (xem `workflow-cross-repo.mdc`) |

---

## E. Dataset acronym

| Acronym | Full name |
|---|---|
| **PPG-DaLiA** | PPG Dataset for motion compensation and Heart Rate estimation in Daily Life Activities |
| **PAMAP2** | Physical Activity Monitoring dataset 2 |
| **PIF_v3** | Post-Impact Fall version 3 (internal) |
| **UP-Fall** | Universidad Panamericana Fall Detection dataset |
| **Sleep-EDF** | Sleep European Data Format database |
| **WESAD** | Wearable Stress and Affect Detection dataset |
| **VitalDB** | Vital signs database (Korean ICU) |
| **BIDMC** | Beth Israel Deaconess Medical Center dataset |

---

## F. Tooling / process term

| Term | Definition |
|---|---|
| **`/auto`** | Automated pipeline workflow — chain check → brainstorm → plan → build → review → test |
| **`/check`** | Comprehensive module/bug audit (Phase 1 of `/auto`) |
| **`/brainstorm`** | Senior-vetted fix direction proposal (GATE 1 — anh confirm) |
| **`/plan`** | Vertical-slice task breakdown |
| **`/build`** | TDD per task implementation |
| **`/review`** | 5-axis self-review (correctness/readability/architecture/security/performance) |
| **`/test`** | DB + API + E2E smoke (Phase 6 of `/auto`) |
| **GATE 1 / GATE 2** | 2 user confirmation point trong `/auto` (anh decide direction + final test) |
| **Skill** | `.cursor/skills/<name>/SKILL.md` — discipline em invoke trước task |
| **Rule** | `.cursor/rules/*.mdc` — auto-load behavioral guideline |
| **Hook** | `.cursor/hooks/*.py` — guard agent action (block dangerous, protect secret) |
| **MCP** | Model Context Protocol — external tool server (postgres, github, context7) |
| **Provenance audit** | Verify mọi field từ dataset có tag đúng |
| **Hard Boundary check** | Verify clamp ở mọi vital generator |

---

## G. Common abbreviations in code

| Abbrev | Meaning |
|---|---|
| `bpm` | Beats per minute (HR) hoặc Breaths per minute (RR) — context-dependent |
| `rpm` | Respirations per minute (luôn cho RR) |
| `mmHg` | millimeter of mercury (BP unit) |
| `bp_sys` / `bp_dia` | Blood pressure systolic / diastolic |
| `ts` | timestamp (epoch second hoặc ISO-8601) |
| `did` / `device_id` | Device identifier (UUID hoặc string) |
| `sid` / `session_id` | Session identifier |
| `uid` | User identifier (BE only — sim không track user) |
| `EDF` | European Data Format (Sleep-EDF file format) |
| `FSM` | Finite State Machine |
| `WS` | WebSocket |
| `ETL` | Extract-Transform-Load |
| `DI` | Dependency Injection |
| `DTO` | Data Transfer Object |
| `BE` | Backend |
| `FE` | Frontend |
| `PII` | Personally Identifiable Information |
| `PHI` | Protected Health Information |

---

## H. Anti-pattern naming (đừng dùng)

| Avoid | Use instead |
|---|---|
| "fake" / "synthetic" cho fallback | `mock` (provenance tag standard) |
| "lite" / "mini" / "simple" | Specific term (`heuristic`, `subset`, `single-channel`) |
| "v2" suffix without bump | Bump schema version chính thức (`sim_vitals_v2`) |
| "patch" / "hack" trong commit | `fix(<scope>)` Conventional Commits |
| "data" / "info" / "thing" var name | Specific (`vitals_payload`, `device_metadata`) |
| Đặt tên file English chỉ vì English | Match codebase convention (snake_case Python, camelCase TS) |

---

**Last verified:** 2026-05-21 (cross-reference với `api_server/schemas.py`, `simulator_core/`, `docs/FEATURE_SPEC.md`).
