---
description: Fix a specific issue (link/description/Crashlytics report) end-to-end — analyze, plan minimal fix, implement, test.
---

# /fix-issue — Targeted Issue Resolution

End-to-end fix for a specific issue: bug report, Logcat/console error, user complaint, JIRA bug story, or a clear bug with reproduction steps.

> **Anti-loop rule:** if `PM_REVIEW/BUGS/<BUG-ID>.md` exists, READ ALL prior attempts FIRST. Don't propose any approach already marked `failed`. If only failed approaches remain → `/stuck` workflow.

## Pre-flight

1. **Invoke skills:** `systematic-debugging` (primary), `tdd`, `karpathy-guidelines`, `bug-log` (if recurring/non-trivial bug).
2. **Get issue details:**
   - Link / ID / description of the issue (JIRA bug story, free-form).
   - Repro steps (who actor? doing what? expected vs actual?).
   - Stack trace / error log if available.
   - Affected repo + version + platform.
3. **Check bug log** (anti-loop):
   ```pwsh
   $bug = "d:\DoAn2\VSmartwatch\PM_REVIEW\BUGS\<BUG-ID>.md"
   if (Test-Path $bug) { Get-Content $bug }
   ```
   If exists → list prior failed approaches. DO NOT retry them.
   If non-trivial bug + no log → create one (skill `bug-log`).
4. **New branch** from correct trunk (deploy/develop/master/main per repo):
   ```pwsh
   git -C <repo> checkout <trunk>
   git -C <repo> pull origin <trunk>
   git -C <repo> checkout -b fix/<short-description>
   ```

## Step 1: Understand the issue

### 1.1 Read carefully

- Read the full issue description, comments, related issues.
- Read the error message / stack trace line by line.
- Identify affected component(s): UI? data layer? rule? Function?

### 1.2 Reproduce locally

- Have you reproduced the issue on your machine?
- If you can't reproduce → gather more info before attempting a fix:
  - User device model, OS version.
  - Account state (logged in? friend list?).
  - Network conditions.
  - App version, build flavor.

**DO NOT fix** an issue you can't reproduce, unless:
- Stack trace + logs clearly identify the root cause.
- The user has verified reproduction and confirmed.

## Step 2: Root cause analysis

**→ Apply skill `systematic-debugging`** Phases 1-3 (read errors carefully → reproduce → check recent changes → trace data flow → form hypothesis).

VSmartwatch entry points (which layer to suspect first):

```pwsh
git -C <repo> log -n 20 --oneline -- <affected files>
git -C <repo> blame <file> | Select-String <line>
```

| Symptom | First check | Repo |
|---|---|---|
| Mobile: `setState() after dispose` | `mounted` guard after `await`, dispose Timer/Subscription | health_system/lib |
| Mobile: API call returns 401 loop | dio refresh interceptor + token storage | health_system/lib |
| Mobile: FCM not delivered | Token registration → server payload → fg/bg handler | health_system/lib + backend |
| Mobile: Fall alert không hiển thị | Full-screen intent permission (Android) + critical alert (iOS) | health_system/lib |
| BE: Endpoint 500 lộ stack trace | Exception handler in `app/main.py` (FastAPI) or `errorHandler` middleware (Express) | health_system/backend, HealthGuard/backend |
| BE: Postgres query slow | Missing index → run `EXPLAIN ANALYZE`; check Prisma `select` for over-fetching | HealthGuard/backend, health_system/backend |
| BE: SQL constraint violation in test | Prisma `P2002` mapping not handled in errorHandler | HealthGuard/backend |
| Cross-repo: API contract mismatch | `topology.md` + check producer Pydantic schema vs consumer dio call | multiple |
| Auth: token expired loop | Refresh handler boundary; check `iss` claim matches (`healthguard-mobile` vs `healthguard-admin`) | All |
| ML: Model API 500 | Check model file path in env, fallback when model load fails | healthguard-model-api |
| IoT: Trigger không tới backend | Check internal secret header + endpoint URL in `Iot_Simulator_clean/transport/http_publisher.py` | Iot_Simulator_clean |

## Step 3: Plan a minimal fix

**Karpathy guideline: surgical changes.**

- Identify the **minimal change** to address the root cause.
- DON'T bundle:
  - Refactors of unrelated files "while I'm here".
  - "While I'm here" cleanup.
  - Other bug fixes opportunistically.
- Consider side effects: will this fix break old tests / other features?

If small (≤ 20 lines): implement directly.
If big (multi-file, architectural): consider running mini `/spec` or discussing with the user first.

## Step 4: Implement (TDD)

