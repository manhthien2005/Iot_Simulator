# IoT Simulator — Feature Specification

Tài liệu này mô tả chi tiết **tất cả các Feature** mà IoT Simulator có thể cung cấp cho từng domain: Sinh hiệu (Vital Signs), Giấc ngủ (Sleep) và Té ngã (Fall Detection).

> **Dành cho:** Backend Engineers, AI/ML team, Reviewer, QA  
> **Cập nhật:** 2026-04-02  
> **Liên quan:** `simulator_core/generators.py`, `simulator_core/sleep_vitals_enricher.py`, `docs/design/05_Canonical_Schemas.md`

### Quy ước cột "Phát sinh"

| Ký hiệu | Ý nghĩa |
|---------|---------|
| ✅ **Luôn có** | Field này **luôn xuất hiện** trong mọi payload — không bao giờ thiếu |
| 🔀 **Có điều kiện** | Field xuất hiện khi thỏa điều kiện cụ thể (ghi rõ trong cột Ghi chú) |
| ⚙️ **Backend tự tính** | Simulator **không phát** field này — backend/adapter tự derive từ các field khác |
| 🚧 **Chưa implement** | Nằm trong schema spec nhưng simulator hiện **chưa phát** — field sẽ là `null` |

---

## 1. Domain: Sinh Hiệu (Vital Signs)

### 1.1. Real-time Telemetry — `sim_vitals_v1` @ ~1 Hz

Mỗi tick simulator phát một dict qua HTTP POST lên Backend. Đây là danh sách **chính xác** từng field:

| # | Field Name (thực tế trong payload) | Đơn vị | Nguồn Dataset | Phát sinh | Ghi chú |
|---|-------------------------------------|--------|--------------|----------|---------|
| 1 | `heart_rate` | bpm | PPG-DaLiA + WESAD | ✅ **Luôn có** | Baseline từ PPG-DaLiA; stress scenario cộng thêm delta từ WESAD distribution. Fallback = 72.0 nếu dataset offline |
| 2 | `spo2` | % | VitalDB | ✅ **Luôn có** | Lấy từ VitalDB clinical ICU. Fallback = 98.0 nếu VitalDB không có dòng hợp lệ |
| 3 | `temperature` | °C | PPG-DaLiA | ✅ **Luôn có** | Lấy từ PPG-DaLiA. Fallback = Gaussian(mean=36.7, std=0.3) nếu thiếu |
| 4 | `blood_pressure_sys` | mmHg | VitalDB | ✅ **Luôn có** | Clinical ICU data. Fallback = 120.0 |
| 5 | `blood_pressure_dia` | mmHg | VitalDB | ✅ **Luôn có** | Clinical ICU data. Fallback = 80.0 |
| 6 | `respiratory_rate` | bpm | BIDMC | ✅ **Luôn có** | PPG-derived respiration từ BIDMC ICU. Fallback = 16.0 |
| 7 | `activity_label` | enum | PAMAP2 | ✅ **Luôn có** | Giá trị: `resting` · `walking` · `running` · `sleeping` · `fall` · `recovery` · `standing` |
| 8 | `spo2_source` | string | — | ✅ **Luôn có** | Provenance tag: `real:VitalDB` khi lấy từ dataset / `mock` khi dùng fallback |
| 9 | `rr_source` | string | — | ✅ **Luôn có** | Provenance tag: `real:BIDMC` khi lấy từ dataset / `mock` khi dùng fallback |
| 10 | `stress_data_source` | string | — | ✅ **Luôn có** | Provenance tag: `real:WESAD` khi có stress sample / `mock` khi không có |
| 11 | `timestamp` | ISO-8601 | Dataset | 🔀 **Có điều kiện** | Chỉ có khi dataset trả về row thực. Vắng mặt ở fallback mode |
| 12 | `dataset` | string | — | 🔀 **Có điều kiện** | Tên dataset nguồn của row baseline. Vắng mặt ở fallback mode |
| 13 | `sim_time` | float | — | 🔀 **Có điều kiện** | Thời gian simulation (giây từ khi start). Chỉ xuất hiện khi session truyền `sim_time` |
| 14 | `sleep_phase` | enum | Sleep-EDF | 🔀 **Có điều kiện** | Chỉ xuất hiện khi `activity_label = sleeping`. Giá trị: `light` · `deep` · `rem` · `awake` |
| 15 | `pulse_pressure` | mmHg | — | ⚙️ **Backend tự tính** | `sys - dia`. Simulator không phát — backend adapter tự compute |
| 16 | `map` (Mean Arterial Pressure) | mmHg | — | ⚙️ **Backend tự tính** | `dia + (sys - dia) / 3`. Simulator không phát |
| 17 | `hrv_ms` | ms | — | 🚧 **Chưa implement** | Nằm trong schema `sim_vitals_v1` nhưng generator chưa phát field này |
| 18 | `signal_quality_pct` | % | — | 🚧 **Chưa implement** | Kế hoạch từ PPG-DaLiA nhưng chưa được extract vào output |
| 19 | `motion_artifact` | boolean | — | 🚧 **Chưa implement** | Kế hoạch từ PPG-DaLiA accel data nhưng chưa sinh vào payload |
| 20 | `body_position` | enum | — | 🚧 **Chưa implement** | Schema định nghĩa `standing/sitting/lying` nhưng chưa phát |

