---
description: Systematic debugging — root cause investigation required before any fix, following 4 phases.
---

# /debug — Systematic Debugging

> "Fix root causes, not symptoms."

Use when you hit:

- A test failure (CI or local).
- A bug from user report / Crashlytics / runtime error.
- Strange behaviour (intermittent, "works on my machine").
- Build / lint failure you don't understand.

## Pre-flight

1. **→ Invoke skill `systematic-debugging`** — full 4-phase process + iron law + red flags.
2. **STOP** — do NOT propose a fix before Phase 1 of the skill is done.
3. **Branch:** `fix/<DevName>/<issue>` (per `.windsurf/rules/20-stack-conventions.md`) or the originating feature branch. NOT `develop` or `deploy`.

## Workflow on top of the skill

The skill walks through Phases 1-4 (root cause → pattern → hypothesis → fix). This workflow adds Meep-specific entry points + commit/handoff steps.

### Quick commands for Meep

```bash
# Test failure
flutter test test/path/test.dart --reporter=expanded
cd firebase/functions && npm test -- file.test.ts

# Recent changes
git log -n 10 --oneline
git diff HEAD~5 -- <suspect file>

# Multi-component diagnosis (UI → controller → repo → Firestore → rules → CF)
# Add print at each boundary, run once to see WHICH layer fails:
print('[DEBUG] FeedController.refresh, uid=${ref.read(authProvider).uid}');
```

**Remove debug logs before commit** — `grep -rn '\[DEBUG\]' lib/` then clean.

### Meep-specific debugging entry points

| Symptom | First thing to check |
|---|---|
| Flutter widget doesn't rebuild | Trace `build` → state → notifier → repo. Don't `setState()` randomly. |
| Firestore query empty in prod (works in emulator) | Rules first, then index, then field-name typo (case-sensitive), then query path. |
| Firestore query empty everywhere | Compound query missing index — check `firestore.indexes.json`. |
| FCM not received on iOS background | APNs cert + entitlements + Background Modes > Remote notifications. |
| FCM not received on Android | Check token registration timing, topic subscription, server payload, channel ID. |
| Flaky test | DO NOT retry. Find the race condition / shared state / missing await / Future.delayed. |
| Cloud Function timeout | `timeoutSeconds`. Long task → Cloud Tasks / Pub/Sub. |
| `setState() called after dispose` | Check `mounted` first, or migrate to Riverpod (handles it). |

### Phase 4 → write a regression test

**→ Apply skill `tdd`** "Bug fix" section: failing test that reproduces → fix → verify red-green-red cycle (revert fix → test FAILs → restore → test PASSES).

Without that revert step, the test might pass for the wrong reason.

## Phase 5 — Commit + document

```bash
git add <files>
git commit -m "fix(<scope>): <description> + regression test for #<issue>"
```

Body of commit (when non-trivial):

```
The bug occurred because <short root cause>.
Fix: <approach>.
Test: regression test in <test file> reproduces by <how>.
```

## When the fix doesn't work

- < 3 attempts: → back to Phase 1 of the skill with new info.
- **≥ 3 attempts:** STOP. Architecture might be wrong. Discuss with the user before more attempts.

## Output

- ✅ Root cause documented in the commit message.
- ✅ Regression test alongside the fix.
- ✅ Bug verified gone (the actual repro step no longer fails — not just a green test).
- ✅ No "while I'm here" cleanup outside the fix.