**→ Apply skill `tdd`** "Bug fix → reproduction test" section: write failing test that reproduces → verify FAIL with the right symptom → minimal fix → verify PASS → revert fix → verify FAIL again (proof) → restore → verify PASS → commit.

Name the test `regression: <issue title> (#<id>)` so it's traceable later. Without the revert step (proof the test catches the bug), the test might pass for the wrong reason.

## Step 5: Verify the fix end-to-end

Beyond unit tests:

### Mobile fix (Flutter — health_system/lib)

- Run app on real device (not just emulator if device-specific bug, e.g., FCM/sensor).
- Repro original steps → confirm bug gone.
- Smoke-test related features (e.g., fall fix → also check SOS escalation).

### Backend fix (FastAPI — health_system/backend, model-api, IoT sim)

- Run focused pytest first, then full suite.
- Hit endpoint locally with curl or Postman → assert expected response shape.
- Check log output (no new error patterns, no PHI leaked).
- Test with edge cases from the original report.

### Admin BE fix (Express+Prisma — HealthGuard/backend)

- Run focused jest test, then full suite.
- Hit endpoint with admin JWT → assert response.
- Check Prisma query log (no N+1, no over-fetch).
- Verify audit log entry created if action mutates PHI.

### Admin FE fix (React+Vite — HealthGuard/frontend)

- `npm run dev` → manually click through affected page.
- Repro original UX issue → confirm fixed.
- Check console: no warning, no React render error.
- Smoke-test linked pages (e.g., device list → device detail).

### Apply skill `verification-before-completion`

Don't claim "fixed" until:
- ✅ Unit tests pass.
- ✅ Original reproduction steps → bug gone.
- ✅ Full test suite passes.
- ✅ Lint clean.

## Step 6: Commit

Conventional Commits — Vietnamese subject, English type prefix:

```pwsh
git -C <repo> add <files>
git -C <repo> commit -m "fix(<scope>): <mô tả tiếng Việt>

Root cause: <ngắn — gốc vấn đề>
Fix: <approach>
Test: regression test trong <test file>
Bug log: PM_REVIEW/BUGS/<BUG-ID>.md (nếu đã tạo)"
```

Update bug log: mark this attempt as `successful` with link to fix commit.

## Step 7: PR / merge

### Self-review first

Apply workflow `/review`:

```pwsh
git -C <repo> diff <trunk>...HEAD
# + per-stack lint/test (xem /review workflow)
```

### Open a PR (optional for solo dev)

PR description template (Vietnamese):

```markdown
## Issue
Bug ID: `<BUG-ID>` (xem `PM_REVIEW/BUGS/<BUG-ID>.md`)
JIRA: <Story-ID> (nếu có)
UC: UC<XXX> (nếu có)

## Root cause
<1-2 câu>

## Fix
<approach + tại sao approach này>

## Test
- Regression test: `<test file>::<test name>`
- Manual repro: <bước + kết quả>

## Verification
- [ ] Tests pass (per stack)
- [ ] Lint clean
- [ ] Manual repro confirmed bug gone
- [ ] Smoke-tested related features
- [ ] Bug log updated (`PM_REVIEW/BUGS/<BUG-ID>.md`)
```

## Step 8: Post-merge

- Confirm fix deployed if CI/CD triggered.
- Monitor logs for 24h to spot regressions (mobile: Logcat / iOS Console; BE: stdout/log file).
- Close JIRA bug story if applicable.
- Update `PM_REVIEW/BUGS/<BUG-ID>.md`: status = `resolved`, link to fix commit, note how to verify.

## When the issue isn't a bug

Sometimes "issue" is actually:

- **Feature request in disguise** → push back, suggest creating a spec via `/spec`.
- **User misunderstanding** → reply explaining expected behavior, don't change code.
- **Documentation gap** → fix the doc, don't fix code.

Don't force-fix when it isn't a bug — clarify with the user first.

## Anti-patterns

| Anti-pattern | Problem |
|---|---|
| Fix without reproducing | Might fix the wrong thing |
| Fix multiple issues in one commit | Can't revert granularly |
| Skip the regression test | Bug can recur silently |
| Fix the symptom, not the root cause | Similar issues appear elsewhere |
| "While I'm here" refactor | Hard-to-review diff, scope creep |
| Skip verification, trust the unit test | Might be testing the wrong thing |

## Output

- ✅ Branch `fix/<name>` with clean commits.
- ✅ Regression test guarding against recurrence.
- ✅ Original reproduction steps → bug gone (verified).
- ✅ Issue closed with a link to the fix commit/PR.