> **Dev note:** Với Replay mode (`source_mode = replay`), payload được lấy nguyên row từ dataset và thêm `source_mode = "replay"`. Các field trên có thể thiếu nếu dataset không có cột tương ứng.

### 1.2. Sleep Phase Vitals — Điều chỉnh tự động khi `activity_label = sleeping`

Khi đang trong trạng thái ngủ, simulator cộng thêm delta vào các field hiện có:

| Pha Ngủ (`sleep_phase`) | Điều chỉnh `heart_rate` | Điều chỉnh `respiratory_rate` | Điều chỉnh `temperature` |
|------------------------|------------------------|------------------------------|--------------------------|
| `light` | −8 bpm (min: 35.0) | −2 bpm (min: 8.0) | −0.3°C |
| `deep` | −18 bpm (min: 35.0) | −4 bpm (min: 8.0) | −0.8°C |
| `rem` | −5 bpm (min: 35.0) | −1 bpm (min: 8.0) | −0.5°C |
| `awake` | +2 bpm | 0 | 0 |

### 1.3. Kịch bản Vitals Built-in

| Scenario ID | Mô tả | Field & Giá trị kỳ vọng |
|-------------|-------|------------------------|
| `normal_rest` | Nghỉ ngơi khỏe mạnh | `heart_rate` 60–80, `spo2` 98–99%, `respiratory_rate` 14–16 |
| `tachycardia_warning` | Nhịp tim nhanh do stress | `heart_rate` >100 (WESAD stress delta), `stress_data_source = real:WESAD` |
| `hypoxia_critical` | Giảm oxy máu nguy hiểm | `spo2` <90% (VitalDB clinical hypoxic row), `spo2_source = real:VitalDB` |
| `hypertension_moderate` | Tăng huyết áp | `blood_pressure_sys` >140 mmHg sustained |

### 1.4. Hard Boundaries Y Tế

Mọi giá trị phát ra được clamp theo các ngưỡng AHA/WHO. Backend nhận và so sánh với các mức sau:

| Field | Normal | Warning | Critical | Tiêu chuẩn |
|-------|--------|---------|---------|-----------|
| `heart_rate` | 60–100 bpm | <50 hoặc >100 | <40 hoặc ≥120 | AHA 2020 |
| `spo2` | 95–100% | 90–95% | <90% | WHO 2011 |
| `blood_pressure_sys` | <120 mmHg | 120–139 | ≥180 | ACC/AHA 2017 |
| `respiratory_rate` | 12–20 bpm | <10 hoặc >20 | <8 hoặc >25 | NEWS2/ERS |
| `temperature` | 36.4–37.0°C | — | <35 hoặc >39 | Harrison's |

