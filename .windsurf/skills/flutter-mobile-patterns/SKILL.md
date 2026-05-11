---
name: flutter-mobile-patterns
description: Use when writing or modifying Flutter/Dart code in VSmartwatch mobile app (health_system/lib). Reference patterns for Riverpod state management, dio HTTP, repository pattern, GoRouter navigation, FCM (push only), elderly UX, and widget testing.
---

# Flutter Mobile Patterns — VSmartwatch HealthGuard

> Apply when working in `health_system/lib/`. Stack: Flutter 3.11 + Riverpod 2 + dio + GoRouter + FCM (push only — backend is FastAPI, NOT Firestore).

## State management — Riverpod 2

Default to Riverpod (not Provider/BLoC/GetX). Use `flutter_riverpod` + optional `riverpod_annotation` (code-gen).

### Provider types — pick the right one

| Type | When |
|---|---|
| `Provider` | Computed value, immutable, derived from other providers |
| `StateProvider` | Simple primitive state (counter, toggle) |
| `StateNotifierProvider` / `NotifierProvider` | Complex state with business logic |
| `FutureProvider` | One-shot async load (vital snapshot, profile) |
| `StreamProvider` | Live updates (telemetry stream, FCM events) |

### Pattern (StateNotifier)

```dart
// fall_alert_notifier.dart
class FallAlertState {
  final bool isShowing;
  final int countdownSeconds;
  final FallEvent? event;
  
  const FallAlertState({
    required this.isShowing,
    required this.countdownSeconds,
    this.event,
  });
  
  FallAlertState copyWith({bool? isShowing, int? countdownSeconds, FallEvent? event}) =>
    FallAlertState(
      isShowing: isShowing ?? this.isShowing,
      countdownSeconds: countdownSeconds ?? this.countdownSeconds,
      event: event ?? this.event,
    );
}

class FallAlertNotifier extends StateNotifier<FallAlertState> {
  FallAlertNotifier(this._repo) : super(const FallAlertState(isShowing: false, countdownSeconds: 30));
  final FallEventRepository _repo;
  Timer? _timer;
  
  void startCountdown(FallEvent event) {
    state = state.copyWith(isShowing: true, event: event, countdownSeconds: 30);
    _timer = Timer.periodic(const Duration(seconds: 1), (t) {
      if (state.countdownSeconds <= 1) {
        t.cancel();
        triggerSos();
      } else {
        state = state.copyWith(countdownSeconds: state.countdownSeconds - 1);
      }
    });
  }
  
  Future<void> cancel() async {
    _timer?.cancel();
    if (state.event != null) {
      await _repo.confirmSafe(state.event!.id);
    }
    state = state.copyWith(isShowing: false, countdownSeconds: 30);
  }
  
  @override
  void dispose() {
    _timer?.cancel();
    super.dispose();
  }
}

final fallAlertProvider = StateNotifierProvider<FallAlertNotifier, FallAlertState>(
  (ref) => FallAlertNotifier(ref.watch(fallEventRepositoryProvider)),
);
```

## HTTP client — dio singleton with interceptors

Centralize HTTP in `lib/core/network/`.

```dart
// dio_client.dart
final dioProvider = Provider<Dio>((ref) {
  final dio = Dio(BaseOptions(
    baseUrl: AppConfig.apiBaseUrl,
    connectTimeout: const Duration(seconds: 10),
    receiveTimeout: const Duration(seconds: 15),
    headers: {'Content-Type': 'application/json'},
  ));
  dio.interceptors.addAll([
    _authInterceptor(ref),    // attach JWT
    _refreshInterceptor(ref), // 401 -> refresh -> retry
    _loggingInterceptor(),    // dev only
  ]);
  return dio;
});

InterceptorsWrapper _authInterceptor(Ref ref) => InterceptorsWrapper(
  onRequest: (options, handler) async {
    final token = await ref.read(authTokenStorageProvider).readAccessToken();
    if (token != null) options.headers['Authorization'] = 'Bearer $token';
    handler.next(options);
  },
);
```

**Cấm:** `Dio()` mới mỗi screen → leak resources + bypass interceptors.

## Repository pattern — boundary contract

UI/Notifier KHÔNG gọi dio trực tiếp. Đi qua repository.

```dart
// fall_event_repository.dart
abstract class FallEventRepository {
  Future<List<FallEvent>> recent({int limit = 20});
  Future<void> confirmSafe(String eventId);
  Future<void> triggerSos(String eventId);
}

class HttpFallEventRepository implements FallEventRepository {
  HttpFallEventRepository(this._dio);
  final Dio _dio;
  
  @override
  Future<List<FallEvent>> recent({int limit = 20}) async {
    final res = await _dio.get<List<dynamic>>('/api/mobile/fall-events', queryParameters: {'limit': limit});
    return (res.data ?? []).map((j) => FallEvent.fromJson(j as Map<String, dynamic>)).toList();
  }
  
  @override
  Future<void> confirmSafe(String eventId) =>
    _dio.post<void>('/api/mobile/fall-events/$eventId/confirm');
  
  @override
  Future<void> triggerSos(String eventId) =>
    _dio.post<void>('/api/mobile/fall-events/$eventId/trigger-sos');
}

final fallEventRepositoryProvider = Provider<FallEventRepository>(
  (ref) => HttpFallEventRepository(ref.watch(dioProvider)),
);
```

## Async safety — `mounted` after await

```dart
// BAD: BuildContext after await without mounted check
Future<void> _save() async {
  await _repo.save(data);
  Navigator.of(context).pop();  // CRASH if widget unmounted mid-await
}

// GOOD
Future<void> _save() async {
  await _repo.save(data);
  if (!mounted) return;
  Navigator.of(context).pop();
}
```

