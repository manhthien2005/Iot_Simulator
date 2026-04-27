# Fall Detection Pipeline — Cấu hình phát hiện té ngã (Wrist-Worn)

## Mục đích

File `fall_pipeline_wrist_config.json` định nghĩa **pipeline phát hiện té ngã 2 giai đoạn** cho thiết bị đeo tay (smartwatch). Pipeline bao gồm: pre-trigger liên tục trên thiết bị → gọi fall model khi phát hiện ứng viên → xác nhận bằng dấu hiệu sinh tồn sau té ngã.

## Cách sử dụng

File được load bởi [`api_server/routers/settings.py`](../../api_server/routers/settings.py) qua API endpoint `/api/sim/settings`. Đường dẫn cấu hình:

```python
_FALL_CONFIG_PATH = _PROJECT_ROOT / "pre_model_trigger" / "fall" / "fall_pipeline_wrist_config.json"
```

## 3 Giai đoạn (Stages)

### Stage 1: Pre-Trigger (chạy liên tục trên thiết bị)

Phát hiện các sự kiện ứng viên té ngã **rẻ về tính toán** trước khi gọi fall model.

- **Hard trigger**: Kích hoạt ngay khi `accel_mag_peak ≥ 3.0 G`
- **Soft trigger**: Kết hợp nhiều tín hiệu (gia tốc + tư thế + bất động + môi trường)
- **Streaming**: Cửa sổ 1s, bước trượt 0.2s, buffer trước 1.5s + sau 3.0s

### Stage 2: Fall Model (chạy khi Stage 1 trigger)

Gọi fall classifier chỉ trên event window đã trigger.

- **Input**: Event window (pre-buffer + post-buffer) + derived features
- **Output**: `fall_probability` (0–1) + `predicted_label` (FALL / NON_FALL)
- **Ngưỡng mặc định**: `fall_probability ≥ 0.7`

### Stage 3: Post-Fall Validation (xác nhận sau té ngã)

Xác nhận té ngã bằng bất động sau va chạm và dấu hiệu sinh tồn xấu đi.

- **Cửa sổ ngắn**: 10 phút — đánh giá tức thì
- **Cửa sổ mở rộng**: 60 phút — theo dõi xu hướng
- **Không bắt buộc health stream** — hoạt động với hoặc không có vital signs

## Cấu trúc file JSON

| Section | Mô tả |
|---------|-------|
| `version` / `name` / `description` | Metadata phiên bản |
| `scope` | Loại thiết bị (wrist-worn), tần số mẫu (50 Hz), đối tượng (adults) |
| `input_schema` | Schema đầu vào: accel (x,y,z), gyro (x,y,z), orientation, environment |
| `derived_features` | Công thức tính accel_mag, gyro_mag, delta pitch/roll/yaw, low_motion |
| `streaming_policy` | Cấu hình streaming: window, step, buffer, minimum event gap |
| `stage_1_pretrigger` | Hard trigger + soft trigger rules + supporting flags |
| `stage_2_fall_model` | Model input/output format, ngưỡng `fall_probability` |
| `stage_3_post_fall_validation` | Inactivity rules + vital sign instant/trend rules |
| `fusion_logic` | Logic kết hợp 3 stages thành kết quả cuối cùng |
| `output_schema` | Schema đầu ra: final_status, final_label, reason_codes |
| `example_output` | Ví dụ output hoàn chỉnh |

## Đơn vị đo

| Metric | Đơn vị | Mô tả |
|--------|--------|-------|
| `accel` (x, y, z) | G | Gia tốc 3 trục (1 G ≈ 9.81 m/s²) |
| `gyro` (x, y, z) | °/s (dps) | Vận tốc góc 3 trục |
| `orientation` (pitch, roll, yaw) | ° (degrees) | Góc tư thế |
| `floor_vibration` | arbitrary | Rung sàn (so với baseline) |
| `pressure_mat` | arbitrary | Tín hiệu thảm áp lực |
| `accel_mag` | G | Biên độ gia tốc tổng hợp |
| `gyro_mag` | °/s | Biên độ vận tốc góc tổng hợp |
| `heart_rate` | bpm | Nhịp tim |
| `resp_rate` | breaths/min | Nhịp thở |
| `body_temp` | °C | Nhiệt độ cơ thể |
| `spo2` | % | Độ bão hòa oxy máu |
| `sys_bp` / `dia_bp` | mmHg | Huyết áp tâm thu / tâm trương |
| `map_val` | mmHg | Mean Arterial Pressure |

## Bảng ngưỡng chính

### Stage 1 — Pre-Trigger

| Loại | Điều kiện | Reason Code |
|------|-----------|-------------|
| **Hard** | `accel_mag_peak ≥ 3.0 G` | IMPACT_PEAK_3G |
| Soft | `accel ≥ 2.5 G` AND `posture_change ≥ 45°` | IMPACT_PLUS_POSTURE_CHANGE |
| Soft | `accel ≥ 2.5 G` AND `low_motion ≥ 1.0s` | IMPACT_PLUS_LOW_MOTION |
| Soft | `gyro ≥ 250 °/s` AND `posture_change ≥ 45°` | GYRO_PLUS_POSTURE_CHANGE |
| Soft | `accel ≥ 2.0 G` AND `floor_vibration` AND `pressure_mat` | MULTIMODAL_ENVIRONMENTAL |

### Stage 2 — Fall Model

| Ngưỡng | Giá trị |
|--------|---------|
| `model_threshold_default` | 0.7 (70%) |

### Stage 3 — Post-Fall Vital Signs (Instant Rules)

| Vital | URGENT | SEND_TO_RISK_MODEL |
|-------|--------|---------------------|
| SpO₂ | < 90% | ≤ 94% |
| Resp Rate | ≤ 8 hoặc ≥ 25 breaths/min | 21–24 breaths/min |
| SBP | ≤ 90 mmHg | 91–100 mmHg |
| Heart Rate | ≤ 40 hoặc ≥ 131 bpm | 41–50 hoặc 111–130 bpm |
| Body Temp | ≤ 35.0 hoặc ≥ 39.1 °C | 38.0–39.0 °C |
| MAP | < 65 mmHg | — |

## Fusion Logic — Kết hợp 3 giai đoạn

Pipeline sử dụng logic tuần tự để quyết định kết quả cuối cùng:

| Điều kiện | Final Status | Final Label |
|-----------|-------------|-------------|
| Stage 1 không trigger | `NO_EVENT` | NON_FALL |
| Stage 1 trigger + `fall_prob < 0.7` | `NON_FALL_CANDIDATE` | NON_FALL |
| Stage 1 trigger + `fall_prob ≥ 0.7` | `FALL_CANDIDATE` | FALL_CANDIDATE |
| `fall_prob ≥ 0.85` + bất động/nằm | `CONFIRMED_FALL` | FALL |
| `fall_prob ≥ 0.7` + vital sign bất thường | `HIGH_RISK_FALL` | FALL |
| Bất kỳ vital rule nào severity = URGENT | `URGENT` | → Kích hoạt quy trình khẩn cấp |

### Nguyên tắc quan trọng

- **Không** phân loại té ngã chỉ từ Stage 1 — Stage 1 chỉ trigger Stage 2
- **Không** dùng vital sign xấu đi để thay thế fall model — chỉ dùng để tăng confidence và urgency
- Post-fall vital deterioration **tăng** mức nghiêm trọng, không phải bằng chứng té ngã
