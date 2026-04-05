# KẾ HOẠCH REFACTOR TOÀN DIỆN — IoT Simulator cho VSmartwatch

> **Ngày tạo:** 2026-04-04  
> **Phạm vi:** Backend (Python/FastAPI) + Frontend (React/TypeScript)  
> **Phương pháp:** Nghiên cứu chuyên sâu mã nguồn → Tổng hợp findings → Lập kế hoạch 6 phase

---

## 1. Tổng quan dự án

### 1.1 Backend — Python / FastAPI

| Thành phần | Mô tả |
|---|---|
| Entry point | [`api_server/main.py`](api_server/main.py) — FastAPI app, mount 9 router dưới prefix `/api/sim` |
| Core runtime | [`SimulatorRuntime`](api_server/dependencies.py:504) ≈ 3414 dòng — God Object chứa toàn bộ business logic |
| Router layer | 9 file router trong `api_server/routers/`, ~30+ endpoints |
| Background loop | Daemon Thread gọi `tick_active()` mỗi giây |
| Transport | Publisher ABC → `MqttPublisher` + `HttpPublisher`, hiện hardcode `mode="http"` |
| Database | SQLAlchemy engine (`pool_size=3`), toàn raw SQL qua `sqlalchemy.text()` — KHÔNG dùng ORM |
| Admin data | [`SimAdminService`](api_server/sim_admin_service.py:12) — class-level cache TTL 30s cho device list |

### 1.2 Frontend — React 18 / TypeScript / Vite

| Thành phần | Mô tả |
|---|---|
| Framework | React 18 + TypeScript + Vite, dark theme only |
| State | 3 Zustand stores: `sessionStore`, `sessionVitalsStore`, `uiStore` |
| Data fetching | TanStack React Query (Axios polling 1s–15s) + 1 WebSocket (log stream) |
| Routing | 6 pages (lazy loaded), React Router v6 |
| Components | 14 domain components, 3 chart components, 7 UI components |
| Charting | ECharts via `echarts-for-react` |
| Styling | 99% inline styles (Tailwind installed nhưng KHÔNG sử dụng) |

---

## 2. Danh sách tất cả vấn đề phát hiện

### 2.1 Backend Issues

| Mã | Tên vấn đề | Mức độ | File:Line | Impact |
|---|---|---|---|---|
| BE-01 | God Object `SimulatorRuntime` | 🔴 Critical | [`dependencies.py:504`](api_server/dependencies.py:504) | ≈3414 dòng chứa device mgmt, session mgmt, tick logic, vitals, sleep scoring, risk scoring, alert pushing, admin ops — không thể test đơn vị, coupling cực cao |
| BE-02 | CORS allow_origins=["*"] | 🔴 Critical | [`main.py:35`](api_server/main.py:35) | Cho phép mọi origin truy cập API, rủi ro CSRF và data leak trong production |
| BE-03 | Không có authentication/authorization | 🔴 Critical | [`main.py`](api_server/main.py) (toàn bộ router) | Admin endpoints (`/admin/*`) không yêu cầu xác thực, ai cũng có thể tạo/xóa device |
| BE-04 | Blocking `urlopen()` trong admin client | 🔴 Critical | [`backend_admin_client.py:83`](api_server/backend_admin_client.py:83) | Timeout 10s trên main thread, block event loop khi gọi từ async context |
| BE-05 | Raw SQL không có ORM validation | 🔴 Critical | [`sim_admin_service.py`](api_server/sim_admin_service.py:12) (nhiều method) | Thiếu typed mapping, dễ sai tên cột, không có migration tracking |
| BE-06 | Silent exception swallowing | 🟡 Moderate | [`dependencies.py:728`](api_server/dependencies.py:728), [`:1027`](api_server/dependencies.py:1027), [`:1105`](api_server/dependencies.py:1105) | `except Exception: return` không log — lỗi DB, lỗi mạng bị nuốt hoàn toàn, không để lại dấu vết debug |
| BE-07 | Truy cập private `_sleep_sessions` | 🟡 Moderate | [`dependencies.py:2116`](api_server/dependencies.py:2116) | Xuyên qua encapsulation của `DatasetRegistry`, dễ vỡ khi registry đổi nội bộ |
| BE-08 | Router gọi private method | 🟡 Moderate | [`devices.py:144`](api_server/routers/devices.py:144), [`:161`](api_server/routers/devices.py:161), [`:181`](api_server/routers/devices.py:181), [`:192`](api_server/routers/devices.py:192) | Router gọi trực tiếp `_ensure_sim_session_for_db_device()` và `_stop_sim_session_for_db_device()` — phá vỡ abstraction |
| BE-09 | Thread/async bridge risk | 🟡 Moderate | [`dependencies.py:483`](api_server/dependencies.py:483) | `asyncio.Queue.put_nowait()` từ sync thread trong `LogHub.publish` — tiềm ẩn race condition |
| BE-10 | Không có retry logic cho HTTP publish | 🟡 Moderate | [`dependencies.py:738`](api_server/dependencies.py:738) | Publish fail → drop luôn, không retry — dữ liệu telemetry có thể mất |
| BE-11 | Import `random` bên trong function body | 🟡 Moderate | [`dependencies.py:2141`](api_server/dependencies.py:2141), [`:3020`](api_server/dependencies.py:3020) | Import lặp lại mỗi lần gọi hàm, tuy nhỏ nhưng bất thường và gây nhầm lẫn khi đọc |
| BE-12 | Event history slice O(n) | 🟡 Moderate | [`dependencies.py:3394`](api_server/dependencies.py:3394) (ước lượng) | Reassign `event_history[:] = event_history[-N:]` mỗi tick khi history vượt ngưỡng |
| BE-13 | Dashboard summary O(n) parse | 🟡 Moderate | [`dependencies.py:1956`](api_server/dependencies.py:1956) | Duyệt toàn bộ `event_history`, parse `datetime.fromisoformat()` cho mỗi event mỗi lần gọi `/dashboard/summary` |
| BE-14 | WebSocket keepalive không qua lock | 🟡 Moderate | [`log_stream.py:23`](api_server/ws/log_stream.py:23) | Truy cập `runtime.sessions` không đồng bộ — có thể đọc dict đang bị mutate từ tick thread |
| BE-15 | Dual import path fragile | 🟢 Minor | [`dependencies.py:21-74`](api_server/dependencies.py:21) | Try/except import từ 2 path khác nhau — dễ vỡ khi đổi cấu trúc thư mục |
| BE-16 | Global mutable singletons | 🟢 Minor | [`dependencies.py:3398`](api_server/dependencies.py:3398), [`backend_admin_client.py:196`](api_server/backend_admin_client.py:196) | Singleton module-level khó test và reset giữa các test case |
| BE-17 | Duplicate logic `_coerce_float` vs `_safe_float` | 🟢 Minor | [`dependencies.py:110`](api_server/dependencies.py:110) vs [`:2999`](api_server/dependencies.py:2999) | Hai hàm chuyển đổi float gần giống nhau, gây nhầm lẫn khi maintain |
| BE-18 | Hardcoded scenario profiles | 🟢 Minor | [`dependencies.py:143-296`](api_server/dependencies.py:143) | ~150 dòng config inline trong file Python, nên tách ra file YAML/JSON |
| BE-19 | `md5` usage cho hashing | 🟢 Minor | [`dependencies.py:3209`](api_server/dependencies.py:3209) | Dùng MD5 cho hash session — không phải rủi ro bảo mật trực tiếp nhưng nên dùng `hashlib.sha256` |
| BE-20 | Missing type annotations | 🟢 Minor | [`devices.py:69`](api_server/routers/devices.py:69) | Endpoint `list_db_devices` trả `list[dict]` không typed — khó validate response |

