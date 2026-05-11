---
description: Systematic debugging — root cause investigation required before any fix, following 4 phases. Anti-loop integration with bug log.
---

# /debug — Systematic Debugging (VSmartwatch)

> "Fix root causes, not symptoms."

Use when you hit:
- A test failure (CI or local).
- A bug from user report / log / runtime error.
- Strange behaviour (intermittent, "works on my machine").
- Build / lint failure you don't understand.

## Pre-flight

1. **→ Invoke skill `systematic-debugging`** — full 4-phase process + iron law + red flags.
2. **STOP** — do NOT propose a fix before Phase 1 of the skill is done.
3. **Anti-loop check** — read prior attempts:
   ```pwsh
   $bug = "d:\DoAn2\VSmartwatch\PM_REVIEW\BUGS\<BUG-ID>.md"
   if (Test-Path $bug) {
     Get-Content $bug
     Write-Host "DO NOT propose any approach marked 'failed' above"
   }
   ```
   If only failed approaches remain → switch to `/stuck` workflow.
4. **Branch** (per rule 20-stack-conventions.md): `fix/<short-desc>` from correct trunk:
   - HealthGuard, health_system, Iot_Simulator_clean → `develop`
   - healthguard-model-api → `master`
   - PM_REVIEW → `main`

## Workflow on top of the skill

Skill walks Phases 1-4 (root cause → pattern → hypothesis → fix). This workflow adds VSmartwatch-specific entry points + commit/handoff steps.

### Quick commands per stack

```pwsh
# === Flutter (health_system/lib) ===
# cwd: d:\DoAn2\VSmartwatch\health_system
flutter test test/features/<area>/<file>_test.dart --reporter=expanded
flutter analyze
adb logcat | Select-String -Pattern "(HealthGuard|FATAL|ERROR)"  # mobile runtime

# === FastAPI (Python BE) ===
# cwd: d:\DoAn2\VSmartwatch\<repo>
pytest tests/<file>::<test> -xvs   # stop on first fail, verbose, no capture
# Live log:
uvicorn app.main:app --reload --log-level debug

# === Express+Prisma (HealthGuard/backend) ===
# cwd: d:\DoAn2\VSmartwatch\HealthGuard\backend
npm test -- <file>.test.js --verbose
DEBUG=prisma:* npm run dev   # see all Prisma queries

# === React+Vite (HealthGuard/frontend) ===
# cwd: d:\DoAn2\VSmartwatch\HealthGuard\frontend
npm test -- <component>.test.jsx --reporter=verbose

# === Recent changes (any repo) ===
git -C <repo> log -n 10 --oneline
git -C <repo> diff HEAD~5 -- <suspect file>

# === Boundary diagnosis (multi-layer) ===
# Add temp log at each boundary, run once to see WHICH layer fails.
# Mobile (Dart):     developer.log('[DEBUG] FallNotifier.cancel id=$id');
# FastAPI (Python):  logger.debug("[DEBUG] FallService.predict req=%s", req)
# Express (JS):      logger.debug({ deviceId }, '[DEBUG] deviceService.create');
```

**Remove debug logs before commit** — grep:
```pwsh
# Flutter
Get-ChildItem -Recurse -Filter '*.dart' lib | Select-String '\[DEBUG\]'
# FastAPI
Get-ChildItem -Recurse -Filter '*.py' app | Select-String '\[DEBUG\]'
# Express/React
Get-ChildItem -Recurse -Filter '*.js' src | Select-String '\[DEBUG\]'
```

### VSmartwatch-specific debugging entry points

