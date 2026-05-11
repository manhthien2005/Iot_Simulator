---
description: When UC/SRS/SQL canonical changes, ripple updates across code, tests, JIRA stories, and dependent UCs. Prevents spec drift.
---

# /sync-spec — Spec Drift Detection & Ripple

> Spec change without ripple = drift = bugs months later. This workflow systematically traces impact.

Use when:
- UC updated (new flow, changed BR, new field).
- SRS section revised.
- SQL canonical schema changed.
- API contract version bumped.

## Pre-flight

1. **Invoke skills:** `karpathy-guidelines` (surgical updates), `decision-log` (if change is architectural).
2. **Identify the spec change:** which file, which sections, what semantic change?

## Phase 1 — Locate spec change

```pwsh
# What changed in spec?
git -C 'd:\DoAn2\VSmartwatch\PM_REVIEW' diff HEAD~1 -- Resources/UC/<Module>/UC<XXX>.md
git -C 'd:\DoAn2\VSmartwatch\PM_REVIEW' diff HEAD~1 -- "SQL SCRIPTS/"
```

Classify change type:

| Type | Examples | Ripple severity |
|---|---|---|
| **Behavioral** | Main flow step added/changed, BR added | High — code logic + tests |
| **Field added** | New data field in UC | High — DB column + model + UI |
| **Field renamed** | Field name change | Medium — refactor cascade |
| **Field removed** | Deprecated field | High — caller cleanup |
| **NFR change** | Performance/security threshold | Variable — review impact |
| **Cosmetic** | Wording, formatting | Low — no code impact |

## Phase 2 — Trace ripple targets

For each spec change, list downstream artifacts to update.

### A. Code repos affected

Search for UC reference in code:

```pwsh
foreach ($r in @('HealthGuard','health_system','Iot_Simulator_clean','healthguard-model-api')) {
  Write-Host "=== $r ===" -ForegroundColor Cyan
  Get-ChildItem "d:\DoAn2\VSmartwatch\$r" -Recurse -File -Include '*.dart','*.py','*.js','*.jsx','*.tsx' -ErrorAction SilentlyContinue |
    Select-String -Pattern 'UC<XXX>' -List
}
```

### B. Test files

Tests reference UC behaviors:
```pwsh
# Search for UC in test files
foreach ($r in @('...')) {
  Get-ChildItem "d:\DoAn2\VSmartwatch\$r" -Recurse -File -Include '*test*' |
    Select-String -Pattern 'UC<XXX>' -List
}
```

### C. JIRA Stories

```pwsh
Get-ChildItem 'd:\DoAn2\VSmartwatch\PM_REVIEW\Resources\TASK\JIRA' -Filter 'STORIES.md' -Recurse |
  Select-String -Pattern 'UC<XXX>' -List
```

### D. Related UCs (include/extend chain)

```pwsh
Get-ChildItem 'd:\DoAn2\VSmartwatch\PM_REVIEW\Resources\UC' -Filter '*.md' -Recurse |
  Select-String -Pattern 'UC<XXX>' -List
```

### E. DB schema (if data field change)

```pwsh
Get-ChildItem 'd:\DoAn2\VSmartwatch\PM_REVIEW\SQL SCRIPTS' -Filter '*.sql' |
  Select-String -Pattern '<table_or_column>' -List
```

### F. Test cases in PM_REVIEW

```pwsh
Get-ChildItem 'd:\DoAn2\VSmartwatch\PM_REVIEW\TESTING' -Recurse -Filter '*testcases.md' -ErrorAction SilentlyContinue |
  Select-String -Pattern 'UC<XXX>' -List
```

## Phase 3 — Build ripple plan

Output: actionable todo per affected file.

```markdown
# Spec Ripple: UC<XXX> change YYYY-MM-DD

## Spec change
- File: `PM_REVIEW/Resources/UC/<Module>/UC<XXX>.md`
- Change: <what changed semantically>
- Type: Behavioral / Field-added / etc.

## Ripple targets

### Code
- [ ] `health_system/lib/features/<area>/<file>.dart:<line>` — update <what>
- [ ] `health_system/backend/app/routers/<file>.py:<line>` — update <what>

### Tests
- [ ] `health_system/test/features/<area>/<file>_test.dart` — add test for new BR
- [ ] `health_system/backend/tests/test_<file>.py` — update assertion

### JIRA Stories
- [ ] `PM_REVIEW/Resources/TASK/JIRA/Sprint-N/<Epic>/STORIES.md` — story `<ID>` references this UC; update acceptance criteria

### Related UCs
- [ ] UC<YYY> includes UC<XXX> — verify still consistent

### DB
- [ ] `PM_REVIEW/SQL SCRIPTS/init_full_setup.sql` — add column
- [ ] `HealthGuard/backend/prisma/schema.prisma` — add field
- [ ] Migration: write `PM_REVIEW/SQL SCRIPTS/migrations/YYYYMMDD_<desc>.sql`

### Test cases
- [ ] `PM_REVIEW/TESTING/<Module>/<Function>_testcases.md` — add new TC for BR
```

## Phase 4 — Decision log (if architectural)

If spec change introduces:
- New API contract or major version bump
- Breaking change to data model
- New cross-repo coordination

→ Write ADR via skill `decision-log`. Include:
- What changed
- Why (driving factor)
- Migration strategy for existing consumers
- Reverse decision triggers

## Phase 5 — Cross-repo handoff

If ripple touches ≥ 2 repos → switch to `/cross-repo-feature` workflow for sequenced execution.

If single repo → `/plan` to break into vertical-slice tasks, then `/build`.

## Phase 6 — Verify ripple complete

Before claiming "spec synced":

| Check | Command |
|---|---|
| All UC references in code updated | `grep UC<XXX> -r <repo>` shows updated context |
| Tests reference new behavior | New test exists, runs, passes |
| JIRA Stories reflect new acceptance | Story acceptance criteria match UC |
| DB schema matches UC data fields | Manual diff `init_full_setup.sql` vs UC data fields |
| No orphan references to old field/flow | `grep <old-field>` = empty |

Apply skill `verification-before-completion`.

## Phase 7 — Commit

```pwsh
git -C PM_REVIEW commit -m "docs(uc): cập nhật UC<XXX> với <change>

Ripple: <list of repos updated>"

# Per repo
git -C <repo> commit -m "<type>(<scope>): cập nhật theo UC<XXX> change

UC ref: PM_REVIEW@<sha>"
```

Each commit references the UC commit SHA — traceable across repos.

## Anti-patterns

| Pattern | Risk |
|---|---|
| Update UC, skip ripple | Code drifts from spec; bugs surface months later |
| Update only obvious files | Hidden references in tests/JIRA missed |
| Skip DB schema sync | Production schema mismatch |
| Skip ADR for breaking change | Future-you re-debates |
| Bundle multiple UC changes in one commit | Hard to revert one without others |
| Skip cross-repo verify | Producer-consumer drift |

## Output

- ✅ Ripple plan with all affected files identified
- ✅ Each affected file actually updated (verified by grep)
- ✅ Tests updated to reflect new behavior
- ✅ JIRA Stories updated
- ✅ DB schema in sync (if data field change)
- ✅ ADR written if architectural change
- ✅ Commits reference UC change SHA for traceability
