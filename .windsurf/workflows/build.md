---
description: Implement task from plan, TDD cycle per task, commit per increment. Stack-aware (Flutter/FastAPI/Express+Prisma/React+Vite).
---

# /build — Incremental Implementation (VSmartwatch)

> "The simplest thing that could work."

Implement task by task. Each task = one Red-Green-Refactor cycle. Each commit leaves codebase in a working state.

## Pre-flight checklist

### 1. Identify stack + invoke skills

Detect current repo, then load patterns:

| Repo | Stack | Skill to invoke |
|---|---|---|
| `health_system/lib/` | Flutter | `tdd` + `flutter-mobile-patterns` + `karpathy-guidelines` |
| `health_system/backend/` | FastAPI | `tdd` + `fastapi-patterns` + `karpathy-guidelines` |
| `Iot_Simulator_clean/` | FastAPI | `tdd` + `fastapi-patterns` + `karpathy-guidelines` |
| `healthguard-model-api/` | FastAPI | `tdd` + `fastapi-patterns` + `karpathy-guidelines` |
| `HealthGuard/backend/` | Express+Prisma | `tdd` + `express-prisma-patterns` + `karpathy-guidelines` |
| `HealthGuard/frontend/` | React+Vite | `tdd` + `karpathy-guidelines` |
| `PM_REVIEW/` | Docs/SQL | (no code) — just `karpathy-guidelines` |

### 2. Verify task source

- **Plan-driven (recommended for ≥ 3 tasks):** read `docs/plans/<feature>.md` + `tasks/todo-<feature>.md`. Pick the next `- [ ]` task.
- **JIRA Story-driven:** read `PM_REVIEW/Resources/TASK/JIRA/Sprint-N/<EpicCode>/STORIES.md` for the target story. UC reference at `PM_REVIEW/Resources/UC/<Module>/UC<XXX>.md`.
- **Bug fix:** check `PM_REVIEW/BUGS/<BUG-ID>.md` for prior attempts (anti-loop). Skip if file doesn't exist.
- **Single-task ad-hoc:** clarify with user, but proceed if scope ≤ 1 file + 1 test.

### 3. Verify branch (CRITICAL)

```pwsh
git -C <repo> branch --show-current
```

Trunk per repo (NEVER commit directly — per ADR-003):
- HealthGuard, health_system, Iot_Simulator_clean: `develop`
- healthguard-model-api: `master`
- PM_REVIEW: `main`

HealthGuard `deploy` is user-owned release branch — AI never touches it.

If on trunk → STOP. Create branch: `feat/<short-desc>` or `fix/<short-desc>` (English type, kebab-case, ≤ 50 chars).

### 4. Infra-file guard

Before touching ANY of these on a `feat/` or `fix/` branch:
- `.windsurf/`, `.github/`, `docs/adr/`, `scripts/`, `PM_REVIEW/tooling/`

→ STOP. Stash changes. Create `chore/<desc>` from trunk. Commit infra there. Reason: keeps PRs reviewable + history clean (lesson from past mixed-PR pain).

### 5. Pre-existing fix attempts (bug fix only)

If task is bug fix and `PM_REVIEW/BUGS/<BUG-ID>.md` exists:
- Read all prior attempts.
- DO NOT propose any approach already marked `failed`.
- If only failed approaches remain → STOP. Switch to `/stuck` workflow.

## Per-task TDD cycle

**→ Apply skill `tdd`** for the full RED-GREEN-REFACTOR cycle.

Quick command reference:

### Flutter (`health_system/lib/`)

```pwsh
# cwd: d:\DoAn2\VSmartwatch\health_system
flutter test test/features/<area>/<file>_test.dart   # focused (RED + GREEN)
flutter test                                          # full suite (final)
flutter analyze                                       # zero warnings
```

### FastAPI (Python BE repos)

```pwsh
# cwd: d:\DoAn2\VSmartwatch\<repo>
pytest tests/<file>::<test_name>                      # focused
pytest                                                 # full suite
black . ; isort .                                     # format before commit
```

### Express + Prisma (`HealthGuard/backend/`)

```pwsh
# cwd: d:\DoAn2\VSmartwatch\HealthGuard\backend
npm test -- <file>.test.js                            # focused
npm test                                               # full suite
npm run lint                                           # zero errors
```

### React + Vite (`HealthGuard/frontend/`)

```pwsh
# cwd: d:\DoAn2\VSmartwatch\HealthGuard\frontend
npm test -- <component>.test.jsx                      # focused
npm test
npm run lint
```

## Final verify (before claiming done)

**→ Apply skill `verification-before-completion`.** Iron rule: NO completion claim without fresh verification evidence.

Mapping (memorize):

| Claim | Required evidence |
|---|---|
| "Tests pass" | Test command output: 0 fail, exit 0 |
| "Lint clean" | Lint output: 0 error |
| "Bug fixed" | Reproduction test: red → fix → green → revert fix → red → restore → green |
| "Spec met" | Line-by-line checklist vs UC/spec |

