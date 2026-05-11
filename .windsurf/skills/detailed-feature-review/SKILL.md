---
name: detailed-feature-review
description: |
  Perform a detailed evaluation of a specific feature — analyze actual source code
  against architecture standards, verify SRS compliance, assess implementation quality,
  and cross-check JIRA Stories for the project development team.
  Use when user says "review code", "đánh giá chi tiết", "evaluate feature",
  "check implementation", "review module", "review chức năng", "kiểm tra code",
  "detailed review", "danh gia chi tiet", "xem code giúp", "chấm điểm code",
  "review feature", "score this module".
  DO NOT use for: PR reviews, debugging, writing new code, generating test cases.
risk: safe
source: custom
date_added: "2026-03-03"
date_updated: "2026-03-06"
---

<!-- Version: 3.0.0 -->
<!-- Last reviewed: 2026-03-06 -->
<!-- Changelog:
  v3.0.0 (2026-03-06) — BREAKING: Full English rewrite for optimal AI comprehension.
                         All instructions, examples, constraints in English.
                         Report output stays Vietnamese (stakeholder-facing).
  v2.1.0 (2026-03-06) — Fix: complete examples, anti-triggers, consolidate sub-skills,
                         WHY for constraints, semantic verbs, new edge cases.
  v2.0.0 (2026-03-06) — BREAKING: Full rewrite — Goal, Examples, Constraints, verify.
  v1.1.0 (2026-03-04) — Add Re-review Protocol, SRS_INDEX reference
  v1.0.0 (2026-03-03) — Initial release
-->

# Goal

Evaluate actual source code against 8 standardized criteria (100 points) to ensure every feature scores ≥76/100 before release.

# Instructions

## Step 0: Project Detection

1. IDENTIFY the target project: ADMIN (`d:\DoAn2\VSmartwatch\HealthGuard`) or MOBILE (`d:\DoAn2\VSmartwatch\health_system`)
   - If user does not specify → **ASK**: "Which project should I review — Admin or Mobile?"
   - If only 1 project exists → use that project, notify user

## Step 1: Context Loading (Tiered — Mandatory)

**Tier 1 — Navigation (ALWAYS first):**
1. READ `PM_REVIEW/MASTER_INDEX.md` → LOCATE the row for the target module
   - ⚠️ If module not found in MASTER_INDEX → INFORM user: "Module [X] not found. Available modules: [list]" → STOP
2. READ `PM_REVIEW/Resources/SRS_INDEX.md` → System-level context
3. NOTE: Sprint number, UC references, summary file path

**Tier 2 — Module Context (ONE summary only):**
4. READ the corresponding summary file (e.g., `summaries/AUTH_summary.md`)
   - ⚠️ If summary does not exist → Note "Missing summary" in report, continue with source scan
5. READ `PM_REVIEW/Resources/TASK/JIRA/README.md` → Quick lookup for Epics/Stories

**Tier 3 — Architecture Standards (ONE consolidated reference):**
6. READ `references/architecture-standards.md` — contains all architecture evaluation criteria
   - Only read original sub-skills in `skills/` if deep-dive needed for a specific edge case

**Tier 4 — Source Code Deep Dive (Progressive):**
7. **SCAN**: List files in the relevant folder → VERIFY files actually exist
8. **OUTLINE**: Run `view_file_outline` on key files → EXTRACT function names, class names, LOC
9. **DEEP READ**: Read in detail ONLY the files being evaluated — do not read everything
   - ⚠️ If source code folder is empty or does not exist → INFORM user: "Folder [X] has no source code. Please verify the path." → STOP

### ⛔ WHAT NOT TO DO
- ❌ DO NOT read the full SRS → use summaries. If details are needed, read the specific UC file from `PM_REVIEW/Resources/UC/`
- ❌ DO NOT read the full JIRA CSV → use `JIRA/README.md` to find Epics, then read related Stories
- ❌ DO NOT read files unrelated to the module under review
- ❌ DO NOT read all source code at once → read file-by-file selectively

## Step 2: Check Previous Review (Re-review Protocol)

