# Dataset Manifest Cho IoT Simulator

Tài liệu này liệt kê các bộ dataset khuyến nghị để anh tải về thư mục `Iot_Simulator/datasets` nhằm phục vụ việc tạo sinh dữ liệu giả cho IoT simulator.

Trạng thái link và hướng dẫn tải chi tiết được ghi riêng ở `DOWNLOAD_GUIDE.md`.

## 1. Nguyên tắc dùng dataset

- Không dùng 1 dataset duy nhất để sinh toàn bộ dữ liệu.
- Dùng dataset mở, nguồn chính thức, và ưu tiên nguồn còn được duy trì/tái sử dụng rộng.
- Tách rõ dataset cho:
  - vitals liên tục
  - wearable noise và motion artifact
  - stress/context
  - sleep
  - activity intensity
  - fall replay

## 2. Cấu trúc thư mục khuyến nghị

```text
Iot_Simulator/datasets/
  01_vitals/
  02_wearable/
  03_sleep/
  04_activity/
  05_fall/
  06_clinical_optional/
```

## 3. Bộ dataset đang dùng — Tier 1 (Core + Bổ sung)

> ✅ = Đã tải + tích hợp hoàn chỉnh | 🔄 = Đã tải, integration plan sẵn sàng

| Index | Dataset | Thư mục | Tín hiệu chính | Trạng thái | Plan |
|---|---|---|---|---|---|
| Core | PPG-DaLiA | `02_wearable/PPG-DaLiA/` | HR wrist PPG, motion noise | ✅ wired | — |
| Core | PAMAP2 | `04_activity/PAMAP2/` | ACC + Gyro + 18 activities | ✅ wired | — |
| Core | PIF_v3 | `05_fall/PIF_v3/` | Fall + vitals bridge | ✅ wired | — |
| Core | UP-Fall | `05_fall/UP-Fall/` | Fall replay variants | ✅ wired | — |
| Core | Sleep-EDF | `03_sleep/Sleep-EDF/` | Sleep stages hypnogram | ✅ wired | — |
| 1/3 | **WESAD** | `02_wearable/WESAD/` | Stress HR distribution | 🔄 plan ready | `docs/plans/P06_wesad_stress_integration.md` |
| 2/3 | **VitalDB** | `01_vitals/VitalDB/` | SpO2 + BP clinical | 🔄 plan ready | `docs/plans/P07_vitaldb_spo2_bp_integration.md` |
| 3/3 | **BIDMC** | `06_clinical_optional/BIDMC/` | Respiration rate (RR) | 🔄 plan ready | `docs/plans/P08_bidmc_respiration_integration.md` |

## 4. Bộ dataset tương lai — Tier 2 (Chưa tích hợp, sau Tier 1)

> Tier 2 chưa được ưu tiên. Chỉ tải khi Tier 1 đã hoàn chỉnh.

| Dataset | Thư mục | Mục đích | Link |
|---|---|---|---|
| CeTI-Age-Kinematics 2025 | `04_activity/CeTI_2025/` | Motion template theo tuổi (elderly) | [figshare](https://doi.org/10.6084/m9.figshare.26983645) |
| Full-body IMU 2026 | `04_activity/FullBodyIMU_2026/` | 7-point IMU thay vì 3-point | [Nature](https://doi.org/10.6084/m9.figshare.30234940) |
| MIMIC-IV Waveform | `06_clinical_optional/MIMIC4WDB/` | Clinical edge case validation | [PhysioNet](https://physionet.org/content/mimic4wdb/0.1.0/) |
| MIMIC-IV 3.1 | `06_clinical_optional/MIMIC-IV/` | Statistical validation thresholds | [PhysioNet](https://physionet.org/content/mimiciv/3.1/) |

## 5. Gợi ý sử dụng thực tế

- `VitalDB` + `PPG-DaLiA` + `WESAD` là lõi để tạo vitals realism, wearable noise và state modulation.
- `Sleep-EDF Expanded` bổ sung logic giấc ngủ, không nên thay bằng random sleep score.
- `PAMAP2` giúp chuyển trạng thái hoạt động trong ngày có quán tính hợp lý hơn.
- `PIF v3` nên được ưu tiên hơn `UP-Fall` khi cần nối sự kiện té ngã với biến đổi sinh lý.
- `UP-Fall` nên dùng như thư viện replay/regression test cho fall alert.
- `MIMIC-IV`, `MIMIC4WDB` và `BIDMC` chỉ nên dùng để calibrate biên bất thường, respiration tuning và validation, không dùng thẳng để giả lập người khỏe mạnh đại diện cho cộng đồng.

## 6. Lưu ý trước khi tải

- Một số nguồn cần đăng ký hoặc chấp nhận điều khoản truy cập.
- Một số trang là "landing page" hoặc "share page", anh có thể mở link rồi tải bằng trình duyệt.
- Nên giữ nguyên cấu trúc file gốc của dataset và tạo thêm thư mục `normalized/` riêng nếu cần ETL sang schema nội bộ.