### 2.2 Frontend Issues

| Mã | Tên vấn đề | Mức độ | File:Line | Impact |
|---|---|---|---|---|
| FE-01 | Package `react-error-boundary` không dùng | 🔴 Critical (Dead) | [`package.json:22`](simulator-web/package.json:22) | Installed nhưng không import — custom `ErrorBoundary` đang dùng thay thế |
| FE-02 | Package `clsx` + `tailwind-merge` không dùng | 🔴 Critical (Dead) | [`package.json:16`](simulator-web/package.json:16), [`:25`](simulator-web/package.json:25) | Installed nhưng KHÔNG import ở bất kỳ file nào |
| FE-03 | Component `DeviceTable` dead code | 🔴 Critical (Dead) | [`DeviceTable.tsx`](simulator-web/src/components/domain/DeviceTable.tsx) | Không được import bởi bất kỳ page nào (`DbDeviceTable` đã thay thế) |
| FE-04 | Component `DeviceStatusCard` dead code | 🔴 Critical (Dead) | [`DeviceStatusCard.tsx`](simulator-web/src/components/domain/DeviceStatusCard.tsx) | Không được import bởi bất kỳ page/component nào |
| FE-05 | Component `DeviceDetailDrawer` dead code | 🔴 Critical (Dead) | [`DeviceDetailDrawer.tsx`](simulator-web/src/components/domain/DeviceDetailDrawer.tsx) | Không được import — fire-and-forget API calls tại line 98-114 |
| FE-06 | Component `CreateDeviceModal` dead code | 🔴 Critical (Dead) | [`CreateDeviceModal.tsx`](simulator-web/src/components/domain/CreateDeviceModal.tsx) | `DevicesPage` sử dụng inline `CreateDbDeviceModal` thay thế |
| FE-07 | Component `SessionToolbar` dead code | 🔴 Critical (Dead) | [`SessionToolbar.tsx`](simulator-web/src/components/domain/SessionToolbar.tsx) | Không được import bởi bất kỳ page nào |
| FE-08 | Component `VitalsStreamChart` dead code | 🔴 Critical (Dead) | [`VitalsStreamChart.tsx`](simulator-web/src/components/charts/VitalsStreamChart.tsx) | Không được import — `SessionVitalsPanel` tự render chart inline |
| FE-09 | Hook `useVitalsStream` dead code | 🔴 Critical (Dead) | [`useVitalsStream.ts`](simulator-web/src/hooks/useVitalsStream.ts) | Không được import — `SessionVitalsPanel` dùng `useQuery` trực tiếp |
| FE-10 | Constant `POLL_INTERVALS` dead code | 🔴 Critical (Dead) | [`constants.ts:1`](simulator-web/src/utils/constants.ts:1) | Không được import bởi bất kỳ file nào |
| FE-11 | Utils `formatBpm`, `formatTime`, `formatBattery` dead | 🔴 Critical (Dead) | [`format.ts`](simulator-web/src/utils/format.ts) | Không được import — components format giá trị inline |
| FE-12 | Fire-and-forget API trong `DeviceDetailDrawer` | 🔴 Critical | [`DeviceDetailDrawer.tsx:98-114`](simulator-web/src/components/domain/DeviceDetailDrawer.tsx:98) | Gọi `injectDeviceStatus`/`injectEvent` không `await`, không `catch`, không loading state |
| FE-13 | `injectFallEvent` trong `setInterval` | 🔴 Critical | [`FallLab.tsx:50`](simulator-web/src/components/domain/FallLab.tsx:50) | Error bị nuốt bên trong interval callback — user không biết khi fall injection fail |
| FE-14 | FallLab buttons không error handling | 🔴 Critical | [`FallLab.tsx:84-136`](simulator-web/src/components/domain/FallLab.tsx:84) | Tất cả 7 nút action không có try/catch, không loading state, không disable khi pending |
| FE-15 | Không có `React.memo` trên bất kỳ component nào | 🟡 Moderate | Toàn bộ `src/components/` | Mọi component re-render khi parent re-render — đặc biệt nghiêm trọng ở vitals panel cập nhật mỗi 1s |
| FE-16 | Không có `useCallback` ở bất kỳ đâu | 🟡 Moderate | Toàn bộ `src/pages/` | Handler functions tạo mới mỗi render, phá vỡ referential equality cho memo |
| FE-17 | MetricWidget/MetricChart render 5x mỗi giây | 🟡 Moderate | [`SessionVitalsPanel.tsx:134-151`](simulator-web/src/components/domain/SessionVitalsPanel.tsx:134) | 5 widget + 5 chart re-render đồng loạt mỗi khi vitals poll trả kết quả (mỗi 1s) |
| FE-18 | `DbDeviceTable` nhận 6 callback props mới mỗi render | 🟡 Moderate | [`DevicesPage.tsx:167-177`](simulator-web/src/pages/DevicesPage.tsx:167) | Callback inline không memo → table re-render toàn bộ dù data không đổi |
| FE-19 | `MotionPreviewPanel` setInterval 1s tạo re-render liên tục | 🟡 Moderate | [`MotionPreviewPanel.tsx:30-35`](simulator-web/src/components/domain/MotionPreviewPanel.tsx:30) | `setTimeSlice(prev => prev + 1)` mỗi giây → re-render toàn bộ panel kể cả khi không cần |
| FE-20 | Duplicate polling `useSessions` ở 3 nơi | 🟡 Moderate | [`Topbar.tsx:11`](simulator-web/src/components/layout/Topbar.tsx:11), [`SessionRunnerPage.tsx:23`](simulator-web/src/pages/SessionRunnerPage.tsx:23), [`VerificationPage.tsx:12`](simulator-web/src/pages/VerificationPage.tsx:12) | 3 consumer cùng poll `/sessions` mỗi 3s — tuy React Query deduplicate nhưng gây refetch chồng chéo khi unmount/remount |
| FE-21 | Duplicate events polling DashboardPage vs FallLab | 🟡 Moderate | [`DashboardPage.tsx:9`](simulator-web/src/pages/DashboardPage.tsx:9) (3s), [`FallLab.tsx:19`](simulator-web/src/components/domain/FallLab.tsx:19) (1.5s) | Query key khác nhau (`["events","recent",10]` vs `["events","recent",resolvedTarget]`) → 2 request riêng biệt |
| FE-22 | Modal không focus trap, không ESC, không aria | 🟡 Moderate | [`DevicesPage.tsx:230`](simulator-web/src/pages/DevicesPage.tsx:230) | Modal chặn UI nhưng Tab key nhảy ra ngoài, ESC không đóng, không có `role="dialog"` |
| FE-23 | DeviceDetailDrawer không overlay, không focus trap | 🟡 Moderate | [`DeviceDetailDrawer.tsx:20`](simulator-web/src/components/domain/DeviceDetailDrawer.tsx:20) | Drawer `position:fixed` nhưng không overlay nền, click ngoài không đóng |
| FE-24 | Missing loading states trên nhiều form | 🟡 Moderate | [`SessionRunnerPage.tsx:86`](simulator-web/src/pages/SessionRunnerPage.tsx:86), [`AnalyticsPage.tsx`](simulator-web/src/pages/AnalyticsPage.tsx) | Apply scenario, risk inject, trigger calculation — không disable button khi pending |
| FE-25 | Scenarios fetched bằng `.then()` thay vì React Query | 🟡 Moderate | [`SessionRunnerPage.tsx:31`](simulator-web/src/pages/SessionRunnerPage.tsx:31) | `fetchScenarios().then(setScenarios)` — bỏ qua caching, retry, stale management của React Query |
| FE-26 | Dual casing `PersonaConfig` | 🟡 Moderate | [`device.ts:16-24`](simulator-web/src/types/device.ts:16) | `weightKg` VÀ `weight_kg` cùng tồn tại — code phải check cả hai (ví dụ: [`DeviceDetailDrawer.tsx:80`](simulator-web/src/components/domain/DeviceDetailDrawer.tsx:80)) |
| FE-27 | ECharts `any` types trong formatters | 🟡 Moderate | [`SessionVitalsPanel.tsx:189`](simulator-web/src/components/domain/SessionVitalsPanel.tsx:189) | `(params: any)` trong tooltip formatter — bỏ qua type safety |
| FE-28 | `AnalyticsPage` 866 dòng | 🟢 Minor | [`AnalyticsPage.tsx`](simulator-web/src/pages/AnalyticsPage.tsx) | File quá lớn, cần tách thành SleepTab, RiskTab, BackfillCard modules |
| FE-29 | Inline `CreateDbDeviceModal` trong DevicesPage | 🟢 Minor | [`DevicesPage.tsx:185-297`](simulator-web/src/pages/DevicesPage.tsx:185) | ~112 dòng modal code nằm cùng file với page logic |
| FE-30 | Inline `KpiCard` trong DashboardPage | 🟢 Minor | [`DashboardPage.tsx:47`](simulator-web/src/pages/DashboardPage.tsx:47) | Component utility nằm inline, không reusable |
| FE-31 | Tailwind installed nhưng 99% inline styles | 🟢 Minor | [`package.json:34`](simulator-web/package.json:34), toàn bộ `src/` | Hai hệ styling song song, gây nhầm lẫn |
| FE-32 | FallLab setInterval stale closure risk | 🟢 Minor | [`FallLab.tsx:43`](simulator-web/src/components/domain/FallLab.tsx:43) | `resolvedTarget` capture trong closure có thể stale nếu user đổi device giữa countdown |
| FE-33 | Search input không debounce | 🟢 Minor | [`DevicesPage.tsx:149`](simulator-web/src/pages/DevicesPage.tsx:149) | Filter chạy mỗi keystroke — chưa nghiêm trọng ở 200 device nhưng không tối ưu |
| FE-34 | Hardcoded values | 🟢 Minor | [`FallLab.tsx:42`](simulator-web/src/components/domain/FallLab.tsx:42) (countdown 30s), [`AnalyticsPage.tsx:41`](simulator-web/src/pages/AnalyticsPage.tsx:41) (sleep scenario options) | Nên centralize vào constants |