1. DERIVE the expected filename: `{FEATURE}_{MODULE}_review.md` (see Output Protocol below)
2. SEARCH for an existing file in `REVIEW_ADMIN/` or `REVIEW_MOBILE/`
   - **If FOUND** → READ old file, EXTRACT: old scores (per criterion + total), old weaknesses, old recommendations, old date, old review count
   - **If NOT found** → First review, set `Lần đánh giá: 1`
   - ⚠️ If old file is corrupted/unreadable → Treat as first review, log warning

## Step 3: Code Evaluation (8 Criteria)

**READ `references/evaluation-criteria.md`** for detailed scoring rubrics per criterion.

SCORE the code against 8 criteria (100 points total):

| #   | Criterion                   | Max | Action                                                            |
| --- | --------------------------- | --- | ----------------------------------------------------------------- |
| 1   | Feature correctness         | 15  | COMPARE UC main/alt flows vs actual implementation                |
| 2   | API Design                  | 10  | VERIFY RESTful conventions + Error Response + Data Contract       |
| 3   | Architecture & Patterns     | 15  | ASSESS Clean Architecture layers + Domain Logic + Design Patterns |
| 4   | Validation & Error Handling | 12  | INSPECT input validation + error response format                  |
| 5   | Security                    | 12  | AUDIT Auth/AuthZ + Input Security + Rate Limiting                 |
| 6   | Code Quality                | 12  | MEASURE SOLID compliance + Clean Code Metrics + Anti-patterns     |
| 7   | Testing                     | 12  | EVALUATE test coverage + test quality + advanced testing          |
| 8   | Documentation               | 12  | VERIFY code docs + API docs + ADRs                                |

**Self-rate confidence for each criterion:**
- IF confidence ≥ 85% → SCORE directly
- IF confidence 50-84% → SCORE + add note "⚠️ Low confidence — needs verification"
- IF confidence < 50% → Write "❓ Insufficient data to score" + ASK user for more info

## Step 4: Cross-Reference JIRA Stories

1. MAP relevant Epic/Story from JIRA Index to the module under review
2. COMPARE each acceptance criterion against actual implementation — mark ✅/❌
3. FLAG discrepancies (if any) — specify: Story ID, description of gap, severity (🔴/🟡/🟢)
   - ⚠️ If no Epic found for this module → Write "JIRA: TBD" in report, flag in recommendations

## Step 5: SRS/Use Case Verification

1. COMPARE each step in the UC main flow against actual code — mark Match ✅/❌
2. VERIFY alternative flows: list each alt flow → confirm whether implemented
3. VERIFY exception flows: list each exception → confirm whether handled
4. POPULATE the SRS Compliance table in the report template

## Step 6: Generate Report

1. **MANDATORY**: READ the template from `references/report-template.md` → FOLLOW the exact structure
2. POPULATE all sections in the template — leave no section empty (write "N/A" if not applicable)
3. If this is a re-review (Step 2 found old file) → APPEND the "🔄 SO SÁNH VỚI LẦN ĐÁNH GIÁ TRƯỚC" section
4. INCREMENT the `Lần đánh giá` counter
5. Report content MUST be in **Vietnamese** — because stakeholders read Vietnamese

## Step 7: ✅ VERIFY (Self-Check Loop)

Before outputting, self-check:
- CALCULATE: Sum of 8 criterion scores = displayed total score? (re-add them)
- VERIFY: Every weakness has a file path + line number reference (if missing → add it)
- VERIFY: SRS Compliance table covers main flow + alternative flows
- VERIFY: Quality Status matches score range (76-100=✅ Pass, 51-75=⚠️ Needs Fix, 0-50=❌ Fail)
- If re-review: VALIDATE comparison section logic (fixed / still-exists / new)

## Step 8: Save & Update MASTER_INDEX

1. SAVE the review file per Output File Protocol
2. **OVERWRITE** the old file if this is a re-review — DO NOT create a new file
3. UPDATE `MASTER_INDEX.md`:
   - `Review Status` → ✅ Done
   - `Score` → XX/100
   - `Quality` → Per score range
   - `Review File` → Relative link
   - `Last Review` → Today's date (ISO format)

# Output File Protocol

### File Naming
```
{FEATURE}_{MODULE}_review.md
```
- **FEATURE**: Feature name, UPPERCASE, spaces → `_` (e.g., `AUTH_LOGIN`)
- **MODULE**: Module name from MASTER_INDEX, UPPERCASE (e.g., `AUTH`)
- If feature name = module name → use `{MODULE}_review.md` only

