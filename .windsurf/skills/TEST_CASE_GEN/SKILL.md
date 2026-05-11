---
name: test-case-generator
description: "Generate structured test case files from UC/SRS/SQL/API sources, execute existing test cases with timestamp tracking, or create AI-executable test plans. Triggers: generate test case, test case, testing, TC generation, sinh test case, test function, test module, run test, execute test, test tracking, QA test, test plan, kế hoạch test, tạo test plan."
category: project-management
risk: safe
source: custom
date_added: "2026-03-05"
date_updated: "2026-03-06"
---

# Skill: TEST_CASE_GEN — Test Case Generator & Executor

## Goal

Generate **complete, structured test case files** from project sources (UC, SRS, SQL schema, API code), **execute test cases** via API calls or browser interactions with precise tracking, or **create AI-executable test plans** that orchestrate multi-file test execution. All output is optimized for AI agent (Antigravity) consumption.

---

## Instructions

### Mode A — GENERATE

User says: "Sinh ra bộ test case cho chức năng {FUNCTION}" or similar.

- Generate test cases for a specific module/function
- Create test case file from UC main flows, alt flows, business rules, and NFRs
- Cover both positive and negative scenarios
- Output: new `.md` file in `TESTING/{MODULE}/` folder

### Mode B — EXECUTE

User says: "Thực hiện test theo file {FILE}" or similar.

- Read an existing test case file
- Determine test layer for each TC (L1: API / L2: UI Smoke / L3: Manual)
- Execute L1 tests via `run_command` + curl (read `references/be-test-execution.md`)
- Execute L2 tests via `browser_subagent` (read `references/fe-test-execution.md`)
- Mark L3 tests as `SKIP` with note "Requires manual testing"
- Update: Status, Actual result, Tester, DateTime
- Append execution log with session summary

### Mode C — TEST_PLAN

User says: "Tạo test plan cho module {MODULE}" or similar.

- Scan all existing test case files in `TESTING/{MODULE}/`
- Generate an AI-executable Test Plan (read `references/test-plan-protocol.md`)
- Includes: environment setup, execution order, tool mapping, duration estimate
- Output: `{MODULE}_test_plan.md` in `TESTING/{MODULE}/`
- If no test case files exist → tell user to run GENERATE mode first

---

## Test Execution Layers

> [!IMPORTANT]
> When executing tests (Mode B) or planning tests (Mode C), classify each TC into one of 3 layers:

| Layer  | Name      | Tool                 | What It Tests                                | AI Capability       |
| ------ | --------- | -------------------- | -------------------------------------------- | ------------------- |
| **L1** | API Tests | `run_command` + curl | HTTP status, response JSON, DB state         | ✅ Full auto         |
| **L2** | UI Smoke  | `browser_subagent`   | Page load, form submit, redirect, text       | ✅ Auto (happy path) |
| **L3** | Manual    | Human tester         | Performance, visual regression, long session | ❌ Flag only         |

**Layer assignment rules:**
- TC steps contain `POST/GET/PUT/DELETE {URL}` → **L1**
- TC steps contain `Navigate to`, `Click`, `Enter in field` → **L2**
- TC steps involve `response time`, `concurrent users`, `visual comparison` → **L3**
- TC tests both API call AND UI result → **L1+L2** (run API first, verify UI after)

---

## Context Loading Protocol (MANDATORY)

> [!IMPORTANT]
> Follow this strict tiered protocol. DO NOT skip tiers. DO NOT read sources not needed.

Read `references/context-loading.md` for detailed per-tier instructions.

### Quick Summary

| Tier | Source                        | When          | Purpose                            |
| ---- | ----------------------------- | ------------- | ---------------------------------- |
| 1    | `MASTER_INDEX.md`             | ALWAYS        | Project GPS, module lookup         |
| 2    | `SRS_INDEX.md`                | ALWAYS        | System requirements, HG-FUNC refs  |
| 3    | Target UC file(s)             | GENERATE mode | Main/Alt flows, BRs, NFRs          |
| 4    | SQL schema for module         | GENERATE mode | Table structure, constraints       |
| 5    | API code (routes/controllers) | GENERATE mode | Endpoints, validators, error codes |

