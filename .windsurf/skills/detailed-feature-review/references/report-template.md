CRITICAL INSTRUCTION: You MUST generate the final report in Vietnamese, exactly matching the markdown template below. Do not generate English text in the final report. The table headers, structure, and template wording must remain exactly as defined below in Vietnamese.

```markdown
# 🔬 BÁO CÁO ĐÁNH GIÁ CHI TIẾT

## Thông tin chung
- **Chức năng**: [Tên]
- **Module**: [AUTH/DEVICE/MONITORING/EMERGENCY/NOTIFICATION/ANALYSIS/SLEEP/ADMIN/INFRA]
- **Dự án**: [Admin / Mobile / Cả hai]
- **Sprint**: [Sprint N]
- **JIRA Epic**: [Epic Name — VD: EP04-Login]
- **JIRA Story**: [Story name từ CSV]
- **UC Reference**: [UC0XX]
- **Ngày đánh giá**: [ISO date]
- **Lần đánh giá**: [N] ← (1 = lần đầu, 2+ = re-review)
- **Ngày đánh giá trước**: [ISO date hoặc "N/A" nếu lần đầu]

---

## 🏆 TỔNG ĐIỂM: XX/100

| Tiêu chí                    | Điểm | Ghi chú |
| --------------------------- | ---- | ------- |
| Chức năng đúng yêu cầu      | /15  | ...     |
| API Design                  | /10  | ...     |
| Architecture & Patterns     | /15  | ...     |
| Validation & Error Handling | /12  | ...     |
| Security                    | /12  | ...     |
| Code Quality                | /12  | ...     |
| Testing                     | /12  | ...     |
| Documentation               | /12  | ...     |

---

## 📐 ARCHITECTURE DEEP DIVE

### Clean Architecture Layers (/5)
| Kiểm tra                                       | Đạt? | Ghi chú |
| ---------------------------------------------- | ---- | ------- |
| Route → Controller → Service → Repo separation | ✅/❌  | ...     |
| ...                                            |      |         |

### Design Patterns (/5)
| Pattern    | Có? | Đánh giá |
| ---------- | --- | -------- |
| Middleware | ✅/❌ | ...      |
| ...        |     |          |

---

## 📂 FILES ĐÁNH GIÁ
| File           | Layer                     | LOC | Đánh giá tóm tắt |
| -------------- | ------------------------- | --- | ---------------- |
| `path/to/file` | [Controller/Service/Repo] | [N] | [Tóm tắt]        |

---

## 📋 JIRA STORY TRACKING

### Epic: [Tên Epic] (Sprint X)

#### [Role Name]
| #   | Checklist Item | Trạng thái | Ghi chú    |
| --- | -------------- | ---------- | ---------- |
| 1   | [Item]         | ✅/⚠️/❌/🔄    | [Chi tiết] |

#### Acceptance Criteria
| #   | Criteria   | Trạng thái | Ghi chú    |
| --- | ---------- | ---------- | ---------- |
| 1   | [Criteria] | ✅/❌        | [Chi tiết] |

---

## 📊 SRS COMPLIANCE

### Main Flow
| Bước | SRS Yêu cầu | Implementation | Match? |
| ---- | ----------- | -------------- | ------ |
| 1    | [Mô tả]     | [Thực tế]      | ✅/❌    |

### Alternative Flows
| Flow | SRS Yêu cầu | Implementation | Match? |
| ---- | ----------- | -------------- | ------ |

### Exception Flows
| Flow | SRS Yêu cầu | Implementation | Match? |
| ---- | ----------- | -------------- | ------ |

---

## ✅ ƯU ĐIỂM
1. [Ưu điểm + file/line reference]

## ❌ NHƯỢC ĐIỂM
1. [Nhược điểm + lý do + file/line reference]

## 🔧 ĐIỂM CẦN CẢI THIỆN
1. **[HIGH]** [Mô tả] → Cách sửa: [suggestion]
2. **[MEDIUM]** [Mô tả] → Cách sửa: [suggestion]
3. **[LOW]** [Mô tả] → Cách sửa: [suggestion]

## 🗑️ ĐIỂM CẦN LOẠI BỎ
1. [Code/pattern cần loại bỏ + lý do]

## ⚠️ SAI LỆCH VỚI JIRA / SRS
| Source         | Mô tả sai lệch | Mức độ | Đề xuất   |
| -------------- | -------------- | ------ | --------- |
| JIRA Story [X] | [Mô tả]        | 🔴/🟡/🟢  | [Đề xuất] |

## 💡 CODE SNIPPETS ĐÁNG CHÚ Ý

### ✅ Code tốt:
\```[language]
// file: path/to/file, line X-Y
[code snippet]
\```

### ❌ Code cần sửa:
\```[language]
// HIỆN TẠI:
[current code]
// NÊN SỬA THÀNH:
[suggested code]
\```

## 📋 KHUYẾN NGHỊ HÀNH ĐỘNG
| #   | Action  | Owner  | Priority     | Sprint     |
| --- | ------- | ------ | ------------ | ---------- |
| 1   | [Mô tả] | [Role] | HIGH/MED/LOW | [Sprint N] |

---

## 🔄 SO SÁNH VỚI LẦN ĐÁNH GIÁ TRƯỚC

> ⚠️ **CHỈ THÊM SECTION NÀY KHI ĐÂY LÀ LẦN ĐÁNH GIÁ THỨ 2 TRỞ LÊN** (tức là đã tìm thấy file review cũ). Nếu là lần đầu tiên → KHÔNG thêm section này.

### Tổng quan thay đổi
- **Điểm cũ**: XX/100 (ngày [ISO date cũ])
- **Điểm mới**: YY/100 (ngày [ISO date mới])
- **Thay đổi**: [+N hoặc -N] điểm

### So sánh điểm theo tiêu chí
| Tiêu chí                    | Điểm cũ | Điểm mới | Thay đổi | Ghi chú           |
| --------------------------- | ------- | -------- | -------- | ----------------- |
| Chức năng đúng yêu cầu      | X/15    | Y/15     | +N/−N    | [Lý do tăng/giảm] |
| API Design                  | X/10    | Y/10     | +N/−N    | ...               |
| Architecture & Patterns     | X/15    | Y/15     | +N/−N    | ...               |
| Validation & Error Handling | X/12    | Y/12     | +N/−N    | ...               |
| Security                    | X/12    | Y/12     | +N/−N    | ...               |
| Code Quality                | X/12    | Y/12     | +N/−N    | ...               |
| Testing                     | X/12    | Y/12     | +N/−N    | ...               |
| Documentation               | X/12    | Y/12     | +N/−N    | ...               |

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
