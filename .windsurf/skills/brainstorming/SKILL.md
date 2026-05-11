---
name: brainstorming
description: Use BEFORE writing spec or code for new features. Explores user intent, constraints, and 2-3 design approaches through one-question-at-a-time dialogue. Required before /spec.
---

# Brainstorming Ideas Into Designs

> Adapted from `superpowers/skills/brainstorming`. Trimmed for small-team capstone (no subagent dispatch, no visual companion).

Help turn ideas into fully formed designs through natural collaborative dialogue. Workflow: agent + user (anh, team leader), no subagents. Output spec sẽ được team đọc — viết rõ ràng cho human reviewer, không chỉ cho agent.

## Hard gate

**Do not invoke skill implementations, do not write code, do not scaffold a project, do not take ANY implementation action** until a design has been presented and the user has approved it.

This applies to EVERY project, no matter how simple it seems. "It's simple, no design needed" is the most common rationalization → unexamined assumption → wasted work.

The design can be short (a few sentences for a genuinely simple project), but it MUST be presented and approved.

## Checklist — follow in order

1. **Explore project context** — read existing files, `plan.md`, `AGENTS.md`, recent commits.
2. **Ask clarifying questions** — one at a time. Understand purpose / constraints / success criteria.
3. **Propose 2-3 approaches** — clear tradeoffs + your recommendation.
4. **Present the design section by section** — get approval per section.
5. **Write the design doc** — save to `docs/specs/YYYY-MM-DD-<topic>.md` and commit.
6. **Spec self-review** — quick check for placeholders / contradictions / ambiguity (below).
7. **User reviews the final spec** — ask them to read the file.
8. **Transition** → invoke skill `writing-plans`.

## Process

### Understand the idea

- **Check current state** before asking detail questions (files, docs, recent commits).
- **Scope check:** if the request spans multiple independent subsystems (auth + feed + billing + analytics) — flag immediately and suggest decomposing. Each sub-project gets its own spec/plan/build cycle.
- **For the right project size:** ask one question at a time to refine.
- **Prefer multiple-choice questions** when possible — easier for the user to answer.
- **Focus:** purpose, constraints, success criteria — don't ramble.

### Explore approaches

- **Propose 2-3 different approaches** with tradeoffs.
- **Lead with your recommendation** + why.
- Conversational tone; don't tax the user with two paragraph-long options.

### Present the design

- **Scale each section to complexity:** simple → a few sentences; nuanced → 200-300 words max.
- **Ask after each section** "Does this design look right?".
- **Cover:**
  - Architecture (high-level boxes, the main flow)
  - Components (Flutter feature folder, Firestore collections, Function triggers)
  - Data flow / data model
  - Error handling
  - Testing strategy
- Be ready to back up and clarify if something isn't sitting right.

### Design for isolation

- Break the system into small units — each with one clear responsibility, communicating through explicit interfaces, understandable and testable on its own.
- For each unit, you must be able to answer: what does it do, how is it used, what does it depend on?
- A good boundary = file < 300 lines, swappable implementation without breaking consumers.

### Working in an existing codebase

- Explore the structure before proposing.
- Follow existing patterns. Deviate only with a specific reason.
- Don't refactor unrelated code "while you're at it".

## After the design

### Documentation

- Write the spec to `docs/specs/YYYY-MM-DD-<topic>.md`.
- Commit the spec to git: `docs(spec): add <topic> design`.

### Spec self-review (do this before handing it to the user)

1. **Placeholder scan:** "TBD", "TODO", empty sections, vague requirements? → Fix.
2. **Internal consistency:** do sections contradict each other? Does the architecture match the feature description?
3. **Scope check:** focused enough for one implementation plan, or does it need to be decomposed?
4. **Ambiguity check:** any requirement that could be read two ways? → Pick one, make it explicit.

If you find issues, fix them inline. No need for re-review, fix and move on.

### User review gate

After self-review passes, ask the user:

> "Spec written and committed at `<path>`. Please review and let me know what to change before we move on to /plan."

Wait for response. Changes → re-run self-review. Approval → invoke `writing-plans`.

## Implementation

- Invoke skill `writing-plans` to create a detailed implementation plan.
- DO NOT invoke other skills. `writing-plans` is the next step.

## Key principles

- **One question at a time** — don't overwhelm.
- **Multiple choice preferred** — easier than open-ended.
- **YAGNI ruthlessly** — remove unneeded features from every design.
- **Explore alternatives** — always 2-3 approaches before deciding.
- **Incremental validation** — present, approve, move on.
- **Be flexible** — re-clarify if something isn't sitting right.

## Anti-pattern: "It's simple, no design needed"

Every project goes through this process. Todo list, single-function utility, config change — all of them. "Simple" projects are exactly where unexamined assumptions waste the most time. The design can be short, but it MUST exist and MUST be approved.