### ⛔ WHAT NOT TO DO
- ❌ DO NOT read the full SRS — use SRS_INDEX
- ❌ DO NOT read all SQL files — only the relevant layer
- ❌ DO NOT read all UC files — only the target function's UCs
- ❌ DO NOT generate test cases without reading the UC first

---

## Phase 1: GENERATE — Test Case Generation

### Step 1 — Identify Target

1. Parse user request → extract: **Module** (e.g., AUTH) and **Function** (e.g., LOGIN)
2. Look up in `MASTER_INDEX.md` → find UC Refs (e.g., UC001)
3. Determine **Platform**: ADMIN / MOBILE / BOTH

### Step 2 — Load Context

Follow Context Loading Protocol (Tiers 1–5). For each UC:

| Extract From UC     | Use For                                |
| ------------------- | -------------------------------------- |
| Main Flow steps     | Positive test cases (happy path)       |
| Alternative Flows   | Negative test cases, edge cases        |
| Business Rules (BR) | Validation test cases, boundary values |
| NFR Requirements    | Performance, security, usability tests |
| Preconditions       | Test preconditions column              |
| Postconditions      | Expected results verification          |

From SQL schema:
- Column constraints (NOT NULL, UNIQUE, CHECK) → validation test cases
- Data types → boundary value test cases
- Foreign keys → referential integrity test cases

From API code (if available):
- Route definitions → endpoint test cases
- Validators → input validation test cases
- Error responses → error handling test cases

### Step 3 — Generate Test Data (Materials)

Before writing test cases, generate the **Test Data** section. See `references/testcase-template.md` → "Test Data — Materials" for format.

- Analyze UC preconditions → identify required accounts, roles, device data
- Analyze API endpoints → identify required URLs, tokens, keys
- Set all sensitive values to `⬜ PENDING` — user fills in before EXECUTE
- Pre-fill obvious mock data (e.g., `notexist@test.com` for invalid email tests)

### Step 4 — Generate Test Cases

Read `references/testcase-template.md` for the MANDATORY output format.
Read `references/naming-convention.md` for ID and file naming rules.

**Coverage Rules (MANDATORY):**

| UC Element        | Min Test Cases | Severity Default |
| ----------------- | -------------- | ---------------- |
| Main Flow (happy) | 1 per flow     | CRITICAL         |
| Alt Flow (error)  | 1 per alt flow | HIGH             |
| Business Rule     | 1-2 per BR     | HIGH / MEDIUM    |
| NFR (performance) | 1 per NFR      | MEDIUM           |
| Boundary values   | 2 per field    | MEDIUM           |
| Security checks   | 1--2 per UC    | HIGH             |

**Test Derivation Methodology:**
- Each Main Flow step → 1 happy path TC (CRITICAL)
- Each Alt Flow → 1 error/edge case TC (HIGH)
- Each Business Rule → 1-2 validation TCs
- Each NFR → 1 performance/security TC
- Apply boundary value analysis to every input field (min, max, over-max)
- Apply equivalence partitioning to enum/select fields

### Step 5 — Write Output File

**File location:**
```
PM_REVIEW/{PLATFORM_FOLDER}/TESTING/{MODULE}/{FUNCTION}_testcases.md
```

Where:
- `{PLATFORM_FOLDER}` = `REVIEW_ADMIN` or `REVIEW_MOBILE`
- `{MODULE}` = Module name (AUTH, DEVICES, MONITORING, etc.)
- `{FUNCTION}` = Function name (LOGIN, REGISTER, LIST, etc.)

If platform = BOTH → generate **two separate files** (one per platform folder).

---

## Phase 2: EXECUTE — Test Execution & Tracking

### Step 1 — Load Test File & Validate Materials

1. Read the existing test case file from `TESTING/{MODULE}/{FUNCTION}_testcases.md`
2. **Check Test Data section** — if any `⬜ PENDING` materials exist → **ASK the user** to provide values before proceeding
3. Parse all test case rows
4. Identify test cases with Status = `NOT_RUN` or `FAIL` (for re-test)
5. Classify each TC into test layer (L1/L2/L3) based on Steps column

### Step 2 — Execute Tests

