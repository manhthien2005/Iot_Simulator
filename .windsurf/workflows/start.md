---
description: Kickoff a new VSmartwatch task — load context (UC + JIRA Story + spec), check blockers, create branch.
---

# /start <task-ref> — Task Kickoff (VSmartwatch)

> Run BEFORE `/build`. Never start coding without completing this checklist.

`<task-ref>` accepted formats:
- JIRA Story: `HG-S-042` or `Story-042` (looks up in PM_REVIEW)
- UC ID: `UC010`
- Plan task: `T2.1` (with optional `--plan <feature>` arg)
- Bug ID: `HG-001` (looks up `PM_REVIEW/BUGS/`)
- Free text: "fix sos countdown" — em hỏi để locate UC/Story

## Step 1 — Resolve task reference

### Case: JIRA Story
```pwsh
# Find which Sprint contains the story
Get-ChildItem -Path 'd:\DoAn2\VSmartwatch\PM_REVIEW\Resources\TASK\JIRA' -Filter 'STORIES.md' -Recurse | 
  Select-String -Pattern '<task-ref>'
```
→ Read the matching `STORIES.md` + sibling `_EPIC.md` for context.

### Case: UC
```pwsh
Get-ChildItem -Path 'd:\DoAn2\VSmartwatch\PM_REVIEW\Resources\UC' -Filter '<UC-ID>.md' -Recurse
```
→ Read the UC + related JIRA Epic(s) via `JIRA/README.md` UC→Epic Lookup.

### Case: Bug
```pwsh
$bug = "d:\DoAn2\VSmartwatch\PM_REVIEW\BUGS\<BUG-ID>.md"
if (Test-Path $bug) { Get-Content $bug }
```
→ Read full bug log. Note prior failed attempts (DO NOT retry them).

### Case: Free text
- Search UC: `grep -r "<keyword>" PM_REVIEW/Resources/UC/`
- Search JIRA: `grep -r "<keyword>" PM_REVIEW/Resources/TASK/JIRA/`
- If multiple match → ask user which one.
- If no match → propose creating new UC via `/spec` first.

## Step 2 — Extract acceptance criteria

From UC + JIRA Story, build a clear list:

```markdown
## Task: <name>

**Source:** UC<XXX> + JIRA <Story-ID>
**Module:** <Module>
**Repos affected:** <list>

### Acceptance criteria (from UC main flow + business rules)
- [ ] <criterion 1>
- [ ] <criterion 2>
- ...

### Out-of-scope
- <thing NOT in this iteration>

### Files to read first (context)
- <path 1> — <why>
- <path 2> — <why>

### Files allowed to touch (scope guard)
- <path or pattern>
```

This becomes the working contract for the session.

## Step 3 — Check blockers

For every dependency listed in UC "Related" or JIRA Story:
- Other UC must be implemented (look in code)
- Other Story must be Done (check STORIES.md status)
- DB migration must be deployed (`PM_REVIEW/SQL SCRIPTS/`)

If any blocker open → STOP. Report: "Blocker `<ref>` chưa done. Không bắt đầu task này."

## Step 4 — Sync trunk + check working tree

Repo of focus determined by Step 2 ("Repos affected"). For each:

```pwsh
git -C <repo> fetch origin
git -C <repo> status --short
```

If uncommitted changes → ask user: stash or commit first?

## Step 5 — Create branch

Per rule 20-stack-conventions.md format: `<type>/<short-desc>` (kebab-case, ≤ 50 chars, no DevName).

| Type | When |
|---|---|
| `feat/` | New functionality |
| `fix/` | Bug fix |
| `refactor/` | Restructure without behavior change |
| `chore/` | Infra, config, docs (NOT feature) |
| `docs/` | Documentation only |

Trunk per repo (start branch from this):

| Repo | Trunk |
|---|---|
| HealthGuard | `deploy` |
| health_system, Iot_Simulator_clean | `develop` |
| healthguard-model-api | `master` |
| PM_REVIEW | `main` |

```pwsh
git -C <repo> checkout <trunk>
git -C <repo> pull origin <trunk>
git -C <repo> checkout -b <type>/<short-desc>
```

## Step 6 — Pre-existing fix attempts (bug only)

If this is a bug fix:
```pwsh
$bug = "d:\DoAn2\VSmartwatch\PM_REVIEW\BUGS\<BUG-ID>.md"
if (Test-Path $bug) { Get-Content $bug }
```

Note all prior failed approaches. **DO NOT retry them in `/build`.**

If file doesn't exist + this is a real bug worth tracking → create new bug log entry (skill `bug-log`):
```pwsh
# Use template
Copy-Item 'd:\DoAn2\VSmartwatch\PM_REVIEW\BUGS\_TEMPLATE.md' "d:\DoAn2\VSmartwatch\PM_REVIEW\BUGS\<NEW-ID>.md"
```

## Step 7 — Summary + handoff

Print concise summary:

```
Task:        <name>
Source:      UC<XXX> + JIRA <Story-ID>  (or Bug <ID>)
Repos:       <list>
Blockers:    ✅ all done / ❌ blocked by <ref>
Branch:      <type>/<short-desc> (from <trunk>)
Bug log:     ✅ no prior attempts / ⚠️ N prior attempts (DO NOT retry: <list>)

Acceptance criteria (N items):
  □ <criterion 1>
  □ <criterion 2>
  ...

Files to read first:
  - <path> — <why>

Files allowed to touch:
  - <pattern>

Ready → run /build to start TDD cycle.
```

## Step 8 — If anything fails

| Failure | Action |
|---|---|
| Task ref ambiguous (multiple matches) | Ask user to pick |
| No matching UC/Story | Propose `/spec` first |
| Blocker open | STOP, report blocker |
| Uncommitted changes | Stash or commit first |
| Bug has only failed attempts | Switch to `/stuck` workflow |

## Cross-repo task

If task affects multiple repos:
- Create branch with same name in each affected repo (sync naming).
- Sequence work per dependency order (use `topology.md` data flow):
  1. PM_REVIEW (spec/UC update)
  2. SQL canonical (if schema change)
  3. Producer side (BE producing API)
  4. Consumer side (mobile/admin consuming)
  5. E2E test
- See `/cross-repo-feature` workflow for detailed sequencing.

## Output

- ✅ UC + Story + acceptance criteria identified
- ✅ Blockers verified clear
- ✅ Branch created from correct trunk
- ✅ Bug log checked (if applicable)
- ✅ Working tree clean
- ✅ User has clear handoff to `/build`