### Output Location
- Admin → `PM_REVIEW/REVIEW_ADMIN/{filename}`
- Mobile → `PM_REVIEW/REVIEW_MOBILE/{filename}`

### Naming Examples
| User Request                            | File Output                              |
| --------------------------------------- | ---------------------------------------- |
| "Review Login, module AUTH, Admin"      | `REVIEW_ADMIN/AUTH_LOGIN_review.md`      |
| "Review AUTH module, Admin"             | `REVIEW_ADMIN/AUTH_review.md`            |
| "Review Device Connect, DEVICE, Mobile" | `REVIEW_MOBILE/DEVICE_CONNECT_review.md` |

# Examples

## Example 1: Happy path — First-time review of AUTH_LOGIN

**Context:** Developer just finished the login feature. PM wants a quality review before merging.

**Input:**
> "Review chức năng Login, module AUTH, project Admin"

**Thought Process:**
- Parse request → Feature: LOGIN, Module: AUTH, Project: ADMIN
- Tier 1: READ MASTER_INDEX → AUTH module, Sprint 1, UC001
- Tier 2: READ AUTH_summary.md → API endpoints: POST /api/auth/sessions
- Tier 3: READ references/architecture-standards.md
- Tier 4: SCAN `HealthGuard/src/modules/auth/` → controller, service, routes
- Check previous: SEARCH `REVIEW_ADMIN/AUTH_LOGIN_review.md` → Not found → First review
- SCORE 8 criteria → Generate report

**Output:**
```markdown
# 🔬 BÁO CÁO ĐÁNH GIÁ CHI TIẾT

## Thông tin chung
- **Chức năng**: Login
- **Module**: AUTH
- **Dự án**: Admin
- **Sprint**: Sprint 1
- **JIRA Epic**: EP04-Login
- **JIRA Story**: VS-001: Đăng nhập Admin
- **UC Reference**: UC001
- **Ngày đánh giá**: 2026-03-06
- **Lần đánh giá**: 1
- **Ngày đánh giá trước**: N/A

---

## 🏆 TỔNG ĐIỂM: 72/100

| Tiêu chí                    | Điểm  | Ghi chú                         |
| --------------------------- | ----- | ------------------------------- |
| Chức năng đúng yêu cầu      | 13/15 | Main flow OK, thiếu 2 alt flows |
| API Design                  | 8/10  | RESTful chuẩn, thiếu pagination |
| Architecture & Patterns     | 12/15 | Clean arch tốt, thiếu DTO       |
| Validation & Error Handling | 9/12  | Có validation, thiếu rate limit |
| Security                    | 8/12  | JWT OK, thiếu brute force guard |
| Code Quality                | 9/12  | SOLID tốt, 1 God function       |
| Testing                     | 5/12  | Chỉ có unit test cơ bản         |
| Documentation               | 8/12  | JSDoc có, thiếu API docs        |

---

## 📊 SRS COMPLIANCE

### Main Flow
| Bước | SRS Yêu cầu                 | Implementation             | Match? |
| ---- | --------------------------- | -------------------------- | ------ |
| 1    | User nhập email + password  | Form validation + API call | ✅      |
| 2    | Server validate credentials | bcrypt compare in service  | ✅      |
| 3    | Trả JWT token               | JWT sign with 24h expiry   | ✅      |

### Alternative Flows
| Flow | SRS Yêu cầu         | Implementation | Match? |
| ---- | ------------------- | -------------- | ------ |
| AF1  | Email không tồn tại | 401 response   | ✅      |
| AF2  | Password sai        | 401 response   | ✅      |
| AF3  | Account bị lock     | Chưa implement | ❌      |

---

## ✅ ƯU ĐIỂM
1. Clean Architecture separation rõ ràng — `authController.js` chỉ handle HTTP, `authService.js` chứa business logic
2. Password hashing dùng bcrypt (rounds=12) — chuẩn bảo mật

## ❌ NHƯỢC ĐIỂM
1. God function `authService.login()` (85 dòng) — `src/modules/auth/authService.js:L45-L130` — nên tách validate, authenticate, token generation
2. Thiếu rate limiting trên POST /api/auth/sessions — `src/modules/auth/authRoutes.js:L12` — brute force risk

## 🔧 ĐIỂM CẦN CẢI THIỆN
1. **[HIGH]** Thêm rate limiting → Cách sửa: dùng `express-rate-limit` middleware
2. **[HIGH]** Implement account lockout (AF3) → Cách sửa: thêm `failedAttempts` counter trong User model
3. **[MEDIUM]** Tách `authService.login()` thành 3 functions → Cách sửa: extractMethod refactoring

## 📋 KHUYẾN NGHỊ HÀNH ĐỘNG
| #   | Action                    | Owner     | Priority | Sprint   |
| --- | ------------------------- | --------- | -------- | -------- |
| 1   | Thêm rate limiting        | Developer | HIGH     | Sprint 2 |
| 2   | Implement account lockout | Developer | HIGH     | Sprint 2 |
| 3   | Refactor God function     | Developer | MEDIUM   | Sprint 2 |
```

