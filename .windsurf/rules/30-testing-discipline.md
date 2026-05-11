---
trigger: always_on
---

# Testing Discipline

Solo dev không có QA team đứng sau. Test là bảo hiểm sinh tồn của anh khi refactor.

## Iron law

- **Tests trước/cùng implement** cho feature mới.
- **Bug fix luôn có regression test** — đọc skill `tdd` "Bug fix" section.
- **Đừng claim done** trước khi `verification-before-completion` checklist pass.
- **Không weaken/disable test** khi nó fail — root-cause trước, sửa code hoặc sửa test với lý do rõ ràng.

## Test pyramid per stack

### Flutter (`health_system/test/`)

- **Unit:** business logic, models, repositories, providers
  - Run: `flutter test test/<feature>/`
- **Widget:** UI behavior (state changes, gestures, navigation)
- **Integration:** `health_system/integration_test/` (real device or emulator)
- Don't test framework code (`MaterialApp`, `Scaffold`) — only your widget logic.

### FastAPI (`health_system/backend/tests/`, `Iot_Simulator_clean/tests/`, `healthguard-model-api/tests/`)

- **Unit:** services, validators, business logic
- **Contract:** API endpoint shape (use FastAPI's `TestClient`)
- **Integration:** with test DB (SQLite or test Postgres)
- Pattern: `tests/test_<module>.py`
- Run: `pytest tests/<file>::<test_func>` (specific) trước `pytest` (full).

### Express + Prisma (`HealthGuard/backend/src/__tests__/`)

- **Unit:** services, validators
- **Integration:** API route → service → mock Prisma
- Run: `npm test -- <file>` trước `npm test` (full).

### Vite + React (`HealthGuard/frontend/`)

- **Unit:** hooks, utilities
- **Component:** render, fire event, assert (Vitest + Testing Library)
- Snapshot tests **không khuyến khích** — fragile.

## Boundary testing rule

Test ở **boundary** (API surface, repository return, store dispatch), không test internal implementation. Implementation thay đổi → test còn pass.

## Test data

- **No production data trong test.** Dùng factory/builder pattern.
- **Reset state giữa các test.** Fixture cho DB, cleanup teardown cho file.
- **Deterministic.** Không depend on time/network/random — mock chúng.

## Flaky test = banned

Test flaky **không phải lỗi của test runner**. Nó là:
- Race condition trong code
- Missing `await`
- Shared mutable state giữa tests
- Time-dependent assertion

Find + fix root cause. **Không retry/skip flaky test.**

## Coverage

- Mục tiêu khả thi: **60–70% line coverage** cho code mới.
- Don't chase 100% — chỉ test code có complexity/risk.
- Trivial getter/setter, framework wiring → skip.

## Khi anh request "skip test" hoặc "test fail mặc kệ"

Em sẽ push back:
- Skip test = bug có sẵn nhưng giấu đi → catastrophe sau.
- Fail test = signal có vấn đề → cần root-cause, không bypass.

Nếu test thực sự không còn relevant (feature đã đổi): **delete test với commit message giải thích**, không skip.
