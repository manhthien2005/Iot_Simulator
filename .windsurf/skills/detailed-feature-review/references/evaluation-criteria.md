# Evaluation Criteria Reference

## 📊 SCORE CLASSIFICATION

| Score Range | Quality Status | Meaning                                           |
| ----------- | -------------- | ------------------------------------------------- |
| **76–100**  | ✅ Pass         | Quality meets standards, eligible for release     |
| **51–75**   | ⚠️ Needs Fix    | Functional but requires fixes before release      |
| **0–50**    | ❌ Fail         | Does not meet requirements, major refactor needed |

> [!IMPORTANT]
> After scoring, the AI MUST determine the Quality Status from this table and update it in `MASTER_INDEX.md`.

---

## 🏗️ API DESIGN CHECKLIST (Criterion #2 — Details)

### 2A. RESTful Conventions (/4)

| Check                                                                         | Pass? | Notes |
| ----------------------------------------------------------------------------- | ----- | ----- |
| Correct HTTP methods (GET=read, POST=create, PUT/PATCH=update, DELETE=delete) |       |       |
| Standard status codes (200, 201, 400, 401, 403, 404, 500)                     |       |       |
| Logical URL resource naming (plural nouns, no verbs)                          |       |       |
| Consistent and predictable API paths (`/api/v1/resource`)                     |       |       |

### 2B. Error Response Format (/3)

| Check                                                          | Pass? | Notes |
| -------------------------------------------------------------- | ----- | ----- |
| Unified error response structure (`{status, message, errors}`) |       |       |
| Validation errors provide field-level details                  |       |       |
| No internal errors/stack traces leaked to the client           |       |       |

### 2C. Data Contract (/3)

| Check                                                 | Pass? | Notes |
| ----------------------------------------------------- | ----- | ----- |
| Clear Request/Response schemas                        |       |       |
| Pagination pattern for list endpoints (cursor/offset) |       |       |
| Consistent date format (ISO 8601)                     |       |       |

## 📐 ARCHITECTURE & PATTERNS CHECKLIST (Criterion #3 — Details)

### 3A. Clean Architecture Layers (/5)

| Check                                                                     | Pass? | Notes |
| ------------------------------------------------------------------------- | ----- | ----- |
| **Route → Controller → Service → Repository/Model** clear separation      |       |       |
| Controller ONLY handles request/response, NO business logic               |       |       |
| Service isolates business logic, DOES NOT access request/response objects |       |       |
| Repository/Model isolates data access, NO business logic                  |       |       |
| Dependency direction: Controller → Service → Repository (never inverted)  |       |       |

### 3B. Domain Logic & Business Rules (/5)

| Check                                               | Pass? | Notes |
| --------------------------------------------------- | ----- | ----- |
| Business rules are centralized in the Service layer |       |       |
| Domain validation is separated from API validation  |       |       |
| Edge cases handled (null, empty, boundary values)   |       |       |
| Business logic can be tested without HTTP/DB        |       |       |
| No duplicated business logic                        |       |       |

### 3C. Design Patterns Applied (/5)

| Pattern                                                           | Used? | Assessment |
| ----------------------------------------------------------------- | ----- | ---------- |
| **Middleware** — Auth guard, validation, error handler            |       |            |
| **Repository** — Data access abstraction                          |       |            |
| **DTO/Schema** — Data transfer objects for request/response       |       |            |
| **Factory/Builder** — Object creation (if applicable)             |       |            |
| **Strategy** — Handling multiple logic variations (if applicable) |       |            |

## 🔒 SECURITY CHECKLIST (Criterion #5 — Details)

### 5A. Authentication & Authorization (/4)

| Check                                                           | Pass? | Notes |
| --------------------------------------------------------------- | ----- | ----- |
| JWT token properly validated (signature, expiry, issuer)        |       |       |
| Refresh token flow implemented (if applicable)                  |       |       |
| Route-level authorization (only authorized users can access)    |       |       |
| Passwords hashed securely: bcrypt/argon2, NO md5/sha1/plaintext |       |       |

### 5B. Input Security (/4)

| Check                                                              | Pass? | Notes |
| ------------------------------------------------------------------ | ----- | ----- |
| Input validation AND sanitization on the server-side               |       |       |
| SQL injection prevention (parameterized queries / ORM)             |       |       |
| XSS prevention (output encoding, prevent raw HTML injection)       |       |       |
| File upload validation (if applicable): type, size, content checks |       |       |