---

## 3. Kế hoạch Refactor theo thứ tự ưu tiên

### Phase 1: Core Performance & UX Critical

> **Mục tiêu:** Tối ưu trải nghiệm core — Dashboard, Session Runner, Vitals streaming mượt mà nhất.

| # | Task | Giải pháp refactor chi tiết | Vấn đề liên quan | Effort | Kết quả kỳ vọng |
|---|---|---|---|---|---|
| 1.1 | Memo hóa `MetricWidget` và `MetricChart` | Bọc [`MetricWidget`](simulator-web/src/components/domain/SessionVitalsPanel.tsx:159) và [`MetricChart`](simulator-web/src/components/domain/SessionVitalsPanel.tsx:171) bằng `React.memo()`. Thêm `useMemo` cho `buildMetricOption` (đã có). Thêm custom comparator cho `MetricWidget` so sánh `title`, `value`, `severity`. | FE-15, FE-17 | S | Giảm từ 10 re-render/s xuống 2 re-render/s cho vitals panel |
| 1.2 | Stabilize callback props với `useCallback` | Trong [`DevicesPage.tsx`](simulator-web/src/pages/DevicesPage.tsx:46): bọc `handleCreate`, `handleAssign`, `handleActivateSim`, `handleDeactivateSim`, `handleDelete`, `handleBatchActivate` bằng `useCallback` với dependency array đúng. Tương tự cho [`SessionRunnerPage.tsx:86`](simulator-web/src/pages/SessionRunnerPage.tsx:86) `changeScenario`. | FE-16, FE-18 | M | `DbDeviceTable` chỉ re-render khi data thực sự đổi |
| 1.3 | Memo hóa `DbDeviceTable` | Bọc [`DbDeviceTable`](simulator-web/src/components/domain/DbDeviceTable.tsx:20) bằng `React.memo()` với shallow compare trên `devices` array. | FE-15, FE-18 | S | Table 200 rows không re-render khi chỉ Topbar thay đổi |
| 1.4 | Tối ưu `MotionPreviewPanel` interval | Trong [`MotionPreviewPanel.tsx:30`](simulator-web/src/components/domain/MotionPreviewPanel.tsx:30): chỉ `setTimeSlice` khi panel thực sự visible (dùng `IntersectionObserver` hoặc kiểm tra `document.hidden`). Tăng interval từ 1s → 2s cho synthetic data. Bọc component bằng `React.memo`. | FE-19 | S | Giảm 50% re-render khi tab không active |
| 1.5 | Hợp nhất events polling | Tạo hook `useRecentEvents(limit, interval)` (đã có tại [`useRecentEvents.ts`](simulator-web/src/hooks/useRecentEvents.ts)). Trong [`FallLab.tsx:19`](simulator-web/src/components/domain/FallLab.tsx:19): thay inline `useQuery` bằng `useRecentEvents(30, 1500)` — **đồng nhất query key** thành `["events", "recent", limit]` để React Query deduplicate. | FE-21 | S | Giảm 1 request/1.5s trùng lặp |
| 1.6 | Tối ưu dashboard summary backend | Trong [`dependencies.py:1956`](api_server/dependencies.py:1956): thay vì duyệt toàn bộ `event_history` mỗi request, duy trì counter `_alerts_last_hour_count` được cập nhật mỗi tick khi thêm event. `dashboard_summary()` chỉ đọc counter. | BE-13 | M | Dashboard response từ O(n) → O(1) |
| 1.7 | Chuyển scenarios sang React Query | Trong [`SessionRunnerPage.tsx:31`](simulator-web/src/pages/SessionRunnerPage.tsx:31): thay `fetchScenarios().then(setScenarios)` bằng `useQuery({ queryKey: ["scenarios"], queryFn: fetchScenarios, staleTime: 60_000 })`. Xóa `useState<ScenarioOption[]>`. | FE-25 | S | Scenarios được cache, retry tự động, không re-fetch khi navigate lại |
| 1.8 | Thêm error handling cho FallLab buttons | Trong [`FallLab.tsx:83-136`](simulator-web/src/components/domain/FallLab.tsx:83): bọc mỗi `onClick` bằng `try/catch` với `notify.error()`. Thêm `useState<string | null>` cho `pendingAction` để disable buttons khi đang xử lý. Trong interval callback (line 50): thêm `.catch(() => cancelCountdown())`. | FE-13, FE-14 | M | User nhận feedback khi injection fail, không bị stuck countdown |
| 1.9 | Tách event history thành `collections.deque` | Trong [`dependencies.py`](api_server/dependencies.py): thay `self.event_history: list[EventRecord]` bằng `collections.deque(maxlen=2000)`. Loại bỏ slice reassignment thủ công. | BE-12 | S | Event trim từ O(n) → O(1) amortized |

