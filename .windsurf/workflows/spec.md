---
description: Create or update spec for a VSmartwatch feature — UC-driven, propose 2-3 approaches, link JIRA + DB.
---

# /spec — Specification-Driven Development (VSmartwatch)

> "Plan the work, then work the plan."

Build a clear spec **before** writing code. Align on requirements, constraints, acceptance criteria. Use the existing UC infrastructure in PM_REVIEW.

## Pre-flight

1. **Invoke skill `brainstorming`** — primary skill.
2. **Locate existing UC** — VSmartwatch has 26 UCs at `PM_REVIEW/Resources/UC/<Module>/UC<XXX>.md`. Check before creating new.
   ```pwsh
   ls PM_REVIEW/Resources/UC/<Module>/
   ```
3. **Read related context:**
   - `PM_REVIEW/MASTER_INDEX.md` — project GPS
   - `PM_REVIEW/Resources/SRS_INDEX.md` — system context
   - Existing UC if exists
   - Related JIRA Epic at `PM_REVIEW/Resources/TASK/JIRA/Sprint-N/<Epic>/STORIES.md`
   - Related SQL schema at `PM_REVIEW/SQL SCRIPTS/`
4. **Clean branch** — `git status` no uncommitted intentional changes.

## Phase 1 — Discovery (one question at a time)

### Scope questions

- What user pain point does this feature solve?
- Primary actor (user role): elderly patient / family monitor / admin / clinician?
- Smallest MVP scope? What's OUT-OF-SCOPE for this iteration?
- Cross-repo impact: feature touches mobile only, backend only, or full pipeline (mobile + BE + admin + IoT sim + model)?

### Acceptance questions

- Main flow: step 1 → 2 → 3 → ...?
- Edge cases:
  - Network loss (mobile especially — health-critical)
  - Permission denied / token expired
  - Concurrent sessions (linked profiles)
  - Device offline / sensor reading stale
- "Done" demoable to user?

### Technical questions

- DB changes? New table or column? → must update `PM_REVIEW/SQL SCRIPTS/` canonical.
- API contract change? → who consumes it (verify cross-repo per `topology.md`).
- PHI (Personal Health Information) handling? → encryption at rest/transit, audit log requirement.
- Push notification flow? → FCM payload shape, foreground/background behavior.
- ML model dependency? → version, fallback if model API down.

## Phase 2 — Propose 2-3 approaches

Lead with recommendation. Format:

```markdown
**Approach A (recommended):** [short name]
- Pros: ...
- Cons: ...
- Effort: [S/M/L — hours]
- Cross-repo impact: [list repos]

**Approach B:** [short name]
- Pros / Cons / Effort

**Approach C:** [if any]
- ...
```

Wait for user to choose.

## Phase 3 — Write/Update UC + spec

### If new feature → create UC

Path: `PM_REVIEW/Resources/UC/<Module>/UC<XXX>.md`. Module folders: Authentication, Monitoring, Emergency, Analysis, Sleep, Admin, Notification, Device.

UC format (follow PM_REVIEW template — Vietnamese section headers):

```markdown
# UC<XXX>: <Tên use case>

## Spec table

| Field | Value |
|---|---|
| UC ID | UC<XXX> |
| Name | <Tên> |
| Actor | <User role> |
| Primary Goal | <1 dòng> |
| Priority | High / Medium / Low |
| Module | <Module> |
| Platform | Mobile / Admin / Both |

## Pre-conditions
- ...

## Main Flow

| Step | Actor | System |
|---|---|---|
| 1 | ... | ... |
| ... | | |

## Alternative Flows

### Alt 1: <Tên> (from step X)
1. ...

## Business Rules
- BR-XXX-01: <rule>
- ...

## Non-Functional Requirements
- Performance: <e.g., response < 200ms>
- Security: <e.g., JWT required, audit log>
- Usability: <e.g., elderly-friendly UI, min 16sp font>

## Data Fields
- <field>: <type> — <source table>

## Related
- SRS: HG-FUNC-XX
- JIRA: <Epic-Code>
- DB tables: <list>
```

