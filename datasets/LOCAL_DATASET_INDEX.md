# Local Dataset Index

Tài liệu này ghi lại các dataset đã có sẵn trong máy tại workspace hiện tại.

Ngày cập nhật: `2026-03-23`

## 1. Tình trạng hiện tại

| Dataset | Archive | Extracted folder | Trạng thái | Ghi chú |
|---|---|---|---|---|
| PPG-DaLiA | `02_wearable/PPG-DaLiA/PPG-DaLiA_Dataset.zip` | `02_wearable/PPG-DaLiA/PPG-DaLiA_Raw/` | Ready for ETL | Có 15 subject, đủ file `pkl`, `RespiBAN.h5`, `E4.zip`, `activity.csv`, `quest.csv` |
| WESAD | `02_wearable/WESAD/WESAD_Dataset.zip` | `02_wearable/WESAD/WESAD_Raw/` | Ready for ETL | Có 15 subject, phù hợp cho stress/rest/amusement state ETL |
| Sleep-EDF Expanded | `03_sleep/Sleep-EDF/Sleep-EDF_Dataset.zip` | `03_sleep/Sleep-EDF/Sleep-EDF_Raw/` | Ready for ETL | Đã giải nén và giữ subset `sleep-cassette` phục vụ sleep staging |
| UP-Fall | `05_fall/UP-Fall/UP-Fall_Dataset.zip` | `05_fall/UP-Fall/UP-Fall_Raw/` | Ready for replay ETL | Hiện chỉ thấy `4 subject`, nhiều khả năng là bản subset/preliminary |
| PIF v3 | `05_fall/PIF_v3/PIF_v3_Dataset.zip` | `05_fall/PIF_v3/PIF_v3_Raw/` | Ready for ETL | Có cả physiology CSV và inertial CSV, phù hợp nhất cho fall + physiology bridge |
| PAMAP2 | `04_activity/PAMAP2/PAMAP2_Dataset.zip` | `04_activity/PAMAP2/PAMAP2_Raw/` | Ready for ETL | Đã xử lý lớp ZIP lồng bên trong |

## 2. Chi tiết từng bộ

### 2.1. PPG-DaLiA

Vị trí:

- Archive: `D:\DoAn2\VSmartwatch\Iot_Simulator\datasets\02_wearable\PPG-DaLiA\PPG-DaLiA_Dataset.zip`
- Raw: `D:\DoAn2\VSmartwatch\Iot_Simulator\datasets\02_wearable\PPG-DaLiA\PPG-DaLiA_Raw`

Kiểm tra nhanh:

- `15` subject folders
- `15` file `.pkl`
- `15` file `RespiBAN.h5`
- `15` file `E4.zip`

Nhận xét:

- Sẵn sàng dùng cho `wearable realism`
- Rất phù hợp để ETL cho `noise model` và `signal quality model`

### 2.2. WESAD

Vị trí:

- Archive: `D:\DoAn2\VSmartwatch\Iot_Simulator\datasets\02_wearable\WESAD\WESAD_Dataset.zip`
- Raw: `D:\DoAn2\VSmartwatch\Iot_Simulator\datasets\02_wearable\WESAD\WESAD_Raw`

Kiểm tra nhanh:

- `15` subject folders
- `15` file `.pkl`
- `15` file `E4_Data.zip`
- `15` file `respiban.txt`

Nhận xét:

- Sẵn sàng dùng cho `stress state ETL`
- Là bộ rất tốt để map `stress/rest/amusement` sang simulator state machine

### 2.3. UP-Fall

Vị trí:

- Archive: `D:\DoAn2\VSmartwatch\Iot_Simulator\datasets\05_fall\UP-Fall\UP-Fall_Dataset.zip`
- Raw: `D:\DoAn2\VSmartwatch\Iot_Simulator\datasets\05_fall\UP-Fall\UP-Fall_Raw`

Kiểm tra nhanh:

