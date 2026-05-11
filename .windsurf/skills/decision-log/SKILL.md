---
name: decision-log
description: Use when making an architectural or design decision (choosing approach A over B, adopting library, changing convention, defining cross-repo contract). Records context + options + decision + consequences in PM_REVIEW/ADR for future-self and other sessions to read.
---

# Decision Log (ADR-lite) — Cross-Session Memory of Why

> **Why this skill exists:** Decisions made today are forgotten next session. Without a log, AI re-asks the same question, or worse, silently picks a different option. ADR records the WHY behind every non-trivial choice.

## When to invoke

**MUST log** when:
- Choosing approach A over B (with C as alternative).
- Adopting a new library/framework/pattern.
- Changing a project-wide convention (naming, branching, commit format).
- Defining a cross-repo contract (API shape, internal secret scheme).
- Reversing a previous decision.
- Making a trade-off (security vs UX, perf vs simplicity).

**Skip** for:
- Local micro-choices (variable name, single function structure).
- Following established convention (already decided in earlier ADR).
- Trivial defaults (`max_length=200` because field is reasonable).

## ADR ID convention

Sequential, 3-digit, system-wide (NOT per repo — decisions are project-level).

Format: `<NNN>-<short-kebab-title>.md`

Examples:
- `001-workspace-tooling-host.md`
- `002-bug-log-location.md`
- `015-prediction-contract-versioning.md`

## File location

```
PM_REVIEW/ADR/
├── INDEX.md            # GPS — all decisions chronological + by tag
├── _TEMPLATE.md        # Copy to start a new ADR
├── 001-workspace-tooling-host.md
├── 002-bug-log-location.md
└── ...
```

## Workflow when making a decision

### Step 1 — Check if related decision exists

```pwsh
# Search by tag/keyword
Get-ChildItem 'd:\DoAn2\VSmartwatch\PM_REVIEW\ADR' -Filter '*.md' -Exclude 'INDEX.md','_TEMPLATE.md' | 
  Select-String -Pattern '<keyword>' -List

# Or read INDEX.md tag table
Get-Content 'd:\DoAn2\VSmartwatch\PM_REVIEW\ADR\INDEX.md'
```

If a related ADR exists:
- Reading + reusing > deciding fresh.
- If it conflicts with current need → write new ADR that **supersedes** the old one (link both ways).

### Step 2 — Frame the decision

Before writing, articulate:
- **Context:** what problem requires a decision now?
- **Constraints:** non-negotiable factors (existing stack, time, skill).
- **Options:** at least 2, ideally 3.
- **Trade-offs:** explicitly compare.

### Step 3 — Determine next ADR number

```pwsh
$adrDir = 'd:\DoAn2\VSmartwatch\PM_REVIEW\ADR'
$existing = Get-ChildItem $adrDir -Filter '[0-9]*-*.md' | Sort-Object Name -Descending | Select-Object -First 1
$nextNum = if ($existing) {
  [int]($existing.BaseName -split '-')[0] + 1
} else { 1 }
$nextId = '{0:D3}' -f $nextNum
```

### Step 4 — Create ADR file

```pwsh
$slug = '<short-kebab-title>'
$file = "$adrDir\$nextId-$slug.md"
Copy-Item "$adrDir\_TEMPLATE.md" $file
```

Fill in:
- Status: `Proposed` (waiting user approval) → `Accepted` (decided) → later `Superseded by NNN`
- Date
- Context + Decision + Consequences

### Step 5 — Update INDEX.md

Add row to chronological table + tag table.

## Template (see `_TEMPLATE.md` for actual file)

```markdown
# ADR-<NNN>: <Short title>

**Status:** Proposed / Accepted / Superseded by <NNN>
**Date:** YYYY-MM-DD
**Decision-maker:** ThienPDM (solo)
**Tags:** [workspace, tooling, mobile, backend, security, ...]

## Context

What's the situation? What forces are at play (technical, organizational, time-bound)?

Reference UC/Spec if applicable: UC<XXX>, `<repo>/docs/specs/<file>.md`.

## Decision

**Chose:** <Option name>

**Why:** <1-3 paragraphs — the reasoning>

## Options considered

### Option A (chosen): <name>
- Pros: ...
- Cons: ...
- Effort: ...

### Option B (rejected): <name>
- Pros: ...
- Cons: ...
- **Why rejected:** ...

### Option C (rejected, if any): <name>
- ...

## Consequences

**Positive:**
- ...

**Negative / Trade-offs accepted:**
- ...

**Follow-up actions required:**
- [ ] ...
- [ ] ...

## Reverse decision triggers

Conditions under which this decision should be reconsidered:
- If <X> changes (e.g., team grows beyond 1 dev → reconsider PM_REVIEW hosting)
- If <Y> becomes unacceptable (e.g., audit log size > 10GB → split table)

## Related

- UC: UC<XXX>
- ADR: supersedes <NNN> / superseded by <NNN>
- Bug: triggered by <BUG-ID>
- Code: enforces in `<file>:<line>`
```

## INDEX.md format

```markdown
# ADR Index

## Chronological

| # | Title | Status | Date | Tags |
|---|---|---|---|---|
| 001 | Workspace tooling host | Accepted | 2026-05-11 | workspace, tooling |
| 002 | Bug log centralized in PM_REVIEW | Accepted | 2026-05-11 | workspace, anti-loop |
| 003 | ... | ... | ... | ... |

## By tag

### workspace
- 001-workspace-tooling-host
- 002-bug-log-centralized

### security
- 008-jwt-refresh-rotation
- 012-phi-encryption-at-rest

### mobile
- 015-prediction-contract-versioning
- ...
```

## Anti-patterns

| Anti-pattern | Why bad |
|---|---|
| Decision made, no ADR | Future-you re-asks; AI re-proposes alternatives |
| ADR with only "decision", no "options considered" | Can't tell if alternatives were evaluated |
| ADR with "we chose A because it's better" | Useless — better at WHAT? quantify |
| Update existing ADR's content (not status) | Lose history. New ADR supersedes instead |
| Skip "Reverse decision triggers" | Decision becomes religious — can't reconsider |
| Tag everything as `general` | Tags must be searchable signal |

## Solo dev + ADR

> **"Em là solo dev, có cần ADR không?"** YES. ADR is FOR future-you (next month) + AI sessions. Without it, you'll re-litigate the same trade-off 3 times across 6 months.

Keep it light: 1 page max for most ADRs. The point is record + searchable, not perfect prose.

## Integration

Referenced by:
- Rule `60-context-continuity.md` — declares ADR location
- Workflow `/spec` Phase 4 — add ADR ref if architectural decision made
- Workflow `/build` final step — log decision if approach chosen
- Workflow `/refactor-module` — log refactor rationale (M4 deliverable)
