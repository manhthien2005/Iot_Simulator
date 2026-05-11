---
trigger: always_on
---

# Context Continuity — Cross-Session Memory

Anh có thể làm việc parallel trên nhiều module/session khác nhau. Em (AI) phải đọc context từ session trước để tránh:
- Đề xuất lại approach đã thử fail.
- Hỏi lại quyết định đã chốt.
- Re-implement feature đã có ở repo khác.

## 2 nguồn ngữ cảnh em PHẢI biết về

### 1. Bug Log — `PM_REVIEW/BUGS/`

**Mục đích:** Track mọi non-trivial bug + tất cả attempts (kể cả thất bại).

**Khi em phải đọc:**
- BẮT ĐẦU `/debug`, `/fix-issue` workflow → check `PM_REVIEW/BUGS/<BUG-ID>.md` nếu anh nhắc bug ID.
- Khi anh báo "still broken", "tried that", "this bug again" → search BUGS folder by keyword.
- Khi attempt fix #N với N ≥ 2 cho cùng bug.

**Khi em phải UPDATE:**
- Sau mỗi attempt (failed or successful) — append entry vào file.
- Khi bug resolved — đổi status, link fix commit.

**Iron rule:** KHÔNG đề xuất approach đã được mark `failed` trong log. Variations chỉ OK khi variation address documented failure reason.

**Skill:** `bug-log` (chi tiết template + workflow).

### 2. Decision Log (ADR-lite) — `PM_REVIEW/ADR/`

**Mục đích:** Track architectural decisions với context + options + consequences.

**Khi em phải đọc:**
- BẮT ĐẦU `/spec`, `/refactor-module`, `/cross-repo-feature` → check tags relevant.
- Khi anh hỏi "tại sao chúng ta chọn X" → search ADR.
- Khi đề xuất approach mới → check nếu đã có ADR conflict.

**Khi em phải CREATE ADR mới:**
- Choosing approach A over B (cần ≥ 2 options).
- Adopting new library/framework/pattern.
- Changing project-wide convention.
- Defining cross-repo contract.
- Reversing previous decision.

**Skill:** `decision-log` (chi tiết template + workflow).

## Em PHẢI làm gì khi conversation start

Implicit (without anh asking):
- Nếu anh nhắc bug ID hoặc symptom keyword → search `PM_REVIEW/BUGS/` trước khi propose fix.
- Nếu anh nhắc architectural choice → search `PM_REVIEW/ADR/` trước khi propose.
- Nếu anh nói "stuck" hoặc bug fix #3+ → ép `/stuck` workflow + đọc full bug log.

## ID convention — quick reference

### Bug ID
Format: `<REPO-PREFIX>-<NUM>` (3-digit zero-padded)

| Prefix | Repo |
|---|---|
| HG | HealthGuard |
| HS | health_system |
| IS | Iot_Simulator_clean |
| MA | healthguard-model-api |
| PM | PM_REVIEW (rare) |
| XR | Cross-repo |

Ví dụ: `HG-001`, `HS-005`, `XR-002`.

### ADR ID
Format: `<NNN>-<short-kebab-title>` — sequential, system-wide (NOT per repo).

Ví dụ: `001-workspace-tooling-host`, `015-prediction-contract-versioning`.

## INDEX files — GPS

Always check first:
- `PM_REVIEW/BUGS/INDEX.md` — open bugs by status, repo, severity.
- `PM_REVIEW/ADR/INDEX.md` — decisions chronological + by tag.

INDEX MUST stay in sync — em phải update khi tạo/resolve bug hoặc tạo/supersede ADR.

## Anti-patterns auto-flag

Khi em nhận thấy mình sắp:
- Đề xuất approach đã có trong bug log với status `failed` → STOP, đọc lại lý do, đề xuất khác.
- Re-debate decision đã có ADR `Accepted` → STOP, reference ADR.
- Skip update INDEX sau khi tạo bug/ADR mới → STOP, update.
- Tạo bug log mới khi đã có file existing với cùng symptom → STOP, append vào file existing.

## Lý do tồn tại rule này

Rule 50-token-discipline khuyên đọc tiết kiệm. Rule này nói "nhưng đọc bug log + ADR là MUST". Hai cái không conflict — bug log + ADR là external memory, đọc 1-2 file 200 lines là token tốt nhất anh có thể đầu tư khi entering bug fix session.

> **Solo dev specific:** anh không có team review. Bug log + ADR LÀ team review của anh — anh-của-tuần-trước review anh-của-tuần-này.
