# Naming Convention Reference

> Reference document for `TEST_CASE_GEN` skill.
> All IDs, file names, and folder paths MUST follow these rules.

---

## Test Case ID Format

```
TC-UC{XX}-{PLATFORM}-{NNN}
```

| Segment      | Format          | Description                          | Example         |
| ------------ | --------------- | ------------------------------------ | --------------- |
| `TC`         | Fixed           | Test Case prefix                     | `TC`            |
| `UC{XX}`     | UC + 2-3 digits | Source Use Case number (zero-padded) | `UC01`, `UC042` |
| `{PLATFORM}` | Enum            | `ADMIN` or `MOBILE`                  | `ADMIN`         |
| `{NNN}`      | 3 digits        | Sequential number within UC+Platform | `001`           |

### Examples

| ID                   | Meaning                                    |
| -------------------- | ------------------------------------------ |
| `TC-UC01-ADMIN-001`  | 1st test case for UC001 on Admin platform  |
| `TC-UC01-ADMIN-015`  | 15th test case for UC001 on Admin platform |
| `TC-UC01-MOBILE-001` | 1st test case for UC001 on Mobile platform |
| `TC-UC42-MOBILE-003` | 3rd test case for UC042 on Mobile platform |

### Numbering Rules

- Start at `001` for each UC+Platform combination
- Number sequentially within category groups:
  - `001-019` → Happy Path (Main Flow)
  - `020-049` → Alternative Flows
  - `050-069` → Validation & Business Rules
  - `070-079` → Security Tests
  - `080-099` → Edge Cases & Boundary Values
- If a category exceeds its range, continue numbering — ranges are guidelines, not hard limits

---

## File Naming

```
{FUNCTION}_testcases.md
```

| Rule          | Format                 | Example                        |
| ------------- | ---------------------- | ------------------------------ |
| Function name | UPPER_SNAKE_CASE       | `LOGIN`, `REGISTER`            |
| Suffix        | Always `_testcases.md` | `LOGIN_testcases.md`           |
| Multi-word    | Underscore separated   | `FORGOT_PASSWORD_testcases.md` |

### Examples

| Function           | File Name                         |
| ------------------ | --------------------------------- |
| Login              | `LOGIN_testcases.md`              |
| Register           | `REGISTER_testcases.md`           |
| Forgot Password    | `FORGOT_PASSWORD_testcases.md`    |
| Reset Password     | `RESET_PASSWORD_testcases.md`     |
| Device List        | `DEVICE_LIST_testcases.md`        |
| View Health Vitals | `VIEW_HEALTH_VITALS_testcases.md` |

---

## Folder Structure

```
PM_REVIEW/
├── REVIEW_ADMIN/
│   └── TESTING/
│       ├── AUTH/
│       │   ├── LOGIN_testcases.md
│       │   ├── REGISTER_testcases.md
│       │   ├── FORGOT_PASSWORD_testcases.md
│       │   └── CHANGE_PASSWORD_testcases.md
│       ├── ADMIN_USERS/
│       │   └── CRUD_USERS_testcases.md
│       ├── DEVICES/
│       │   └── DEVICE_MANAGEMENT_testcases.md
│       ├── CONFIG/
│       │   └── SYSTEM_SETTINGS_testcases.md
│       └── LOGS/
│           └── VIEW_LOGS_testcases.md
│
├── REVIEW_MOBILE/
│   └── TESTING/
│       ├── AUTH/
│       │   ├── LOGIN_testcases.md
│       │   └── REGISTER_testcases.md
│       ├── DEVICE/
│       │   ├── CONNECT_DEVICE_testcases.md
│       │   └── DEVICE_LIST_testcases.md
│       ├── MONITORING/
│       │   └── VIEW_VITALS_testcases.md
│       ├── EMERGENCY/
│       │   ├── FALL_DETECTION_testcases.md
│       │   └── SOS_MANUAL_testcases.md
│       ├── NOTIFICATION/
│       │   └── ALERT_SETTINGS_testcases.md
│       ├── ANALYSIS/
│       │   └── RISK_SCORE_testcases.md
│       └── SLEEP/
│           └── SLEEP_ANALYSIS_testcases.md
```

### Folder Rules

- Module folder names match `MASTER_INDEX.md` module names (UPPER_CASE)
- `TESTING/` folder is always directly under platform folder
- Create module folders only when generating test cases for that module
- Never mix Admin and Mobile test cases in the same folder

---

## Platform Code Mapping

| MASTER_INDEX Module | Platform | Platform Code |
| ------------------- | -------- | ------------- |
| AUTH (Admin)        | Admin    | `ADMIN`       |
| AUTH (Mobile)       | Mobile   | `MOBILE`      |
| ADMIN_USERS         | Admin    | `ADMIN`       |
| DEVICES             | Admin    | `ADMIN`       |
| CONFIG              | Admin    | `ADMIN`       |
| LOGS                | Admin    | `ADMIN`       |
| DEVICE (Mobile)     | Mobile   | `MOBILE`      |
| MONITORING          | Mobile   | `MOBILE`      |
| EMERGENCY           | Mobile   | `MOBILE`      |
| NOTIFICATION        | Mobile   | `MOBILE`      |
| ANALYSIS            | Mobile   | `MOBILE`      |
| SLEEP               | Mobile   | `MOBILE`      |

---

## Severity Assignment Rules

| Source Element              | Default Severity |
| --------------------------- | ---------------- |
| Main Flow (happy path)      | `CRITICAL`       |
| Alt Flow (auth failure)     | `HIGH`           |
| Alt Flow (validation error) | `HIGH`           |
| Alt Flow (edge case)        | `MEDIUM`         |
| Business Rule (security)    | `HIGH`           |
| Business Rule (validation)  | `MEDIUM`         |
| NFR (performance)           | `MEDIUM`         |
| NFR (usability)             | `LOW`            |
| Boundary value (min/max)    | `MEDIUM`         |
| Security test (injection)   | `HIGH`           |