### Write supplementary spec doc (architectural detail)

Save: `<repo>/docs/specs/YYYY-MM-DD-<feature-slug>.md`

```markdown
# Spec: <Feature>

**Date:** YYYY-MM-DD
**Status:** Draft → Approved → Implemented
**Owner:** ThienPDM (solo)
**UC ref:** UC<XXX>

## Goal
[1-2 sentences]

## User stories
- As a [role], I want [action], so that [outcome].

## Scope

### In-scope (MVP)
1. [Feature A] — Acceptance: [specific criterion measurable]
2. [Feature B] — ...

### Out-of-scope (later)
- [thing NOT in this iteration]

## Technical approach

### Architecture
[ASCII diagram or 2-3 sentences — show data flow across repos if cross-repo]

### Data model
- Postgres tables (per `PM_REVIEW/SQL SCRIPTS/`):
  - `<table>` — fields: ...
- Cache (mobile local DB): ...

### API contract

**Endpoint:** `POST /api/mobile/<resource>` (or admin/internal)
**Auth:** JWT user / JWT admin / X-Internal-Secret
**Request:**
```json
{ "field": "..." }
```
**Response 200:**
```json
{ "field": "..." }
```
**Error:** 400 (validation) / 401 (auth) / 404 (not found) / 500 (internal — sanitized)

### Cross-repo impact
| Repo | Change | Owner |
|---|---|---|
| health_system/backend | New endpoint POST /api/mobile/... | ... |
| health_system/lib | New repository call + UI | ... |
| HealthGuard/backend | (no change) | ... |
| ...

### Dependencies
- New packages: [name + version + reason]
- ML model: [model API version, fallback]

## Security
- Auth: [JWT user / admin / internal]
- PHI handling: [encrypt at rest? mask in logs?]
- Audit log: [which action, what fields]
- Rate limit: [endpoint-specific limit]

## Testing strategy
- Unit (per stack): [areas + ~target coverage]
- Integration: [scenarios]
- E2E (cross-repo): [main flow]
- Manual smoke: [critical user-visible test]

## Boundaries

### Always do
- [non-negotiable — e.g., "validate sensor reading magnitude", "use parameterized SQL"]

### Ask first (decision needs user approval)
- [e.g., "if confidence < 0.5: discard or store?"]

### Never do
- [hard constraint — "don't log raw vital values"]

## Open questions
- [unresolved, needs research]

## Risks
- [technical, performance, cost, schedule]

## ADR reference
- If architectural decision was made, link to `PM_REVIEW/ADR/<num>-<topic>.md`
```

## Phase 4 — Self-review + user gate

1. **Self-review** (per skill `brainstorming`):
   - Placeholders, contradictions, ambiguity
   - Scope leaks (in-scope contains out-of-scope hint?)
   - Cross-repo impact complete?
   - UC has measurable acceptance criteria?

2. **Commit:**
   ```pwsh
   git -C PM_REVIEW add Resources/UC/<Module>/UC<XXX>.md
   git -C <repo> add docs/specs/<file>.md
   git -C <repo> commit -m "docs(spec): thêm spec cho <feature> (UC<XXX>)"
   ```

3. **Notify user:**
   > "Spec done. UC at `PM_REVIEW/Resources/UC/<Module>/UC<XXX>.md`, design at `<repo>/docs/specs/<file>.md`. Review trước khi /plan."

4. **Wait for approval.**

## Phase 5 — Transition

Once approved → suggest:
- Run `/plan` to break into vertical-slice tasks.
- Or `/build` directly if scope ≤ 1-2 tasks.

## Output

- ✅ UC created/updated in PM_REVIEW (if new functionality)
- ✅ Design doc committed in `<repo>/docs/specs/`
- ✅ Approach has clear reasoning (no random pick)
- ✅ Acceptance criteria measurable
- ✅ Cross-repo impact mapped
- ✅ Out-of-scope explicit