- `4` subject folders: `Subject_01` đến `Subject_04`
- `126` file CSV
- Đã dọn `__MACOSX` và `.DS_Store`

Nhận xét:

- Dùng tốt cho replay fall/ADL nhanh
- Chưa nên xem là full dataset chính thức hoàn chỉnh vì số subject đang ít hơn kỳ vọng từ tài liệu nguồn

### 2.4. PIF v3

Vị trí:

- Archive: `D:\DoAn2\VSmartwatch\Iot_Simulator\datasets\05_fall\PIF_v3\PIF_v3_Dataset.zip`
- Raw: `D:\DoAn2\VSmartwatch\Iot_Simulator\datasets\05_fall\PIF_v3\PIF_v3_Raw`

Kiểm tra nhanh:

- Có file `Participants.xlsx`
- `32` thư mục participant kiểu `PID*`
- `64` file CSV

Nhận xét:

- Đây là bộ tốt nhất hiện đã có local cho nhánh `fall + physiology`
- Nên ưu tiên ETL bộ này trước khi làm assisted-event và post-fall scenario

### 2.5. PAMAP2

Vị trí:

- Archive: `D:\DoAn2\VSmartwatch\Iot_Simulator\datasets\04_activity\PAMAP2\PAMAP2_Dataset.zip`
- Raw: `D:\DoAn2\VSmartwatch\Iot_Simulator\datasets\04_activity\PAMAP2\PAMAP2_Raw`
- Readme phụ: `D:\DoAn2\VSmartwatch\Iot_Simulator\datasets\04_activity\PAMAP2\PAMAP2_readme.pdf`

Kiểm tra nhanh:

- Đã xử lý nested ZIP thành công
- Có thư mục `Protocol/` và `Optional/`
- `Protocol/` đang có các file `subject101.dat` đến `subject109.dat`
- `Optional/` có các file bổ sung cho một số subject

Nhận xét:

- Sẵn sàng dùng cho activity state engine
- Nên ưu tiên ETL nhánh `Protocol/` trước

### 2.6. Sleep-EDF Expanded

Vị trí:

- Archive: `D:\DoAn2\VSmartwatch\Iot_Simulator\datasets\03_sleep\Sleep-EDF\Sleep-EDF_Dataset.zip`
- Raw: `D:\DoAn2\VSmartwatch\Iot_Simulator\datasets\03_sleep\Sleep-EDF\Sleep-EDF_Raw`

Kiểm tra nhanh:

- Có thư mục `sleep-cassette/`
- Có các file metadata: `RECORDS`, `RECORDS-v1`, `SC-subjects.xls`, `ST-subjects.xls`, `SHA256SUMS.txt`
- Số file trong `sleep-cassette`: `306`
- Đã dọn `sleep-telemetry` để giảm dung lượng và tập trung cho luồng sleep staging chính

Nhận xét:

- Sẵn sàng dùng cho ETL nhánh `sim_sleep_v1`
- Có thể tải lại `sleep-telemetry` nếu về sau cần nghiên cứu sâu telemetry subset

## 3. Thứ tự ETL khuyến nghị

1. `PIF v3`
2. `PPG-DaLiA`
3. `WESAD`
4. `PAMAP2`
5. `UP-Fall`

## 4. Việc nên làm tiếp theo

1. Chuẩn hóa mapping từ:
   - `PPG-DaLiA -> sim_motion_v1 + wearable noise library`
   - `WESAD -> stress state templates + context modulation`
   - `PIF v3 -> sim_motion_v1 + sim_event_v1`
   - `PAMAP2 -> sim_motion_v1 + activity state labels`
   - `UP-Fall -> replay fall library`
   - `Sleep-EDF -> sim_sleep_v1 + sleep phase timeline`
2. Nếu cần full `UP-Fall`, tải thêm bản complete dataset từ nguồn gốc để thay cho bản subset hiện tại
3. Nếu cần sleep telemetry use-cases, tải lại thư mục `sleep-telemetry` từ archive/full source
