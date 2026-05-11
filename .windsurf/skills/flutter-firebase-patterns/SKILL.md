---
name: flutter-firebase-patterns
description: Use when writing or modifying Flutter/Dart code that touches Firestore, Storage, FCM, or Auth. Reference patterns for state management, repository pattern, Firestore data modeling, security rules, and home widget integration.
---

# Flutter + Firebase Patterns — Meep

> Custom skill for the Meep stack. Based on Flutter best practices 2024+ and Firebase docs.

## Recommended state management: Riverpod 2 (code-gen)

```dart
// pubspec.yaml
dependencies:
  flutter_riverpod: ^2.5.0
  riverpod_annotation: ^2.3.0

dev_dependencies:
  riverpod_generator: ^2.4.0
  build_runner: ^2.4.0
```

```dart
// feed_controller.dart
import 'package:riverpod_annotation/riverpod_annotation.dart';
part 'feed_controller.g.dart';

@riverpod
class FeedController extends _$FeedController {
  @override
  Future<List<Post>> build() async {
    final repo = ref.watch(postRepositoryProvider);
    return repo.fetchFeed(limit: 20);
  }

  Future<void> refresh() async {
    state = const AsyncValue.loading();
    state = await AsyncValue.guard(() => ref.read(postRepositoryProvider).fetchFeed(limit: 20));
  }
}
```

**Why Riverpod over Provider/BLoC/GetX:**
- Type-safe, compile-time errors instead of runtime.
- Testable without a `Widget` tree.
- Auto-disposes when not in use.
- Code-gen reduces boilerplate.

## Repository pattern (data layer)

UI / controllers do **not** call Firestore directly. All I/O goes through a repository:

```dart
abstract class PostRepository {
  Future<List<Post>> fetchFeed({required int limit});
  Future<Post> createPost({required String caption, required String imageUrl});
  Stream<List<Post>> watchFeed();
}

class FirestorePostRepository implements PostRepository {
  FirestorePostRepository({required this.firestore, required this.auth});
  final FirebaseFirestore firestore;
  final FirebaseAuth auth;

  @override
  Future<Post> createPost({required String caption, required String imageUrl}) async {
    final uid = auth.currentUser?.uid;
    if (uid == null) throw const UnauthenticatedError();

    final ref = await firestore.collection('posts').add({
      'authorId': uid,
      'caption': caption,
      'imageUrl': imageUrl,
      'createdAt': FieldValue.serverTimestamp(),
    });
    final snap = await ref.get();
    return Post.fromFirestore(snap);
  }

  @override
  Stream<List<Post>> watchFeed() {
    return firestore
        .collection('posts')
        .orderBy('createdAt', descending: true)
        .limit(50)
        .snapshots()
        .map((s) => s.docs.map(Post.fromFirestore).toList());
  }
}
```

**Test with `fake_cloud_firestore`:**

```dart
test('createPost throws when unauthenticated', () async {
  final repo = FirestorePostRepository(
    firestore: FakeFirebaseFirestore(),
    auth: MockFirebaseAuth(),  // currentUser = null
  );
  expect(
    () => repo.createPost(caption: 'hi', imageUrl: 'x.jpg'),
    throwsA(isA<UnauthenticatedError>()),
  );
});
```

## Data classes with freezed + json_serializable

```dart
@freezed
class Post with _$Post {
  const factory Post({
    required String id,
    required String authorId,
    required String caption,
    required String imageUrl,
    required DateTime createdAt,
  }) = _Post;

  factory Post.fromFirestore(DocumentSnapshot snap) {
    final data = snap.data() as Map<String, dynamic>;
    return Post(
      id: snap.id,
      authorId: data['authorId'] as String,
      caption: data['caption'] as String,
      imageUrl: data['imageUrl'] as String,
      createdAt: (data['createdAt'] as Timestamp).toDate(),
    );
  }

  factory Post.fromJson(Map<String, dynamic> json) => _$PostFromJson(json);
}
```

**Generate:**
```bash
dart run build_runner build --delete-conflicting-outputs
```

## Firestore data modeling for Meep

### Collection layout

```
/users/{uid}                    # public profile
/users/{uid}/private/{docId}    # subcollection for private data
/posts/{postId}                 # post (denormalize authorName, authorAvatarUrl)
/friendships/{pair_id}          # pair_id = sorted "uidA_uidB"
/friend_requests/{requestId}
/notifications/{uid}/items/{itemId}  # notif per user
```

### Intentional denormalization

Copy `authorName`, `authorAvatarUrl` into `/posts/{postId}` so the feed query needs no join. When the user changes their name → Cloud Function `onDocumentUpdated('users/{uid}')` syncs into all of that user's posts.

### Pagination with cursor

```dart
Future<List<Post>> fetchFeed({DocumentSnapshot? after, int limit = 20}) async {
  Query q = firestore.collection('posts').orderBy('createdAt', descending: true).limit(limit);
  if (after != null) q = q.startAfterDocument(after);
  final snap = await q.get();
  return snap.docs.map(Post.fromFirestore).toList();
}
```