**L1 (API tests):** Read `references/be-test-execution.md` for curl patterns.
**L2 (UI smoke):** Read `references/fe-test-execution.md` for browser patterns.
**L3 (Manual):** Mark as `SKIP` with Actual = "Requires manual testing — {reason}".

For each test case:

1. Follow the Steps column exactly
2. Compare actual result with Expected column
3. Record:

| Field    | Value                                |
| -------- | ------------------------------------ |
| Status   | `PASS` / `FAIL` / `BLOCKED` / `SKIP` |
| Actual   | Describe what actually happened      |
| Tester   | `AI_AGENT` or user-specified name    |
| DateTime | ISO 8601: `YYYY-MM-DD HH:MM` (local) |

### Step 3 — Update File

Read `references/execution-tracker.md` for the detailed update protocol.

Key actions:
1. Update each test case row in-place (Status, Actual, Tester, DateTime)
2. Append **Execution Log** section at file bottom
3. Update **Summary** counts (PASS/FAIL/BLOCKED/SKIP/NOT_RUN)

---

## Phase 3: TEST_PLAN — Test Plan Generation

Read `references/test-plan-protocol.md` for the complete output format and generation steps.

### Quick Steps

1. **Scan** all test case files in `TESTING/{MODULE}/`
2. **Inventory** each file: function, TC count, status, severity breakdown
3. **Determine execution order**: dependencies first (e.g., login before CRUD)
4. **Assign layers**: for each TC → L1 (API), L2 (UI), or L3 (Manual)
5. **Estimate duration**: L1 ~15s/TC, L2 ~45s/TC, L3 = manual
6. **Write plan** to `TESTING/{MODULE}/{MODULE}_test_plan.md`

---

## Examples

### Example 1: GENERATE Mode — User requests login test cases

**User:** "Sinh test case cho chức năng LOGIN admin"

**AI Actions:**
1. Load MASTER_INDEX → find AUTH module, UC001, Platform=ADMIN
2. Load SRS_INDEX → system context
3. Read UC001.md → extract main flow (login), alt flows (wrong password, locked account, etc.), BRs, NFRs
4. Read SQL `02_create_tables_user_management.sql` → users table constraints
5. Read `backend/src/controllers/authController.ts` → login endpoint, validators
6. Generate test data table with `⬜ PENDING` for real credentials
7. Generate 20+ test cases grouped by: Happy Path, Alt Flows, Validation, Security, Edge Cases
8. Write to `PM_REVIEW/REVIEW_ADMIN/TESTING/AUTH/LOGIN_testcases.md`

**Output snippet (3 of 22 TCs):**

| ID                | UC    | Platform | Severity | Title                                | Steps                                                         | Expected                                                            |
| ----------------- | ----- | -------- | -------- | ------------------------------------ | ------------------------------------------------------------- | ------------------------------------------------------------------- |
| TC-UC01-ADMIN-001 | UC001 | ADMIN    | CRITICAL | Valid login with correct credentials | 1. POST `/api/auth/sessions` with valid email+password        | HTTP 200, JWT with `iss=healthguard-admin`, `last_login_at` updated |
| TC-UC01-ADMIN-020 | UC001 | ADMIN    | HIGH     | Login fails — wrong password         | 1. POST `/api/auth/sessions` with valid email, wrong password | HTTP 401, error code `INVALID_CREDENTIALS`                          |
| TC-UC01-ADMIN-070 | UC001 | ADMIN    | HIGH     | SQL Injection in email field         | 1. POST `/api/auth/sessions` with email=`' OR '1'='1`         | No injection, returns 400/401, Prisma parameterized query           |

---

### Example 2: EXECUTE Mode — AI runs API tests

**User:** "Thực hiện test LOGIN admin theo file testcases"

**AI Actions:**
1. Read `TESTING/AUTH/LOGIN_testcases.md`
2. Check Test Data → `⬜ PENDING` on admin email/password → ASK user
3. User provides: email=`admin@siu.edu.vn`, password=`Admin123!`
4. Classify TCs: TC-001~002 = L1 (API), TC-003 = L2 (UI), TC-080 = L1
5. Execute L1 via curl:
   ```bash
   curl -s -w "\n%{http_code}" -X POST http://localhost:5000/api/auth/sessions \
     -H "Content-Type: application/json" \
     -d '{"email":"admin@siu.edu.vn","password":"Admin123!"}'
   ```