| Symptom | First check | Repo / Layer |
|---|---|---|
| Flutter widget doesn't rebuild | Trace `build` → state → notifier → repo. Provider `watch` vs `read`? | health_system/lib |
| `setState() called after dispose` | `mounted` guard after `await`; dispose Timer/Subscription | health_system/lib |
| Mobile API call returns 401 in loop | dio refresh interceptor + token storage → check `iss` claim mismatch | health_system/lib |
| FCM not received foreground | `FirebaseMessaging.onMessage.listen` registered? | health_system/lib |
| FCM not received background | iOS: critical alert entitlement; Android: notification channel ID + full-screen intent | health_system/lib |
| Fall alert dialog không hiện | Background → store deep link, navigate on resume; full-screen intent permission Android 14+ | health_system/lib |
| FastAPI 500 reveals stack trace | Exception handler `app/main.py` returns generic message; log details internally | health_system/backend, model-api |
| FastAPI endpoint timeout | Sync I/O trong async function (use `asyncio.to_thread`) | All FastAPI repos |
| Pydantic validation error confusing | Use `model_config = ConfigDict(extra="forbid")` to surface unknown fields early | All FastAPI repos |
| Postgres query slow | `EXPLAIN ANALYZE` + check Prisma `select` for over-fetch + check missing index | HealthGuard/backend, health_system/backend |
| Prisma `P2002` (unique constraint) | Map in `errorHandler` middleware; surface as 409 ConflictError | HealthGuard/backend |
| Prisma `P2025` (record not found) | Map in `errorHandler` to 404 NotFoundError | HealthGuard/backend |
| Socket.IO no events | JWT verify in handshake middleware; room join after auth | HealthGuard/backend + frontend |
| React component re-renders excessively | Check inline anonymous function in JSX; missing `useMemo` for expensive compute | HealthGuard/frontend |
| Vite build fails (works in dev) | `import.meta.env.VITE_*` only — non-VITE prefix not exposed in build | HealthGuard/frontend |
| Cross-repo API contract mismatch | `topology.md` + producer Pydantic schema vs consumer dio call | multiple |
| Auth `iss` mismatch | `healthguard-mobile` vs `healthguard-admin` — check JWT generator + verifier | All BE |
| ML predict 500 | Model file path in env; fallback when model load fails; check `prediction_contract.py` version | healthguard-model-api |
| IoT trigger không tới backend | Internal secret header + endpoint URL in `transport/http_publisher.py` | Iot_Simulator_clean |
| Flaky test | DO NOT retry. Find race condition / shared state / missing await / time dependency | Any |

### Phase 4 → write a regression test

**→ Apply skill `tdd`** "Bug fix" section: failing test reproduces → fix → verify red-green-red cycle (revert fix → test FAILs → restore → test PASSES).

Without that revert step, the test might pass for the wrong reason.

## Phase 5 — Commit + document

```pwsh
git -C <repo> add <files>
git -C <repo> commit -m "fix(<scope>): <mô tả tiếng Việt>

Root cause: <gốc vấn đề ngắn gọn>
Fix: <approach>
Test: regression test trong <test file>
Bug log: PM_REVIEW/BUGS/<BUG-ID>.md (nếu có)"
```

If non-trivial bug → update `PM_REVIEW/BUGS/<BUG-ID>.md` (skill `bug-log`):
- Mark current attempt `successful` with link to fix commit.
- Note: how to verify, what to monitor for regression.

## When the fix doesn't work

| Attempt count | Action |
|---|---|
| < 3 | Back to Phase 1 of the skill with new info. Update bug log: mark previous attempt `failed` + reason. |
| ≥ 3 | **STOP. Architecture might be wrong.** Switch to `/stuck` workflow. Bug log shows clearly we're looping. |

## When you're truly stuck

→ `/stuck` workflow — forces re-evaluation:
- Read entire bug log to map all attempted approaches.
- Step back: is this the right bug to fix? (Maybe symptom of upstream bug)
- Discuss with user before attempt #4.

## Output

- ✅ Root cause documented in commit message.
- ✅ Regression test alongside fix (red-green-red cycle verified).
- ✅ Bug verified gone (actual repro step no longer fails — not just green test).
- ✅ No "while I'm here" cleanup outside fix.
- ✅ Bug log updated (if non-trivial bug).
