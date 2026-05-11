---
name: verification-before-completion
description: Use when about to claim work is complete, fixed, or passing. Requires running verification commands and reading actual output BEFORE making any success claims. Evidence before assertions.
---

# Verification Before Completion

> Adapted from `superpowers/skills/verification-before-completion`. Trimmed.

## Core principle

**Evidence before claims, always.** Claiming "done" without verification = dishonesty, not efficiency.

## The Iron Law

```
NO COMPLETION CLAIMS WITHOUT FRESH VERIFICATION EVIDENCE
```

If you have not run a verification command **in this message**, you cannot claim it passes.

## Gate function (run mentally before any claim)

```
BEFORE claiming a status or expressing satisfaction:

1. IDENTIFY: which command would prove this claim?
2. RUN: run the full command (fresh, not partial).
3. READ: read the full output, check exit code, count failures.
4. VERIFY: does the output confirm the claim?
   - No → state the actual status with the evidence.
   - Yes → state the claim WITH the evidence.
5. ONLY THEN: speak the claim.

Skipping any step = lying.
```

## Mapping claim → required evidence

| Claim | Required | Not enough |
|---|---|---|
| "Tests pass" | Test command output: 0 failures | Old run, "should pass" |
| "Linter clean" | Linter output: 0 errors | Partial check, extrapolation |
| "Build OK" | Build command exit 0 | Lint passing, "logs look good" |
| "Bug fixed" | Test that reproduces the bug → passes | Code changed, "assumed fixed" |
| "Regression test works" | Red-green cycle verified (revert fix → fail; restore → pass) | Test passes once |
| "Requirement met" | Line-by-line checklist vs spec | "Tests pass, done" |

## Red flags — STOP

- Using "should", "probably", "seems to", "looks like".
- Expressing satisfaction before verification ("Great!", "Perfect!", "Done!").
- About to commit / push / open a PR before verifying.
- Trusting an agent / subagent "success" report without checking.
- Partial verification.
- Tired and wanting to wrap up.
- **ANY wording that implies success when you haven't run verification.**

## Rationalization → reality

| Excuse | Reality |
|---|---|
| "Should work now" | RUN the verification. |
| "I'm confident" | Confidence ≠ evidence. |
| "Just this once" | No exceptions. |
| "Linter passed" | Linter ≠ compiler ≠ runtime. |
| "I'm tired" | Exhaustion ≠ excuse. |
| "Partial check is enough" | Partial proves nothing. |

## Standard patterns

### Tests

```
✅ "I ran `flutter test test/feed/`. 12/12 pass. Done."
❌ "Tests should pass now."
```

### Build

```
✅ "I ran `flutter build apk --release`. Exit 0. APK 28MB."
❌ "Lint passed, build is probably OK."
```

### Bug fix with regression test

```
✅ Write test → run (FAIL) → fix → run (PASS) → revert fix → run (FAIL) → restore → run (PASS) → done.
❌ "I added a test" (red-green-red not actually verified).
```

### Requirements vs spec

```
✅ Re-read the spec → checklist each requirement → verify each → report any gaps.
❌ "Tests pass, phase complete."
```

### Subagent / parallel work

```
✅ Subagent reports success → check `git diff` → verify changes are actually right → report actual state.
❌ Trust the subagent report.
```

## When to apply

**ALWAYS before:**

- Any form of success / completion claim.
- Expressing satisfaction.
- Any positive statement about work state.
- Commit, PR, marking a task done.
- Moving to the next task.
- Finalising a subagent delegation.

This rule applies to:
- The exact phrase.
- Paraphrases and synonyms.
- Implications of success.
- ANY communication suggesting completion / correctness.

## Bottom line

**There are no shortcuts to verification.**

Run the command. Read the output. THEN claim.

Non-negotiable.

## Applied to Meep

| Claim | Verification command |
|---|---|
| "Flutter feature done" | `flutter test test/<feature>/` + `flutter analyze` |
| "Functions deploy OK" | `firebase functions:log --only <fn>` shows no error within 5 minutes after deploy |
| "Firestore rules OK" | `firebase emulators:exec --only firestore "npm test:rules"` |
| "App release build OK" | `flutter build apk --release` (iOS build deferred per ADR-0002) |
| "BE Node tests pass" | `npm test` exit 0 + coverage didn't drop |
