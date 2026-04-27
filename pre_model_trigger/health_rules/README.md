# Health Rules — Cấu hình ngưỡng cảnh báo sức khỏe (Pre-Model Trigger)

## Mục đích

File `rules_config.json` định nghĩa **bộ quy tắc phân luồng rủi ro sức khỏe** cho hệ thống IoT health monitoring. Đây là tầng **pre-model** — phân loại dữ liệu sinh hiệu thành các mức độ nghiêm trọng trước khi gửi đến risk model phía sau. File này **không phải** công cụ chẩn đoán y khoa.

## Cách sử dụng

File được load bởi [`api_server/routers/settings.py`](../../api_server/routers/settings.py) qua API endpoint `/api/sim/settings`. Đường dẫn cấu hình:

```python
_RULES_CONFIG_PATH = _PROJECT_ROOT / "pre_model_trigger" / "health_rules" / "rules_config.json"
```

## Cấu trúc file JSON

| Section | Mô tả |
|---------|-------|
| `version` / `name` / `description` | Metadata phiên bản và mô tả bộ quy tắc |
| `scope` | Đối tượng áp dụng (adults only), các context hỗ trợ (resting, sleep, post_fall, active) |
| `severity` | Thứ tự mức độ nghiêm trọng và nguyên tắc xử lý |
| `inputs` | Các trường đầu vào: profile, vital signs, context fields |
| `derived_metrics` | Công thức tính BMI, pulse pressure, MAP |
| `data_quality` | Điều kiện lọc dữ liệu không hợp lệ (signal quality ≥ 0.7) |
| `sampling` | Cấu hình khoảng thời gian lấy mẫu và cửa sổ phân tích |
| `context_policy` | Chính sách riêng cho từng context (resting, sleep, post_fall, active) |
| `baseline` | Cấu hình baseline cá nhân (median + MAD, 7–14 ngày) |
| `profile` | Quy tắc điều chỉnh theo hồ sơ cá nhân (tuổi, BMI) |
| `instant_rules` | **Ngưỡng tức thì** — đánh giá từng chỉ số riêng lẻ |
| `profile_adjusted_rules` | Quy tắc nâng cấp WATCH → SEND khi profile high sensitivity |
| `time_series_rules` | Quy tắc chuỗi thời gian: drift, rapid change, recurrence |
| `combination_rules` | Quy tắc kết hợp nhiều chỉ số bất thường cùng lúc |
| `special_policies` | Chính sách đặc biệt: post-fall monitoring, sleep, COPD override |
| `decision_engine` | Thứ tự đánh giá và logic quyết định cuối cùng |
| `implementation_notes` | Ghi chú triển khai và ràng buộc quan trọng |

## Đơn vị đo

| Vital Sign | Đơn vị | Mô tả |
|------------|--------|-------|
| `heart_rate` | bpm | Nhịp tim (beats per minute) |
| `resp_rate` | breaths/min | Nhịp thở |
| `body_temp` | °C | Nhiệt độ cơ thể |
| `spo2` | % | Độ bão hòa oxy máu |
| `sys_bp` | mmHg | Huyết áp tâm thu |
| `dia_bp` | mmHg | Huyết áp tâm trương |
| `map_val` | mmHg | Mean Arterial Pressure = (SBP + 2×DBP) / 3 |
| `pulse_pressure` | mmHg | Áp lực mạch = SBP − DBP |
| `hrv` | ms | Heart Rate Variability (biến thiên nhịp tim) |

## Bảng ngưỡng chính (Instant Rules)

| Vital | URGENT | SEND_TO_RISK_MODEL | WATCH |
|-------|--------|---------------------|-------|
| Heart Rate | ≤ 40 hoặc ≥ 131 bpm | 41–50 hoặc 111–130 bpm | 91–110 bpm |
| Resp Rate | ≤ 8 hoặc ≥ 25 breaths/min | 21–24 breaths/min | 19–20 breaths/min |
| Body Temp | ≤ 35.0 hoặc ≥ 39.1 °C | 35.1–36.0 hoặc 38.0–39.0 °C | 37.5–37.9 °C |
| SpO₂ | < 90% | ≤ 94% | 95% |
| SBP | ≤ 90 hoặc ≥ 180 mmHg | 91–100 hoặc ≥ 140 mmHg | 121–139 mmHg |
| DBP | ≥ 120 mmHg | ≥ 90 mmHg | 80–89 mmHg |
| MAP | < 65 mmHg | 65–74 mmHg | 75–84 mmHg |
| Pulse Pressure | — | — | < 30 hoặc > 60 mmHg |

## Severity Levels

Hệ thống sử dụng 4 mức độ nghiêm trọng, chỉ leo thang (escalation-only):

| Level | Giá trị | Hành động |
|-------|---------|-----------|
| `NORMAL` | 0 | Tiếp tục lấy mẫu bình thường |
| `WATCH` | 1 | Tăng tần suất lấy mẫu, theo dõi xu hướng |
| `SEND_TO_RISK_MODEL` | 2 | Gọi risk model phía sau và ghi log sự kiện |
| `URGENT` | 3 | Gọi risk model **ngay lập tức** và kích hoạt quy trình khẩn cấp |

### Nguyên tắc quan trọng

- URGENT tức thì ghi đè tất cả các mức khác
- Profile chỉ được **tăng** độ nhạy, không được hạ ngưỡng URGENT
- Time-series chỉ được **nâng** severity, không được hạ
- Combination rules chỉ được **nâng** severity
- Kết quả cuối cùng = **max severity** từ tất cả các rule đã kích hoạt
- Giữ lại tất cả reason codes khi nhiều rules cùng trigger

## Quy trình đánh giá (Decision Engine)

1. Kiểm tra chất lượng dữ liệu (`data_quality`)
2. Xác định context (resting / sleep / post_fall / active)
3. Tính các chỉ số phái sinh (BMI, pulse pressure, MAP)
4. Cập nhật hoặc load baseline cá nhân
5. Đánh giá instant rules (ngưỡng tức thì)
6. Đánh giá profile-adjusted rules (điều chỉnh theo hồ sơ)
7. Đánh giá time-series rules (drift, rapid change, recurrence)
8. Đánh giá combination rules (kết hợp nhiều chỉ số)
9. Áp dụng special policies (post-fall, sleep, COPD)
10. Chọn **max severity** làm kết quả cuối cùng