6. Check response: HTTP 200, JSON has `token` → PASS
7. Execute L2 via `browser_subagent`: navigate /login, fill form, click Login, verify /dashboard
8. Update file: Status=PASS, Actual="HTTP 200, JWT issued", Tester=AI_AGENT, DateTime=2026-03-06 14:30
9. Append Execution Log with session summary

---

### Example 3: TEST_PLAN Mode — Generate execution plan

**User:** "Tạo test plan cho module AUTH admin"

**AI Actions:**
1. List files in `TESTING/AUTH/`: LOGIN, REGISTER, FORGOT_PASSWORD, CHANGE_PASSWORD
2. Count: 4 files, ~80 TCs total
3. Execution order: LOGIN(1st, no deps) → REGISTER(2nd, needs token) → FORGOT/CHANGE PASSWORD
4. Layer breakdown: ~50 L1 (API), ~15 L2 (UI smoke), ~15 L3 (manual)
5. Write `AUTH_test_plan.md` with env setup, execution order, tool mapping

---

## Output Protocol (MANDATORY)

| Rule                 | Detail                                                                |
| -------------------- | --------------------------------------------------------------------- |
| **Format**           | Markdown table — read `references/testcase-template.md`               |
| **Language**         | English for all fields (AI-optimized parsing)                         |
| **ID Format**        | `TC-UC{XX}-{PLATFORM}-{NNN}` — read `references/naming-convention.md` |
| **File Naming**      | `{FUNCTION}_testcases.md` or `{MODULE}_test_plan.md`                  |
| **Folder**           | `{REVIEW_ADMIN\|REVIEW_MOBILE}/TESTING/{MODULE}/`                     |
| **Overwrite**        | If file exists in GENERATE mode → ask user before overwrite           |
| **Execution Update** | In EXECUTE mode → update in-place, never create a new file            |

---

## Reference Documents

| Name               | Path                               | When to Read              |
| ------------------ | ---------------------------------- | ------------------------- |
| **MASTER INDEX**   | `PM_REVIEW/MASTER_INDEX.md`        | **ALWAYS**                |
| **SRS Index**      | `PM_REVIEW/Resources/SRS_INDEX.md` | **ALWAYS**                |
| UC Files           | `PM_REVIEW/Resources/UC/{Module}/` | GENERATE — target UC only |
| SQL README         | `PM_REVIEW/SQL SCRIPTS/README.md`  | GENERATE — schema lookup  |
| SQL Files          | `PM_REVIEW/SQL SCRIPTS/0{N}_*.sql` | GENERATE — detail only    |
| Test Case Template | `references/testcase-template.md`  | GENERATE — output format  |
| Naming Convention  | `references/naming-convention.md`  | GENERATE — ID/file names  |
| Test Plan Protocol | `references/test-plan-protocol.md` | TEST_PLAN — plan format   |
| BE Test Execution  | `references/be-test-execution.md`  | EXECUTE — L1 API patterns |
| FE Test Execution  | `references/fe-test-execution.md`  | EXECUTE — L2 UI patterns  |
| Execution Tracker  | `references/execution-tracker.md`  | EXECUTE — update protocol |
| Context Loading    | `references/context-loading.md`    | GENERATE — source loading |

---

## Constraints

- **Read UC BEFORE generating** — never generate test cases from assumptions
- **One function per file** — do not combine multiple functions in one test case file
- **English only** — all test case content in English for AI parsing
- **Cover all UC flows** — main flow + every alt flow must have at least one test case
- **Include boundary values** — for every input field, include min/max/invalid tests
- **Security test cases** — every auth-related UC must have security tests (SQL injection, XSS, token expiry)
- **Timestamp precision** — always use `YYYY-MM-DD HH:MM` format with local timezone
- **Never skip NOT_RUN** — in EXECUTE mode, attempt every NOT_RUN test case (except L3)
- **Progressive context** — read source files progressively, not all at once
- **Overwrite protection** — in GENERATE mode, confirm with user before overwriting existing files
- **L3 = Manual only** — never attempt performance, visual regression, or long-session tests automatically
- **Token chain** — when tests require authentication, login first and reuse JWT for subsequent tests