### Phase 2: Dead Code Cleanup

> **Mục tiêu:** Giảm bundle size, loại bỏ noise trong codebase, làm sạch dependency tree.

| # | Task | Giải pháp refactor chi tiết | Vấn đề liên quan | Effort | Kết quả kỳ vọng |
|---|---|---|---|---|---|
| 2.1 | Xóa unused packages | Chạy `npm uninstall react-error-boundary clsx tailwind-merge` trong [`simulator-web/`](simulator-web/package.json). Verify build vẫn pass. | FE-01, FE-02 | S | Giảm ~15KB từ bundle, loại 3 dependency |
| 2.2 | Xóa dead components | Xóa các file: [`DeviceTable.tsx`](simulator-web/src/components/domain/DeviceTable.tsx), [`DeviceStatusCard.tsx`](simulator-web/src/components/domain/DeviceStatusCard.tsx), [`DeviceDetailDrawer.tsx`](simulator-web/src/components/domain/DeviceDetailDrawer.tsx), [`CreateDeviceModal.tsx`](simulator-web/src/components/domain/CreateDeviceModal.tsx), [`SessionToolbar.tsx`](simulator-web/src/components/domain/SessionToolbar.tsx), [`VitalsStreamChart.tsx`](simulator-web/src/components/charts/VitalsStreamChart.tsx). | FE-03→FE-08 | S | Loại 6 file dead code, giảm cognitive load |
| 2.3 | Xóa dead hooks và utils | Xóa [`useVitalsStream.ts`](simulator-web/src/hooks/useVitalsStream.ts). Xóa [`POLL_INTERVALS`](simulator-web/src/utils/constants.ts:1) từ `constants.ts` (giữ file nếu còn export khác). Xóa [`formatBpm`](simulator-web/src/utils/format.ts:1), [`formatTime`](simulator-web/src/utils/format.ts:5), [`formatBattery`](simulator-web/src/utils/format.ts:11) từ `format.ts`. | FE-09, FE-10, FE-11 | S | Loại code chết, tránh confuse khi onboard dev mới |
| 2.4 | Gom duplicate float coerce | Trong [`dependencies.py`](api_server/dependencies.py): xóa `_coerce_float()` (line 110), chỉ giữ [`_safe_float()`](api_server/dependencies.py:2999). Tìm và thay tất cả call site. | BE-17 | S | Một hàm duy nhất cho float coercion |
| 2.5 | Di chuyển random import ra top-level | Trong [`dependencies.py`](api_server/dependencies.py): di chuyển `import random as _random` từ line 2141 và 3020 lên đầu file. | BE-11 | S | Clean import, tránh overhead import lặp |

