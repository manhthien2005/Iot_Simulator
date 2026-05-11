---
description: Decompose an approved spec into bite-sized vertical-slice tasks with exact files, test code, and commands.
---

# /plan — Planning & Task Breakdown

> "Vertical slices, not horizontal layers."

Transform a spec → an ordered list of small verifiable tasks. Each task delivers end-to-end functionality.

## Pre-flight

1. **Invoke skill `writing-plans`** — primary skill. Follow its checklist + template.
2. **Read the spec** at `docs/specs/<feature>.md` (approved).
3. **Check:** does the spec have measurable acceptance criteria? If not → go back to `/spec` and refine.

## Phase 1 — Analysis (read-only)

1. **Read the spec end-to-end.**
2. **Survey the codebase:** which files already exist for this area, what integration points.
3. **Map dependencies:** which task depends on which.

> **Do NOT modify code in this phase.**

## Phase 2 — File structure mapping

Before defining tasks, list:

- Files to **create**: [full path + 1-line responsibility]
- Files to **modify**: [path + line range if known + reason]
- **Test** files: [corresponding test path]

## Phase 3 — Vertical slice ordering

```
❌ Horizontal:
   T1: All Firestore models
   T2: All Cloud Functions
   T3: All Flutter UI

✅ Vertical:
   T1: Create + view one post (model + repo + controller + minimal UI)
   T2: Like a post (FieldValue.increment + button + count display)
   T3: Comment on a post (subcollection + UI + rule)
```

Order tasks by:

1. **Foundation first** — types, DI, shared utilities everything else needs.
2. **Risk-first** — uncertain item early to fail-fast learn.
3. **Dependency order** — respect the graph.
4. **Quick wins** — small tasks first to build momentum.

## Phase 4 — Task definition

Each task uses the template (see skill `writing-plans` for full):

```markdown
### Task N: [Component name]

**Files:**
- Create: `<full path>`
- Modify: `<full path>:<lines>`
- Test: `<full path>`

**Dependencies:** Task X, Y

- [ ] **Step 1: Write failing test**
[exact test code in a code block]

- [ ] **Step 2: Run test → confirm FAIL**
[exact command + expected failure message]

- [ ] **Step 3: Implement minimal**
[exact code]

- [ ] **Step 4: Run test → confirm PASS**
[exact command + expected output]

- [ ] **Step 5: Commit**
[exact git commit command]
```

## Phase 5 — Checkpoints

Insert checkpoints between major phases:

```markdown
---
## Checkpoint: [Phase name] complete

Verify:
- [ ] All tests in this phase pass
- [ ] Lint clean
- [ ] Manual test: [specific scenario]
- [ ] Coverage didn't drop below baseline
---
```

## Phase 6 — Output files

Save **2 files**:

### `docs/plans/YYYY-MM-DD-<feature>.md`

Full plan with task details, code samples, commands. This is the source of truth.

### `tasks/todo-<feature>.md`

Compact actionable checklist:

```markdown
# TODO: [Feature]

> Plan: docs/plans/YYYY-MM-DD-<feature>.md

## Phase 1: Foundation
- [ ] T1.1: ...
- [ ] T1.2: ...

## Checkpoint: Foundation complete

## Phase 2: Core features
- [ ] T2.1: ...
- [ ] T2.2: ...

## Checkpoint: MVP complete

## Phase 3: Polish
- [ ] T3.1: ...
```

## Phase 7 — Self-review

Per skill `writing-plans`:

1. **Spec coverage:** is there a task for each requirement? List gaps.
2. **Placeholder scan:** "TBD", "TODO", "implement later", vague "handle errors". Fix.
3. **Type/name consistency:** function/class names consistent across tasks.

If you find issues, fix them inline.

## Phase 8 — Commit + handoff

```bash
git add docs/plans/<file>.md tasks/todo-<feature>.md
git commit -m "docs(plan): break down <feature> into tasks"
```

Notify the user:

> "Plan done. Plan at `docs/plans/<file>.md`, todo at `tasks/todo-<feature>.md`. X tasks total, Y checkpoints. Want me to start Task 1, or do you want to review first?"

## Output

- ✅ `docs/plans/<file>.md` committed.
- ✅ `tasks/todo-<feature>.md` committed.
- ✅ Each task: exact files, exact code/commands, no placeholders.
- ✅ Order respects dependencies + risk.

## Next step

After plan approval → `/build` to execute task by task with TDD.
