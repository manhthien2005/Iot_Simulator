# Test Case File Template

> Reference document for `TEST_CASE_GEN` skill.
> All generated test case files MUST follow this format exactly.

---

## File Header (MANDATORY)

Every test case file starts with this header block:

```markdown
# Test Cases: {MODULE} — {FUNCTION}

| Property     | Value                              |
| ------------ | ---------------------------------- |
| **Module**   | {MODULE_NAME}                      |
| **Function** | {FUNCTION_NAME}                    |
| **UC Refs**  | UC{XXX}, UC{YYY}                   |
| **Platform** | ADMIN / MOBILE / BOTH              |
| **Sprint**   | S{N}                               |
| **Version**  | v1.0                               |
| **Created**  | YYYY-MM-DD                         |
| **Author**   | AI_AGENT                           |
| **Status**   | DRAFT / READY / IN_PROGRESS / DONE |
```

---

## Test Data — Materials (MANDATORY)

After the header, include a **Test Data** section. AI generates the table with `Value` = `⬜ PENDING` — user fills in real values before execution.

```markdown
## Test Data

> **Instruction**: Fill in the `Value` column before running tests. AI will use these during EXECUTE mode.
> Items marked ⬜ PENDING are required. Items marked ✅ are filled.

### Accounts

| #   | Material             | Purpose             | Value               | Status |
| --- | -------------------- | ------------------- | ------------------- | ------ |
| 1   | Admin email          | Valid login test    | ⬜ PENDING           | ⬜      |
| 2   | Admin password       | Valid login test    | ⬜ PENDING           | ⬜      |
| 3   | Invalid email        | Wrong email test    | `notexist@test.com` | ✅      |
| 4   | Locked account email | Account locked test | ⬜ PENDING           | ⬜      |

### Environment

| #   | Material              | Purpose          | Value     | Status |
| --- | --------------------- | ---------------- | --------- | ------ |
| 1   | Base URL (Admin)      | All admin tests  | ⬜ PENDING | ⬜      |
| 2   | Base URL (Mobile API) | All mobile tests | ⬜ PENDING | ⬜      |

### Tokens & Keys

| #   | Material          | Purpose             | Value            | Status |
| --- | ----------------- | ------------------- | ---------------- | ------ |
| 1   | Valid JWT token   | Auth endpoint tests | ⬜ AUTO-GENERATED | ⬜      |
| 2   | Expired JWT token | Token expiry test   | ⬜ PENDING        | ⬜      |
```

### Material Categories

AI generates material tables from these categories based on what the UC requires:

| Category              | When to Include     | Examples                              |
| --------------------- | ------------------- | ------------------------------------- |
| **Accounts**          | Any auth-related UC | email, password, role, locked account |
| **Environment**       | ALWAYS              | Base URL, API URL, DB connection      |
| **Tokens & Keys**     | Auth/API tests      | JWT, API key, refresh token           |
| **Test Devices**      | Mobile/Device UCs   | device_id, mac_address, firmware      |
| **Test Data**         | CRUD operations     | sample records, file uploads          |
| **External Services** | Integration tests   | MQTT broker, email server             |

### Status Values

| Status             | Meaning                                 |
| ------------------ | --------------------------------------- |
| `⬜ PENDING`        | User must fill in before test execution |
| `⬜ AUTO-GENERATED` | AI will generate during test execution  |
| `✅`                | Value is filled and ready               |

### Rules

- **NEVER hardcode real credentials** — always use `⬜ PENDING`
- AI may pre-fill obvious test data (e.g., `notexist@test.com`)
- **Environment section is ALWAYS required** — minimum: Base URL
- In EXECUTE mode: if any `⬜ PENDING` exists → **ASK the user** before proceeding
- User fills values directly in the generated file → AI reads them during EXECUTE

---

## Test Case Table (MANDATORY)


Use this exact column structure. Each row = one test case.

```markdown
| ID                | UC    | Platform | Severity | Title | Preconditions | Steps | Expected | Actual | Status  | Tester | DateTime |
| ----------------- | ----- | -------- | -------- | ----- | ------------- | ----- | -------- | ------ | ------- | ------ | -------- |
| TC-UC01-ADMIN-001 | UC001 | ADMIN    | CRITICAL | ...   | ...           | ...   | ...      | —      | NOT_RUN | —      | —        |
```

### Column Definitions

| Column            | Type   | Description                                            | Example                                                                    |
| ----------------- | ------ | ------------------------------------------------------ | -------------------------------------------------------------------------- |
| **ID**            | String | Unique test case ID (see naming-convention.md)         | `TC-UC01-ADMIN-001`                                                        |
| **UC**            | String | Source Use Case reference                              | `UC001`                                                                    |
| **Platform**      | Enum   | `ADMIN` / `MOBILE`                                     | `ADMIN`                                                                    |
| **Severity**      | Enum   | `CRITICAL` / `HIGH` / `MEDIUM` / `LOW`                 | `HIGH`                                                                     |
| **Title**         | String | Short descriptive test title (English)                 | `Valid login with correct credentials`                                     |
| **Preconditions** | String | Required state before test execution                   | `User account exists, not locked`                                          |
| **Steps**         | String | Numbered steps, separated by semicolons                | `1. Navigate to /login; 2. Enter email; 3. Enter password; 4. Click Login` |
| **Expected**      | String | Expected outcome after all steps                       | `Redirect to dashboard, JWT token issued`                                  |
| **Actual**        | String | Actual outcome (filled during EXECUTE). `—` if not run | `Redirected to dashboard OK`                                               |
| **Status**        | Enum   | `NOT_RUN` / `PASS` / `FAIL` / `BLOCKED` / `SKIP`       | `NOT_RUN`                                                                  |
| **Tester**        | String | Who executed. `—` if not run. `AI_AGENT` if AI ran it  | `AI_AGENT`                                                                 |
| **DateTime**      | String | Execution timestamp ISO 8601. `—` if not run           | `2026-03-05 08:30`                                                         |

