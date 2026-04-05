# Download Guide Cho Dataset IoT Simulator

## 1. Phạm vi kiểm tra

Ngày kiểm tra: `2026-03-22`

Em đã kiểm tra lại các link trong manifest theo 3 mức:

- `OK`: trang/link mở được rõ ràng
- `OK - manual step`: trang mở được nhưng cần bấm nút tải trong trình duyệt hoặc trang dùng JS/share page
- `Restricted`: mở được trang mô tả nhưng tải file cần credential, đăng nhập hoặc điều khoản riêng

Lưu ý:

- Một số link `.zip` là binary endpoint nên không hiển thị nội dung trong client này, nhưng vẫn là dạng link tải trực tiếp phù hợp để mở bằng trình duyệt.
- Với các nguồn như `sciebo`, `Google Drive`, `Mendeley`, việc tải thực tế nên làm bằng trình duyệt.

---

## 2. Trạng thái link

| Dataset | Trạng thái | Ghi chú |
|---|---|---|
| VitalDB | OK | Trang dataset mở tốt, có `Web API`, `Python Library`, `Data Viewer` |
| PPG-DaLiA | OK - manual step | Trang chính mở tốt, share page sciebo hiện file `PPG_FieldStudy.zip` 2.7 GB và có nút `Download` |
| WESAD | OK - manual step | Trang chính mở tốt, share page sciebo mở được nhưng phần nút tải phụ thuộc JS/browser |
| Sleep-EDF Expanded | OK | Trang PhysioNet mở tốt; link ZIP là binary download |
| PAMAP2 | OK | Trang UCI mở tốt, có nút `Download (656.3 MB)` |
| PIF v3 | OK - manual step | Trang Mendeley mở tốt, có `Download All` trên trang |
| UP-Fall | OK - manual step | Trang chính mở tốt; phần `Complete Downloads` là embedded layout, nên thao tác trong browser |
| BIDMC PPG and Respiration | OK | Trang PhysioNet mở tốt; có download file trực tiếp |
| MIMIC-IV Waveform | OK | Trang mở tốt, là Open Access |
| MIMIC-IV 3.1 | Restricted | Trang mở tốt nhưng file chỉ cho credentialed users đã ký DUA |
| Full-body inertial dataset 2026 | OK - manual step | Nên vào bài báo rồi theo DOI/figshare |
| CeTI-Age-Kinematics 2025 | OK - manual step | Nên vào bài báo rồi theo DOI/figshare |

---

## 3. Hướng dẫn tải từng bộ

### 3.1. VitalDB

Thư mục đích:

`Iot_Simulator/datasets/01_vitals/VitalDB`

Link:

