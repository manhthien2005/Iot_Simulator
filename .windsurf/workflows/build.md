---
description: Implement a task from the plan, each task following TDD cycle, commit per increment.
---

# /build — Incremental Implementation

> "The simplest thing that could work."

Implement task by task from `tasks/todo-<feature>.md`. Each task = one Red-Green-Refactor cycle. Each commit leaves the codebase in a working state.

## Pre-flight

1. **Invoke skills:** `tdd` (primary), `karpathy-guidelines`, plus `flutter-firebase-patterns` (if Flutter) or `nodejs-ts-backend` (if BE).
2. **Read** `docs/plans/<feature>.md` and `tasks/todo-<feature>.md`.
3. **Branch** must be a feature branch matching `<type>/<DevName>/<short-desc>` (vd `feature/ThienPDM/auth-google-signin`) — see `.windsurf/rules/20-stack-conventions.md`. NOT `develop` or `deploy`.
   ```bash
   git branch --show-current   # must NOT be develop or deploy
   ```
4. **Infra-file guard** — before touching ANY file under `.windsurf/`, `.github/`, `docs/adr/`, `scripts/`:
   - Verify current branch is `chore/<DevName>/...` (not a `feature/` branch).
   - If on a `feature/` branch → **STOP**. Stash changes, create `chore/<DevName>/<desc>` from `develop`, commit infra there, open a separate PR.
   - Lesson: PR #27 mixed infra + feature → required painful cherry-pick to untangle.
5. **Identify** the next task: first `- [ ]` not ticked.

## Per-task workflow

### Step 1: Load context

- Read the task description in the plan.
- Read files to be touched (existing patterns + adjacent code).
- Confirm dependency tasks are done.

### Step 2: Run the TDD cycle

**→ Apply skill `tdd`** for the full RED-GREEN-REFACTOR cycle (write failing test → verify FAIL for the right reason → minimal impl → verify PASS → refactor while green).

The skill covers: how to write the test, when to suspect the test is wrong, how to keep the impl minimal, and how to verify before claiming "done". Don't re-derive that here.

**Quick command reference for Meep:**

```bash
# Flutter
flutter test test/<path>/<file>_test.dart   # focused
flutter test                                 # full suite
flutter analyze

# Functions / BE
cd firebase/functions && npm test -- <file>.test.ts
cd firebase/functions && npm test
npm run lint
```

### Step 3: Final verify

**→ Apply skill `verification-before-completion`.** Don't claim "done" without running the full suite + lint and reading the actual output.

### Step 4: Commit

Conventional Commits, ≤ 50-char subject, imperative:

```bash
git branch --show-current          # confirm still on feature branch
git diff --name-only --cached      # scan staged files before committing
git add <specific files>
git commit -m "feat(<scope>): <description>"
```

**Before `git add`:** scan staged files. If any path starts with `.windsurf/`, `.github/`, `docs/adr/`, `scripts/` → do NOT add on a `feature/` branch. Move them to a `chore/` branch first.

Allowed types: `feat`, `fix`, `chore`, `docs`, `test`, `refactor`, `perf`, `style`. Body (optional) explains **why**, not what.

### Step 5: Update todo

Tick the box in `tasks/todo-<feature>.md`:

```markdown
- [x] T2.1: Create PostRepository.createPost
- [ ] T2.2: ...
```

Either fold into the code commit, or commit separately as `chore(plan): tick T2.1`.

## Rules

| Rule | Why |
|---|---|
| **≤ 100 lines per increment** | Test before writing too much |
| **Touch only what's needed** | No "while I'm here" refactors of unrelated files (see `karpathy-guidelines`) |
| **Keep it building** | `flutter analyze` / `npm run lint` clean after every commit |
| **Each commit revertable** | If stuck, revert is easy |
| **No skipped tests** | `skip:` / `it.skip` = tech debt |

## When you hit a blocker

1. **Stop** — don't push through a broken state.
2. **→ Apply skill `systematic-debugging`** (4 phases: root cause → pattern → hypothesis → fix).
3. **Add a regression test** alongside the fix.
4. **Resume** from where you stopped.

## When you find the plan is wrong

1. **Stop coding.**
2. **Update the plan** in `docs/plans/<file>.md` — explain why in the commit message.
3. **Update the todo** accordingly.
4. **Resume** from the updated task.

DON'T silently deviate — future-you's context will be confused.

## When all tasks for the feature are done

1. **Final verify:**
   ```bash
   flutter test --coverage
   flutter analyze
   # or BE
   npm test -- --coverage
   npm run lint
   ```

2. **Tick issue checklist + set status to Review:**
   ```bash
   # Mark all acceptance criteria as done on GitHub issue
   pwsh -File scripts/tick-issue-checklist.ps1 -IssueNum <issue-id>

   # Move issue to "Review" on the project board
   pwsh -File scripts/set-issue-status.ps1 -IssueNum <issue-id> -Status "Review"
   ```

3. **Run `/review` — MANDATORY before creating PR.** Do NOT open a PR until review is clean (no 🔴, 🟡 addressed or documented).

4. **Only after `/review` passes** → create PR with auto-generated body:
   ```bash
   git push origin <branch>

   # Generate PR body from commits + issue link (PowerShell on Windows)
   $changes = (git log develop..HEAD --oneline) -replace '^', '- '
   $prBody = "## Thay đổi`n$($changes -join "`n")`n`n## Issue liên quan`nCloses #<issue-id>`n`n## Checklist`n- [ ] Tests pass (flutter test / npm test)`n- [ ] flutter analyze / npm run lint clean`n- [ ] /review sạch (không còn 🔴)`n- [ ] Acceptance criteria ticked trên issue"
   gh pr create --base develop `
     --title "feat(<scope>): <mô tả tiếng Việt>" `
     --body $prBody
   ```

5. **Mark feature complete** in the todo file.

> ⛔ Anti-pattern: `gh pr create` trước `/review` = skip quality gate. PR reviewer sẽ catch issues mà lẽ ra self-review phải catch trước.

## Output per task

- ✅ New test file + new impl file (or updated).
- ✅ Tests pass.
- ✅ Clean commit in git log.
- ✅ Todo updated.

## Anti-patterns

| Anti-pattern | Problem |
|---|---|
| Code first, test later | Test passes immediately → proves nothing |
| 5 consecutive "WIP" commits | Dirty history, can't revert |
| Mix 3 features in one commit | Hard to review, no granular rollback |
| Skip RED verify | Test might be testing the wrong thing |
| `gh pr create` trước `/review` | Skip quality gate — reviewer catches issues bạn lẽ ra đã tự catch được |
| "While I'm here" rename in 5 unrelated files | Scope creep |