**Don't** use offset (Firestore doesn't support it efficiently). Always cursor-based.

## Firestore security rules — Meep pattern

```javascript
rules_version = '2';
service cloud.firestore {
  match /databases/{database}/documents {

    function isAuthed() { return request.auth != null; }
    function isOwner(uid) { return isAuthed() && request.auth.uid == uid; }
    function isFriend(uidA, uidB) {
      let pairId = uidA < uidB ? uidA + '_' + uidB : uidB + '_' + uidA;
      return exists(/databases/$(database)/documents/friendships/$(pairId));
    }

    match /users/{uid} {
      allow read: if isAuthed();  // public profile to logged-in users
      allow create: if isOwner(uid) && request.resource.data.keys().hasOnly(['displayName','avatarUrl','createdAt']);
      allow update: if isOwner(uid);
      allow delete: if false;  // no client delete; use a Function
    }

    match /posts/{postId} {
      allow read: if isAuthed() && (
        isOwner(resource.data.authorId) ||
        isFriend(request.auth.uid, resource.data.authorId)
      );
      allow create: if isOwner(request.resource.data.authorId)
        && request.resource.data.caption.size() <= 200
        && request.resource.data.keys().hasAll(['authorId','caption','imageUrl','createdAt']);
      allow update, delete: if isOwner(resource.data.authorId);
    }
  }
}
```

**Test rules:** use `@firebase/rules-unit-testing` (npm) — run via `firebase emulators:exec`.

## Storage rules

```javascript
rules_version = '2';
service firebase.storage {
  match /b/{bucket}/o {

    match /posts/{uid}/{filename} {
      allow read: if request.auth != null;
      allow write: if request.auth.uid == uid
        && request.resource.size < 10 * 1024 * 1024  // 10MB
        && request.resource.contentType.matches('image/.*');
    }
  }
}
```

## FCM pattern

### Token registration (mobile)

```dart
class FcmService {
  Future<void> init({required String uid}) async {
    final messaging = FirebaseMessaging.instance;
    await messaging.requestPermission();
    final token = await messaging.getToken();
    if (token != null) {
      await FirebaseFirestore.instance
          .collection('users').doc(uid)
          .collection('private').doc('fcm')
          .set({'token': token, 'platform': defaultTargetPlatform.name, 'updatedAt': FieldValue.serverTimestamp()});
    }
    messaging.onTokenRefresh.listen((newToken) {
      // update Firestore
    });
  }
}
```

### Send from a Cloud Function

```ts
// functions/src/notifyOnNewPost.ts
import { onDocumentCreated } from 'firebase-functions/v2/firestore';
import { getMessaging } from 'firebase-admin/messaging';

export const notifyOnNewPost = onDocumentCreated(
  { document: 'posts/{postId}', region: 'asia-southeast1' },
  async (event) => {
    const post = event.data?.data();
    if (!post) return;
    const friendTokens = await getFriendTokens(post.authorId);
    if (friendTokens.length === 0) return;
    await getMessaging().sendEachForMulticast({
      tokens: friendTokens,
      notification: { title: post.authorName, body: post.caption },
      data: { postId: event.params.postId, type: 'new_post' },
    });
  }
);
```

## Home widget integration

Package: `home_widget` (https://pub.dev/packages/home_widget).

> **MVP scope:** Android only per ADR-0002. `iOSName` argument left in code for future, but iOS widget native code is **not built** for MVP.

```dart
// When a new post arrives → cache image locally + update widget
await HomeWidget.saveWidgetData<String>('latest_image', localImagePath);
await HomeWidget.saveWidgetData<String>('latest_caption', post.caption);
await HomeWidget.updateWidget(
  androidName: 'MeepWidgetProvider',
  iOSName: 'MeepWidget', // ignored when iOS not targeted; kept for future
);
```

**Native widget code:**
- Android: `apps/widget/android/` — Kotlin AppWidgetProvider, reads from a shared `SharedPreferences`. **MVP target.**
- iOS: `apps/widget/ios/` — Swift WidgetKit, reads from shared App Group `UserDefaults`. **Deferred per ADR-0002, do not implement for MVP.**

**The widget does NOT call Firebase directly** — it only renders data the app has already cached.

## Common gotchas

| Issue | Fix |
|---|---|
| `setState()` after dispose | Check `mounted` first, or use Riverpod (handles it) |
| `Future` inside `build()` | Use `FutureProvider` / `StreamProvider`, don't call inside build |
| Firestore rules pass locally but fail in prod | Emulator is sometimes more lenient — always test against real Firestore staging |
| Image upload OOM | Compress before upload (`flutter_image_compress`), max 2048px width |
| FCM background not received on iOS | _Out of MVP scope per ADR-0002._ When iOS comes back: check APNs cert + entitlements + `Background Modes > Remote notifications` |
| Cloud Function cold start slow | Lazy-import heavy libs, region near users, `min instances ≥ 1` for critical fns |