- [Dataset page](https://vitaldb.net/dataset)

Cách tải:

1. Mở dataset page.
2. Nếu cần tải chọn lọc, dùng `Data Viewer` hoặc `Web API`.
3. Nếu cần xử lý hàng loạt, ưu tiên `Python Library` hoặc export các track CSV/GZIP từ dataset page.

Ghi chú:

- VitalDB không giống UCI/PhysioNet kiểu một file ZIP duy nhất ở landing page.
- Đây là nguồn nên tải có chọn lọc theo track/case phục vụ calibration.

### 3.2. PPG-DaLiA

Thư mục đích:

`Iot_Simulator/datasets/02_wearable/PPG-DaLiA`

Link:

- [Trang chính](https://ubi29.informatik.uni-siegen.de/usi/data_ppgdalia.html)
- [Share page](https://uni-siegen.sciebo.de/s/pfHzlTepXkiJ4jP)
- [Direct ZIP](https://uni-siegen.sciebo.de/s/pfHzlTepXkiJ4jP/download/PPG_FieldStudy.zip)

Cách tải:

1. Mở share page.
2. Bấm `Download`.
3. Lưu file ZIP vào thư mục đích.
4. Giải nén giữ nguyên cấu trúc thư mục gốc.

Ghi chú:

- Share page hiện hiển thị rõ file `PPG_FieldStudy.zip (2.7 GB)`.

### 3.3. WESAD

Thư mục đích:

`Iot_Simulator/datasets/02_wearable/WESAD`

Link:

- [Trang chính](https://ubi29.informatik.uni-siegen.de/usi/data_wesad.html)
- [Share page](https://uni-siegen.sciebo.de/s/HGdUkoNlW1Ub0Gx)

Cách tải:

1. Mở trang chính.
2. Bấm link `ICMI'18 dataset`.
3. Trong trang sciebo, tải file `WESAD.zip`.

Ghi chú:

- Share page mở được nhưng phần tải phụ thuộc browser/JS; nên thao tác bằng Chrome/Edge.

### 3.4. Sleep-EDF Expanded

Thư mục đích:

`Iot_Simulator/datasets/03_sleep/Sleep-EDF`

Link:

- [Trang chính](https://physionet.org/content/sleep-edfx/1.0.0/)
- [Direct ZIP](https://physionet.org/static/published-projects/sleep-edfx/sleep-edf-database-expanded-1.0.0.zip)

Cách tải:

1. Nếu muốn tải nhanh, mở direct ZIP.
2. Nếu muốn xem metadata trước, mở trang PhysioNet rồi tải.

### 3.5. PAMAP2

Thư mục đích:

`Iot_Simulator/datasets/04_activity/PAMAP2`

Link:

- [Trang chính](https://archive.ics.uci.edu/dataset/231/pamap2+physical+activity+monitoring)
- [Direct download](https://archive.ics.uci.edu/static/public/231/pamap2%2Bphysical%2Bactivity%2Bmonitoring.zip)

Cách tải:

1. Mở trang UCI.
2. Bấm `Download (656.3 MB)`.
3. Giải nén vào thư mục đích.

### 3.6. PIF v3

Thư mục đích:

`Iot_Simulator/datasets/05_fall/PIF_v3`

Link:

- [Mendeley Data page](https://data.mendeley.com/datasets/phb9y6cp5c/3)

Cách tải:

1. Mở trang Mendeley.
2. Bấm `Download All`.
3. Nếu có prompt xác nhận, tiếp tục tải.
4. Giải nén giữ nguyên theo subject folders.

Ghi chú:

- Trang mở tốt và hiển thị `Download All`, nhưng thao tác tải nên làm trong browser.

### 3.7. UP-Fall

Thư mục đích:

`Iot_Simulator/datasets/05_fall/UP-Fall`

Link:

- [Trang chính](https://sites.google.com/up.edu.mx/har-up/)

Cách tải:

1. Mở trang chính.
2. Kéo xuống phần `Downloads`.
3. Tải từ `Complete Downloads` nếu có thể.
4. Nếu chỉ cần bộ nhỏ để test nhanh, có thể dùng link `Preliminar-Fall-UP Dataset`.

Ghi chú:

- Trong client kiểm tra, phần tải đầy đủ là embedded layout nên không render sạch.
- Link preliminar dẫn qua Google Drive và có thể yêu cầu login/xác nhận trong trình duyệt.

### 3.8. BIDMC PPG and Respiration

Thư mục đích:

`Iot_Simulator/datasets/06_clinical_optional/BIDMC`

Link:

- [Trang chính](https://physionet.org/content/bidmc/1.0.0/)
- [Direct ZIP](https://physionet.org/static/published-projects/bidmc/bidmc-ppg-and-respiration-dataset-1.0.0.zip)

Cách tải:

1. Tải bằng direct ZIP nếu cần toàn bộ dataset.
2. Hoặc mở PhysioNet page để tải từng file.

### 3.9. MIMIC-IV Waveform

Thư mục đích:

`Iot_Simulator/datasets/06_clinical_optional/MIMIC4WDB`

Link:

- [MIMIC-IV Waveform](https://physionet.org/content/mimic4wdb/0.1.0/)

Cách tải:

1. Mở trang PhysioNet.
2. Tải các record cần thiết theo nhu cầu validation.

Ghi chú:

- Đây là `Open Access`.

### 3.10. MIMIC-IV 3.1

Thư mục đích:

`Iot_Simulator/datasets/06_clinical_optional/MIMIC-IV`

Link:

- [MIMIC-IV 3.1](https://physionet.org/content/mimiciv/3.1/)

Cách tải:

1. Tạo hoặc đăng nhập tài khoản PhysioNet.
2. Hoàn tất `CITI Data or Specimens Only Research`.
3. Ký `PhysioNet Credentialed Health Data Use Agreement`.
4. Sau khi được cấp quyền, tải dataset từ trang.

Ghi chú:

- Đây là dataset `credentialed`.

### 3.11. Full-body inertial dataset 2026

Thư mục đích:

`Iot_Simulator/datasets/04_activity/FullBodyIMU_2026`

Link:

- [Bài báo](https://www.nature.com/articles/s41597-026-06710-9)
- [DOI dữ liệu](https://doi.org/10.6084/m9.figshare.30234940)

Cách tải:

1. Mở bài báo.
2. Đi tới phần data availability hoặc mở DOI dữ liệu.
3. Tải từ figshare.

### 3.12. CeTI-Age-Kinematics 2025

Thư mục đích:

`Iot_Simulator/datasets/04_activity/CeTI_2025`

Link:

- [Bài báo](https://www.nature.com/articles/s41597-025-04818-y)
- [DOI dữ liệu](https://doi.org/10.6084/m9.figshare.26983645)

Cách tải:

1. Mở bài báo.
2. Đi tới dataset DOI/figshare.
3. Tải toàn bộ file gốc.

---

## 4. Thứ tự tải khuyến nghị

Nếu anh muốn tải ít mà hiệu quả trước, em khuyên theo đúng thứ tự này:

1. `PPG-DaLiA`
2. `WESAD`
3. `PAMAP2`
4. `Sleep-EDF Expanded`
5. `PIF v3`
6. `VitalDB`

Sau đó mới đến:

7. `UP-Fall`
8. `BIDMC`
9. `MIMIC-IV Waveform`
10. `MIMIC-IV 3.1`
11. `Full-body inertial dataset 2026`
12. `CeTI-Age-Kinematics 2025`

---

## 5. Sau khi tải xong nên làm gì

1. Giữ nguyên file gốc trong thư mục dataset.
2. Không sửa trực tiếp file raw.
3. Tạo thêm thư mục `normalized/` hoặc `etl/` nếu cần quy đổi schema.
4. Ghi lại `README_local.md` cho mỗi dataset nếu có bước xử lý riêng.
