---
description: Self-review code before merging — 5 axes (correctness, readability, architecture, security, performance).
---

# /review — Five-Axis Code Review

> "15 minutes of self-review saves 30 minutes of debugging + 2 hours of rollback."

Workflow for reviewing already-written code (your own commit / branch / PR) before merge.

> ⚠️ **Thứ tự bắt buộc:** `/build` (implement + commit) → `/review` (self-review) → push + PR (nếu cần). KHÔNG mở PR trước khi `/review` sạch.

## Pre-flight

1. **→ Invoke skill `code-review-five-axis`** — full 5-axis framework + checklist + severity levels + output format.
2. **Identify scope** of the review:
   - Self-review: `git diff develop...HEAD` or `git diff <base-sha>...HEAD`
   - PR review: clone the branch, read the full diff.

## Phase 1 — Read context

1. **Spec/UC** — `<repo>/docs/specs/<feature>.md` + `PM_REVIEW/Resources/UC/<Module>/UC<XXX>.md`. Does code match acceptance criteria?
2. **Commit messages** — what did the author (you) intend?
3. **Diff overview** (replace `<trunk>` per repo: deploy/develop/master/main):
   ```pwsh
   git -C <repo> diff <trunk>...HEAD --stat
   git -C <repo> log <trunk>..HEAD --oneline
   ```
4. **Map changed files** to layers (per stack):
   - Flutter: `data/` (repos, models) / `domain/` / `presentation/` (screens, providers)
   - FastAPI: `routers/` / `services/` / `repositories/` / `models/`
   - Express: `routes/` / `controllers/` / `services/` / `lib/`
   - React: `pages/` / `features/` / `hooks/` / `components/`

## Phase 2 — Run automated checks

Let the machine do the easy part FIRST. Any warning/error → flag and pause detailed review.

```pwsh
# Flutter (health_system/lib)
cd d:\DoAn2\VSmartwatch\health_system
flutter analyze
flutter test
dart format --set-exit-if-changed .

# FastAPI (health_system/backend, healthguard-model-api, Iot_Simulator_clean)
cd d:\DoAn2\VSmartwatch\<repo>
pytest
black --check . ; isort --check-only .
mypy app/   # if configured

# Express+Prisma (HealthGuard/backend)
cd d:\DoAn2\VSmartwatch\HealthGuard\backend
npm test
npm run lint

# React+Vite (HealthGuard/frontend)
cd d:\DoAn2\VSmartwatch\HealthGuard\frontend
npm test
npm run lint
```

## Phase 3 — Manual 5-axis pass

**→ Apply skill `code-review-five-axis`** for the 5 axes (Correctness / Readability / Architecture / Security / Performance), full checklist per axis, severity rubric, and output format. Don't re-derive the checklist here.

### VSmartwatch-specific things to flag (in addition to skill checklist)

**Cross-cutting (any stack):**
- **PHI in logs:** grep `email`, `phone`, `bloodPressure`, `heartRate`, `vital` in `console.log` / `logger.*` / `print()` → flag (medical app, leak = serious).
- **Hardcoded secret:** `grep -rnE "(api[_-]?key|secret|token|password)\s*=\s*['\"]" <changed file>` → flag.
- **Cross-repo contract change:** if API request/response shape changed, check `topology.md` for downstream consumer. Update prediction_contract.py / repository signature accordingly.
- **Audit log missing:** PHI access (read/write user vital, fall event, sleep data) MUST log to audit table per `PM_REVIEW/Audit_Log_Specification.md`.

**Mobile (Flutter):**
- `setState()` after `await` without `mounted` check → race crash.
- `dispose()` thiếu cho `Timer`/`StreamSubscription`/`Controller` → memory leak.
- `Dio()` constructor inline trong screen → bypass JWT interceptor.
- Hardcoded color/string → use theme token + `app_strings.dart`.
- FCM background handler navigate ngay → store deep link, navigate on resume.
- Touch target < 48dp (or < 56dp for emergency UI) → fail accessibility.

**FastAPI:**
- `except Exception:` không log + không re-raise.
- `str(exc)` leaked to client response → security risk.
- Sync I/O trong async function (use `asyncio.to_thread`).
- Pydantic v1 syntax (`@validator`, `class Config`) — must be v2.
- CORS `["*"]` in production config.
- Endpoint thiếu auth dependency.

**Express+Prisma:**
- `new PrismaClient()` outside `lib/prisma.js` singleton.
- SQL string concat (always Prisma parameterized).
- `app.use(cors())` không có origin allowlist (production).
- `io.emit` broadcast tất cả socket (use room-based).
- Pre-signed S3 URL bypassed (proxy file qua backend = memory bloat).
- Stack trace in 500 response.

**React+Vite:**
- `dangerouslySetInnerHTML` với user input → XSS.
- `localStorage` lưu JWT (use httpOnly cookie hoặc memory store).
- Inline anonymous function in list render → unnecessary re-render.
- Missing `key` or `key={index}` for reorderable list.
- Direct DOM manipulation (`getElementById`) trừ khi thật cần.

**Naming:** check diff dùng đúng VSmartwatch canonical terms — `User` role với linked profiles (NOT deprecated `patient`/`caregiver`), `fall_events` (snake_case table), `User Linked` for family share.

## Phase 4 — Output

Use the format from skill `code-review-five-axis` (🔴 Critical / 🟡 Important / 🟢 Suggestion / ✅ Highlights + Summary).

## Phase 5 — Action

- 🔴 or 🟡 → return to `/build` or `/fix-issue`. After fix → re-review the delta only.
- All clean → merge / approve.

## Quick checklist before commit (mini-review for small commits)

For each routine commit, no need for full 5-axis pass — just verify:

- [ ] Tests pass (ran the command, read the output).
- [ ] Lint clean (`flutter analyze` / `npm run lint` exit 0).
- [ ] Diff focused — only changes for this task.
- [ ] No `console.log` / `print` debug left over.
- [ ] No commented-out dead code.
- [ ] No `// TODO` without a linked issue.
- [ ] Commit message conventional + describes **why** for non-obvious changes.

## Anti-patterns

| Anti-pattern | Problem |
|---|---|
| "Looks good to me" without reading | Rubber-stamp catches no bugs |
| Bikeshedding naming when there's an unresolved 🔴 | Loses focus |
| Suggesting whole-module rewrite in a small PR | Scope creep |
| Blocking PR over style preference (`if` vs ternary) | Religious, not shipping |
| Reviewing only syntax | Skips security, perf, architecture |
