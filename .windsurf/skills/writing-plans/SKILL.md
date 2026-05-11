---
name: writing-plans
description: Use when you have an approved spec and need to break it into bite-sized vertical-slice tasks with exact files, test code, and commands. Required before /build for non-trivial features.
---

# Writing Plans

> Adapted from `superpowers/skills/writing-plans`. Trimmed for small-team capstone (no subagent handoff; plan files are read by both agent and human teammates).

Write a comprehensive implementation plan assuming you (or future-you, two weeks later) have zero context. Document everything: which files to touch per task, code, tests, commands.

DRY. YAGNI. TDD. Frequent commits.

## When to use

- A spec exists from `/spec` (or skill `brainstorming`).
- Feature ≥ 3 tasks. Sub-1-task feature → bypass, code directly with TDD.

## Output location

Save the plan to: `docs/plans/YYYY-MM-DD-<feature-name>.md`

Also create `tasks/todo-<feature>.md` with an actionable checkbox list.

## Scope check

Does the spec cover multiple independent subsystems? → suggest breaking it into sub-project plans, each with its own spec → plan. Each plan must produce working, testable software on its own.

## File structure mapping

Before defining tasks, map out the files to be created/modified:

- **Each file has one clear responsibility.** Files that change together → live together. Split by responsibility, not by technical layer.
- **Prefer small focused files** (< 300 lines) over large files doing many things.
- **Existing codebase:** follow patterns. Don't unilaterally restructure.

## Plan document header

Every plan MUST start with:

```markdown
# [Feature Name] Implementation Plan

> **For executor:** Follow the TDD cycle (skill `tdd`). Each step has a checkbox `- [ ]` for tracking.

**Goal:** [1 sentence describing what this builds]

**Architecture:** [2-3 sentences on the approach]

**Tech stack:** [key libs/tech]

**Spec:** `docs/specs/<spec-file>.md`

---
```

## Task granularity (bite-sized)

Each step = 1 action ~2-5 minutes:

- "Write failing test" — step
- "Run test, confirm it fails" — step
- "Implement minimal code to pass" — step
- "Run tests, confirm pass" — step
- "Commit" — step

## Task structure template

```markdown
### Task N: [Component name]

**Files:**
- Create: `apps/mobile/lib/features/feed/data/post_repository.dart`
- Create: `apps/mobile/test/features/feed/post_repository_test.dart`
- Modify: `apps/mobile/lib/features/feed/feed.dart` (add export)

**Dependencies:** Task 1, 2

- [ ] **Step 1: Write failing test**

```dart
test('createPost saves to Firestore with serverTimestamp', () async {
  final repo = PostRepository(firestore: fakeFirestore);
  await repo.createPost(authorId: 'u1', caption: 'hello', imageUrl: 'x.jpg');
  final docs = await fakeFirestore.collection('posts').get();
  expect(docs.docs.length, 1);
  expect(docs.docs.first.data()['createdAt'], isNotNull);
});
```

- [ ] **Step 2: Run test, confirm FAIL**

```bash
flutter test test/features/feed/post_repository_test.dart
```

Expected: FAIL — `PostRepository` not defined.

- [ ] **Step 3: Implement minimal**

```dart
class PostRepository {
  PostRepository({required this.firestore});
  final FirebaseFirestore firestore;

  Future<void> createPost({
    required String authorId,
    required String caption,
    required String imageUrl,
  }) async {
    await firestore.collection('posts').add({
      'authorId': authorId,
      'caption': caption,
      'imageUrl': imageUrl,
      'createdAt': FieldValue.serverTimestamp(),
    });
  }
}
```

- [ ] **Step 4: Run test, confirm PASS**

```bash
flutter test test/features/feed/post_repository_test.dart
```

Expected: PASS 1/1.

- [ ] **Step 5: Commit**

```bash
git add apps/mobile/lib/features/feed/ apps/mobile/test/features/feed/
git commit -m "feat(feed): add PostRepository.createPost"
```
```

## No placeholders — plan failure

Don't write any of these. Every step MUST have real content:

- "TBD", "TODO", "implement later", "fill in details"
- "Add appropriate error handling" / "add validation" / "handle edge cases" — write the exact code
- "Write tests for the above" — write the actual test code
- "Similar to Task N" — repeat the code; the executor may read out of order
- Steps that describe what without showing how — code blocks are mandatory for code steps
- References to types/functions/methods not defined in any task

## Vertical slice ordering

Order tasks by:

1. **Foundation first** — config, types, shared utilities, DI setup.
2. **Risk-first** — uncertain/complex items early to fail-fast learn.
3. **Dependencies** — respect the dependency graph.
4. **Quick wins** — momentum from small tasks first.

```
❌ Horizontal (anti-pattern):
   Task 1: Create all DB schemas
   Task 2: Create all APIs
   Task 3: Create all UI

✅ Vertical (correct):
   Task 1: User can create one post (Firestore + repo + controller + UI)
   Task 2: User can view the feed (query + UI)
   Task 3: User can like a post (FieldValue.increment + UI)
```

## Checkpoints

Insert between major phases:

```markdown
---
## Checkpoint: Auth flow complete

**Verify before proceeding:**
- [ ] Login email + Apple + Google work
- [ ] Logout clears cache
- [ ] Auth state persists across restart
- [ ] Test coverage ≥ 70% for the auth feature
- [ ] Manual test: cold start → login → kill app → reopen → still logged in
---
```

## Self-review before committing the plan

After writing the plan, reread with fresh eyes:

1. **Spec coverage:** skim each spec section / requirement. Is there a task implementing each? List gaps.
2. **Placeholder scan:** search the plan for the red-flag patterns from "No Placeholders". Fix.
3. **Type/name consistency:** function named `clearLayers()` in Task 3 but `clearFullLayers()` in Task 7 = bug. Check naming consistency throughout.

If you find issues, fix them inline. If you find a spec requirement with no task, add the task.

## Execution handoff

Plan written and saved → notify the user:

> "Plan saved to `docs/plans/<file>.md`. I'm ready to start with Task 1. Want me to run, or do you want to review first?"

Once approved → invoke skill `tdd` + execute task by task. Update `tasks/todo-<feature>.md` checkboxes after each task.

## Remember

- Exact file paths, every time.
- Complete code per step — if a step changes code, show the code.
- Exact commands with expected output.
- DRY, YAGNI, TDD, frequent commits.
