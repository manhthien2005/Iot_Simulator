# Test Plan Protocol

> Reference document for `TEST_CASE_GEN` skill — **Mode C: TEST_PLAN**.
> Defines the format and generation rules for AI-executable test plans.

---

## When to Generate

User says: "Tạo test plan cho module {MODULE}" or "create test plan for {MODULE}" or similar.

---

## Test Plan Output Format

```markdown
# Test Plan: {MODULE} — {PLATFORM}

| Property       | Value                       |
| -------------- | --------------------------- |
| **Module**     | {MODULE_NAME}               |
| **Platform**   | ADMIN / MOBILE              |
| **Scope**      | {list of functions covered} |
| **Test Files** | {count} files, {count} TCs  |
| **Created**    | YYYY-MM-DD                  |
| **Author**     | AI_AGENT                    |

## Environment Setup

### Prerequisites
- [ ] Backend running at `{BE_URL}` (default: http://localhost:5000)
- [ ] Frontend running at `{FE_URL}` (default: http://localhost:5173)
- [ ] Database accessible and seeded with test data
- [ ] All `⬜ PENDING` materials filled in test case files

### Start Commands
| Service  | Command                             | Expected         |
| -------- | ----------------------------------- | ---------------- |
| Backend  | `cd backend && npm run dev`         | "Server on 5000" |
| Frontend | `cd frontend && npm run dev`        | "ready on 5173"  |
| DB Seed  | `npx prisma db seed` (if available) | Seed complete    |

## Execution Order

> Execute in this order. Dependencies flow top-down.

| #   | Test File               | Layer | Tool           | Depends On | Est. Time |
| --- | ----------------------- | ----- | -------------- | ---------- | --------- |
| 1   | AUTH/LOGIN_testcases.md | L1+L2 | curl + browser | —          | ~5m       |
| 2   | AUTH/REGISTER_...       | L1    | curl           | #1 (token) | ~5m       |
| ... |

## Test Layers

| Layer | Name        | Tool                 | What It Tests                        |
| ----- | ----------- | -------------------- | ------------------------------------ |
| L1    | API Tests   | `run_command` + curl | HTTP status, response JSON, DB state |
| L2    | UI Smoke    | `browser_subagent`   | Form submit, redirect, visual        |
| L3    | Manual Flag | Human tester         | Performance, visual regression       |

## Execution Instructions

### L1: API Tests (via curl)
Read `references/be-test-execution.md` for detailed curl patterns.

### L2: UI Smoke Tests (via browser)
Read `references/fe-test-execution.md` for browser_subagent patterns.

### L3: Manual Required
Test cases marked `MANUAL_REQUIRED` in Status column — skip during AI execution.
Log as `SKIP` with note: "Requires manual testing".

## Post-Execution

1. Update each test case file with results (per execution-tracker.md)
2. Generate summary below:

### Execution Summary
| Metric          | Value                            |
| --------------- | -------------------------------- |
| **Total TCs**   | {N}                              |
| **L1 (API)**    | {N} executed, {N} pass, {N} fail |
| **L2 (UI)**     | {N} executed, {N} pass, {N} fail |
| **L3 (Manual)** | {N} skipped                      |
| **Pass Rate**   | {NN}% (excluding L3)             |
| **Duration**    | ~{N}m                            |

### Issues Found
- {TC_ID}: {description}

### Recommendations
- {Follow-up actions}
```

---

## Generation Steps

### Step 1 — Scan Existing Test Case Files

```
1. List all files in TESTING/{MODULE}/
2. For each file: read header → extract function, TC count, status
3. Build inventory table
```

### Step 2 — Determine Execution Order

```
1. Identify dependencies (login must come before CRUD)
2. Order: auth → read → write → delete
3. Within each file: CRITICAL → HIGH → MEDIUM → LOW
```

### Step 3 — Assign Test Layers

For each test case, assign layer based on:

| Test Characteristic                | Layer |
| ---------------------------------- | ----- |
| API endpoint call + response check | L1    |
| Form interaction + page navigation | L2    |
| Performance, load, visual          | L3    |
| API + UI verification combined     | L1+L2 |

**Decision rules:**
- Test has `POST/GET/PUT/DELETE {URL}` in steps → **L1**
- Test has `Navigate to`, `Click`, `Enter in field` → **L2**
- Test has `response time`, `concurrent`, `visual` → **L3**
- Test has both API call AND UI verification → **L1+L2** (run API first, then verify UI)

### Step 4 — Estimate Duration

| Layer | Per TC Estimate |
| ----- | --------------- |
| L1    | ~15 seconds     |
| L2    | ~45 seconds     |
| L3    | N/A (manual)    |

### Step 5 — Write Output

**File location:**
```
PM_REVIEW/{PLATFORM_FOLDER}/TESTING/{MODULE}/{MODULE}_test_plan.md
```

**Example:**
```
PM_REVIEW/REVIEW_ADMIN/TESTING/AUTH/AUTH_test_plan.md
```

---

## Rules

- **One plan per module per platform** — do not combine modules
- **Always check test case files exist** before generating plan
- **If no test case files exist** → tell user to run GENERATE mode first
- **Update plan** when new test case files are added to the module
- **L3 tests are NEVER auto-executed** — always flagged for human
