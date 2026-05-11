CRITICAL INSTRUCTION: You MUST generate the final report in Vietnamese, exactly matching the markdown template below. Do not generate English text in the final report. The table headers, structure, and template wording must remain exactly as defined below in Vietnamese.

```markdown
# 📊 BÁO CÁO ĐÁNH GIÁ TỔNG QUAN

## Thông tin chung
- **Dự án**: [Admin / Mobile]
- **Phạm vi đánh giá**: [Toàn bộ / Module cụ thể]
- **Ngày đánh giá**: [ISO date]
- **Sprint hiện tại**: [Sprint N]
- **Lần đánh giá**: [N] ← (1 = lần đầu, 2+ = re-review)
- **Ngày đánh giá trước**: [ISO date hoặc "N/A" nếu lần đầu]

---

## 🏆 TỔNG ĐIỂM: XX/100

| Tiêu chí                 | Điểm | Ghi chú |
| ------------------------ | ---- | ------- |
| Bám sát SRS              | /20  | ...     |
| Kiến trúc & Cấu trúc     | /20  | ...     |
| Tính nhất quán           | /15  | ...     |
| Tiến độ vs JIRA          | /20  | ...     |
| Code Quality             | /15  | ...     |
| Bảo mật & Best Practices | /10  | ...     |

---

## 📐 ARCHITECTURE ASSESSMENT
> Chi tiết tiêu chí #2

### Clean Architecture & Layers (/8)
| Kiểm tra                          | Đạt? | Ghi chú |
| --------------------------------- | ---- | ------- |
| Separation of Concerns            | ✅/❌  | ...     |
| Dependency Direction              | ✅/❌  | ...     |
| Business logic tách framework     | ✅/❌  | ...     |
| DB queries không trong controller | ✅/❌  | ...     |

### Folder Structure (/6)
| Kiểm tra | Đạt? | Ghi chú |
| -------- | ---- | ------- |
| ...      | ✅/❌  | ...     |

### Design Patterns (/6)
| Kiểm tra | Đạt? | Ghi chú |
| -------- | ---- | ------- |
| ...      | ✅/❌  | ...     |

---

## ✅ ƯU ĐIỂM
1. [Liệt kê ưu điểm nổi bật]

## ❌ NHƯỢC ĐIỂM
1. [Liệt kê nhược điểm cần cải thiện]

## 🔧 ĐIỂM CẦN CẢI THIỆN
1. [Cải thiện cụ thể + mức độ ưu tiên: HIGH/MEDIUM/LOW]

## 🗑️ ĐIỂM CẦN LOẠI BỎ
1. [Code/pattern/dependency cần loại bỏ]

## ⚠️ SAI LỆCH VỚI JIRA TASKS
> Phần này BẮT BUỘC phải có nếu phát hiện sai lệch

| JIRA Story   | Sprint     | Mô tả sai lệch | Mức độ |
| ------------ | ---------- | -------------- | ------ |
| [Story name] | [Sprint N] | [Mô tả]        | 🔴/🟡/🟢  |

## 📋 KHUYẾN NGHỊ HÀNH ĐỘNG
1. [Action item + Owner + Deadline khuyến nghị]

---

## 🔄 SO SÁNH VỚI LẦN ĐÁNH GIÁ TRƯỚC

> ⚠️ **CHỈ THÊM SECTION NÀY KHI ĐÂY LÀ LẦN ĐÁNH GIÁ THỨ 2 TRỞ LÊN** (tức là đã tìm thấy file review cũ). Nếu là lần đầu tiên → KHÔNG thêm section này.

### Tổng quan thay đổi
- **Điểm cũ**: XX/100 (ngày [ISO date cũ])
- **Điểm mới**: YY/100 (ngày [ISO date mới])
- **Thay đổi**: [+N hoặc -N] điểm

### So sánh điểm theo tiêu chí
| Tiêu chí                 | Điểm cũ | Điểm mới | Thay đổi | Ghi chú           |
| ------------------------ | ------- | -------- | -------- | ----------------- |
| Bám sát SRS              | X/20    | Y/20     | +N/−N    | [Lý do tăng/giảm] |
| Kiến trúc & Cấu trúc     | X/20    | Y/20     | +N/−N    | ...               |
| Tính nhất quán           | X/15    | Y/15     | +N/−N    | ...               |
| Tiến độ vs JIRA          | X/20    | Y/20     | +N/−N    | ...               |
| Code Quality             | X/15    | Y/15     | +N/−N    | ...               |
| Bảo mật & Best Practices | X/10    | Y/10     | +N/−N    | ...               |

### ✅ Nhược điểm ĐÃ KHẮC PHỤC (có trong lần trước, không còn trong lần này)
| #   | Nhược điểm cũ         | Trạng thái | Chi tiết khắc phục  |
| --- | --------------------- | ---------- | ------------------- |
| 1   | [Mô tả nhược điểm cũ] | ✅ Đã sửa   | [Mô tả cách đã sửa] |

### ⚠️ Nhược điểm VẪN TỒN TẠI (có trong cả lần trước và lần này)
| #   | Nhược điểm | Mức độ | Ghi chú                  |
| --- | ---------- | ------ | ------------------------ |
| 1   | [Mô tả]    | 🔴/🟡    | [Có cải thiện gì không?] |

### 🆕 Nhược điểm MỚI PHÁT SINH (không có trong lần trước, xuất hiện lần này)
| #   | Nhược điểm mới | Mức độ | Ghi chú    |
| --- | -------------- | ------ | ---------- |
| 1   | [Mô tả]        | 🔴/🟡/🟢  | [Chi tiết] |

### 💬 Nhận xét tổng quan
> [Nhận xét chung về sự tiến bộ: code có cải thiện rõ rệt không? Những điểm nào team đã làm tốt? Những điểm nào cần ưu tiên tiếp?]
```
