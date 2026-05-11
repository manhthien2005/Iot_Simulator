---
name: tdd
description: Test-Driven Development discipline. Use when implementing any feature or bugfix BEFORE writing implementation code. Enforces RED-GREEN-REFACTOR cycle with mandatory failing-test verification.
---

# Test-Driven Development (TDD)

> Adapted from `superpowers/skills/test-driven-development`. Trimmed for solo Flutter/TS workflow.

## Core principle

**Write the test first. Watch it fail. Write minimal code to pass.**

If you didn't watch the test fail, you don't know if it tests the right thing.

## The Iron Law

```
NO PRODUCTION CODE WITHOUT A FAILING TEST FIRST
```

Wrote code before the test? Delete it. Start over from the test.

**Exceptions (must ask the user first):**
- Throwaway prototype.
- Generated code (codegen, freezed, json_serializable).
- Config files.

"Skip TDD just this once" = rationalization. Stop.

## Red-Green-Refactor

### 1. RED — Write a failing test

```dart
// Flutter example
test('rejects post with empty caption', () async {
  final controller = PostController(repo: FakePostRepository());
  final result = await controller.createPost(caption: '', imageUrl: 'x.jpg');
  expect(result.isFailure, true);
  expect(result.error, isA<EmptyCaptionError>());
});
```

```ts
// Functions / BE example
test('returns 400 when authorId missing', async () => {
  const res = await request(app).post('/posts').send({ caption: 'hi' });
  expect(res.status).toBe(400);
  expect(res.body.error).toBe('authorId required');
});
```

**Requirements:**
- One behavior per test.
- A clear name (describes behavior, not implementation).
- Real-ish code where possible (`fake_cloud_firestore`, in-memory fakes — not full mocking of everything).

### 2. Verify RED — run the test, watch it fail

```bash
flutter test test/features/feed/post_controller_test.dart
# or
npm test -- post_controller.test.ts
```

**Confirm:**
- The test FAILS (not errors out due to a typo).
- The failure message matches what you expect.

**Test passes immediately?** You're testing existing behaviour. Rewrite the test.
**Test errors out?** Fix the typo, re-run until it fails for the right reason.

### 3. GREEN — minimum code to pass

Write only enough code for the test to pass. No extra options, no abstractions, no "for later" code.

```dart
class PostController {
  Future<Result<Post, AppError>> createPost({
    required String caption,
    required String imageUrl,
  }) async {
    if (caption.isEmpty) return Result.failure(EmptyCaptionError());
    // ... minimal happy path
  }
}
```

### 4. Verify GREEN — test passes + nothing else broke

```bash
flutter test  # full suite
```

- New test passes ✓
- Old tests still pass ✓
- Output is clean (no warnings, no error logs)

### 5. REFACTOR — clean up while green

- Rename for clarity, extract helpers, remove duplication.
- **No new behaviour during refactor.**
- Tests stay green after every refactor step.

### 6. Commit

```bash
git add tests/... lib/...
git commit -m "feat(feed): reject empty caption in createPost"
```

### 7. Loop

Next failing test for the next behaviour.

## Bug fix → reproduction test

1. **Write the test that reproduces the bug** first (don't touch the code).
2. **Run** → confirm FAIL with the right symptom.
3. **Fix** the code → run → PASS.
4. **Revert the fix** → run → FAIL (proof the test actually catches the bug).
5. **Restore the fix** → run → PASS.
6. Commit.

Skip step 4 → the test might pass for the wrong reason.

## When stuck

| Problem | Direction |
|---|---|
| Don't know how to test something | Write the wished-for API first. "I want this function to look like ..." then test that. |
| Test setup is too complex | Design is too coupled. Inject dependencies, use repository pattern. |
| Need to mock everything | Code coupling is high. Use DI + in-memory fakes instead of mocks. |
| Async timing issues | Use `pumpAndSettle()`, `expectLater(future, completes)`, polling — never `Future.delayed`. |

## Verification checklist before claiming "done"

- [ ] Each new function/method has at least one test.
- [ ] You watched each test fail before writing the implementation.
- [ ] Each failure was due to a missing feature, not a typo / setup error.
- [ ] Implementation is minimal — no "for later" branching.
- [ ] Full suite passes.
- [ ] Output is clean (no warnings, no error logs outside what tests assert).
- [ ] Edge cases covered (empty, null, max-size, error path).

Can't tick all? You skipped TDD. Go back.
