# Additional Examples — mobile-agent Skill

> These examples supplement the main SKILL.md examples (PLAN + TASK).
> See SKILL.md for Example 1 (PLAN) and Example 2 (TASK).

---

## Example 3: Mode BUILD — Implementing Login Screen

**Input:** `@mobile-agent mode BUILD "Build the Login screen based on the approved Plan"`

**Context:** AI reads the finalized Plan for `AUTH_Login` screen.

**Internal Checklist (not printed):**
```
[x] Loading state → shimmer placeholder
[x] Empty state → N/A for login
[x] Success state → navigate to Dashboard
[x] Error state → show error banner + retry
[x] Edge case: network loss → show offline message
[x] Edge case: wrong password 5x → lock 15 min
[x] Widget tree matches Plan
[x] Clean Architecture: file in features/auth/presentation/
```

**Output:**

```
📦 BUILD Report: Login Screen

Files created/modified:
- lib/features/auth/presentation/screens/login_screen.dart (NEW — 187 LOC)
- lib/features/auth/presentation/widgets/login_form.dart (NEW — 94 LOC)
- lib/features/auth/presentation/widgets/social_login_buttons.dart (NEW — 45 LOC)
- lib/shared/widgets/loading_shimmer.dart (MODIFIED — added login variant)

Checklist Coverage: 8/8 items ✅
Edge Cases Handled: 4/4 ✅

Confidence: 92% — All Plan items covered. Minor uncertainty: Social login button 
layout may need adjustment after visual testing on small screens (< 5 inch).
```

**Sample Code Generated:**

```dart
// lib/features/auth/presentation/screens/login_screen.dart
import 'package:flutter/material.dart';
import '../widgets/login_form.dart';

class LoginScreen extends StatefulWidget {
  const LoginScreen({super.key});

  @override
  State<LoginScreen> createState() => _LoginScreenState();
}

class _LoginScreenState extends State<LoginScreen> {
  bool _isLoading = false;
  String? _errorMessage;

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      body: SafeArea(
        child: _isLoading
            ? const LoginShimmer()
            : _errorMessage != null
                ? _buildErrorState()
                : _buildLoginForm(),
      ),
    );
  }

  Widget _buildErrorState() {
    return Column(
      mainAxisAlignment: MainAxisAlignment.center,
      children: [
        Icon(Icons.error_outline, size: 64, color: Colors.red.shade400),
        const SizedBox(height: 16),
        Text(_errorMessage!, style: const TextStyle(fontSize: 16)),
        const SizedBox(height: 16),
        ElevatedButton(
          onPressed: () => setState(() => _errorMessage = null),
          style: ElevatedButton.styleFrom(minimumSize: const Size(200, 48)),
          child: const Text('Retry'),
        ),
      ],
    );
  }

  Widget _buildLoginForm() {
    return const SingleChildScrollView(
      padding: EdgeInsets.all(24),
      child: LoginForm(),
    );
  }
}
```

---

## Example 4: Mode REVIEW — Code Review of Login Screen

**Input:** `@mobile-agent mode REVIEW "Review code for login screen: lib/features/auth/presentation/screens/login_screen.dart"`

**Output (in Vietnamese):**

```markdown
# 🔍 Báo Cáo Đánh Giá: Login Screen

## Điểm tổng: 7/10
## Confidence: 88%

## Checklist đối chiếu Plan
| Mục                 | Plan yêu cầu          | Thực tế                           | Kết quả |
| ------------------- | --------------------- | --------------------------------- | ------- |
| Loading State       | Skeleton shimmer      | LoginShimmer widget               | ✅ PASS  |
| Error State         | Error banner + Retry  | Có ErrorState + Retry button      | ✅ PASS  |
| Success State       | Navigate to Dashboard | Chưa thấy logic navigation        | ❌ FAIL  |
| Network Loss        | Offline message       | Chưa handle ConnectivityException | ❌ FAIL  |
| Password lock 5x    | Lock 15 min           | Chưa implement                    | ❌ FAIL  |
| Touch target ≥ 48dp | Min 48dp              | Button minSize: 200x48 ✅          | ✅ PASS  |
| Font ≥ 16sp         | Min 16sp body         | fontSize: 16 ✅                    | ✅ PASS  |

## Lỗi phát hiện
1. 🔴 [Nghiêm trọng] Thiếu navigation sau login thành công — User login xong không chuyển màn hình
2. 🔴 [Nghiêm trọng] Chưa handle mất mạng — Ứng dụng y tế cần xử lý edge case này
3. 🟡 [Trung bình] Chưa implement password lockout sau 5 lần sai
4. 🟢 [Nhẹ] `_buildLoginForm()` nên extract thành widget riêng để reuse

## Đề xuất sửa
- Thêm `Navigator.pushReplacement` đến DashboardScreen trong `onLoginSuccess`
- Wrap API call trong try-catch, catch `SocketException` → hiển thị offline UI
- Thêm counter cho wrong password attempts trong AuthService
```

---

## Example 5: Full Pipeline — PLAN → BUILD → REVIEW (One Screen)

> This example shows how the 3 modes chain together for a single screen.

### Step 1: PLAN

```
User: @mobile-agent mode PLAN "Design the Device List screen — UC040"
AI: [Outputs full Plan with 4 states, 3 edge cases, widget tree, dependencies]
User: "Looks good, approved."
```

### Step 2: BUILD

```
User: @mobile-agent mode BUILD "Build Device List screen based on approved Plan"
AI: [Reads Plan → builds internal checklist → codes 3 files → outputs BUILD Report]
     📦 BUILD Report: Device List
     Files: 3 created, 1 modified
     Checklist: 7/7 ✅ | Edge Cases: 3/3 ✅ | Confidence: 95%
```

### Step 3: REVIEW

```
User: @mobile-agent mode REVIEW "Review code: lib/features/device/presentation/screens/device_list_screen.dart"
AI: [Reads code → compares against Plan → outputs Vietnamese Review Report]
     🔍 Báo Cáo Đánh Giá: Device List — 9/10
     1 lỗi nhẹ: Empty state illustration chưa center đúng
```

### Result: Screen is **designed → built → quality-checked** in 3 interactions.