---

## Test Case Grouping

Group test cases by category using markdown headers:

```markdown
## Happy Path (Main Flow)
| ID | UC | ... |

## Alternative Flows
| ID | UC | ... |

## Validation & Business Rules
| ID | UC | ... |

## Security Tests
| ID | UC | ... |

## Edge Cases & Boundary Values
| ID | UC | ... |
```

---

## Execution Log Section (Appended by EXECUTE mode)

After test execution, append this section at the bottom of the file:

```markdown
---

## Execution Log

### Session: YYYY-MM-DD HH:MM

| Metric        | Value |
| ------------- | ----- |
| **Executed**  | N     |
| **PASS**      | N     |
| **FAIL**      | N     |
| **BLOCKED**   | N     |
| **SKIP**      | N     |
| **NOT_RUN**   | N     |
| **Pass Rate** | NN%   |
| **Tester**    | Name  |
| **Duration**  | ~Nm   |

#### Failed Tests
- `TC-UC01-ADMIN-003`: Brief failure reason
- `TC-UC01-ADMIN-007`: Brief failure reason

#### Blocked Tests
- `TC-UC01-ADMIN-005`: Reason blocked

#### Notes
- Any environmental issues, observations, or follow-up actions
```

---

## Complete Example

```markdown
# Test Cases: AUTH — LOGIN

| Property     | Value      |
| ------------ | ---------- |
| **Module**   | AUTH       |
| **Function** | LOGIN      |
| **UC Refs**  | UC001      |
| **Platform** | ADMIN      |
| **Sprint**   | S1         |
| **Version**  | v1.0       |
| **Created**  | 2026-03-05 |
| **Author**   | AI_AGENT   |
| **Status**   | READY      |

## Test Data

> **Instruction**: Fill in the `Value` column before running tests.

### Accounts

| #   | Material             | Purpose             | Value               | Status |
| --- | -------------------- | ------------------- | ------------------- | ------ |
| 1   | Admin email          | Valid login test    | ⬜ PENDING           | ⬜      |
| 2   | Admin password       | Valid login test    | ⬜ PENDING           | ⬜      |
| 3   | Invalid email        | Wrong email test    | `notexist@test.com` | ✅      |
| 4   | Wrong password       | Wrong password test | `WrongPass123!`     | ✅      |
| 5   | Locked account email | Account locked test | ⬜ PENDING           | ⬜      |

### Environment

| #   | Material       | Purpose         | Value     | Status |
| --- | -------------- | --------------- | --------- | ------ |
| 1   | Admin Base URL | All admin tests | ⬜ PENDING | ⬜      |


## Happy Path (Main Flow)

| ID                | UC    | Platform | Severity | Title                                       | Preconditions                                                    | Steps                                                                                       | Expected                                                               | Actual | Status  | Tester | DateTime |
| ----------------- | ----- | -------- | -------- | ------------------------------------------- | ---------------------------------------------------------------- | ------------------------------------------------------------------------------------------- | ---------------------------------------------------------------------- | ------ | ------- | ------ | -------- |
| TC-UC01-ADMIN-001 | UC001 | ADMIN    | CRITICAL | Valid login with correct email and password | 1. User account exists; 2. Account not locked; 3. Email verified | 1. Navigate to /login; 2. Enter valid email; 3. Enter valid password; 4. Click Login button | 1. Redirect to /dashboard; 2. JWT token stored; 3. User info displayed | —      | NOT_RUN | —      | —        |

## Alternative Flows

| ID                | UC    | Platform | Severity | Title                                   | Preconditions                 | Steps                                                                                | Expected                                                                   | Actual | Status  | Tester | DateTime |
| ----------------- | ----- | -------- | -------- | --------------------------------------- | ----------------------------- | ------------------------------------------------------------------------------------ | -------------------------------------------------------------------------- | ------ | ------- | ------ | -------- |
| TC-UC01-ADMIN-002 | UC001 | ADMIN    | HIGH     | Login fails with wrong password         | 1. User account exists        | 1. Navigate to /login; 2. Enter valid email; 3. Enter wrong password; 4. Click Login | 1. Error message displayed; 2. No redirect; 3. Attempt counter incremented | —      | NOT_RUN | —      | —        |
| TC-UC01-ADMIN-003 | UC001 | ADMIN    | HIGH     | Login blocked after max failed attempts | 1. User has 4 failed attempts | 1. Navigate to /login; 2. Enter valid email; 3. Enter wrong password; 4. Click Login | 1. Account locked message; 2. Status set to LOCKED in DB                   | —      | NOT_RUN | —      | —        |
```
