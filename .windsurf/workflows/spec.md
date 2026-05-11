---
description: Create a PRD/spec for a new feature — discover requirements, propose 2-3 approaches, write design doc.
---

# /spec — Specification-Driven Development

> "Plan the work, then work the plan."

Build a clear spec **before** writing code. Align on requirements, constraints, acceptance criteria.

## Pre-flight

1. **Invoke skill `brainstorming`** — that's the primary skill for this workflow. Follow its checklist.
2. **Read `plan.md` + `AGENTS.md` + `docs/specs/`** to understand context and prior specs.
3. **Ensure a clean branch** — `git status` shows no uncommitted intentional changes.

## Phase 1 — Discovery (one question at a time)

Ask the user one question at a time, prefer multiple-choice:

**Scope:**
- What user pain point does this feature solve?
- Who is the primary user?
- What's the smallest MVP scope? What's OUT-OF-SCOPE for this iteration?

**Acceptance:**
- Main user flow: step 1 → 2 → 3 → ...?
- Important edge cases (offline, no permission, throttling, abuse)?
- What does "done" look like? What can be demoed to the user?

**Technical:**
- Any Firebase tier constraint (Spark vs Blaze)?
- Any specific data privacy concern (PII, location)?
- Integration with existing features?

## Phase 2 — Propose 2-3 approaches

Lead with your recommendation. Format:

```markdown
**Approach A (recommended):** [short name]
- Pros: ...
- Cons: ...
- Effort: ...

**Approach B:** [short name]
- Pros: ...
- Cons: ...

**Approach C:** [short name — if any]
- ...
```

Wait for the user to choose.

## Phase 3 — Generate the spec doc

Save to `docs/specs/YYYY-MM-DD-<feature-slug>.md` with this template:

```markdown
# Spec: [Feature Name]

**Date:** YYYY-MM-DD
**Status:** Draft → Approved → Implemented
**Owner:** the user (solo)

## Goal
[1-2 sentences: what the feature does, what problem it solves]

## User stories
- As a [role], I want [action], so that [outcome].
- ...

## Scope

### In-scope (MVP)
1. [Feature A] — Acceptance: [specific criterion]
2. [Feature B] — Acceptance: [specific criterion]

### Out-of-scope (later iterations)
- [thing NOT in this phase]

## Technical approach

### Architecture
[ASCII/text diagram or 2-3 sentences]

### Data model
- Firestore collections: ...
- Storage paths: ...
- Local cache (SharedPreferences / Hive / SQLite): ...

### API / contract
[Cloud Function signature, endpoint, or Firestore query shape]

### Dependencies
- New Flutter packages: [name + version + reason]
- Firebase services: [Auth/Firestore/Storage/FCM/Functions]

## Security
- Firestore rule changes: [which collection, new rule]
- Storage rule changes: ...
- PII handling: ...
- Rate limit / abuse prevention: ...

## Testing strategy
- Unit: [areas + ~target coverage]
- Widget: [critical UI flows]
- Integration / E2E: [main user flow]
- Firestore rules tests: [scenarios]

## Boundaries

### Always do
- [non-negotiable — e.g. "validate caption length", "use serverTimestamp"]

### Ask first (decisions that need user approval)
- [e.g. "when caption > 200 chars: truncate or reject?"]

### Never do
- [hard constraint — "don't cache full-size images > 100 on device"]

## Open questions
- [unresolved, needs research]

## Risks
- [technical, performance, cost]
```

## Phase 4 — Self-review & user gate

1. **Self-review** (per skill `brainstorming`): placeholders, contradictions, scope, ambiguity.
2. **Commit the spec:**
   ```bash
   git add docs/specs/<file>.md
   git commit -m "docs(spec): add <feature> design"
   ```
3. **Notify the user:**
   > "Spec done, committed at `docs/specs/<file>.md`. Please review; let me know what to change before we move on to /plan."
4. **Wait for approval.**

## Phase 5 — Transition

Once approved → suggest running `/plan` to break it into tasks.

## Output

- ✅ `docs/specs/YYYY-MM-DD-<feature>.md` committed.
- ✅ Chosen approach has clear reasoning.
- ✅ Acceptance criteria are measurable.
- ✅ Out-of-scope is explicit.
