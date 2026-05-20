# Phase Report — Trung tâm Bằng chứng Refactor

## Summary

Refactor trang `/verification` (Trung tâm Bằng chứng) để bỏ thông tin thừa
(session ID dạng `[xxxxxxxx…]`, raw deviceId mono lặp lại) và tập trung vào
hai tín hiệu cốt lõi: **liveness** (thiết bị có đang phát dữ liệu hay không)
và **log evidence** (3 dòng log gần nhất chứng minh điều đó). Mỗi thiết bị
giờ là một thẻ độc lập trong lưới `DeviceEvidenceCard`, ghép sẵn pipeline 3
stage rút gọn (Telemetry / Risk score / Alert dispatch) và một strip log nội
tuyến. `LogViewer` ở dưới cùng nhận filter focus theo deviceId khi user bấm
"Xem log đầy đủ →" từ một thẻ.

Mockup HTML đã được duyệt trước (`docs/mockups/evidence-center.html`) trước
khi viết React, nên cấu trúc final khớp 1-1 với layout đã chốt.

## Files Modified

### Created

- `simulator-web/src/hooks/useRelativeTime.ts` — hook trả `{ label, ageMs }`,
  re-render mỗi 1s, dùng cho liveness pill + summary cập nhật.
- `simulator-web/src/components/domain/DeviceEvidenceCard.tsx` — thẻ
  bằng-chứng-một-thiết-bị (header, liveness pill, pipeline 3 stage, log
  strip 3 dòng, failure banner, footer focus-link).
- `simulator-web/src/components/domain/EvidenceGrid.tsx` — wrapper Card +
  grid `auto-fill minmax(360px, 1fr)`, group logs theo deviceId trong
  `useMemo`, giới hạn 50 dòng/device để FE nhẹ.

### Modified

- `simulator-web/src/pages/VerificationPage.tsx` — bỏ
  `VerificationTable`/`LastGoodPublishCard`, thêm state
  `focusedDeviceId`, render `EvidenceGrid` + `LogViewer`, viết
  `LivenessSummary` thay cho dòng session-ID cũ.
- `simulator-web/src/components/domain/LogViewer.tsx` — thêm props
  `focusedDeviceId` / `onClearFocus`, sync `device` filter qua
  `useEffect`, render filter pill có nút `×`.

### Untouched (theo plan, giữ để rollback dễ)

- `simulator-web/src/components/domain/VerificationTable.tsx`
- `simulator-web/src/components/domain/LastGoodPublishCard.tsx`

## Verification

### Build (tsc + vite)

```
> iot-simulator-web@0.1.0 build
> tsc -b && vite build

dist/assets/VerificationPage-DW6bZIhT.js   32.22 kB │ gzip: 10.66 kB
...
✓ built in 14.73s
```

PASS — không có lỗi TypeScript, bundle `VerificationPage` build thành công.

### Unit tests (vitest)

```
> iot-simulator-web@0.1.0 test
> vitest run

Test Files  6 passed (6)
     Tests  23 passed (23)
  Duration  4.58s
```

PASS — tất cả test cũ (sanity, hooks, components UI) tiếp tục xanh sau
refactor.

### Git scope

```
M simulator-web/src/components/domain/LogViewer.tsx
M simulator-web/src/pages/VerificationPage.tsx
M simulator-web/tsconfig.app.tsbuildinfo
?? simulator-web/src/components/domain/DeviceEvidenceCard.tsx
?? simulator-web/src/components/domain/EvidenceGrid.tsx
?? simulator-web/src/hooks/useRelativeTime.ts
```

Đúng phạm vi đã khai báo. Worktree `Iot_Simulator_evidence-refactor` trên
branch `agent/evidence-center-refactor`; repo gốc `Iot_Simulator_clean`
không bị động.

### Skipped

- Không có script `lint` trong `package.json` (`npm run` chỉ liệt kê `dev`,
  `build`, `preview`, `test`, `test:watch`, `test:ui`). Bỏ qua bước lint
  riêng — `tsc -b` chạy bên trong `npm run build` đã đảm bảo type-check.
- Screenshot dev-server chưa chụp ở bước này vì cần backend `api_server` +
  một phiên đang chạy. Sẽ làm khi anh chạy thử end-to-end và cần em đính
  ảnh vào.

## Verdict

PASS — refactor đã hoàn tất, build + test xanh, scope file khớp plan, mockup
HTML và code React thống nhất. Sẵn sàng cho anh chạy
`npm run dev` trong worktree để soi UI thật và quyết định xoá
`VerificationTable.tsx` / `LastGoodPublishCard.tsx` trong plan dọn dẹp tiếp
theo.
