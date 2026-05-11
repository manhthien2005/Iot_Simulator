---
description: Start working on a GitHub issue — load full context, verify blockers, create branch, prepare environment.
---

# /start <issue-id> — Task Kickoff

> Run this before `/build`. Never start coding without completing this checklist.

## Step 1 — Fetch issue details

```bash
gh issue view <issue-id> --repo manhthien2005/Meep
```

Read and extract:
- **Title** — task name + scope
- **Assignee** — who owns this task
- **Lane label** — `lane:specialty-be-native` (BE) or `lane:specialty-ui-design` (FE) or `lane:open`
- **Acceptance criteria** — what done looks like
- **Files có thể chạm** — output scope
- **Files phải đọc trước** — context files (read these in Step 3)
- **Dependencies / blockers** — issue numbers that must be closed first
- **Plan reference** — `docs/plans/` path

## Step 2 — Check blockers

For every issue listed under "Blocked by #":

```bash
gh issue view <blocking-id> --repo manhthien2005/Meep --json state,title
```

- If state = `OPEN` → **STOP**. Report: "Issue #X (`<title>`) chưa done. Không thể bắt đầu task này."
- If all blockers = `CLOSED` → continue.

## Step 3 — Load context files

Pull latest develop to ensure contracts are up to date:

```bash
git fetch origin develop
git status
```

Read every file listed under **"Files phải đọc trước"** in the issue.

If the section is empty or missing:
- Read every file listed under "Files có thể chạm" that already exists on `develop`.
- Focus on: abstract interfaces, freezed models, Riverpod providers, AppError hierarchy.

**Goal:** Understand the existing contract before writing a single line.

## Step 4 — Determine role + load rule context

Check the lane label from Step 1:

| Label | Role | Key rules to internalize |
|---|---|---|
| `lane:specialty-ui-design` | FE | Scope: `presentation/` only. Read `24-flutter-ui-patterns.md`. Use typed mock from leader's freezed models. Never call Firebase directly. |
| `lane:specialty-be-native` | BE | Scope: `data/` + `application/`. Implement abstract interface exactly. Never touch `presentation/`. |
| `lane:open` | Open | Check task scope in issue — follow whichever rules apply. |

If no lane label is set → ask: "Bạn là FE hay BE dev cho task này?"

## Step 5 — Verify contract exists (FE only)

If role = FE:
- Confirm that the freezed models and providers needed by this screen exist on `develop`.
- Check: `git log --oneline origin/develop -- lib/features/<feature>/data/` for recent model commits.
- If models not yet merged → **STOP**. Report: "Contract chưa có trên develop. Hỏi leader trước khi start."

## Step 6 — Create branch + update project status

Branch format: `feature/<DevName>/<short-desc>`

DevName mapping (GitHub handle → DevName):
| GitHub handle | DevName | Role |
|---|---|---|
| `manhthien2005` | `ThienPDM` | Leader |
| `CatS1mp` | `KhoaLND` | BE |
| `katheramp` | `HanDHG` | FE |
| `JanaKimmm` | `NganTNK` | FE |

Resolve DevName from the assignee fetched in Step 1. If the assignee is not in this table → ask: "DevName của bạn là gì?"

**Run the following (in order):**

```bash
# 1. Create and switch to the feature branch
git checkout -b feature/<DevName>/<short-desc> origin/develop

# 2. Update issue status to "In Progress" on the project board
pwsh -File scripts/set-issue-status.ps1 -IssueNum <issue-id> -Status "In Progress"
```

## Step 7 — Summary + handoff to /build

Print a concise summary:

```
Issue:    #<id> <title>
Role:     FE / BE / Open
Blockers: ✅ all closed / ❌ blocked by #X
Contract: ✅ models on develop / ⚠️ missing (stop + ask leader)
Branch:   feature/<DevName>/<short-desc>
Status:   ✅ set to "In Progress" on project board
Scope:    <list of files allowed to touch>

Context loaded:
  - <file1> — <why>
  - <file2> — <why>

Ready → run /build to start TDD cycle.
```

If any blocker or contract check failed → do NOT proceed to `/build`.
