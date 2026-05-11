---
description: Write or extend tests (unit / widget / integration / contract) following TDD pattern. Stack-aware for Flutter / FastAPI / Express+Prisma / React+Vite.
---

# /test — Test-Driven Development (VSmartwatch)

> "Tests are proof, not afterthought."

Use this workflow when:
- Adding tests for existing code (legacy area).
- Writing regression test for a bug fix.
- Auditing coverage and adding tests for gaps.

> **For new feature you're coding:** use `/build` directly (TDD cycle included).

## Pre-flight

1. **Invoke skill `tdd`** — full discipline.
2. **Identify scope:** which file/function/feature needs tests?
3. **Check current coverage** (per stack):

```pwsh
# Flutter
flutter test --coverage
# coverage/lcov.info → genhtml -o coverage/html (optional)

# FastAPI
pytest --cov=app --cov-report=html
# htmlcov/index.html

# Express
npm test -- --coverage

# React
npm test -- --coverage
```

## Pattern by case

### A. Tests for existing code (none yet)

1. **Read the code** — understand current behavior.
2. **List behaviors** to test: happy path, edge case, error path.
3. **For each behavior:**
   - Write the test → run → confirm FAIL if code has a bug, or PASS if correct.
   - **PASS immediately:** characterization test (locking in current behavior). OK, but don't claim correctness proved.
   - **FAIL:** discovered a bug → invoke skill `systematic-debugging`. Log to `PM_REVIEW/BUGS/<ID>.md`.

### B. Regression test for bug fix

**→ Apply skill `tdd`** "Bug fix → reproduction test" section. Full cycle:

1. Write failing test (RED — confirm it fails for the right reason).
2. Apply fix.
3. Verify test PASS.
4. Revert fix → verify test FAIL again.
5. Restore fix → verify test PASS.
6. Commit fix + regression test together.

```pwsh
git -C <repo> commit -m "fix(<scope>): <mô tả tiếng Việt> + regression test cho <bug-id>"
```

If entering from `/fix-issue` workflow, that workflow wraps this cycle.

### C. Coverage audit

1. Generate coverage report (per stack above).
2. Check uncovered files — focus on business logic, not framework wiring.
3. Prioritize:
   - 🔴 Critical: auth, fall detection, SOS, vitals submit, audit log → MUST have tests.
   - 🟡 Important: feature core (sleep analysis, family share).
   - 🟢 Nice-to-have: utilities, formatters, theme.
4. Add tests following pattern A.

## Test types per stack

### Flutter (`health_system/test/`)

#### Unit (Riverpod notifier + repository)

```dart
// test/features/emergency/fall_alert_notifier_test.dart
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:mocktail/mocktail.dart';

class MockFallEventRepository extends Mock implements FallEventRepository {}

void main() {
  setUpAll(() {
    registerFallbackValue(FallEvent(id: 'fb', userId: 'u1'));
  });
  
  group('FallAlertNotifier', () {
    late MockFallEventRepository repo;
    late ProviderContainer container;
    
    setUp(() {
      repo = MockFallEventRepository();
      container = ProviderContainer(overrides: [
        fallEventRepositoryProvider.overrideWithValue(repo),
      ]);
      addTearDown(container.dispose);
    });
    
    test('cancel calls repo.confirmSafe + stops timer', () async {
      when(() => repo.confirmSafe(any())).thenAnswer((_) async {});
      
      final notifier = container.read(fallAlertProvider.notifier);
      notifier.startCountdown(FallEvent(id: 'evt-1', userId: 'u1'));
      await notifier.cancel();
      
      expect(container.read(fallAlertProvider).isShowing, false);
      verify(() => repo.confirmSafe('evt-1')).called(1);
    });
  });
}
```

#### Widget

```dart
// test/features/emergency/fall_alert_screen_test.dart
testWidgets('FallAlertScreen shows countdown then transitions', (tester) async {
  await tester.pumpWidget(ProviderScope(
    overrides: [
      fallEventRepositoryProvider.overrideWithValue(MockFallEventRepository()),
    ],
    child: const MaterialApp(home: FallAlertScreen(eventId: 'evt-1')),
  ));
  
  expect(find.text('30'), findsOneWidget);  // initial countdown
  await tester.tap(find.text('Tôi vẫn ổn'));
  await tester.pumpAndSettle();
  expect(find.byType(FallAlertScreen), findsNothing);  // popped
});
```

