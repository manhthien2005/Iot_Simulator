# Architecture Standards Reference

> Consolidated from 5 sub-skills: architect-review, software-architecture, backend-architect,
> architecture-patterns, architecture-decision-records.
> Read this file at Step 3 (Code Evaluation) for architecture assessment criteria.

---

## Clean Architecture Layers

The expected layer separation:

```
Route → Controller → Service → Repository/Model
```

| Layer                | Responsibility                              | MUST NOT                                 |
| -------------------- | ------------------------------------------- | ---------------------------------------- |
| **Route**            | URL mapping, middleware binding             | Contain business logic                   |
| **Controller**       | Parse request/response, HTTP status codes   | Access DB directly, contain domain logic |
| **Service**          | Business logic, domain rules, orchestration | Access request/response objects          |
| **Repository/Model** | Data access, queries, ORM                   | Contain business logic                   |

**Dependency direction:** Controller → Service → Repository (NEVER inverted)

---

## Design Patterns to Check

| Pattern             | What to look for                       | Red flag if missing                   |
| ------------------- | -------------------------------------- | ------------------------------------- |
| **Middleware**      | Auth guard, validation, error handler  | Security holes, duplicated validation |
| **Repository**      | Data access abstraction                | DB queries scattered in controllers   |
| **DTO/Schema**      | Request/Response data transfer objects | Tight coupling to DB models           |
| **Factory/Builder** | Object creation for complex entities   | Constructor with 10+ parameters       |
| **Strategy**        | Multiple logic variations              | Giant if/else or switch blocks        |

---

## Code Quality Standards

### SOLID Principles
- **S** — Single Responsibility: Each function/class/file = 1 clear purpose
- **O** — Open/Closed: New features addable without modifying existing code
- **D** — Dependency Inversion: Depend on abstractions, not concretions

### Clean Code Metrics

| Metric          | Target                   | Hard Limit    |
| --------------- | ------------------------ | ------------- |
| Function length | ≤ 50 lines               | max 80 lines  |
| File length     | ≤ 200 lines              | max 300 lines |
| Nesting depth   | ≤ 3 levels               | max 4 levels  |
| Early return    | Used over nested if-else | —             |

### Anti-patterns to Flag

| Anti-pattern            | Signal                                      |
| ----------------------- | ------------------------------------------- |
| **God Object/Function** | 1 function doing too many things            |
| **Generic naming**      | `utils.js`, `helpers.js`, `common.js`       |
| **Copy-paste code**     | Logic duplicated in ≥ 2 places              |
| **Magic values**        | Hardcoded numbers/strings without constants |
| **NIH Syndrome**        | Building what libraries already provide     |

---

## API Design Standards

### RESTful Conventions
- HTTP methods: GET=read, POST=create, PUT/PATCH=update, DELETE=delete
- Status codes: 200, 201, 400, 401, 403, 404, 500
- URL naming: plural nouns, no verbs (`/api/v1/users`)
- Consistent paths: `/api/v1/resource`

### Error Response Format
```json
{
  "status": 400,
  "message": "Validation failed",
  "errors": [
    { "field": "email", "message": "Invalid email format" }
  ]
}
```
- Unified structure (`{status, message, errors}`)
- Field-level validation details
- NO internal stack traces leaked to client

### Data Contract
- Clear Request/Response schemas
- Pagination pattern for list endpoints (cursor/offset)
- Consistent date format (ISO 8601)

---

## Security Checklist

### Authentication & Authorization
- JWT validated (signature, expiry, issuer)
- Refresh token flow (if applicable)
- Route-level authorization
- Passwords hashed: bcrypt/argon2, NO md5/sha1/plaintext

### Input Security
- Server-side validation AND sanitization
- SQL injection prevention (parameterized queries / ORM)
- XSS prevention (output encoding)
- File upload validation (type, size, content)

### Rate Limiting & Abuse Prevention
- Rate limiting on login/register/OTP
- Brute force protection (lockout / delay)
- CORS configured (specific origins, no wildcard)
- Secrets in `.env`, NEVER hardcoded

---

## Architecture Decision Records (ADRs)

When reviewing Documentation criterion, check for:
- Tech stack choices documented (via ADRs or README)
- Folder structure reasoning documented
- Known limitations and trade-offs acknowledged

**ADR Template (Lightweight):**
```markdown
# ADR-NNNN: [Title]
**Status**: Accepted | **Date**: YYYY-MM-DD
## Context: [Why we needed to decide]
## Decision: [What we chose]
## Consequences: [What happens as a result — positive AND negative]
```

---

## Source Skills

For deep-dive reference, the original sub-skills are available at:
- `skills/architect-review/SKILL.md` — Architecture review methodology
- `skills/software-architecture/SKILL.md` — Code style & DDD principles
- `skills/backend-architect/SKILL.md` — API design & microservices patterns
- `skills/architecture-patterns/SKILL.md` — Clean/Hexagonal/DDD patterns
- `skills/architecture-decision-records/SKILL.md` — ADR templates & process