For Notifier: check `state` available, don't call `state =` after `dispose`.

## Navigation — GoRouter

Routes in `lib/core/routes/app_router.dart`. **Don't** push routes by string in widget code — use named/typed routes.

```dart
// route names
class AppRoutes {
  static const home = '/home';
  static const fallAlert = '/emergency/fall-alert';
  static const sosActive = '/emergency/sos-active';
}

// usage
context.go(AppRoutes.fallAlert);
context.push(AppRoutes.sosActive);
```

**Deep link / FCM open:** route through `notification_open_router.dart` (don't navigate from background handler — store deep link, navigate when app resumes).

## FCM — push only (no Firestore)

VSmartwatch backend pushes via Firebase Admin SDK from FastAPI; mobile only consumes.

```dart
// fcm_bootstrap.dart
class FcmBootstrap {
  Future<void> init({required String userId}) async {
    final messaging = FirebaseMessaging.instance;
    await messaging.requestPermission(alert: true, badge: true, sound: true);
    
    final token = await messaging.getToken();
    if (token != null) {
      await ref.read(deviceTokenRepositoryProvider).register(token: token, platform: defaultTargetPlatform.name);
    }
    messaging.onTokenRefresh.listen((newToken) {
      ref.read(deviceTokenRepositoryProvider).register(token: newToken, platform: defaultTargetPlatform.name);
    });
  }
}

// Foreground handler — show in-app notification
FirebaseMessaging.onMessage.listen((msg) {
  ref.read(notificationRuntimeServiceProvider).handleForeground(msg);
});

// Background — DON'T navigate, just store deep link
@pragma('vm:entry-point')
Future<void> firebaseMessagingBackgroundHandler(RemoteMessage msg) async {
  await Firebase.initializeApp();
  // store deep link in shared prefs; app resume reads + navigates
}
```

**Fall alert specific:** use `flutter_local_notifications` with full-screen intent (Android) + critical alert (iOS). Don't rely on system notification UI alone — elderly user may miss.

## Elderly UX — accessibility (mandatory medical app)

| Constraint | Value | Rationale |
|---|---|---|
| Min font (body) | 16sp | Readable for low-vision users |
| Min font (caption) | 14sp | Last resort, not for primary text |
| Min touch target | 48dp × 48dp | WCAG; 56dp for emergency UI |
| Min contrast | 4.5:1 (WCAG AA) | High-contrast mode tested |
| Primary action zone | Bottom 40% screen | Thumb reachability |
| TalkBack labels | All interactive | `Semantics(label: ...)` mandatory |

```dart
// Don't:
Text('Submit')  // small, low-contrast default

// Do:
Semantics(
  label: 'Xác nhận an toàn',
  button: true,
  child: ElevatedButton(
    onPressed: _confirm,
    style: ElevatedButton.styleFrom(
      minimumSize: const Size(150, 56),
      backgroundColor: Theme.of(context).colorScheme.primary,
    ),
    child: const Text('Tôi vẫn ổn', style: TextStyle(fontSize: 18, fontWeight: FontWeight.bold)),
  ),
)
```

## Testing patterns

### Unit test (notifier)

```dart
// test/features/emergency/fall_alert_notifier_test.dart
void main() {
  test('cancel stops timer + calls repo.confirmSafe', () async {
    final repo = MockFallEventRepository();
    when(() => repo.confirmSafe(any())).thenAnswer((_) async {});
    final container = ProviderContainer(overrides: [
      fallEventRepositoryProvider.overrideWithValue(repo),
    ]);
    addTearDown(container.dispose);
    
    final notifier = container.read(fallAlertProvider.notifier);
    notifier.startCountdown(FallEvent(id: 'evt-1'));
    await notifier.cancel();
    
    expect(container.read(fallAlertProvider).isShowing, false);
    verify(() => repo.confirmSafe('evt-1')).called(1);
  });
}
```

### Widget test

```dart
testWidgets('FallAlertScreen shows countdown', (tester) async {
  await tester.pumpWidget(ProviderScope(
    overrides: [fallEventRepositoryProvider.overrideWithValue(MockFallEventRepository())],
    child: const MaterialApp(home: FallAlertScreen(eventId: 'evt-1')),
  ));
  expect(find.text('30'), findsOneWidget);
});
```

Run: `flutter test test/features/emergency/` (focused) trước `flutter test` (full).

## Common gotchas

| Issue | Fix |
|---|---|
| `setState() called after dispose()` | Check `mounted` before setState; for Notifier, dispose Timer/Stream first |
| `BuildContext` lost across `await` | `if (!mounted) return;` after every `await` |
| `Dio` instance per screen | Inject via Riverpod Provider — singleton |
| `dispose()` quên cho controller | TextEditingController, AnimationController, StreamSubscription, Timer — luôn dispose |
| `dynamic` ở public API | Use typed model from `domain/entities/` |
| Hardcoded color/string | Theme tokens `Theme.of(context).colorScheme` + `app_strings.dart` |
| Inline `print()` debug | Use `developer.log` hoặc logger package; remove before commit |
| FCM background navigation | Don't navigate from background handler — store deep link, route on resume |

## Quick build commands

```pwsh
cd d:\DoAn2\VSmartwatch\health_system
flutter pub get
flutter analyze                              # zero warnings before commit
flutter test test/features/emergency/        # focused
flutter test                                  # full suite
flutter build apk --release                   # production APK
```

## Anti-patterns auto-flag

- `setState()` trong loop or post-await without `mounted` check
- `dispose()` thiếu cho controller/subscription
- `Dio()` constructor inline trong screen
- `print()` trong production code
- `dynamic` ở public API contract
- `Navigator.push` raw (use GoRouter named route)
- Hardcode hex color or string literal