#### Integration (real device or emulator)

```dart
// integration_test/sos_flow_test.dart
import 'package:integration_test/integration_test.dart';
import 'package:health_system/main.dart' as app;

void main() {
  IntegrationTestWidgetsFlutterBinding.ensureInitialized();
  
  testWidgets('SOS flow end-to-end', (tester) async {
    app.main();
    await tester.pumpAndSettle();
    // login → trigger fall → confirm cancel → assert no SOS sent
  });
}
```

```pwsh
flutter test integration_test/sos_flow_test.dart
```

### FastAPI (`tests/`)

#### Unit (service layer)

```python
# tests/test_fall_service.py
import pytest
from unittest.mock import AsyncMock
from app.services.fall_service import FallService
from app.models.fall import FallPredictRequest

@pytest.mark.asyncio
async def test_predict_low_confidence_returns_no_fall():
    repo = AsyncMock()
    repo.get_fall_model.return_value.predict_proba.return_value = [[0.9, 0.1]]
    service = FallService(repo)
    
    req = FallPredictRequest(user_id="u1", accel=[0,0,9.8], gyro=[0,0,0], timestamp="2026-01-01T00:00:00Z")
    res = await service.predict(req)
    
    assert res.is_fall is False
    assert res.confidence == 0.1
```

#### Contract (API endpoint)

```python
# tests/test_fall_router.py
from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)

def test_predict_unauthorized_without_secret():
    resp = client.post("/api/mobile/fall/predict", json={
        "user_id": "u1", "accel": [0,0,9.8], "gyro": [0,0,0], "timestamp": "2026-01-01T00:00:00Z"
    })
    assert resp.status_code == 401

def test_predict_validates_payload(internal_secret_header):
    resp = client.post("/api/mobile/fall/predict", json={
        "user_id": "u1", "accel": [9999,0,0], "gyro": [0,0,0], "timestamp": "2026-01-01T00:00:00Z"
    }, headers=internal_secret_header)
    assert resp.status_code == 422  # Pydantic validation
```

#### Integration (with test DB)

```python
# tests/test_fall_event_repository.py
import pytest
import asyncpg
from app.repositories.fall_event_repository import FallEventRepository

@pytest.fixture
async def db_pool():
    pool = await asyncpg.create_pool(dsn=TEST_DATABASE_URL)
    yield pool
    await pool.close()

@pytest.mark.asyncio
async def test_insert_and_retrieve(db_pool):
    repo = FallEventRepository(db_pool)
    event_id = await repo.insert(FallEvent(user_id="u1", device_id="d1", confidence=0.85, detected_at=datetime.now()))
    
    recent = await repo.recent_for_user("u1")
    assert len(recent) == 1
    assert recent[0].id == event_id
```

```pwsh
pytest tests/test_fall_router.py::test_predict_unauthorized_without_secret  # focused
pytest                                                                       # full
```

### Express + Prisma (`HealthGuard/backend/src/__tests__/`)

#### Unit (service with Prisma mock)

```js
// src/__tests__/deviceService.test.js
const { mockDeep, mockReset } = require('jest-mock-extended');
const prismaMock = mockDeep();

jest.mock('../lib/prisma', () => prismaMock);

const deviceService = require('../services/deviceService');

beforeEach(() => mockReset(prismaMock));

describe('deviceService.create', () => {
  test('throws ConflictError on duplicate IMEI', async () => {
    prismaMock.device.findUnique.mockResolvedValue({ id: 'd1', imei: '123456789012345' });
    await expect(
      deviceService.create({ imei: '123456789012345', model: 'X' }, { actorUserId: 'u1' })
    ).rejects.toThrow(/already exists/i);
  });
  
  test('creates device + audit log in transaction', async () => {
    prismaMock.device.findUnique.mockResolvedValue(null);
    prismaMock.$transaction.mockImplementation((cb) => cb(prismaMock));
    prismaMock.device.create.mockResolvedValue({ id: 'd1', imei: '123456789012345', model: 'X' });
    
    const result = await deviceService.create({ imei: '123456789012345', model: 'X' }, { actorUserId: 'u1' });
    
    expect(result.id).toBe('d1');
    expect(prismaMock.auditLog.create).toHaveBeenCalledWith({
      data: expect.objectContaining({ actorId: 'u1', action: 'DEVICE_CREATE' }),
    });
  });
});
```

