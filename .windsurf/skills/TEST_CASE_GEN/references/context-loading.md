# Context Loading Protocol

> Reference document for `TEST_CASE_GEN` skill — GENERATE mode.
> Defines the exact order and method for loading source context before generating test cases.

---

## Loading Order (MANDATORY)

> [!IMPORTANT]
> Load context in this exact order. Each tier builds on the previous. DO NOT skip tiers.

### Tier 1: Project Navigation (ALWAYS)

| Step | File                               | Extract                                      |
| ---- | ---------------------------------- | -------------------------------------------- |
| 1    | `PM_REVIEW/MASTER_INDEX.md`        | Target module row, UC Refs, Sprint, Platform |
| 2    | `PM_REVIEW/Resources/SRS_INDEX.md` | System-level context, HG-FUNC mapping        |

**After Tier 1 you should know:**
- Which module the user is asking about
- Which UC(s) cover that module
- Which platform (ADMIN / MOBILE / BOTH)
- Which HG-FUNC requirements are relevant

### Tier 2: Use Case Deep Dive (GENERATE mode)

| Step | File                                         | Extract                                          |
| ---- | -------------------------------------------- | ------------------------------------------------ |
| 3    | `PM_REVIEW/Resources/UC/{Module}/UC{XXX}.md` | Main Flow steps, Alt Flows, Business Rules, NFRs |

**For each UC, extract:**

| Section            | Test Case Purpose                             |
| ------------------ | --------------------------------------------- |
| **Spec Table**     | Actors, preconditions, postconditions         |
| **Main Flow**      | Happy path test cases (CRITICAL severity)     |
| **Alt Flows**      | Error/edge case test cases (HIGH severity)    |
| **Business Rules** | Validation tests, boundary values             |
| **NFR**            | Performance, security, usability tests        |
| **Include/Extend** | Dependencies — may need to test those UCs too |

### Tier 3: Database Schema (GENERATE mode)

| Step | File                               | Extract                                  |
| ---- | ---------------------------------- | ---------------------------------------- |
| 4    | `PM_REVIEW/SQL SCRIPTS/README.md`  | Table overview, identify relevant tables |
| 5    | `PM_REVIEW/SQL SCRIPTS/0{N}_*.sql` | Column names, types, constraints         |

**SQL-to-Test-Case mapping:**

| SQL Element             | Test Case Type                        |
| ----------------------- | ------------------------------------- |
| `NOT NULL` constraint   | Test empty/null input → expect error  |
| `UNIQUE` constraint     | Test duplicate input → expect error   |
| `CHECK` constraint      | Test invalid values → expect error    |
| `VARCHAR(N)` length     | Test boundary: N chars, N+1 chars     |
| `DEFAULT` value         | Test omitting field → expect default  |
| `FOREIGN KEY`           | Test invalid reference → expect error |
| `ENUM` / allowed values | Test each value + invalid value       |

**SQL layer mapping for modules:**

| Module        | SQL File(s)                            |
| ------------- | -------------------------------------- |
| AUTH          | `02_create_tables_user_management.sql` |
| ADMIN_USERS   | `02_create_tables_user_management.sql` |
| DEVICES       | `03_create_tables_devices.sql`         |
| MONITORING    | `04_create_tables_timeseries.sql`      |
| EMERGENCY     | `05_create_tables_events_alerts.sql`   |
| ANALYSIS      | `06_create_tables_ai_analytics.sql`    |
| SLEEP         | `06_create_tables_ai_analytics.sql`    |
| NOTIFICATION  | `05_create_tables_events_alerts.sql`   |
| CONFIG / LOGS | `07_create_tables_system.sql`          |

### Tier 4: API Code Scan (GENERATE mode, if available)

| Step | Action                                             | Extract                            |
| ---- | -------------------------------------------------- | ---------------------------------- |
| 6    | Scan Admin API: `backend/src/routes/`              | Route definitions, HTTP methods    |
| 7    | Scan Admin controllers: `backend/src/controllers/` | Validator logic, error responses   |
| 8    | Scan Mobile API: `health_system/app/api/`          | FastAPI endpoints, Pydantic models |

**API-to-Test-Case mapping:**

| API Element             | Test Case Type                      |
| ----------------------- | ----------------------------------- |
| `POST /api/auth/login`  | Valid login, invalid login tests    |
| Request body validators | Missing field, wrong type tests     |
| Error response codes    | 400, 401, 403, 404, 500 scenarios   |
| Rate limiting           | Burst request test                  |
| JWT token required      | Missing/expired/invalid token tests |

---

## ⛔ WHAT NOT TO DO

| ❌ Don't                              | ✅ Do Instead                                   |
| ------------------------------------ | ---------------------------------------------- |
| Read the full SRS (382 lines)        | Use `SRS_INDEX.md` (~130 lines)                |
| Read all 26 UC files                 | Read only the target UC(s)                     |
| Read all 10 SQL files                | Read only the relevant SQL layer file          |
| Read all API code                    | Scan only the target module routes/controllers |
| Load Tier 4 for non-existing modules | Skip Tier 4 if module code is "Not built"      |
| Generate without reading UC first    | ALWAYS read UC before generating               |

---

## Platform-Specific Source Paths

### Admin Platform

| Source Type   | Path Pattern                                    |
| ------------- | ----------------------------------------------- |
| Frontend      | `frontend/src/pages/{module}/`                  |
| API Routes    | `backend/src/routes/{module}Routes.ts`          |
| Controllers   | `backend/src/controllers/{module}Controller.ts` |
| Middleware    | `backend/src/middleware/`                       |
| Prisma Schema | `backend/prisma/schema.prisma`                  |

### Mobile Platform

| Source Type | Path Pattern                                     |
| ----------- | ------------------------------------------------ |
| Flutter UI  | `health_system/lib/features/{module}/`           |
| FastAPI     | `health_system/app/api/v1/endpoints/{module}.py` |
| Models      | `health_system/app/models/{module}.py`           |
| Schemas     | `health_system/app/schemas/{module}.py`          |
| SQLAlchemy  | `health_system/app/models/`                      |

---

## Context Loading Checklist

Before proceeding to test case generation, verify:

- [ ] Module identified from MASTER_INDEX
- [ ] UC Refs extracted (e.g., UC001, UC002)
- [ ] Platform determined (ADMIN / MOBILE / BOTH)
- [ ] UC file(s) read — main flow, alt flows, BRs, NFRs extracted
- [ ] Relevant SQL file read — table structure and constraints known
- [ ] API code scanned (if module is built) — routes and validators known
- [ ] Ready to generate test cases