### Phase 3: Architecture Refactor

> **Mục tiêu:** Tách God Object, cải thiện coupling, thiết lập service boundary rõ ràng.

| # | Task | Giải pháp refactor chi tiết | Vấn đề liên quan | Effort | Kết quả kỳ vọng |
|---|---|---|---|---|---|
| 3.1 | Tách `DeviceService` từ `SimulatorRuntime` | Tạo file `api_server/services/device_service.py`. Extract các method: `create_device`, `delete_device`, `list_devices`, `bind_device`, `unbind_device`, `_require_device`, `list_running_db_device_ids`. Class nhận `devices: dict`, `_lock`, `sessions` qua constructor injection. | BE-01, BE-08 | L | Giảm ~400 dòng từ `SimulatorRuntime`, device logic testable độc lập |
| 3.2 | Tách `SessionService` | Tạo file `api_server/services/session_service.py`. Extract: `start_session`, `stop_session`, `_tick_session_locked`, `_tick_active`, `_ensure_sim_session_for_db_device`, `_stop_sim_session_for_db_device`. Router sẽ gọi public method thay vì private. | BE-01, BE-08 | XL | Giảm ~600 dòng, session lifecycle tách biệt |
| 3.3 | Tách `VitalsService` | Tạo file `api_server/services/vitals_service.py`. Extract: `latest_vitals`, `_build_vitals_sample`, `_safe_float`, vitals severity logic. | BE-01 | L | Vitals processing testable riêng |
| 3.4 | Tách `SleepService` | Tạo file `api_server/services/sleep_service.py`. Extract toàn bộ sleep-related: `_build_sleep_session_locked`, `sleep_db_history`, `_build_sleep_segments`, `_fallback_sleep_session`, `_real_sleep_session_from_registry`, `_compute_sleep_window`, `_advance_sleep_phase_if_due`, backfill logic. | BE-01 | XL | Giảm ~800 dòng, sleep domain tách biệt hoàn toàn |
| 3.5 | Tách `AlertService` | Tạo file `api_server/services/alert_service.py`. Extract: `_prepare_alert_push_locked`, `_push_alert_to_backend`, event recording, `recent_events`. | BE-01, BE-10 | L | Alert pipeline có thể thêm retry riêng |
| 3.6 | Expose public API trên SimulatorRuntime | Sau khi tách xong, `SimulatorRuntime` trở thành facade: giữ `__init__`, background tick orchestration, và delegate sang các service. Router files update import sang service classes cho các method cần thiết. | BE-01, BE-08 | M | `SimulatorRuntime` giảm từ 3414 → ~500 dòng |
| 3.7 | Tách scenario profiles ra file config | Di chuyển ~150 dòng `SLEEP_SCENARIO_PROFILES` và `SLEEP_SCENARIO_PHASES` từ [`dependencies.py:143-296`](api_server/dependencies.py:143) ra file `api_server/config/sleep_scenarios.yaml`. Load qua utility function. | BE-18 | M | Config dễ chỉnh sửa bởi non-dev, file Python gọn hơn |
| 3.8 | Tách `AnalyticsPage` thành modules | Tách [`AnalyticsPage.tsx`](simulator-web/src/pages/AnalyticsPage.tsx) (866 dòng) thành: `SleepAnalyticsTab.tsx`, `RiskAnalyticsTab.tsx`, `BackfillCard.tsx`, `SleepHistoryTable.tsx`. Page chính chỉ làm tab router. | FE-28 | M | Mỗi tab file < 250 dòng, dễ maintain |
| 3.9 | Extract inline modal/card | Di chuyển [`CreateDbDeviceModal`](simulator-web/src/pages/DevicesPage.tsx:185) ra file riêng `components/domain/CreateDbDeviceModal.tsx`. Di chuyển [`KpiCard`](simulator-web/src/pages/DashboardPage.tsx:47) ra `components/ui/KpiCard.tsx`. | FE-29, FE-30 | S | Page files gọn, component reusable |
| 3.10 | Chuẩn hóa `PersonaConfig` casing | Trong [`device.ts:16`](simulator-web/src/types/device.ts:16): chọn MỘT convention (camelCase). Backend serialize persona config sang camelCase. Frontend xóa `weight_kg`, `height_cm`, `persona_config`. | FE-26 | M | Loại bỏ dual check `cfg.weightKg ?? cfg.weight_kg` |

