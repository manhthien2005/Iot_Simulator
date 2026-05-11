---
description: When 3+ failed attempts on the same bug or you suspect "vòng lặp chết" — force re-evaluation, NOT another fix attempt. Reads bug log, questions framing, escalates.
---

# /stuck — Force Re-Evaluation (Anti-Loop)

> "Insanity is doing the same thing and expecting different results." When fix attempts pile up, the problem isn't the fix — it's the framing.

Use when:
- 3+ failed attempts on the same bug.
- AI proposed similar approach to previous failed attempt.
- Bug "fixed" but new symptoms appear elsewhere.
- Anh said "still broken", "tried that", "this bug again".
- Time pressure tempting "just one more fix".

**This workflow does NOT propose a fix.** It re-evaluates whether the fix-target is correct.

## Phase 1 — Acknowledge and stop

Read this aloud (mentally):

> "More fix attempts will not help. Pattern of failures is signaling something deeper."

DO NOT:
- Propose attempt #4.
- Suggest "let me try one more thing".
- Continue without re-reading bug log.

## Phase 2 — Read entire bug log

```pwsh
$bug = "d:\DoAn2\VSmartwatch\PM_REVIEW\BUGS\<BUG-ID>.md"
Get-Content $bug | Out-Host
```

Build a summary table:

```markdown
| # | Hypothesis | Approach | Why failed |
|---|---|---|---|
| 1 | <H1> | <A1> | <reason> |
| 2 | <H2> | <A2> | <reason> |
| 3 | <H3> | <A3> | <reason> |
```

Look for patterns:
- Same hypothesis with different approaches → hypothesis is wrong.
- Different hypotheses but same outcome → root cause is upstream of all.
- Each fix breaks something else → architecture incompatible with fix shape.

## Phase 3 — Re-frame questions (don't fix yet)

Ask these in order. Each requires honest answer (not "should be fine").

### Question 1: Is this the right bug to fix?

- Is the symptom the actual problem, or surface of upstream issue?
- Example: "Login fails sometimes" — is the bug in login, or in session management upstream?

### Question 2: Is the bug well-defined?

- Repro steps deterministic? Or "sometimes"?
- If non-deterministic → real bug is the timing/race, not the visible symptom.

### Question 3: Is the architecture wrong for this requirement?

- Are we patching around a fundamental incompatibility?
- Example: trying to fix UI lag with debounce when actual issue is repository fetches synchronously.

### Question 4: Is the spec wrong?

- UC says X, code does Y. Maybe code is right and UC is outdated?
- Update UC via `/sync-spec` first if so.

### Question 5: Are constraints making the bug unsolvable in current shape?

- "Quick fix" trade-off accumulated to point where surgical fix impossible?
- May need refactor (`/refactor-module`) before fix.

### Question 6: Are we 90% sure the failure mode is understood?

- If < 90% → return to skill `systematic-debugging` Phase 1 with fresh eyes.
- If 90%+ but fix attempts fail → architectural issue, not implementation.

## Phase 4 — Decide path forward

Based on Phase 3 answers, choose ONE:

### Path A — Re-frame the bug
The visible bug is symptom of upstream. **Stop fixing this. Open new bug for upstream root cause.**
- Create `PM_REVIEW/BUGS/<NEW-ID>.md` for upstream.
- Mark current bug as `Blocked by <NEW-ID>` in INDEX.md.
- Switch to upstream bug.

### Path B — Refactor before fix
Architecture incompatible. **Stop fixing this. Plan refactor.**
- Run `/refactor-module` for affected module.
- Resume fix after refactor merged.

### Path C — Update spec first
Spec is wrong/outdated. **Stop fixing this. Update spec.**
- Run `/sync-spec` for affected UC.
- Re-evaluate if bug still exists with updated spec.

### Path D — Brand new approach
Re-frame succeeded; new hypothesis emerged. **Document why this differs from prior failed attempts.**
- Add to bug log: "Attempt 4 — significantly different hypothesis: <H>"
- Explain in attempt entry why prior failures don't predict this one.
- Apply `/build` for the fix.

### Path E — Accept and document
Bug genuinely hard, current cost > current value. **Defer.**
- Mark bug status = ⛔ Won't fix in INDEX.md.
- Document workaround for users.
- Add to backlog for future reconsideration.
- Reverse trigger: when X changes, reconsider.

## Phase 5 — Discuss with user

Em report to anh BEFORE attempt #4:

```
Bug <ID> — 3 attempts đã fail. Em phân tích pattern:

Attempts:
1. <H1> + <A1> → fail vì <reason1>
2. <H2> + <A2> → fail vì <reason2>
3. <H3> + <A3> → fail vì <reason3>

Pattern em thấy: <observation — vd "all attempts assume bug is in UI, but data shows it's in repository layer">

Em đề xuất Path <X>: <name>

Lý do:
- <điểm 1>
- <điểm 2>

Anh muốn:
A. Theo Path <X> như em đề xuất
B. Tiếp tục attempt #4 với hypothesis khác (em tốn thêm token chứ không khuyến khích)
C. Defer bug
D. Anh có insight em chưa thấy?
```

Wait for anh's decision. Don't ghost forward.

## Phase 6 — Update bug log

Whatever path chosen:

```markdown
## Stuck Analysis — YYYY-MM-DD

After 3 attempts, ran `/stuck` workflow.

**Pattern identified:** <observation>

**Path chosen:** <A/B/C/D/E>

**Reason:** <why this path over alternatives>

**Next action:** <concrete next step>
```

Update INDEX.md status:
- Path A → status = `Blocked by <NEW-ID>`
- Path B → status = `Blocked by refactor`
- Path C → status = `Blocked by spec update`
- Path D → status = stays `In progress` with attempt 4
- Path E → move to `Won't fix` section

## Phase 7 — Decision log if path is architectural

Path B, C, or sometimes A introduce architectural shift. Write ADR via skill `decision-log`:

- ADR-<NNN>: why we're refactoring/re-spec-ing/re-framing this bug.
- Reverse triggers: under what conditions to reconsider.

## Anti-patterns specific to stuck

| Pattern | Why bad |
|---|---|
| "Just one more attempt" without re-frame | Often becomes attempts 5, 6, 7 |
| Attempt #4 with same hypothesis as #2 | Definition of insanity |
| Skip Phase 5 (discuss with anh) | Ghost-forward = wasted hours |
| Mark bug `Won't fix` without trying re-frame | Defer too quickly = bug bites later |
| Re-frame requires major refactor, do refactor + fix in same branch | Scope explosion — separate branches |

## When `/stuck` itself isn't enough

If 2 rounds of `/stuck` (i.e., 6+ attempts total) fail:
- This is a P0 architectural problem.
- Pause feature work in this area.
- Schedule deep dive session — read entire module, prior commits, related ADRs.
- Possibly: throwaway prototype to understand problem space.

## Output

- ✅ Bug log read entire history
- ✅ Pattern of failures identified
- ✅ Path chosen with rationale
- ✅ User informed before any new attempt
- ✅ Bug log + INDEX updated
- ✅ ADR written if architectural shift
- ✅ NO new fix attempt without re-frame succeeding
