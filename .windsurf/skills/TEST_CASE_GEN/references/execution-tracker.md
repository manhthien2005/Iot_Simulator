# Execution Tracker Protocol

> Reference document for `TEST_CASE_GEN` skill — EXECUTE mode.
> Defines how to run tests, update results, and track execution history.

---

## Pre-Execution Checklist

Before executing any test case:

1. ✅ Test case file exists and is parseable
2. ✅ Application under test is running and accessible
3. ✅ Test environment matches preconditions (DB seeded, user accounts exist)
4. ✅ Current local date/time is known (for timestamps)

---

## Execution Process

### Per Test Case

```
FOR each test_case WHERE Status = NOT_RUN or FAIL:
  1. READ Preconditions → verify environment state
  2. EXECUTE Steps sequentially (1, 2, 3...)
  3. COMPARE actual outcome with Expected column
  4. DETERMINE Status:
     - PASS  → actual matches expected
     - FAIL  → actual differs from expected
     - BLOCKED → cannot execute (dependency missing, env issue)
     - SKIP  → intentionally skipped (user request or not applicable)
  5. UPDATE row: Actual, Status, Tester, DateTime
```

### Status Decision Matrix

| Condition                               | Status    |
| --------------------------------------- | --------- |
| Actual result matches Expected exactly  | `PASS`    |
| Actual result partially matches         | `FAIL`    |
| Actual result completely wrong          | `FAIL`    |
| Cannot reach test page / endpoint down  | `BLOCKED` |
| Missing test data / account not created | `BLOCKED` |
| User explicitly says "skip this"        | `SKIP`    |
| Test not relevant on current platform   | `SKIP`    |

---

## Row Update Format

When updating a test case row, modify ONLY these 4 columns:

| Column       | Before    | After                                 |
| ------------ | --------- | ------------------------------------- |
| **Actual**   | `—`       | Description of what actually happened |
| **Status**   | `NOT_RUN` | `PASS` / `FAIL` / `BLOCKED` / `SKIP`  |
| **Tester**   | `—`       | `AI_AGENT` or specified name          |
| **DateTime** | `—`       | `YYYY-MM-DD HH:MM` (local time)       |

### Example Before

```markdown
| TC-UC01-ADMIN-001 | UC001 | ADMIN | CRITICAL | Valid login | ... | ... | Redirect to dashboard | — | NOT_RUN | — | — |
```

### Example After

```markdown
| TC-UC01-ADMIN-001 | UC001 | ADMIN | CRITICAL | Valid login | ... | ... | Redirect to dashboard | Redirected to /dashboard, JWT stored in localStorage | PASS | AI_AGENT | 2026-03-05 08:30 |
```

---

## Re-Test Protocol

When re-running a previously executed test case:

1. **Keep old result** — do NOT delete the previous Actual/Status
2. **Overwrite** the row with new results (latest execution wins)
3. **Log previous result** in the Execution Log section as a note

For regression tracking:
```markdown
#### Re-tested Cases
- `TC-UC01-ADMIN-003`: Previously FAIL (2026-03-04) → now PASS (2026-03-05)
```

---

## Execution Log Format

After completing all test cases in a session, APPEND this section at the bottom of the file.

If an Execution Log section already exists, **append a new session** below the existing ones (do not overwrite history).

```markdown
---

## Execution Log

### Session: {YYYY-MM-DD HH:MM}

| Metric        | Value  |
| ------------- | ------ |
| **Total**     | {N}    |
| **Executed**  | {N}    |
| **PASS**      | {N}    |
| **FAIL**      | {N}    |
| **BLOCKED**   | {N}    |
| **SKIP**      | {N}    |
| **NOT_RUN**   | {N}    |
| **Pass Rate** | {NN}%  |
| **Tester**    | {Name} |
| **Duration**  | ~{N}m  |

#### Failed Tests
- `{TC_ID}`: {brief failure reason}

#### Blocked Tests
- `{TC_ID}`: {reason blocked}

#### Re-tested Cases
- `{TC_ID}`: Previously {OLD_STATUS} ({OLD_DATE}) → now {NEW_STATUS}

#### Notes
- {Environmental issues, observations, follow-up actions}
```

### Pass Rate Calculation

```
Pass Rate = (PASS count / (Total - SKIP - BLOCKED)) × 100
```

Only count executable test cases in the denominator.

---

## File Status Update

After execution, update the file header `Status` field:

| Condition                        | File Status   |
| -------------------------------- | ------------- |
| All tests PASS                   | `DONE`        |
| Some tests FAIL                  | `IN_PROGRESS` |
| All tests executed, some BLOCKED | `IN_PROGRESS` |
| Mix of NOT_RUN and executed      | `IN_PROGRESS` |
| No tests executed yet            | `READY`       |
