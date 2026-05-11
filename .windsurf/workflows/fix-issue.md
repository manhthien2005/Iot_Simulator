---
description: Fix a specific issue (link/description/Crashlytics report) end-to-end — analyze, plan minimal fix, implement, test.
---

# /fix-issue — Targeted Issue Resolution

End-to-end fix for a specific issue: GitHub issue, Crashlytics report, user complaint, or a clear bug with reproduction steps.

## Pre-flight

1. **Invoke skills:** `systematic-debugging` (primary), `tdd`, `karpathy-guidelines`.
2. **Get issue details:**
   - Link / ID / description of the issue.
   - Repro steps (who? doing what? expected vs actual?).
   - Stack trace / error log if available.
   - Affected version / platform / device.
3. **New branch:**
   ```bash
   git checkout -b fix/<short-description>
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

Meep-specific entry points (which layer to suspect first):

```bash
git log -n 20 --oneline -- <affected files>
git blame <file> | grep <line>
```

| Symptom | First check |
|---|---|
| Crashlytics: `setState() after dispose` | Riverpod migration vs `mounted` guard |
| Firestore query empty in prod, OK in emulator | Rules → index → field-name typo |
| FCM not delivered | Token registration → topic → payload → fg/bg state |
| Auth token expired loop | Refresh handler in `AuthRepository` boundary |

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

### Mobile fix

- Run the app on a real device (not just the simulator if device-specific).
- Repro the original steps → confirm bug gone.
- Smoke-test related features for no regression.

### BE / Functions fix

- Deploy to emulator → run integration tests.
- Check logs have no new errors.
- Test with edge cases from the original issue.

### Apply skill `verification-before-completion`

Don't claim "fixed" until:
- ✅ Unit tests pass.
- ✅ Original reproduction steps → bug gone.
- ✅ Full test suite passes.
- ✅ Lint clean.

## Step 6: Commit

Conventional Commits with the issue reference:

```bash
git add <files>
git commit -m "fix(<scope>): <description>

Root cause: <short — what was wrong>
Fix: <approach>
Test: regression test in <test file>

Closes #<issue-id>"
```

## Step 7: PR / merge

### Self-review first

Apply workflow `/review`:

```bash
git diff develop...HEAD
flutter analyze
flutter test
```

### Open a PR (if your workflow uses PRs)

PR description template:

```markdown
## Issue
Closes #<id>

## Root cause
<1-2 sentences>

## Fix
<approach + why this approach>

## Test
- Regression test: `<test file>`
- Manual repro: <steps + expected>

## Verification
- [ ] `flutter test` passes
- [ ] `flutter analyze` clean
- [ ] Manual repro confirmed bug gone
- [ ] Smoke-tested related features
```

## Step 8: Post-merge

- Confirm the fix deployed successfully (if CI/CD triggered).
- Monitor Crashlytics / logs for 24h to spot regressions.
- Close the issue with a comment confirming the fix is verified.

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
