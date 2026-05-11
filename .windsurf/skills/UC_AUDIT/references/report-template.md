# Report Template — UC_AUDIT Output

> Reference for UC_AUDIT Output Protocol. The AI MUST follow this template when generating the audit report.

---

## File Naming

```
UC_AUDIT_report.md
```

## Output Location

- `PM_REVIEW/UC_AUDIT_report.md` (project-wide, not per Admin/Mobile)

## Overwrite Policy

> [!IMPORTANT]
> If `UC_AUDIT_report.md` already exists → **OVERWRITE** directly. Do NOT create versioned copies.

---

## Report Template (Vietnamese)

```markdown
# BÁO CÁO KIỂM TRA USE CASE — HealthGuard

> **Ngày**: {DATE}
> **Phiên bản**: {N}
> **Tổng UC kiểm tra**: 26

---

## 1. TỔNG QUAN KIỂM TRA

| Metric                  | Kết quả     |
| ----------------------- | ----------- |
| Tổng UC                 | {N}         |
| UC đạt chất lượng       | {N}         |
| UC cần sửa              | {N}         |
| HG-FUNC được phủ        | {N}/11      |
| UC có JIRA Task         | {N}/{TOTAL} |
| Cột SQL được phủ bởi UC | {N}/{TOTAL} |

---

## 2. BẢNG KIỂM TRA UC (Inventory)

| UC    | Module | Actors | Platform | Relevance  | Quality | JIRA       | Issues |
| ----- | ------ | ------ | -------- | ---------- | ------- | ---------- | ------ |
| UC001 | Auth   | ...    | Both     | SUPPORTING | ✅       | EP04-Login | —      |
| ...   | ...    | ...    | ...      | ...        | ...     | ...        | ...    |

---

## 3. ĐÁNH GIÁ TÍNH LIÊN QUAN (SRS Alignment)

### 3.1 HG-FUNC Coverage

| HG-FUNC    | Description       | UCs          | Status |
| ---------- | ----------------- | ------------ | ------ |
| HG-FUNC-01 | Collect vitals    | (background) | ✅ N/A  |
| HG-FUNC-02 | Display on Mobile | UC006, UC007 | ✅      |
| ...        | ...               | ...          | ...    |

### 3.2 UC Relevance Classification

| Level      | UCs                             | Count |
| ---------- | ------------------------------- | ----- |
| CORE       | UC006, UC007, UC008, UC010, ... | {N}   |
| SUPPORTING | UC001, UC002, UC003, UC004, ... | {N}   |
| MANAGEMENT | UC022, UC024, UC025, UC026      | {N}   |
| LOW        | (none expected)                 | 0     |

---

## 4. KIỂM TRA CHÉO (Cross-Check)

### 4.1 UC ↔ JIRA Gaps

| UC    | Expected Epic | Actual    | Status | Flag       |
| ----- | ------------- | --------- | ------ | ---------- |
| UC005 | ???           | Not found | ❌      | UC_NO_TASK |
| ...   | ...           | ...       | ...    | ...        |

### 4.2 UC ↔ SQL Gaps

| Table | Column   | Covered by UC | Status          |
| ----- | -------- | ------------- | --------------- |
| users | language | ???           | ⚠️ ORPHAN_COLUMN |
| ...   | ...      | ...           | ...             |

### 4.3 Internal Consistency

| Check    | Source A          | Source B    | Match | Flag         |
| -------- | ----------------- | ----------- | ----- | ------------ |
| UC count | 00_DANH_SACH (26) | README (24) | ❌     | STATS_DESYNC |
| ...      | ...               | ...         | ...   | ...          |

---

## 5. KHUYẾN NGHỊ ƯU TIÊN

| Priority | Issue   | Action Required |
| -------- | ------- | --------------- |
| P0       | {issue} | {action}        |
| P1       | {issue} | {action}        |
| ...      | ...     | ...             |

---

## 🔄 SO SÁNH VỚI LẦN KIỂM TRA TRƯỚC (if re-audit)

> Only include this section if a previous `UC_AUDIT_report.md` existed.

| Metric            | Lần trước | Lần này | Thay đổi |
| ----------------- | --------- | ------- | -------- |
| UC đạt chất lượng | {N}       | {N}     | +{N}     |
| Gaps found        | {N}       | {N}     | -{N}     |

### Issues Fixed
- {list of issues that were in old report but resolved now}

### Issues Remaining
- {list of issues still present}

### New Issues
- {list of issues not in old report}
```