### 5C. Rate Limiting & Abuse Prevention (/4)

| Check                                                         | Pass? | Notes |
| ------------------------------------------------------------- | ----- | ----- |
| Rate limiting on login/register/OTP endpoints                 |       |       |
| Brute force protection (account lockout / delay)              |       |       |
| CORS appropriately configured (specific origins, no wildcard) |       |       |
| Secrets kept in `.env`, NEVER hardcoded in the source         |       |       |

## 🧹 CODE QUALITY CHECKLIST (Criterion #6 — Details)

### 6A. SOLID Principles (/4)

| Principle                     | Question                                                       | Pass? |
| ----------------------------- | -------------------------------------------------------------- | ----- |
| **S** — Single Responsibility | Does each function/class/file have exactly 1 clear purpose?    |       |
| **O** — Open/Closed           | Can new features be added without altering existing code?      |       |
| **D** — Dependency Inversion  | Depends on abstractions (interfaces), rather than concretions? |       |
| Overall                       | Is the code easily extensible and maintainable?                |       |

### 6B. Clean Code Metrics (/4)

| Metric               | Target                                 | Actual | Pass? |
| -------------------- | -------------------------------------- | ------ | ----- |
| Function length      | ≤ 50 lines (max 80)                    |        |       |
| File length          | ≤ 200 lines                            |        |       |
| Nesting depth        | ≤ 3 levels                             |        |       |
| Early return pattern | Used instead of endless nested if-else |        |       |

### 6C. Anti-patterns Check (/4)

| Anti-pattern                                                   | Detected? | Location |
| -------------------------------------------------------------- | --------- | -------- |
| **God Object/Function** — 1 function handling too many things  |           |          |
| **Generic naming** — `utils.js`, `helpers.js`, `common.js`     |           |          |
| **Copy-paste code** — Logic duplicated in ≥ 2 places           |           |          |
| **Magic values** — Hardcoded numbers/strings without constants |           |          |

## 🧪 TESTING CHECKLIST (Criterion #7 — Details)

### 7A. Test Coverage (/4)

| Test Type                                                     | Present? | Coverage estimate |
| ------------------------------------------------------------- | -------- | ----------------- |
| **Unit tests** — Business logic, services                     |          |                   |
| **Integration tests** — API endpoints, DB queries             |          |                   |
| **Edge case tests** — Boundary values, null, empty inputs     |          |                   |
| **Error scenario tests** — Invalid input, unauthorized states |          |                   |

### 7B. Test Quality (/4)

| Check                                                    | Pass? | Notes |
| -------------------------------------------------------- | ----- | ----- |
| Tests have clear descriptive names (describe + it/test)  |       |       |
| Tests are independent — do not rely on execution order   |       |       |
| Proper test data setup/teardown mechanics                |       |       |
| Mocks for external dependencies (DB, API calls) are used |       |       |

### 7C. Advanced Testing (Bonus) (/4)

| Test Type                                | Present? | Notes |
| ---------------------------------------- | -------- | ----- |
| Contract testing (API schema validation) |          |       |
| Load/Performance testing                 |          |       |
| Security testing (OWASP scan)            |          |       |

## 📝 DOCUMENTATION CHECKLIST (Criterion #8 — Details)

### 8A. Code Documentation (/4)

| Check                                                        | Pass? |
| ------------------------------------------------------------ | ----- |
| JSDoc/docstring provided for public functions                |       |
| Complex logic accompanied by inline comments explaining WHY  |       |
| README available for the module (or included in main README) |       |

### 8B. API Documentation (/4)

| Check                                                                 | Pass? |
| --------------------------------------------------------------------- | ----- |
| API endpoints are documented (route, method, params, response schema) |       |
| Request/Response examples provided                                    |       |
| Error codes and their meanings defined                                |       |

### 8C. Architecture Decisions (/4)

| Check                                                             | Pass? |
| ----------------------------------------------------------------- | ----- |
| Tech stack or pattern choices are documented (via ADRs or README) |       |
| Folder structure reasoning is documented                          |       |
| Known limitations and trade-offs are acknowledged                 |       |