## Commit per increment

Conventional Commits + Vietnamese subject (anh's rule):

```
<type>(<scope>): <subject in Vietnamese, no period>

Body: explain WHY (not WHAT — diff already shows what)
```

Examples:

```
feat(fall): thêm full-screen alert khi phát hiện ngã
fix(sos): countdown reset khi user nhấn cancel
refactor(risk): tách model loading ra service riêng
test(auth): bổ sung regression test cho lockout sau 5 lần fail
```

Pre-commit checklist:

```pwsh
git -C <repo> branch --show-current          # confirm not trunk
git -C <repo> diff --name-only --cached      # scan staged files
# If any path under .windsurf/, .github/, docs/adr/, scripts/, PM_REVIEW/tooling/
# → ABORT. Move to chore branch first.
git -C <repo> add <specific files>
git -C <repo> commit -m "feat(<scope>): <mô tả tiếng Việt>"
```

Allowed types: `feat`, `fix`, `chore`, `refactor`, `test`, `docs`, `style`, `perf`, `build`, `ci`.

## Update task tracker

Tick the box in `tasks/todo-<feature>.md` (if plan-driven):

```markdown
- [x] T2.1: Tạo FallEventRepository.confirmSafe
- [ ] T2.2: ...
```

Either fold into code commit, or commit separately as `chore(plan): tick T2.1`.

If JIRA-driven, update STORIES.md status:

```markdown
| Story-ID | ... | Status |
|---|---|---|
| HG-S-042 | ... | ✅ Done |
```

## Boundaries (Karpathy discipline)

| Rule | Reason |
|---|---|
| ≤ 100 lines per increment | Test before writing too much; revertable |
| Touch only what's needed | No "while I'm here" refactor; scope creep kills PRs |
| Keep it building | `flutter analyze` / `npm run lint` / `pytest` clean after every commit |
| Each commit revertable | `git revert <hash>` should leave codebase healthy |
| No skipped/disabled tests | `skip:` / `it.skip` / `pytest.skip` = hidden bug |

## When you hit a blocker

1. **STOP** — don't push through broken state.
2. **Apply skill `systematic-debugging`** (4 phases: root cause → pattern → hypothesis → fix).
3. If this is the 3rd+ failed fix attempt → `/stuck` workflow (force re-evaluation).
4. **Add a regression test** alongside the fix.
5. **Resume** from where stopped.

## When you find the plan/spec wrong

1. **STOP coding.**
2. **Update the spec/plan/UC** — explain why in commit message.
3. **Update task tracker** accordingly.
4. **Resume** from updated task.

DO NOT silently deviate — future-you's session loses context.

## When all tasks done (feature complete)

### 1. Final verify

Run full suite + lint per stack:

```pwsh
# Flutter
flutter test --coverage
flutter analyze

# FastAPI
pytest --cov=app
mypy app/   # if configured

# Express+Prisma
npm test -- --coverage
npm run lint

# React+Vite
npm test -- --coverage
npm run lint
```

Read output. 0 fail. 0 warn. Coverage didn't drop.

### 2. Self-review

**→ Apply skill `code-review-five-axis`** (or invoke `/review` workflow). Check:
- Correctness vs spec/UC
- Readability
- Architecture (no leaks across boundaries)
- Security (no exposed secret, no SQL concat, no PHI in logs)
- Performance (no N+1 query, no unbounded loop)

If any 🔴 issue → fix before PR.

### 3. Push + PR (optional for solo dev)

```pwsh
git -C <repo> push -u origin <branch>
```

Open PR manually on GitHub if anh wants visibility. Solo dev can also merge directly to trunk after self-review (acceptable per anh's flow).

PR title format: same as commit subject.
PR body: link to UC/Story + acceptance criteria checklist.

### 4. Mark done

- Tick remaining checklist items in `tasks/todo-<feature>.md`.
- Update JIRA Story status (if applicable).
- Log decision in `PM_REVIEW/ADR/<num>-<topic>.md` if architectural choice was made (see skill `decision-log`).

## Output per task

- Test file (new or updated) with failing → passing cycle verified.
- Implementation file (minimal, scoped to task).
- Lint clean.
- Commit on feat/fix branch with Vietnamese subject.
- Task tracker updated.

## Anti-patterns auto-flag

| Pattern | Why bad |
|---|---|
| Code first, test after | Test passes immediately → proves nothing |
| 5+ "WIP" commits | Dirty history, can't revert cleanly |
| Mix 3 features in 1 commit | Hard to review, no granular rollback |
| Skip RED verify | Test might be testing nothing |
| `git commit` on trunk | Per rule 00-operating-mode |
| Push without `/review` | Self-review gate skipped — reviewer catches what you should |
| Infra files on feat/fix branch | Scope creep, lesson learned from past mixed PR |
| "While I'm here" rename in 5 files | Same — scope creep |