---

## 2. Domain: Giấc Ngủ (Sleep)

### 2.1. Sleep Session Payload — `sim_sleep_v1` (push 1 lần / phiên ngủ)

Simulator push một bản ghi tổng hợp lên Backend mỗi khi kết thúc phiên ngủ (hoặc qua Backfill API). Đây là danh sách chính xác từng field:

| # | Field Name (thực tế trong payload) | Đơn vị | Nguồn | Phát sinh | Ghi chú |
|---|-------------------------------------|--------|-------|----------|---------|
| 1 | `sleep_score` | 0–100 | HealthGuard AI ONNX / Heuristic | ✅ **Luôn có** | AI mode: gọi `http://localhost:8001/predict`. Heuristic fallback nếu API offline |
| 2 | `sleep_efficiency_pct` | % | Sleep-EDF / Computed | ✅ **Luôn có** | `total_sleep_min / time_in_bed_min × 100` |
| 3 | `total_sleep_min` | phút | Sleep-EDF | ✅ **Luôn có** | Tổng thời gian ngủ thực, không tính các lần thức giữa đêm |
| 4 | `time_in_bed_min` | phút | Sleep-EDF | ✅ **Luôn có** | Thời gian từ lúc nằm đến lúc ra khỏi giường |
| 5 | `wake_count` | lần | Sleep-EDF | ✅ **Luôn có** | Số lần thức giữa đêm từ hypnogram EDF thực |
| 6 | `phases` | array | Sleep-EDF | ✅ **Luôn có** | Mảng các phase: `{stage, start_time, end_time, duration_min, confidence}`. Stage: `awake · light · deep · rem` |
| 7 | `heart_rate_mean_bpm` | bpm | PPG-DaLiA + Enricher | ✅ **Luôn có** | Nhịp tim trung bình cả đêm. Gaussian sample từ profile scenario |
| 8 | `heart_rate_min_bpm` | bpm | PPG-DaLiA + Enricher | ✅ **Luôn có** | Đỉnh thấp nhất = `heart_rate_mean - delta` (clamp min 30.0) |
| 9 | `heart_rate_max_bpm` | bpm | PPG-DaLiA + Enricher | ✅ **Luôn có** | Đỉnh cao nhất = `heart_rate_mean + delta` |
| 10 | `hrv_rmssd_ms` | ms | PPG-DaLiA + Enricher | ✅ **Luôn có** | RMSSD Gaussian sample theo scenario. Không từ raw dataset — từ phân phối đặc trưng của scenario |
| 11 | `respiration_rate_bpm` | bpm | BIDMC + Enricher | ✅ **Luôn có** | Mean nocturnal respiratory rate. Gaussian sample theo scenario profile |
| 12 | `spo2_mean_pct` | % | VitalDB + Enricher | ✅ **Luôn có** | Mean SpO2 cả đêm (clamp 70–100%) |
| 13 | `spo2_min_pct` | % | VitalDB + Enricher | ✅ **Luôn có** | `spo2_mean - dip`. Dip lớn ở kịch bản sleep apnea. Clamp min 70% |
| 14 | `movement_count` | lần | PAMAP2 + Enricher | ✅ **Luôn có** | `wake_count × movement_factor + noise`. Factor thay đổi theo scenario |
| 15 | `snore_events` | lần | Enricher | ✅ **Luôn có** | Random integer trong range `[snore_lo, snore_hi]` theo scenario |
| 16 | `ambient_noise_db` | dB | Enricher / Persona | ✅ **Luôn có** | Ưu tiên lấy từ persona config. Nếu không có: Gaussian sample theo scenario profile |
| 17 | `room_temperature_c` | °C | Enricher / Persona | ✅ **Luôn có** | Ưu tiên lấy từ persona config. Nếu không có: Gaussian sample |
| 18 | `room_humidity_pct` | % | Enricher / Persona | ✅ **Luôn có** | Ưu tiên lấy từ persona config. Nếu không có: Gaussian sample |
| 19 | `disorder_tags` | array | Logic | 🔀 **Có điều kiện** | Phát sinh khi scenario thuộc nhóm bệnh lý. VD: `["sleep_apnea_mild"]`. Rỗng `[]` với `good_sleep_night` |