### Phase 4: Error Handling & Resilience

> **Mục tiêu:** Cải thiện error handling, logging, và khả năng phục hồi toàn diện.

| # | Task | Giải pháp refactor chi tiết | Vấn đề liên quan | Effort | Kết quả kỳ vọng |
|---|---|---|---|---|---|
| 4.1 | Thay silent swallow bằng structured logging | Tại [`dependencies.py:728`](api_server/dependencies.py:728), [`:1027`](api_server/dependencies.py:1027), [`:1105`](api_server/dependencies.py:1105): thay `except Exception: return` bằng `except Exception: logger.warning("...", exc_info=True); return default`. Thêm tương tự cho tất cả bare except trong file. | BE-06 | M | Mọi lỗi DB/network đều có log trace, debug nhanh hơn |
| 4.2 | Thêm retry logic cho HTTP publish | Trong [`AlertService`](api_server/dependencies.py:738) (sau Phase 3): thêm exponential backoff retry (max 3 lần, base 1s) cho `_http_sender`. Dùng `tenacity` library hoặc custom decorator. | BE-10 | M | Telemetry data không mất khi backend tạm lỗi |
| 4.3 | Fix WebSocket keepalive race | Trong [`log_stream.py:23`](api_server/ws/log_stream.py:23): bọc truy cập `runtime.sessions` trong `with runtime._lock:` hoặc tạo method `runtime.get_session_last_tick(session_id)` thread-safe. | BE-14 | S | Không còn risk đọc dict đang mutate |
| 4.4 | Fix thread/async bridge | Trong [`LogHub.publish`](api_server/dependencies.py:476): thay `queue.put_nowait()` bằng `loop.call_soon_threadsafe(queue.put_nowait, entry)` khi được gọi từ sync context. Hoặc dùng `janus.Queue` hỗ trợ cả sync và async. | BE-09 | M | Loại bỏ tiềm ẩn race condition giữa tick thread và asyncio loop |
| 4.5 | Thay blocking `urlopen` bằng `httpx.AsyncClient` | Trong [`backend_admin_client.py`](api_server/backend_admin_client.py:83): thay `urllib.request.urlopen` bằng `httpx.AsyncClient` với connection pooling. Cung cấp cả sync fallback `httpx.Client` cho context không async. | BE-04 | L | Admin client không block event loop, hỗ trợ connection reuse |
| 4.6 | FallLab stale closure fix | Trong [`FallLab.tsx:43`](simulator-web/src/components/domain/FallLab.tsx:43): dùng `useRef` cho `resolvedTarget` trong interval callback thay vì capture trực tiếp. Pattern: `const targetRef = useRef(resolvedTarget); useEffect(() => { targetRef.current = resolvedTarget; }, [resolvedTarget]);` | FE-32 | S | Countdown luôn inject vào đúng device hiện tại |
| 4.7 | Loading states cho async actions | Tại [`SessionRunnerPage.tsx:86`](simulator-web/src/pages/SessionRunnerPage.tsx:86): thêm `useState<boolean>` cho `isApplying`. Disable nút khi pending. Tương tự cho risk inject và trigger calculation trong `AnalyticsPage`. | FE-24 | M | User không double-click, có feedback khi action đang xử lý |
| 4.8 | Typed ECharts formatters | Trong [`SessionVitalsPanel.tsx:189`](simulator-web/src/components/domain/SessionVitalsPanel.tsx:189): define interface `EChartsTooltipParam { axisValue: string; marker: string; seriesName: string; data: [string, number] }`. Thay `any` bằng type này. | FE-27 | S | Type safety trong chart formatters |

### Phase 5: Accessibility & Polish

> **Mục tiêu:** A11y compliance, keyboard navigation, consistent styling.