File saved: `REVIEW_ADMIN/AUTH_LOGIN_review.md`
MASTER_INDEX updated: AUTH → Score: 72/100, Quality: ⚠️ Needs Fix

---

## Example 2: Edge case — Re-review AUTH (round 2, missing source file)

**Context:** Team fixed bugs from the previous review. PM wants a re-review to confirm improvements.

**Input:**
> "Review lại module AUTH, Admin"

**Thought Process:**
- Parse → Feature=AUTH, Module=AUTH, Project=ADMIN
- Check previous: SEARCH `REVIEW_ADMIN/AUTH_review.md` → **FOUND** (Round 1, score 72/100)
- EXTRACT old data: score=72, weaknesses=[missing rate limiting, missing DTO, God function]
- Tier 4: SCAN source → file `auth.middleware.js` does not exist
  → Log warning: "⚠️ auth.middleware.js not found — skipping related sub-checks"
- SCORE → COMPARE with old scores...

**Output (comparison section — appended to the full report):**
```markdown
## 🔄 SO SÁNH VỚI LẦN ĐÁNH GIÁ TRƯỚC

### Tổng quan thay đổi
- **Điểm cũ**: 72/100 (2026-03-01)
- **Điểm mới**: 81/100 (2026-03-06)
- **Thay đổi**: +9 điểm

### So sánh điểm theo tiêu chí
| Tiêu chí                    | Điểm cũ | Điểm mới | Thay đổi | Ghi chú              |
| --------------------------- | ------- | -------- | -------- | -------------------- |
| Chức năng đúng yêu cầu      | 13/15   | 14/15    | +1       | Thêm account lockout |
| API Design                  | 8/10    | 8/10     | 0        | Chưa thay đổi        |
| Architecture & Patterns     | 12/15   | 13/15    | +1       | Tách God function    |
| Validation & Error Handling | 9/12    | 11/12    | +2       | Thêm rate limiting   |
| Security                    | 8/12    | 11/12    | +3       | Rate limit + lockout |
| Code Quality                | 9/12    | 11/12    | +2       | Refactored service   |
| Testing                     | 5/12    | 5/12     | 0        | Chưa thêm tests      |
| Documentation               | 8/12    | 8/12     | 0        | Chưa thay đổi        |

### ✅ Nhược điểm ĐÃ KHẮC PHỤC
| #   | Nhược điểm cũ        | Trạng thái | Chi tiết khắc phục                  |
| --- | -------------------- | ---------- | ----------------------------------- |
| 1   | Thiếu rate limiting  | ✅ Đã sửa   | Thêm express-rate-limit (5 req/min) |
| 2   | God function login() | ✅ Đã sửa   | Tách thành 3 functions nhỏ          |

### ⚠️ Nhược điểm VẪN TỒN TẠI
| #   | Nhược điểm       | Mức độ | Ghi chú                 |
| --- | ---------------- | ------ | ----------------------- |
| 1   | Thiếu unit tests | 🟡      | Chỉ có 2 test cơ bản    |
| 2   | Thiếu API docs   | 🟡      | Chưa có Swagger/OpenAPI |

### 🆕 Nhược điểm MỚI PHÁT SINH
| #   | Nhược điểm mới                    | Mức độ | Ghi chú |
| --- | --------------------------------- | ------ | ------- |
|     | Không có nhược điểm mới phát sinh | —      | —       |

### 💬 Nhận xét tổng quan
> Team đã cải thiện rõ rệt ở mảng Security (+3) và Code Quality (+2). Rate limiting và account lockout đã được implement đúng. Ưu tiên tiếp: bổ sung unit tests và API documentation.
```