### 2.2. Profile Chi Tiết Theo Kịch Bản

| Scenario | `sleep_score` | `sleep_efficiency_pct` | `wake_count` | `heart_rate_mean_bpm` | `spo2_min_pct` | `hrv_rmssd_ms` | `snore_events` |
|----------|-------------|---------------------|------------|---------------------|--------------|--------------|--------------|
| `good_sleep_night` | ≥ 85 | ≥ 85% | 0–2 | 59 ± 3 | ≥ 94% | 57 ± 8 ms | 0–2 lần |
| `fragmented_sleep` | < 70 | ~72% | ≥ 4 | 70 ± 4 | ≥ 92% | 27 ± 6 ms | 4–15 lần |
| `sleep_apnea_mild` | 60–75 | ~75% | 3–6 | 73 ± 5 | ≥ 89% | 20 ± 4 ms | 18–40 lần |
| `sleep_apnea_severe` | < 55 | < 70% | ≥ 6 | 78 ± 6 | ≥ 84% | 10 ± 3 ms | 50–80 lần |

### 2.3. Sleep Phase Distribution Theo Kịch Bản (Chuẩn AASM)

| Scenario | `awake` % | `light` % (N1+N2) | `deep` % (N3) | `rem` % | Tổng `total_sleep_min` |
|----------|----------|-----------------|-------------|--------|----------------------|
| `good_sleep_night` | < 5% | ~38% | ≥ 28% | ≥ 19% | ~410 phút |
| `fragmented_sleep` | > 20% | ~55% | < 10% | < 15% | ~220 phút |
| `sleep_apnea_mild` | ~15% | ~50% | ~15% | ~20% | ~300 phút |
| `sleep_apnea_severe` | > 25% | ~55% | < 10% | < 10% | ~260 phút |

### 2.4. AI Sleep Score — 14 Features Input cho Model

Khi HealthGuard AI API online, simulator gửi đúng 14 features sau vào `/predict`:

| # | Feature gửi vào AI | Lấy từ field nào |
|---|-------------------|----------------|
| 1 | HR mean | `heart_rate_mean_bpm` |
| 2 | HR min | `heart_rate_min_bpm` |
| 3 | HR max | `heart_rate_max_bpm` |
| 4 | HRV RMSSD | `hrv_rmssd_ms` |
| 5 | Respiratory rate | `respiration_rate_bpm` |
| 6 | SpO2 mean | `spo2_mean_pct` |
| 7 | SpO2 min | `spo2_min_pct` |
| 8 | Movement count | `movement_count` |
| 9 | Snore events | `snore_events` |
| 10 | Ambient noise | `ambient_noise_db` |
| 11 | Room temperature | `room_temperature_c` |
| 12 | Room humidity | `room_humidity_pct` |
| 13 | Sleep duration | `total_sleep_min` |
| 14 | Wake count | `wake_count` |

Nếu AI API offline → `sleep_score` được tính bằng heuristic nội bộ từ `efficiency`, `wake_count`, `spo2_min_pct`.

### 2.5. Backfill & History Injection API

| Endpoint | Method | Tham số | Mô tả |
|----------|--------|---------|-------|
| `/scenarios/sleep/backfill` | POST | `device_id`, `days_behind` (1–90), `scenario_id` | Inject N ngày lịch sử giấc ngủ về trước |
| `/scenarios/sleep/push-date` | POST | `device_id`, `target_date`, `scenario_id` | Inject đúng 1 ngày cụ thể (ngày < hôm nay) |

---

## 3. Domain: Té Ngã (Fall Detection)

### 3.1. Motion Window — `sim_motion_v1` @ 50 Hz (window 50 mẫu)

