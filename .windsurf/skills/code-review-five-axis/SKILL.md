---
name: code-review-five-axis
description: Five-axis code review framework. Use when reviewing your own changes before merge, or reviewing PR. Evaluates correctness, readability, architecture, security, performance.
---

# Code Review — Five-Axis Framework

> Combined from `class-ai-agent/.claude/commands/review.md` + `superpowers/skills/requesting-code-review`. Used for both self-review before opening a PR and reviewing teammates' PRs (anh là default reviewer).

## When to use

- **After finishing a feature task / bug fix**, before commit or PR.
- **Before merging a branch** into `develop` (or `develop` → `deploy` for releases).
- **When stuck** — fresh perspective on the code you just wrote.
- **Before a large refactor** — baseline check.

## 5 evaluation axes

### 1. Correctness — does the code do the right thing?

- [ ] Logic matches the spec/plan acceptance criteria.
- [ ] Edge cases covered: empty, null, max-size, boundary, negative.
- [ ] Error paths handled correctly — no swallowing, no panic.
- [ ] Async / concurrency: no race conditions, no deadlocks.
- [ ] State management: clear source of truth, no stale state.
- [ ] Off-by-one, fence post, timezone, encoding bugs?

**Verify:** re-read the spec → checklist each requirement → trace the code that covers it.

### 2. Readability — will another person (or future-you) understand?

- [ ] Naming describes intent, not implementation detail (`fetchUserById` ✓, `doDbStuff` ✗).
- [ ] Functions/methods are small, single-responsibility (≤ 50 lines baseline).
- [ ] Magic numbers → named constants.
- [ ] Comments explain **why** (not **what** — the code already says what).
- [ ] No "clever" code that takes work to decode — Dart/TS have nice syntax, use it.
- [ ] Files < 300 lines, or there's a clear reason they're long.

### 3. Architecture — does the code fit the system?

- [ ] Clear layering: data → application → presentation. UI doesn't call Firestore directly.
- [ ] Dependency direction is right: feature imports shared, not the reverse.
- [ ] Reuses existing patterns rather than introducing ad-hoc new ones.
- [ ] Boundaries through interfaces — can the implementation be swapped?
- [ ] DI is explicit — no hidden singletons, no global mutable state.
- [ ] No premature abstraction (single-implementation interface, factory without reason).

### 4. Security — any holes?

- [ ] No hardcoded secrets / API keys.
- [ ] User input validated thoroughly (zod / form validator). Don't trust the client.
- [ ] Authentication check on every protected endpoint / Firestore rule.
- [ ] Authorization check enforces ownership (`isOwner(uid)`) — not just "is authenticated".
- [ ] PII not logged to console / Crashlytics / production logs.
- [ ] SQL/NoSQL injection (parametrized queries, no string concat).
- [ ] XSS (sanitize HTML user-generated before render).
- [ ] File upload: check MIME + size **server-side**.
- [ ] Rate limiting on auth endpoints.

### 5. Performance — is the code fast and cheap enough?

- [ ] No N+1 queries (Firestore: 1 query for 50 users instead of 50 queries for 1 user).
- [ ] Pagination on large lists — no `.get()` of the whole collection.
- [ ] Images: resized before upload, lazy-loaded, cached (`cached_network_image`).
- [ ] Firestore: indexes exist for every compound query.
- [ ] Cloud Function cold start: dependencies are light, expensive imports lazy.
- [ ] Flutter: `const` constructors, `ListView.builder`, no rebuilds of the whole tree.
- [ ] Memory: stream subscriptions disposed, controllers disposed.
- [ ] Network: retries with backoff, sensible timeouts.

## Output format

Report by severity:

- 🔴 **Critical** — must fix before merge. Bugs, security holes, breaking changes.
- 🟡 **Important** — should fix before merge. Performance issues, maintainability.
- 🟢 **Suggestion** — nice-to-have. Naming, DRY, micro-optimization.
- ✅ **Good** — highlight what was done well (preserves morale, reinforces good patterns).

Example:

```markdown
## Code Review: PostRepository

### 🔴 Critical
- `createPost` doesn't validate `authorId` ≠ null before the query → crash if the user logs out racing with upload. Fix: throw `AppError.unauthenticated()` early.

### 🟡 Important
- Field `imageUrl` is stored raw from the client. If the client sends a URL outside Firebase Storage (third-party CDN) → loss of control. Suggest: validate the prefix `gs://meep-prod.appspot.com/` or upload via a Function.

### 🟢 Suggestion
- Magic string `'posts'` appears 3 times. Extract `static const _collection = 'posts'`.

### ✅ Good
- Tests cover empty caption, max length, server timestamp.
- Clear naming `createPost` instead of `add`.
```

## Anti-patterns in review

| Anti-pattern | Problem |
|---|---|
| "Looks good to me" without reading carefully | Rubber-stamp = no review |
| Bikeshedding naming when there's an unresolved 🔴 | Loses focus on the real issue |
| Suggesting a rewrite of a whole module in a small PR | Scope creep |
| Blocking PRs over style preference (`if` vs ternary) | Going religious, not shipping |

## Cross-skill / when to use vs others

| Need | Use |
|---|---|
| Quick PR/commit self-review (5-min checklist) | This skill |
| Feature deep audit with 8-criteria score + Vietnamese report (cho stakeholder) | `detailed-feature-review` skill |
| Module-level code health audit | `/audit` workflow |
| Project-level overview (entire admin or mobile) | `TongQuan` skill |
| Sync PM_REVIEW docs với code reality | `CHECK` skill |

## Self-review = ship faster

15 minutes of self-review saves:

- 30 minutes of debugging post-merge.
- 2 hours of rollback if it breaks prod.
- Reputation with the team.

## Quick checklist (run fast before commit)

```
[ ] Tests pass: ran the command, read the output (skill `verification-before-completion`)
[ ] Lint clean: `flutter analyze` / `npm run lint` exit 0
[ ] No commented-out dead code blocks
[ ] No console.log / print debug statements left over
[ ] No TODO without a linked issue
[ ] Diff focused — only changes for this task, no "while I'm here" 5-file edits
[ ] Commit message is conventional + describes WHY
```
