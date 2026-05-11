---
description: Post-merge cleanup — verify merge, pull trunk, delete local + remote branches, update bug log/ADR/JIRA trackers, optional tag.
---

# /close-task — Post-merge cleanup

> **When to use:** After PR merged successfully (manual via GitHub UI by anh). Closes the task lifecycle: tracker sync + branch hygiene.

> **When NOT to use:**
> - PR not yet merged → wait
> - Failing CI on trunk after merge → run `/debug` first
> - Open bugs related to this task → resolve before closing

## Step 1: Verify merge

```pwsh
# cwd: <repo>
git fetch origin
git log origin/<trunk> --oneline -n 5
```

Confirm:
- Merge commit visible on trunk
- Commit message matches PR title
- No follow-up revert commit after merge

If revert detected → STOP. Investigate why merge was reverted, treat as bug.

## Step 2: Pull latest trunk + cleanup local branches

```pwsh
# cwd: <repo>
git checkout <trunk>
git pull origin <trunk>

# Delete local branch (safe — only deletes if fully merged)
git branch -d <task-branch>

# If remote auto-delete on merge is OFF, delete remote branch
git push origin --delete <task-branch>

# Optional: prune stale remote-tracking refs
git remote prune origin
```

If `git branch -d` fails with "not fully merged":
- Branch has commits not in trunk
- DO NOT force-delete (`-D`) — investigate first
- Check `git log <task-branch> --not <trunk> --oneline`

## Step 3: Update trackers

### 3.1 Bug log (if task was a bug fix)

```pwsh
# cwd: d:\DoAn2\VSmartwatch\PM_REVIEW
$bugId = "<REPO-PREFIX>-<NUM>"
$bugFile = "BUGS\$bugId.md"
```

Edit the bug file:
- Set `status: resolved`
- Add `resolution_commit: <merge-commit-sha>`
- Add `resolution_date: <today>`
- Add `regression_test: <test-file-path>::<test-name>`
- Append final `## Resolution` section: root cause + fix summary + how to verify

Update `BUGS/INDEX.md`:
- Move bug from "Open" to "Resolved" section
- Update last-modified date

### 3.2 ADR (if task introduced architectural decision)

```pwsh
$adrFile = "ADR\<NNN>-<title>.md"
```

Edit ADR:
- If status was `Proposed` → change to `Accepted` (post-merge confirms decision stuck)
- Add `implementation_commit: <merge-commit-sha>`

Update `ADR/INDEX.md`:
- Confirm ADR listed in chronological + tag indexes
- No need to move (ADRs persist as historical record)

### 3.3 JIRA story / Sprint backlog

Find related story in `PM_REVIEW/Resources/TASK/JIRA/Sprint-<N>/`:
- Update STORIES.md: change status `In Progress` → `Done`
- Add `Completed: <date>` + `PR: <url>`
- Update `_SPRINT.md` progress counters if formal tracking

If task was unplanned (hotfix not in sprint):
- Add to `Sprint-<current>/_SPRINT.md` under "Unplanned work"
- Document why unplanned (urgent bug, blocker, etc.)

### 3.4 Plan file (if task was plan-driven)

If task came from `docs/plans/<feature>.md`:
- Mark task checkbox `[x]`
- Add commit ref next to checkbox
- If all tasks done → archive plan to `docs/plans/archive/`

### 3.5 Spec / UC (if scope changed during implementation)

If implementation revealed UC was incomplete:
- Update UC file with discovered acceptance criteria
- Run `/sync-spec` to ripple to dependent UCs/tests/JIRA

## Step 4: Tag (optional — milestone only)

Don't tag every task. Tag only when:
- Module milestone reached (vd: "all SOS UCs implemented")
- Cross-repo contract version finalized
- Release candidate ready (anh's domain — anh decides)

```pwsh
# cwd: <repo>
$tag = "milestone/<short-name>-$(Get-Date -Format yyyy-MM-dd)"
git tag -a $tag -m "<one-line description>"
git push origin $tag
```

## Step 5: Cross-repo handoff (if applicable)

If task affected `topology.md` boundary (API contract, DB schema):
- Notify dependent repos in commit message (already done in producer commit)
- For consumers: open follow-up `chore/sync-<feature>-contract` task in their repo
- Update `PM_REVIEW/CONTRACTS/<feature>.md` if used (currently optional)

## Step 6: Verification

```pwsh
# Confirm cleanup state
# cwd: <repo>
git branch | Select-String -Pattern "<task-branch>"   # should return nothing
git status                                              # clean working tree
```

```pwsh
# Confirm tracker updates
# cwd: d:\DoAn2\VSmartwatch\PM_REVIEW
git status --short    # should show updates to BUGS/INDEX.md, etc
```

Commit tracker updates as separate commit in PM_REVIEW (not on the merged repo's branch since it's already deleted):

```pwsh
git -C d:\DoAn2\VSmartwatch\PM_REVIEW checkout -b chore/close-<task-id>
# stage tracker file changes
git -C d:\DoAn2\VSmartwatch\PM_REVIEW add BUGS/ ADR/ Resources/TASK/
git -C d:\DoAn2\VSmartwatch\PM_REVIEW commit -m "chore(trackers): close <task-id> sau khi merge"
git -C d:\DoAn2\VSmartwatch\PM_REVIEW push -u origin chore/close-<task-id>
# Then PR + merge in PM_REVIEW
```

## Apply skill `verification-before-completion`

Before claiming "task closed":

| Claim | Required evidence |
|---|---|
| "Local branch deleted" | `git branch` shows no `<task-branch>` |
| "Remote branch deleted" | `git ls-remote --heads origin` shows no `<task-branch>` |
| "Bug log updated" | Diff in `BUGS/<id>.md` shows status: resolved + commit ref |
| "JIRA updated" | Diff in `STORIES.md` shows status: Done + PR link |
| "Trunk has fix" | `git log origin/<trunk>` shows merge commit |

## Anti-patterns

| Anti-pattern | Risk |
|---|---|
| Skip tracker update | Future-anh debugs same bug because no log |
| Force-delete unmerged branch | Lost work |
| Delete remote branch before confirming merge | If merge reverted, branch gone |
| Tag every task | Tag noise — release tags lose meaning |
| Update tracker on task branch (already deleted) | Commit to wrong place |
| Auto-promote `develop` → `deploy` for HealthGuard | NOT em's job (per ADR-003) |

## Cross-skill / cross-workflow

| Need | Use |
|---|---|
| Just merged a feature | This workflow |
| Closing a bug fix specifically | This workflow + `bug-log` skill (resolve step) |
| Architectural decision implementation finished | This workflow + `decision-log` skill (Accept step) |
| All tasks in sprint done | This workflow per task + `backlog-auditor` skill (sprint summary) |
