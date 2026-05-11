---
name: bug-log
description: Use when investigating or fixing a non-trivial bug to track all attempted approaches in a centralized log. Prevents proposing the same failed approach twice across sessions. MUST read existing log before proposing fix; MUST update after each attempt.
---

# Bug Log — Anti-Loop Cross-Session Memory

> **Why this skill exists:** AI sessions don't remember prior attempts. Without a log, AI re-proposes failed approaches → "vòng lặp chết". This skill is the cure.

## Iron Law

```
NO FIX PROPOSAL WITHOUT READING THE BUG LOG FIRST
```

If `PM_REVIEW/BUGS/<BUG-ID>.md` exists → MUST read all prior attempts. Any approach marked `failed` is OFF-LIMITS without explicit user override.

## When to invoke

**Auto-invoke** when:
- `/debug` workflow starts.
- `/fix-issue` workflow starts.
- User says "this bug again", "still broken", "tried that".
- This is the 2nd+ session on the same bug.

**Manual invoke** when:
- Non-trivial bug expected to span multiple sessions.
- Cross-repo bug affecting 2+ repos.
- Bug whose root cause is unclear after Phase 1 of `systematic-debugging`.

**Skip** for:
- Trivial single-line typo fixes.
- Bugs resolved within one session (no risk of recurrence).

## Bug ID convention

Format: `<REPO-PREFIX>-<NUM>` — sequential per repo, 3-digit zero-padded.

| Prefix | Repo |
|---|---|
| HG | HealthGuard (admin web) |
| HS | health_system (mobile + backend) |
| IS | Iot_Simulator_clean |
| MA | healthguard-model-api |
| PM | PM_REVIEW (rare — docs bugs) |
| XR | Cross-repo bug (affects ≥ 2 repos) |

Examples: `HG-001`, `HS-005`, `XR-002`.

## File location

```
PM_REVIEW/BUGS/
├── INDEX.md           # GPS map of all bugs (status, repo, severity)
├── _TEMPLATE.md       # Copy this to start a new bug log
├── HG-001.md
├── HS-005.md
└── XR-001.md
```

## Workflow when starting a bug

### Step 1 — Check if bug log exists

```pwsh
$bugDir = 'd:\DoAn2\VSmartwatch\PM_REVIEW\BUGS'
# If user provides bug ID:
$bug = "$bugDir\<BUG-ID>.md"
if (Test-Path $bug) { Get-Content $bug } else { Write-Host "No prior log" }

# If exploring — search by symptom keyword:
Get-ChildItem $bugDir -Filter '*.md' -Exclude 'INDEX.md','_TEMPLATE.md' | 
  Select-String -Pattern '<keyword>' -List
```

### Step 2 — Read all prior attempts

For existing bug log, list each attempt's:
- Hypothesis
- Approach taken
- Result (`failed` / `partial` / `successful`)
- Reason (if failed)

**DO NOT propose any approach already marked `failed`.** Variations are OK only if the variation addresses the documented failure reason.

### Step 3 — If no log + bug is non-trivial, create one

```pwsh
# Determine next ID for this repo
$prefix = 'HG'   # adjust per repo
$existing = Get-ChildItem "$bugDir\$prefix-*.md" | Sort-Object Name -Descending | Select-Object -First 1
$nextNum = if ($existing) {
  [int]($existing.BaseName -replace "^$prefix-",'') + 1
} else { 1 }
$newId = "$prefix-$('{0:D3}' -f $nextNum)"
Copy-Item "$bugDir\_TEMPLATE.md" "$bugDir\$newId.md"
Write-Host "Created: $bugDir\$newId.md"
```

Fill in template sections (see template below).

## Workflow per attempt

### Before proposing fix

1. Re-read the log.
2. Identify what hypothesis you're testing.
3. State explicitly what makes THIS attempt different from prior failed ones.

### After applying attempt + verification

Append new attempt entry to log:

```markdown
### Attempt N — YYYY-MM-DD HH:MM

**Hypothesis:** <what you thought caused it>
**Approach:** <what you changed>
**Files touched:** <list>
**Verification:** <command + result>
**Result:** ✅ successful / ⚠️ partial / ❌ failed
**Reason (if not successful):** <why it didn't work>
**Next step (if failed):** <what to investigate next>
```

### When bug resolved

Update top of file:

