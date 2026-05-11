---
description: Convert audit findings into actionable refactor plan with vertical-slice tasks. Run after /audit, before /build.
---

# /refactor-module — Actionable Refactor Planning

> Bridge từ "audit findings list" sang "executable task list". Bảo đảm refactor có scope rõ ràng, không drift thành rewrite.

Use when:
- Vừa chạy `/audit` xong cho module X, cần kế hoạch sửa.
- Module có tech debt tích lũy, muốn refactor có chủ đích (không drive-by).
- Bug fix lan rộng → cần restructure thay vì patch.

## Pre-flight

1. **Invoke skills:** `karpathy-guidelines` (surgical), `writing-plans`, `decision-log` (nếu thay đổi architecture).
2. **Inputs:**
   - Audit report path (output of `/audit`): `<repo>/docs/audits/audit-<module>-YYYY-MM-DD.md`
   - Module name + scope (which folders/files belong to it)
3. **Branch** từ trunk:
   ```pwsh
   git -C <repo> checkout <trunk>
   git -C <repo> pull origin <trunk>
   git -C <repo> checkout -b refactor/<module>-<short-desc>
   ```

## Phase 1 — Triage findings

Read audit report. Classify each finding:

| Tier | Definition | Action |
|---|---|---|
| **P0 — Critical** | Bug, security hole, broken contract, blocked feature | MUST fix in this refactor |
| **P1 — Important** | Tech debt blocking next feature, perf issue, test gap | Fix in this refactor if scope allows |
| **P2 — Nice-to-have** | Code style, micro-perf, naming improvement | DEFER unless touching those lines anyway |

**Rule:** không bundle P2 vào refactor scope. Karpathy: "Touch only what needs touching."

## Phase 2 — Group findings into vertical slices

Each refactor task = vertical slice that delivers a working improvement.

❌ Horizontal (build all of one layer): "Rename all variables", "Reorganize all files".
✅ Vertical (each task improves one capability): "Extract FallEventRepository from screen → service layer", "Split god-service `monitoring_service.py` by sub-domain".

## Phase 3 — Define each task

For each task in the plan:

```markdown
### Task R<N>: <short name>

**Audit reference:** finding `F-XXX` from audit report
**Tier:** P0 / P1
**Files in scope:**
- Modify: `<path>:<line range>` — <change>
- Move: `<src>` → `<dst>` (if extraction/restructure)
- Test: `<test path>` — <new or update>

**Out of scope (explicit):**
- ...

**Behavior preservation:**
- [ ] All existing tests pass before refactor (baseline)
- [ ] Same tests pass after refactor (no regression)
- [ ] No new dependency introduced (or: new dep `X` justified by ADR-<NNN>)

**Risk assessment:**
- API contract change? (yes/no — if yes, ADR + cross-repo impact list)
- DB schema change? (yes/no — if yes, migration script path)
- Cross-repo impact? (per `topology.md`)

**Verification:**
```pwsh
# Per stack — copy from /test workflow
flutter test test/features/<area>/  # or pytest, npm test
flutter analyze                       # or lint per stack
```

**Decision log (if applicable):**
- ADR-<NNN>: why this approach over alternatives
```

## Phase 4 — Risk-first ordering

Order tasks:

1. **Behavior-preservation safety net first** — ensure tests cover existing behavior before touching code.
2. **Foundation extractions** — types, DI, shared utilities (downstream depends).
3. **Risk-first** — task with highest unknown → do early, fail-fast learn.
4. **Independent slices** — tasks that don't block each other can be parallel sessions.
5. **Quick wins last** — momentum after harder work done.

## Phase 5 — Output files

### `<repo>/docs/plans/refactor-<module>-YYYY-MM-DD.md`

Full plan with task details, code references, commands, verification commands.

### `<repo>/tasks/todo-refactor-<module>.md`

Compact checklist:

```markdown
# Refactor: <module>

> Plan: docs/plans/refactor-<module>-YYYY-MM-DD.md
> Audit: docs/audits/audit-<module>-YYYY-MM-DD.md

## P0 — Critical (must fix)
- [ ] R1: ...
- [ ] R2: ...

## Checkpoint: P0 complete (run full suite + lint)

## P1 — Important (fix if scope allows)
- [ ] R3: ...
- [ ] R4: ...

## Checkpoint: P1 complete

## Deferred to next iteration
- F-XXX (P2): <finding> — defer reason
- F-YYY (P1): <finding> — defer reason (e.g., requires ADR for new pattern)
```

## Phase 6 — Cross-repo handoff (if applicable)

If refactor affects multiple repos:
- Switch to `/cross-repo-feature` workflow for sequencing.
- This workflow handles single-repo refactor.

## Phase 7 — Decision log

If refactor introduces new pattern, library, or convention → write ADR via skill `decision-log`:
- ADR-<NNN>: why this refactor approach.
- Reference in plan + commit message.

## Phase 8 — Self-review + commit

```pwsh
git -C <repo> add docs/plans/refactor-<module>-<date>.md tasks/todo-refactor-<module>.md
git -C <repo> commit -m "docs(refactor): kế hoạch refactor <module>"
```

Notify user:
> "Refactor plan done. Plan at `<repo>/docs/plans/refactor-<module>-<date>.md`, todo at `<repo>/tasks/todo-refactor-<module>.md`. R<N> tasks total. Want to start R1, or review first?"

## Phase 9 — Execute

Run `/build` task by task. Each task follows TDD cycle.

For each commit on refactor branch:
- Subject: `refactor(<scope>): <mô tả tiếng Việt>`
- Body: reference audit finding `F-XXX`

## Anti-patterns

| Pattern | Why bad |
|---|---|
| Bundle P2 findings into refactor scope | Scope creep — refactor should fix concrete pain, not improve aesthetics |
| Skip baseline tests | Can't tell if refactor preserved behavior |
| Refactor + add new feature in same task | Hard to review, can't revert refactor without losing feature |
| "While I'm here" rename in 5 unrelated files | Stay surgical |
| Skip ADR when introducing new pattern | Future-you re-debates |
| Refactor branch gets merged with failing tests | Defeats the purpose |

## Output

- ✅ Plan file with R-tasks ordered by risk + dependency
- ✅ Todo file with checkpoints
- ✅ Each task has verification command
- ✅ Out-of-scope explicit per task
- ✅ ADR written if new pattern introduced
- ✅ User has clear handoff to `/build`