| # | Field Name (thực tế trong payload) | Đơn vị | Nguồn Dataset | Phát sinh | Ghi chú |
|---|-------------------------------------|--------|--------------|----------|---------|
| 1 | `accel_x` | m/s² | PAMAP2, UP-Fall, PIF_v3 | ✅ **Luôn có** | Gia tốc trục X. Đủ cả 3 dataset |
| 2 | `accel_y` | m/s² | PAMAP2, UP-Fall, PIF_v3 | ✅ **Luôn có** | Gia tốc trục Y |
| 3 | `accel_z` | m/s² | PAMAP2, UP-Fall, PIF_v3 | ✅ **Luôn có** | Gia tốc trục Z |
| 4 | `gyro_x` | rad/s | PAMAP2, UP-Fall | ✅ **Luôn có** | Con quay trục X. PIF_v3 không có gyro nhưng PAMAP2/UP-Fall đủ bù |
| 5 | `gyro_y` | rad/s | PAMAP2, UP-Fall | ✅ **Luôn có** | Con quay trục Y |
| 6 | `gyro_z` | rad/s | PAMAP2, UP-Fall | ✅ **Luôn có** | Con quay trục Z |
| 7 | `accel_mag` | m/s² | Computed | ✅ **Luôn có** | `sqrt(x²+y²+z²)`. ETL (`window_builder.py`) tính sẵn vào từng window |
| 8 | `pitch` | độ | UP-Fall | 🔀 **Có điều kiện** | Chỉ có khi window lấy từ UP-Fall. Vắng mặt với PAMAP2/PIF_v3 window |
| 9 | `roll` | độ | UP-Fall | 🔀 **Có điều kiện** | Như trên |
| 10 | `yaw` | độ | UP-Fall | 🔀 **Có điều kiện** | Như trên |
| 11 | `gyro_mag` | rad/s | Computed | ⚙️ **Backend tự tính** | Canonical schema định nghĩa nhưng ETL hiện chưa pre-compute vào window |
| 12 | `floor_vibration` | — | — | 🚧 **Chưa implement** | Schema dự phòng cho tấm cảm biến sàn. Luôn `null` hiện tại |
| 13 | `pressure_mat` | — | — | 🚧 **Chưa implement** | Schema dự phòng cho tấm áp lực. Luôn `null` hiện tại |

> **Dev note:** Simulator phát `window_builder` windows — mỗi window là dict chứa array `accel_x[50], accel_y[50], accel_z[50]` (50 mẫu/trục). Backend fall model nhận window này để inference.

### 3.2. Fall Event — `sim_event_v1` (phát tại thời điểm phát hiện ngã)

| # | Field Name | Đơn vị | Phát sinh | Ghi chú |
|---|-----------|--------|----------|---------|
| 1 | `event_type` | string | ✅ **Luôn có** | Luôn = `"fall_detected"` |
| 2 | `event_time` | ISO-8601 | ✅ **Luôn có** | Timestamp thực tế của sự kiện |
| 3 | `severity` | enum | ✅ **Luôn có** | `low · medium · high · critical` |
| 4 | `countdown_sec` | int | ✅ **Luôn có** | Luôn = 30 giây (fall SOS countdown) |
| 5 | `payload.confidence` | 0–1 | ✅ **Luôn có** | Confidence score. `fall_high_confidence` > 0.85 / `fall_false_alarm` < 0.5 |
| 6 | `payload.features.max_accel_mps2` | m/s² | ✅ **Luôn có** | Peak acceleration trong window — đặc trưng va chạm |
| 7 | `payload.features.impact_duration_ms` | ms | ✅ **Luôn có** | Thời gian từ accel spike đến khi về baseline |
| 8 | `payload.features.post_impact_motion` | enum | ✅ **Luôn có** | `low` = bất động (ngã thật) / `medium` / `high` = phục hồi nhanh (ngã giả) |
| 9 | `payload.snapshot.heart_rate_bpm` | bpm | ✅ **Luôn có** | Nhịp tim tại thời điểm ngã (+30 bpm adrenalin so với baseline) |
| 10 | `payload.snapshot.spo2_pct` | % | ✅ **Luôn có** | SpO2 snapshot khi ngã |
| 11 | `payload.snapshot.battery_level_pct` | % | ✅ **Luôn có** | Mức pin thiết bị |
| 12 | `payload.model_version` | string | 🔀 **Có điều kiện** | Phát nếu fall model được load. Vắng mặt nếu rule-based trigger |
| 13 | `payload.location` | object | 🚧 **Chưa implement** | GPS `{latitude, longitude, accuracy_m}`. Schema định nghĩa nhưng simulator chưa gắn GPS |

