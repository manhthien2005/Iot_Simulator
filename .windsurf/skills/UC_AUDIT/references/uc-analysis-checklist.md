# UC Analysis Checklist — Per-UC Quality Criteria

> Reference for Phase 1 of UC_AUDIT. Read when evaluating individual UCs.

---

## Required Sections Check

Every UC file MUST contain these sections. Mark ✅ or ❌ for each:

| #   | Section        | Vietnamese Header in UC File         | Required |
| --- | -------------- | ------------------------------------ | -------- |
| 1   | Spec Table     | `Bảng đặc tả Use Case`               | ✅ MUST   |
| 2   | Main Flow      | `Luồng chính (Main Flow)`            | ✅ MUST   |
| 3   | Alt Flows      | `Luồng thay thế (Alternative Flows)` | ✅ MUST   |
| 4   | Business Rules | `Business Rules`                     | ✅ MUST   |
| 5   | NFR            | `Yêu cầu phi chức năng`              | ✅ SHOULD |

---

## Spec Table Fields Check

The spec table MUST contain these fields:

| Field          | Label in UC File | Validation Rule                                  |
| -------------- | ---------------- | ------------------------------------------------ |
| UC ID          | Mã UC            | Must match filename (e.g., UC001)                |
| UC Name        | Tên UC           | Format: Verb + Object                            |
| Primary Actor  | Tác nhân chính   | Must be external entity, NOT "Hệ thống" (System) |
| Description    | Mô tả            | 1-2 sentences max                                |
| Trigger        | Trigger          | User action that starts the UC                   |
| Preconditions  | Tiền điều kiện   | At least 1                                       |
| Postconditions | Hậu điều kiện    | At least 1                                       |

---

## Main Flow Quality

| Criterion            | Rule                                        | Severity                         |
| -------------------- | ------------------------------------------- | -------------------------------- |
| Step count           | ≤ 10 steps preferred, max 15                | WARN if > 10, ERROR if > 15      |
| Actor column         | Each step has clear actor (User or System)  | ERROR if missing                 |
| Action clarity       | Each action is one atomic operation         | WARN if compound                 |
| No technical details | No API endpoints, SQL queries, JSON in flow | WARN                             |
| Happy path only      | Main flow = everything works correctly      | ERROR if includes error handling |

---

## Alternative Flows Quality

| Criterion      | Rule                                      | Severity       |
| -------------- | ----------------------------------------- | -------------- |
| Numbering      | Must reference main flow step (e.g., 5.a) | ERROR if wrong |
| Error at least | At least 1 alt flow for validation errors | WARN if none   |
| Clear heading  | Each alt flow has descriptive heading     | WARN           |

---

## Business Rules Quality

| Criterion                | Rule                                       | Severity              |
| ------------------------ | ------------------------------------------ | --------------------- |
| BR code format           | `BR-{UCID}-{NN}` (e.g., BR-001, BR-040-01) | WARN if missing code  |
| Specificity              | Must be specific to this UC, not generic   | WARN if copy-paste    |
| No implementation detail | No bcrypt, JWT secrets, algorithm names    | OK if high-level only |
| Thresholds/limits        | Include specific numbers when applicable   | INFO                  |

---

## Relevance Scoring Rubric

Use this rubric in Phase 2 to classify each UC:

### CORE (Direct SRS implementation)
- UC directly implements one or more HG-FUNC requirements
- Without this UC, a core system feature would be missing
- Examples: UC006 (Monitoring), UC010 (Fall Alert), UC016 (Risk Report)

### SUPPORTING (Enables core features)
- UC provides infrastructure needed by core features
- Authentication, profile management, password recovery
- Examples: UC001 (Login), UC002 (Register), UC004 (Change Password)

### MANAGEMENT (Admin/system operations)
- UC is for system administration and configuration
- Not directly used by end-users (patients/caregivers)
- Examples: UC022 (Manage Users), UC024 (Configure System), UC026 (Logs)

### LOW (Weak connection)
- UC has marginal impact on system goals
- Could be deferred without affecting core functionality
- Rare — most UCs should be CORE, SUPPORTING, or MANAGEMENT

---

## Data Field Extraction Guide

When reading UC text, extract data fields from these locations:

1. **Main Flow actions** — Look for user input fields (e.g., "email", "password" in login actions)
2. **Preconditions** — Look for entity references (e.g., "device exists in system" → table: `devices`)
3. **Postconditions** — Look for state changes (e.g., "`devices.user_id` assigned" → field: `user_id`)
4. **Business Rules** — Look for field constraints (e.g., "role: patient, caregiver, admin" → field: `role`)
5. **Alt Flows** — Look for condition checks (e.g., "`is_active = false`" → field: `is_active`)

### Common Field → SQL Table Mapping

| Data Domain       | Typical Fields                                | SQL Table                          |
| ----------------- | --------------------------------------------- | ---------------------------------- |
| Auth              | email, password, JWT token                    | `users`                            |
| Profile           | full_name, date_of_birth, gender, avatar      | `users`                            |
| Medical           | blood_type, height, weight, conditions        | `users`                            |
| Device            | device_id, serial, model, firmware            | `devices`                          |
| Vitals            | heart_rate, spo2, temperature, blood_pressure | `vitals`                           |
| Motion            | accel_x/y/z, gyro_x/y/z                       | `motion_data`                      |
| Fall              | confidence, fall_type, user_cancelled         | `fall_events`                      |
| SOS               | status, location, responder                   | `sos_events`                       |
| Alert             | type, severity, data (jsonb)                  | `alerts`                           |
| Risk              | score, risk_level, feature_importance         | `risk_scores`, `risk_explanations` |
| Emergency Contact | name, phone, priority                         | `emergency_contacts`               |
| Relationship      | patient-caregiver, permissions                | `user_relationships`               |
| Audit             | action, resource_type, ip_address             | `audit_logs`                       |
| Notification      | push/SMS preferences                          | `alerts`                           |
| Sleep             | sleep phases, quality score                   | (sleep tables if exist)            |
