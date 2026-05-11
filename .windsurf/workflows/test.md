---
description: Write or extend tests (unit / widget / integration / Firestore rules) following TDD pattern.
---

# /test — Test-Driven Development

> "Tests are proof, not afterthought."

Use this workflow when:

- Adding tests for existing code (legacy, prototype).
- Writing tests for a bug fix (regression test).
- Auditing coverage and adding tests for gaps.

> **For writing tests for a new feature you're coding:** use `/build` (the TDD cycle is included).

## Pre-flight

1. **Invoke skill `tdd`** — full discipline.
2. **Identify scope:** which file/function/feature needs tests?
3. **Check current coverage** (if applicable):
   ```bash
   flutter test --coverage
   # genhtml coverage/lcov.info -o coverage/html  (optional)
   ```

## Pattern by case

### A. Tests for existing code (none yet)

1. **Read the code** — understand current behavior.
2. **List behaviors** to test: happy path, edge case, error path.
3. **For each behavior:**
   - Write the test → run → confirm it FAILS if the code has a bug, or PASSES if the code is correct.
   - **If it PASSES immediately:** that's a characterization test (locking in current behavior). OK, but don't claim correctness has been proved.
   - **If it FAILS:** you've discovered a bug → invoke skill `systematic-debugging`.

### B. Regression test for a bug fix

**→ Apply skill `tdd`** "Bug fix → reproduction test" section for the full cycle (write failing test → verify FAIL → fix → verify PASS → revert fix → verify FAIL again → restore → verify PASS).

Commit fix + regression test together:

```bash
git commit -m "fix(<scope>): <description> + regression test for #<issue>"
```

If you're entering this from `/fix-issue` workflow, that workflow already wraps the cycle — use it directly.

### C. Coverage audit

1. **Generate coverage report:**
   ```bash
   flutter test --coverage
   ```
2. **Check uncovered files** — focus on business logic, don't chase 100% UI.
3. **Prioritize:**
   - 🔴 Critical: auth, payments, security rules — must have tests.
   - 🟡 Important: feature core (post, friend, feed).
   - 🟢 Nice-to-have: utilities, formatters, theme.
4. **Add tests** following pattern A.

## Test types for Meep

### Unit (Dart)

```dart
// test/features/feed/post_repository_test.dart
import 'package:fake_cloud_firestore/fake_cloud_firestore.dart';
import 'package:firebase_auth_mocks/firebase_auth_mocks.dart';
import 'package:flutter_test/flutter_test.dart';

void main() {
  group('PostRepository', () {
    late FakeFirebaseFirestore firestore;
    late MockFirebaseAuth auth;
    late FirestorePostRepository repo;

    setUp(() {
      firestore = FakeFirebaseFirestore();
      auth = MockFirebaseAuth(signedIn: true, mockUser: MockUser(uid: 'u1'));
      repo = FirestorePostRepository(firestore: firestore, auth: auth);
    });

    test('createPost throws when caption empty', () async {
      expect(
        () => repo.createPost(caption: '', imageUrl: 'x.jpg'),
        throwsA(isA<ValidationError>()),
      );
    });
  });
}
```

### Widget (Flutter)

```dart
// test/features/feed/feed_page_test.dart
testWidgets('FeedPage shows loading then posts', (tester) async {
  await tester.pumpWidget(
    ProviderScope(
      overrides: [
        postRepositoryProvider.overrideWithValue(FakePostRepository(...)),
      ],
      child: const MaterialApp(home: FeedPage()),
    ),
  );

  expect(find.byType(CircularProgressIndicator), findsOneWidget);
  await tester.pumpAndSettle();
  expect(find.byType(PostCard), findsNWidgets(3));
});
```

### Integration / E2E

```dart
// integration_test/login_flow_test.dart
import 'package:integration_test/integration_test.dart';

void main() {
  IntegrationTestWidgetsFlutterBinding.ensureInitialized();

  testWidgets('login flow → feed', (tester) async {
    app.main();
    await tester.pumpAndSettle();
    // ... interact, assert
  });
}
```

Run on a real device / simulator:
```bash
flutter test integration_test/login_flow_test.dart
```

### Firestore rules tests

```bash
# firebase/functions/test/rules.test.ts (npm)
npm install --save-dev @firebase/rules-unit-testing
firebase emulators:exec --only firestore "npm run test:rules"
```

```ts
import { initializeTestEnvironment } from '@firebase/rules-unit-testing';

const env = await initializeTestEnvironment({
  projectId: 'meep-test',
  firestore: { rules: fs.readFileSync('firestore.rules', 'utf8') },
});

test('user cannot read non-friend post', async () => {
  const u1 = env.authenticatedContext('u1').firestore();
  await assertFails(u1.collection('posts').doc('post-of-u2').get());
});
```

## Naming rules

✅ Good:

- `'rejects post with empty caption'`
- `'returns 401 when token expired'`
- `'increments like count by 1 per user'`

❌ Bad:

- `'test1'`, `'works'`, `'create post'`, `'happy path'`
- Has "and" → split into 2 tests.

## Coverage targets for Meep

| Layer | Target | Reason |
|---|---|---|
| Business logic (controllers, services, rules) | ≥ 80% | High-risk |
| Data layer (repositories) | ≥ 70% | Easy to mock Firestore |
| UI widgets | ≥ 50% | Snapshot-fragile |
| Themes, utils | best-effort | Low-risk |

## Verify before declaring done

Apply skill `verification-before-completion`:

```bash
flutter test
flutter analyze
# Or
npm test
npm run lint
```

Read the output. 0 fail. 0 warn. Then claim "tests done".

## Anti-patterns

| Anti-pattern | Fix |
|---|---|
| Mocks instead of real impl | Use `fake_cloud_firestore`, in-memory fakes |
| Testing internals (private methods) | Test inputs/outputs only — public API |
| Large auto-approved snapshots | Small stable snapshots, review every line |
| Shared state across tests | `setUp` resets state |
| `Future.delayed(2s)` to wait for async | `pumpAndSettle()`, `expectLater(future, completes)` |
| Test name with "and" | Split into 2 tests |
| `.skip()` failing tests | Fix or delete. No middle ground. |