### 3.3. Kịch Bản Té Ngã Built-in — Giá Trị Cụ Thể

| Scenario | `post_impact_motion` | `confidence` | `max_accel_mps2` | `heart_rate` khi ngã | Expected Backend Outcome |
|----------|---------------------|------------|----------------|--------------------|-----------------------|
| `fall_high_confidence` | `low` | > 0.85 | > 15 m/s² | Baseline + ~30 bpm | Alert `high`, countdown 30s kích hoạt, SOS nếu không phản hồi |
| `fall_false_alarm` | `high` | < 0.50 | 8–15 m/s² | Tăng rồi về nhanh | Không trigger SOS, recovery state sau 20 ticks |
| `fall_no_response` | `low` | > 0.85 | > 15 m/s² | Baseline + ~30 bpm | Alert escalation → SOS trigger sau countdown |

### 3.4. Fall State Machine — Lifecycle

| Trạng thái | Thời gian | `activity_label` | `heart_rate` | Mô tả |
|-----------|---------|----------------|------------|-------|
| Pre-fall | Bình thường | Bất kỳ | Baseline | Hoạt động bình thường |
| **Fall** | 10 ticks (~10s) | `fall` | Baseline + ~30 bpm | Va chạm, PIF_v3 vitals, fight-or-flight |
| Recovery | 20 ticks (~20s) | `recovery` | Dần về baseline | Bất động hoặc đứng dậy từ từ |
| Post-recovery | Resume | `standing` | Baseline | Về trạng thái bình thường |

---

## 4. Tổng Hợp — Số Field Mỗi Domain

| Domain | Luôn có | Có điều kiện | Backend tự tính | Chưa implement | Tổng field |
|--------|---------|-------------|----------------|---------------|-----------|
| **Vital Signs (real-time)** | 10 | 4 | 2 | 4 | 20 |
| **Sleep (per session)** | 18 | 1 | 0 | 0 | 19 |
| **Fall Motion Window** | 7 | 3 | 1 | 2 | 13 |
| **Fall Event** | 11 | 1 | 0 | 1 | 13 |
| **Tổng** | **46** | **9** | **3** | **7** | **65** |

---

## 5. Data Provenance — Tag Nguồn Gốc

Mọi field telemetry được tag nguồn gốc để backend và AI model biết mức độ tin cậy:

| Tag | Xuất hiện trong field | Ý nghĩa |
|-----|--------------------|---------|
| `real:VitalDB` | `spo2_source` | SpO2 + BP lấy từ VitalDB clinical ICU |
| `real:BIDMC` | `rr_source` | Nhịp thở từ BIDMC ICU PPG-derived |
| `real:WESAD` | `stress_data_source` | HR adjustment từ WESAD stress distribution |
| `real:PPG-DaLiA` | `dataset` | HR + temp từ PPG-DaLiA wearable |
| `real:Sleep-EDF` | (implicit) | Hypnogram phases từ EDF thực tế |
| `real:UP-Fall` | (implicit) | Motion window ngã thực tế |
| `real:PIF_v3` | (implicit) | Vitals sau ngã từ PIF_v3 |
| `mock` | `spo2_source`, `rr_source`, `stress_data_source` | Fallback synthetic khi dataset không khả dụng |