File saved: `REVIEW_ADMIN/AUTH_review.md` (OVERWRITE)
MASTER_INDEX updated: AUTH → Score: 81/100, Quality: ✅ Pass

# Constraints

## Security (Priority #1 — MUST remember)
- 🚫 NEVER include API keys, tokens, or passwords in the report — if found in source code, write "[REDACTED]" and flag as a security issue (WHY: leaked credentials compromise the entire system)
- 🚫 NEVER delete or modify source code during review — this skill only READS and EVALUATES (WHY: modifying code is out of scope and risks regressions)

## Accuracy (Priority #2)
- ✅ ALWAYS cite file path + line number for every weakness — a claim without evidence is worthless (WHY: developers need to know WHERE to fix)
- ✅ ALWAYS recalculate the total score before output — arithmetic errors destroy credibility (WHY: PM uses the score to decide release/hold)
- ⚠️ If insufficient data to score a criterion → write "N/A" + reason, DO NOT guess (WHY: a false positive is worse than no score)

## Format (Priority #3)
- ✅ ALWAYS use the template from `references/report-template.md` — no improvisation (WHY: stakeholders are trained on this format; changing it wastes their re-learning time)
- ✅ ALWAYS overwrite the old file on re-review — DO NOT create a new file (WHY: avoids duplicate files and MASTER_INDEX only links to one file)
- ⚠️ Report content in **Vietnamese** — per template (WHY: stakeholders are Vietnamese speakers; English headers slow down scanning)

# Reference Documents

| Name               | Path                                                | When to read                        |
| ------------------ | --------------------------------------------------- | ----------------------------------- |
| **MASTER INDEX**   | `PM_REVIEW/MASTER_INDEX.md`                         | **ALWAYS** — Tier 1                 |
| **SRS Index**      | `PM_REVIEW/Resources/SRS_INDEX.md`                  | **ALWAYS** — Tier 1                 |
| **Arch Standards** | `references/architecture-standards.md`              | **ALWAYS** — Tier 3                 |
| Eval Criteria      | `references/evaluation-criteria.md`                 | Step 3 — Scoring rubrics            |
| Report Template    | `references/report-template.md`                     | Step 6 — Output format              |
| Admin Structure    | `PM_REVIEW/REVIEW_ADMIN/Project_Structure.md`       | When reviewing Admin                |
| Mobile Structure   | `PM_REVIEW/REVIEW_MOBILE/Project_Structure.md`      | When reviewing Mobile               |
| Summaries          | `PM_REVIEW/REVIEW_{ADMIN\|MOBILE}/summaries/*.md`   | Tier 2 — Module context             |
| Use Cases          | `PM_REVIEW/Resources/UC/**/*.md`                    | When details missing from summaries |
| **JIRA Index**     | `PM_REVIEW/Resources/TASK/JIRA/README.md`           | **ALWAYS** — Tier 2                 |
| JIRA CSV           | `PM_REVIEW/Resources/TASK/JIRA/JIRA_IMPORT_ALL.csv` | Only for full Story details         |

# Edge Cases

| Scenario                                     | Action                                                                  |
| -------------------------------------------- | ----------------------------------------------------------------------- |
| Module not in MASTER_INDEX                   | LIST available modules, ASK user to choose → STOP                       |
| Summary file missing                         | Note "Missing summary" in report, skip Tier 2, proceed with source scan |
| Source code folder empty                     | Mark "⬜ Not built" in report, score = N/A, inform user                  |
| Previous review file corrupted               | Treat as first review, set `Lần đánh giá: 1`                            |
| JIRA Epic not found for module               | Mark "JIRA: TBD" in report, flag in recommendations                     |
| Sub-skill file missing                       | Log warning, continue using architecture-standards.md                   |
| User says "review" without specifying module | ASK: "Which module do you want to review? [list from MASTER_INDEX]"     |

<!-- Generated by Skill Creator Ultra v3.0 -->