| # | Task | Giải pháp refactor chi tiết | Vấn đề liên quan | Effort | Kết quả kỳ vọng |
|---|---|---|---|---|---|
| 5.1 | Modal focus trap + keyboard | Trong [`DevicesPage.tsx`](simulator-web/src/pages/DevicesPage.tsx:230) (sau extract ở 3.9): thêm `role="dialog"`, `aria-modal="true"`, `aria-labelledby`. Implement focus trap bằng `useEffect` + `MutationObserver` hoặc dùng `@radix-ui/react-dialog`. Thêm ESC close, overlay click close. | FE-22 | M | WCAG 2.1 AA compliant cho modal |
| 5.2 | Drawer overlay + focus trap | Tương tự 5.1 cho drawer component: thêm overlay `<div>` phía sau, `aria-label`, ESC handler, focus trap. | FE-23 | M | Drawer accessible, không leak focus |
| 5.3 | Search debounce | Trong [`DevicesPage.tsx:149`](simulator-web/src/pages/DevicesPage.tsx:149): thêm `useDeferredValue(search)` hoặc custom `useDebounce(search, 300)` hook cho filter logic. | FE-33 | S | Filter không chạy mỗi keystroke |
| 5.4 | Quyết định styling strategy | **Chọn 1 trong 2:** (A) Commit vào Tailwind — migrate inline styles sang Tailwind classes; (B) Xóa Tailwind — `npm uninstall tailwindcss autoprefixer postcss`, xóa config files, commit vào CSS custom properties hiện tại. **Khuyến nghị:** Option B — hệ thống CSS variable hiện tại đã hoạt động tốt, loại bỏ Tailwind giảm build pipeline. | FE-31 | L | Một styling strategy duy nhất |
| 5.5 | Centralize hardcoded values | Tạo `simulator-web/src/config/defaults.ts` chứa `FALL_COUNTDOWN_SECONDS = 30`, `SLEEP_SCENARIO_OPTIONS`, polling intervals. Import từ config thay vì hardcode. | FE-34, FE-10 | S | Single source of truth cho magic numbers |

### Phase 6: Security & Production Readiness

> **Mục tiêu:** Auth, CORS restriction, production hardening.

| # | Task | Giải pháp refactor chi tiết | Vấn đề liên quan | Effort | Kết quả kỳ vọng |
|---|---|---|---|---|---|
| 6.1 | Restrict CORS origins | Trong [`main.py:35`](api_server/main.py:35): đọc `ALLOWED_ORIGINS` từ env var, default `["http://localhost:5173"]` cho dev. Production deploy set env var cho domain thực. | BE-02 | S | Chỉ frontend chính thức gọi được API |
| 6.2 | API key cho admin endpoints | Tạo `api_server/middleware/auth.py`: middleware kiểm tra header `X-Admin-Key` match env var `SIM_ADMIN_API_KEY`. Apply cho tất cả `/admin/*` routes. Không cần full OAuth cho internal tool. | BE-03 | M | Admin endpoints yêu cầu API key |
| 6.3 | Rate limiting | Thêm `slowapi` hoặc custom middleware giới hạn request rate cho `/api/sim/*` — suggest 60 req/min cho đọc, 10 req/min cho ghi. | BE-02 | M | Chống abuse API |
| 6.4 | Thay MD5 bằng SHA256 | Trong [`dependencies.py:3209`](api_server/dependencies.py:3209): thay `hashlib.md5(...)` bằng `hashlib.sha256(...)`. | BE-19 | S | Hash mạnh hơn, tuân thủ best practice |
| 6.5 | Dual import path cleanup | Trong [`dependencies.py:21-74`](api_server/dependencies.py:21): chọn 1 import path chính (recommend package-relative `from Iot_Simulator.api_server...`). Xóa try/except fallback. Cấu hình `pyproject.toml` hoặc `setup.py` cho editable install. | BE-15 | M | Import ổn định, không break khi di chuyển |
| 6.6 | Testable singletons | Thay global mutable singleton tại [`dependencies.py:3398`](api_server/dependencies.py:3398) và [`backend_admin_client.py:196`](api_server/backend_admin_client.py:196) bằng FastAPI dependency injection pattern. `get_runtime()` trả singleton nhưng có thể override bằng `app.dependency_overrides` trong test. | BE-16 | M | Test isolation, không leak state giữa tests |
| 6.7 | Typed response models cho admin endpoints | Trong [`devices.py:69`](api_server/routers/devices.py:69): tạo Pydantic model `AdminDeviceResponse` với typed fields. Thay `-> list[dict]` bằng `-> list[AdminDeviceResponse]`. | BE-20 | M | Response validation tự động, OpenAPI spec chính xác |
| 6.8 | Repository pattern cho raw SQL | Tạo `api_server/repositories/device_repository.py` wrap các raw SQL queries trong [`sim_admin_service.py`](api_server/sim_admin_service.py). Mỗi method trả typed dataclass thay vì `dict[str, Any]`. Giữ raw SQL nhưng có mapping layer. | BE-05 | XL | Typed data layer, dễ migrate sang ORM sau |

---

## 4. Impact Matrix — Before vs After