#### Integration (route → service → mocked Prisma)

```js
// src/__tests__/deviceRoute.test.js
const request = require('supertest');
const app = require('../server');

test('GET /api/admin/devices requires JWT', async () => {
  const res = await request(app).get('/api/admin/devices');
  expect(res.status).toBe(401);
});

test('POST /api/admin/devices validates IMEI format', async () => {
  const res = await request(app)
    .post('/api/admin/devices')
    .set('Authorization', `Bearer ${adminToken}`)
    .send({ imei: 'invalid', model: 'X' });
  expect(res.status).toBe(400);
  expect(res.body.error.code).toBe('VALIDATION');
});
```

```pwsh
npm test -- deviceService.test.js   # focused
npm test                             # full
```

### React + Vite (`HealthGuard/frontend/src/__tests__/`)

#### Component

```jsx
// src/__tests__/DeviceList.test.jsx
import { render, screen, fireEvent } from '@testing-library/react';
import DeviceList from '../components/DeviceList';

test('renders empty state when no devices', () => {
  render(<DeviceList devices={[]} />);
  expect(screen.getByText(/chưa có thiết bị/i)).toBeInTheDocument();
});

test('clicking row triggers onSelect', () => {
  const onSelect = vi.fn();
  render(<DeviceList devices={[{ id: 'd1', imei: '123', model: 'X' }]} onSelect={onSelect} />);
  fireEvent.click(screen.getByText('123'));
  expect(onSelect).toHaveBeenCalledWith('d1');
});
```

#### Hook

```jsx
// src/__tests__/useDevices.test.jsx
import { renderHook, waitFor } from '@testing-library/react';
import { useDevices } from '../hooks/useDevices';

test('fetches devices on mount', async () => {
  const { result } = renderHook(() => useDevices());
  await waitFor(() => expect(result.current.isLoading).toBe(false));
  expect(result.current.devices).toHaveLength(2);
});
```

```pwsh
npm test -- DeviceList                # focused
npm test                               # full
```

## Naming rules

✅ Good:
- `'rejects fall event with confidence < 0.5'`
- `'returns 401 when JWT expired'`
- `'increments lockout counter per failed login'`

❌ Bad:
- `'test1'`, `'works'`, `'create device'`, `'happy path'`
- Has "and" → split into 2 tests.

## Coverage targets

| Layer | Target | Reason |
|---|---|---|
| Business logic (service, notifier) | ≥ 80% | High risk |
| Repository (data access) | ≥ 70% | Easy to mock |
| Router/controller | ≥ 60% | Mostly wiring |
| UI widget/component | ≥ 50% | Snapshot-fragile |
| Theme, util, formatter | best-effort | Low risk |

Don't chase 100%. Test code with complexity/risk.

## Verify before declaring done

**→ Apply skill `verification-before-completion`.** Iron Law: NO completion claim without fresh evidence.

```pwsh
# Per stack — read OUTPUT, not just exit code

flutter test ; flutter analyze
pytest ; mypy app/
npm test ; npm run lint
```

Read output. 0 fail. 0 warn. THEN claim "tests done".

## Anti-patterns

| Anti-pattern | Fix |
|---|---|
| Mock everything (incl. Prisma/Pydantic) | Use real impl + real DB for repository tests; mock only at boundaries (HTTP, FCM) |
| Testing internals (private method) | Test public API (input/output, contract) |
| Large auto-approved snapshots | Small stable snapshots, review every line; prefer assertion |
| Shared state across tests | `setUp`/`fixture` resets state |
| `Future.delayed(2s)` to wait async | `pumpAndSettle()`, `await result`, deterministic timing |
| Test name with "and" | Split into 2 tests |
| `.skip()` failing tests | Fix root cause OR delete test. No middle ground. |
| Test depends on system time | Inject Clock; freeze time |
| Test depends on network | Mock HTTP boundary; never hit real API |
