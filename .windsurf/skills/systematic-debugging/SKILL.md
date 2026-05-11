---
name: systematic-debugging
description: Use when encountering any bug, test failure, or unexpected behavior, BEFORE proposing fixes. Enforces root-cause investigation over symptom patching. 4-phase process.
---

# Systematic Debugging

> Adapted from `superpowers/skills/systematic-debugging`. Trimmed for solo Flutter+Firebase workflow.

## Core principle

**Always find the root cause before attempting a fix. Symptom fixes are failure.**

## The Iron Law

```
NO FIXES WITHOUT ROOT CAUSE INVESTIGATION FIRST
```

Phase 1 not done → no fix proposals.

## When to use

- A test fails.
- A bug from user report / Crashlytics.
- UI behaves oddly.
- Build / CI fails.
- "It works on my machine."
- **Especially:** when in a rush, when you've already tried 1-2 fixes, when you don't fully understand the problem.

## 4 Phases

### Phase 1 — Root cause investigation

**Before changing ANY line:**

1. **Read the error message carefully.** Full stack trace. Note line number, file path, error code. Don't skip.
2. **Reproduce reliably.** Can you trigger it 100%? Specific steps? If flaky → gather data, don't guess.
3. **Check recent changes.**
   ```bash
   git log -n 10 --oneline
   git diff HEAD~5 -- <suspect file>
   ```
4. **Trace data flow** from the symptom backwards to the source:
   - The error happens at line X, value Y is wrong.
   - Where does Y come from? Which function sets Y? Which caller passes Y?
   - Trace back to the **real source** of the bad data — don't stop at the first non-null caller.
5. **Multi-component system** (UI → controller → repo → Firestore → rules):
   - Add a log/print at each boundary.
   - Run once to find WHERE it fails.
   - Then focus the investigation on that component.

### Phase 2 — Pattern analysis

1. **Find similar working code** in the same codebase. Compare.
2. **Read the full reference** if you're following a pattern (Flutter docs, Firebase docs) — don't skim.
3. **List every difference** between working and broken code, no matter how small. Don't assume "that doesn't matter".
4. **Understand dependencies** — config, env, version, platform-specific.

### Phase 3 — Hypothesis & test

1. **Form one specific hypothesis.** "I think the root cause is X because Y."
2. **Test with a minimal change** — change one variable, not five.
3. **Verify:**
   - Hypothesis correct → Phase 4.
   - Wrong → form a NEW hypothesis. Don't add more fixes on top.
4. **When you don't know:** say so. "I don't understand X." Don't pretend. Ask the user or research more.

### Phase 4 — Implementation

1. **Write a failing test that reproduces the bug** (skill `tdd` — "Bug fix" section).
2. **Implement the fix** — only the root cause, NOT bundled with "while I'm here" cleanup.
3. **Verify the fix:**
   - Reproduction test passes.
   - Other tests still pass.
   - The bug is actually gone (not just the test passing).
4. **If the fix doesn't work:**
   - Count how many fixes you've tried.
   - <3: go back to Phase 1 with new info.
   - **≥3: STOP. The architecture might be wrong.** Discuss with the user before trying fix #4.

## Red flags — STOP and go back to Phase 1

- "Quick fix now, investigate later."
- "Let me try changing X and see."
- "I don't fully understand it, but this might work."
- "Skip the test, I'll verify by hand."
- "Probably X, let me fix that."
- Proposing a fix without tracing the data flow.
- **3+ fix attempts and the bug is still there / new symptoms appearing elsewhere.**

All → STOP. Back to Phase 1.

## Common rationalizations

| Excuse | Reality |
|---|---|
| "Simple bug, no need for process" | Simple bugs have root causes too. Process is faster than guess-and-check. |
| "I'm in a rush" | Systematic is faster than thrashing. |
| "Try this first then investigate" | The first fix sets the pattern. Do it right from the start. |
| "Will write the test after the fix works" | An untested fix isn't durable. The test proves the fix actually fixes. |
| "Multiple fixes saves time" | You can't isolate which one worked. New bugs spawn. |
| "The reference is too long, I'll adapt the pattern" | Partial understanding = bug. Read the full thing. |

## Real-world impact

Systematic: 15-30 minutes. Random thrashing: 2-3 hours.
First-time fix rate: 95% vs 40%.

## Quick reference card

| Phase | Activities | Done when |
|---|---|---|
| **1. Root cause** | Read error, reproduce, check changes, trace data | You understand WHAT + WHY |
| **2. Pattern** | Compare to working code, list differences | The right difference is identified |
| **3. Hypothesis** | Form theory, test minimally | Confirmed or new theory |
| **4. Fix** | Reproduction test → fix root → verify | Bug gone, tests pass |

## Applied to Meep

- **Flutter widget doesn't rebuild:** trace from `build` method → state → notifier → repo. Don't `setState()` randomly hoping.
- **Firestore query empty:** check rules first (debug with the emulator), check the index, check field-name typo (case-sensitive), check the query path.
- **FCM not received:** check token registration timing → topic subscription → server payload → device foreground/background state.
- **Flaky test:** don't retry. Find the race condition / shared state / timing assumption.
