---
description: Self-review code before merging — 5 axes (correctness, readability, architecture, security, performance).
---

# /review — Five-Axis Code Review

> "15 minutes of self-review saves 30 minutes of debugging + 2 hours of rollback."

Workflow for reviewing already-written code (your own commit / branch / PR) before merge.

> ⚠️ **Thứ tự bắt buộc:** `/build` (implement + commit) → `/review` (self-review) → `gh pr create` (tạo PR). KHÔNG tạo PR trước khi `/review` sạch.

## Pre-flight

1. **→ Invoke skill `code-review-five-axis`** — full 5-axis framework + checklist + severity levels + output format.
2. **Identify scope** of the review:
   - Self-review: `git diff develop...HEAD` or `git diff <base-sha>...HEAD`
   - PR review: clone the branch, read the full diff.

## Phase 1 — Read context

1. **Spec/plan** — `docs/specs/<feature>.md` + `docs/plans/<feature>.md`. Does the code match acceptance criteria?
2. **Commit messages** — what did the author intend?
3. **Diff overview:**
   ```bash
   git diff develop...HEAD --stat
   git log develop..HEAD --oneline
   ```
4. **Map changed files** to layers (data / application / presentation / config / rules / functions).

## Phase 2 — Run automated checks

Let the machine do the easy part FIRST. Any warning/error → flag and pause detailed review.

```bash
# Flutter
cd apps/mobile
flutter analyze
flutter test
dart format --set-exit-if-changed .

# Functions / BE
cd firebase/functions
npm run lint
npm test
```

## Phase 3 — Manual 5-axis pass

**→ Apply skill `code-review-five-axis`** for the 5 axes (Correctness / Readability / Architecture / Security / Performance), full checklist per axis, severity rubric, and output format. Don't re-derive the checklist here.

### Meep-specific things to flag (in addition to the skill checklist)

- **Firestore rule changes:** MUST have new rules unit tests covering owner / friend / stranger / unauthenticated.
- **Cloud Function trigger:** check region (`asia-southeast1`), `maxInstances`, `timeoutSeconds` are explicit.
- **Image / video upload:** size + MIME validated SERVER-SIDE (Storage rules or Function), not just client.
- **PII in logs:** grep `email`, `phoneNumber`, `displayName`, `caption` in `console.log` / `logger.*` / `print` → flag.
- **`--dart-define` env keys:** no key hardcoded in Dart source (`grep -rn 'apiKey\|secret\|token' lib/`).
- **Native widget code (`apps/widget/`):** does it call Firebase directly? It should NOT — only read locally cached data.
- **Naming:** does the diff use the canonical terms from `CONTEXT.md`? (`uid`, `pairId`, `Post`, `home-screen widget`, etc.)

## Phase 4 — Output

Use the format from skill `code-review-five-axis` (🔴 Critical / 🟡 Important / 🟢 Suggestion / ✅ Highlights + Summary).

## Phase 5 — Action

- 🔴 or 🟡 → return to `/build` or `/fix-issue`. After fix → re-review the delta only.
- All clean → merge / approve.

## Quick checklist before commit (mini-review for small commits)

For each routine commit, no need for full 5-axis pass — just verify:

- [ ] Tests pass (ran the command, read the output).
- [ ] Lint clean (`flutter analyze` / `npm run lint` exit 0).
- [ ] Diff focused — only changes for this task.
- [ ] No `console.log` / `print` debug left over.
- [ ] No commented-out dead code.
- [ ] No `// TODO` without a linked issue.
- [ ] Commit message conventional + describes **why** for non-obvious changes.

## Anti-patterns

| Anti-pattern | Problem |
|---|---|
| "Looks good to me" without reading | Rubber-stamp catches no bugs |
| Bikeshedding naming when there's an unresolved 🔴 | Loses focus |
| Suggesting whole-module rewrite in a small PR | Scope creep |
| Blocking PR over style preference (`if` vs ternary) | Religious, not shipping |
| Reviewing only syntax | Skips security, perf, architecture |