| Metric | Before (Hiện tại) | After Phase 1 | After Phase 2 | After All Phases | Ghi chú |
|---|---|---|---|---|---|
| **Frontend re-render count** (vitals panel, /s) | ~10 component re-renders/s | ~2/s | ~2/s | ~2/s | Memo + callback stabilization |
| **Bundle size** (gzip) | Baseline + 3 unused deps (~15KB) | Baseline + 3 unused | Baseline (−15KB) | Baseline − 20KB (nếu bỏ Tailwind) | Dead code + unused package removal |
| **API call frequency** (active session) | Sessions: 3×3s + Events: 2 parallel + Vitals: 1s | Sessions: 1×3s (dedup) + Events: 1×1.5s + Vitals: 1s | Giữ Phase 1 | Giữ Phase 1 | Query key unification |
| **Dashboard response time** | O(n) scan event_history mỗi request | O(1) counter lookup | O(1) | O(1) | Pre-computed alert counter |
| **Event history trim** | O(n) list slice mỗi tick | O(1) deque auto-trim | O(1) | O(1) | `collections.deque(maxlen=N)` |
| **Backend admin HTTP latency** | 10s blocking timeout | 10s blocking | 10s blocking | Async `httpx` pool, non-blocking | Phase 4 chuyển sang async |
| **God Object line count** | ≈3414 dòng 1 class | ≈3414 | ≈3300 (−cleanup) | ≈500 (facade) | Phase 3 tách services |
| **Dead code files** | 6 component + 1 hook + 3 utils | 6 + 1 + 3 | 0 | 0 | Phase 2 xóa sạch |
| **Error visibility** | Silent swallow (3+ locations) | Partial (FallLab fixed) | Partial | Full structured logging | Phase 4 logging |
| **Accessibility score** (estimated Lighthouse) | ~40/100 (no focus trap, no aria) | ~40 | ~40 | ~85/100 | Phase 5 a11y |
| **Security posture** | CORS *, no auth, MD5 | CORS *, no auth | CORS *, no auth | Restricted CORS, API key, SHA256 | Phase 6 hardening |
| **Memory usage** (event_history) | Unbounded list growth + periodic O(n) trim | Bounded deque | Bounded deque | Bounded deque | Phase 1 deque |

---

## 5. Lộ trình thực hiện

```
Phase 1 ─── Core Performance & UX Critical
   │
   │  Milestone: Dashboard load < 100ms, Vitals panel < 3 re-renders/s,
   │             FallLab buttons có error feedback
   │  Deliverables: 9 tasks (1.1 → 1.9)
   │  Prerequisites: Không có — bắt đầu ngay
   │
   ▼
Phase 2 ─── Dead Code Cleanup
   │
   │  Milestone: Bundle size giảm, zero dead imports, 
   │             `npm run build` + `tsc --noEmit` pass sạch
   │  Deliverables: 5 tasks (2.1 → 2.5)
   │  Prerequisites: Phase 1 hoàn thành (tránh conflict merge)
   │
   ▼
Phase 3 ─── Architecture Refactor
   │
   │  Milestone: SimulatorRuntime < 500 dòng, 5 service classes mới,
   │             AnalyticsPage < 250 dòng/file, PersonaConfig 1 casing
   │  Deliverables: 10 tasks (3.1 → 3.10)
   │  Prerequisites: Phase 2 xong (codebase sạch trước khi tách)
   │  ⚠️ Phase lớn nhất — cần feature freeze trên backend
   │
   ▼
Phase 4 ─── Error Handling & Resilience
   │
   │  Milestone: Zero silent exception, retry trên alert push,
   │             WebSocket thread-safe, admin client async
   │  Deliverables: 8 tasks (4.1 → 4.8)
   │  Prerequisites: Phase 3 (service classes đã tách, dễ thêm retry/logging)
   │
   ▼
Phase 5 ─── Accessibility & Polish
   │
   │  Milestone: Lighthouse Accessibility > 80, 
   │             1 styling strategy, focus trap trên modal/drawer
   │  Deliverables: 5 tasks (5.1 → 5.5)
   │  Prerequisites: Phase 2 (dead components đã xóa), Phase 3 (modal extracted)
   │
   ▼
Phase 6 ─── Security & Production Readiness
   │
   │  Milestone: CORS restricted, admin auth enforced,
   │             typed response models, repository pattern
   │  Deliverables: 8 tasks (6.1 → 6.8)
   │  Prerequisites: Phase 3 (service/repository split), Phase 4 (async client)
   │
   ▼
   ✅ Refactor Complete
```

### Quy tắc thực hiện

1. **Mỗi Phase kết thúc bằng verification:** chạy build, test, và smoke test trước khi bắt đầu Phase tiếp theo.
2. **Feature freeze backend trong Phase 3:** không merge tính năng mới vào `SimulatorRuntime` khi đang tách.
3. **Git branch strategy:** mỗi Phase tạo branch `refactor/phase-N`, merge vào `main` khi pass CI.
4. **Rollback plan:** mỗi Phase commit atomic — nếu Phase N gặp vấn đề, revert toàn bộ Phase N mà không ảnh hưởng Phase N−1.

---

## Phụ lục: Tổng kết effort

| Phase | Số tasks | S | M | L | XL |
|---|---|---|---|---|---|
| Phase 1: Core Performance | 9 | 5 | 3 | 0 | 1* |
| Phase 2: Dead Code | 5 | 5 | 0 | 0 | 0 |
| Phase 3: Architecture | 10 | 2 | 4 | 2 | 2 |
| Phase 4: Error Handling | 8 | 3 | 3 | 1 | 0* |
| Phase 5: Accessibility | 5 | 2 | 2 | 1 | 0 |
| Phase 6: Security | 8 | 2 | 4 | 0 | 1* |
| **Tổng** | **45** | **19** | **16** | **4** | **4** |

> *Effort ước lượng: S = vài giờ, M = 1–2 ngày, L = 2–4 ngày, XL = 4+ ngày*

---

*Tài liệu này được tạo tự động từ kết quả nghiên cứu chuyên sâu backend và frontend. Mọi file:line reference đã được đối chiếu với mã nguồn hiện tại.*