```markdown
**Status:** ✅ Resolved
**Resolved:** YYYY-MM-DD
**Fix commit:** <repo>@<sha>
**Verification:** <how to confirm fix works in production>
**Watch for regression:** <signal that bug came back>
```

Then update `INDEX.md` to move from `Open` to `Resolved` section.

## Workflow when getting stuck

If 3+ attempts failed:

1. **STOP** — switch to `/stuck` workflow.
2. Re-read entire log to map all approaches tried.
3. Question: is this the right bug? (Maybe symptom of upstream root cause.)
4. Discuss with user before attempt #4.

## INDEX.md maintenance

`PM_REVIEW/BUGS/INDEX.md` MUST be updated whenever:
- New bug created → add to `Open` section.
- Status changes → move row to appropriate section.
- Bug resolved → move to `Resolved` section + add resolution date.

INDEX format (see `INDEX.md` for live version):

```markdown
## Open

| ID | Repo | Module | Title | Severity | Created | Last attempt |
|---|---|---|---|---|---|---|
| HG-001 | HealthGuard | Auth | Token refresh loops on expired refresh | High | 2026-05-08 | 2026-05-10 (3rd attempt failed) |

## Resolved

| ID | Repo | Module | Title | Resolved | Commit |
|---|---|---|---|---|---|
| HS-002 | health_system | Fall | SOS countdown reset bug | 2026-05-09 | health_system@a1b2c3d |
```

## Template (reference, see `_TEMPLATE.md` for actual file)

```markdown
# Bug <BUG-ID>: <Short title>

**Status:** 🔴 Open / 🟡 In progress / ✅ Resolved
**Repo(s):** <repo name>
**Module:** <module>
**Severity:** Critical / High / Medium / Low
**Reporter:** <name or self>
**Created:** YYYY-MM-DD
**Resolved:** YYYY-MM-DD (if resolved)

## Symptom
<What user observes — concrete, reproducible>

## Repro steps
1. ...
2. ...
3. **Expected:** ...
4. **Actual:** ...

## Environment
- App version / commit:
- Platform: Android X.X / iOS X.X / Browser X.X
- Backend version:
- DB state (if relevant):

## Logs / Stack trace
```
<paste relevant log lines, redact PHI>
```

## Investigation

### Hypothesis log

| # | Hypothesis | Status |
|---|---|---|
| H1 | <e.g., "Refresh interceptor doesn't await before retry"> | ❌ Disproved |
| H2 | <e.g., "Token storage not cleared on logout"> | 🔄 Testing |

### Attempts

#### Attempt 1 — 2026-05-08 14:30
**Hypothesis:** H1
**Approach:** Wrap refresh in async-await, add lock
**Files touched:** `lib/core/network/refresh_interceptor.dart`
**Verification:** `flutter test test/core/network/` → 5/6 pass; manual repro on device → still loops
**Result:** ❌ failed
**Reason:** Lock prevented concurrent refresh but didn't fix root cause — token storage returns stale token even after refresh
**Next step:** Investigate token storage layer (H2)

#### Attempt 2 — ...

## Resolution
**Fix commit:** <repo>@<sha>
**Approach:** <what worked>
**Test added:** <regression test path>
**Verification:** <how to confirm fix>
**Watch for regression:** <signal that bug came back>

## Related
- UC: UC<XXX>
- JIRA: <Story-ID>
- Linked bug: <BUG-ID>
- ADR: <num> (if architectural decision involved)
```

## Anti-patterns

| Anti-pattern | Why bad |
|---|---|
| Skip log because "I'll remember" | You won't remember next session. AI definitely won't. |
| Vague attempt entry ("tried changing stuff") | Useless when read 2 weeks later |
| Don't mark `failed` reason | Future-you can't tell why approach was rejected — risk re-proposing |
| Update only on resolution | Loses the journey — can't review what didn't work |
| Skip INDEX update | INDEX is GPS — stale INDEX = lost bugs |
| Log raw PHI in symptom/logs | Medical app — redact email/name/raw vital |

## Rule integration

This skill is referenced by:
- Rule `60-context-continuity.md` — declares log location to AI on every conversation start
- Workflow `/debug` step 1 — anti-loop check
- Workflow `/fix-issue` pre-flight — anti-loop check
- Workflow `/stuck` — full log review when stuck
