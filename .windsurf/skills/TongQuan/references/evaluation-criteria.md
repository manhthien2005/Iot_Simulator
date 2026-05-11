# Evaluation Criteria Reference

## 📐 ARCHITECTURE CHECKLIST (Criterion #2 — Details)

### 2A. Clean Architecture & Layers (/8)

| Check | Pass? | Notes |
|-------|-------|-------|
| **Separation of Concerns** — Controller ≠ Service ≠ Repository/Model | | |
| **Dependency Direction** — Outer layers depend on inner ones, NOT vice versa | | |
| **Business logic decoupled from framework** — Logic is not inside controllers/routes | | |
| **Database queries** are not directly inside controllers | | |

### 2B. Folder Structure & Organization (/6)

| Check | Pass? | Notes |
|-------|-------|-------|
| Folder structure accurately reflects the modules in the SRS | | |
| Each module has clear boundaries (routes, controllers, services, models) | | |
| No "god folders" containing everything (e.g., all controllers in 1 folder) | | |

### 2C. Design Patterns (/6)

| Check | Pass? | Notes |
|-------|-------|-------|
| **Repository Pattern** — Data access layer is decoupled | | |
| **Middleware Pattern** — Auth, validation, error handling via middlewares | | |
| **Service Pattern** — Business logic is encapsulated in services | | |
| **Dependency Injection** (or proper module imports) is utilized | | |

## 🧹 CODE QUALITY CHECKLIST (Criterion #5 — Details)

### 5A. SOLID Principles (/5)

| Principle | Check | Pass? |
|-----------|-------|-------|
| **S** — Single Responsibility | Each file/class/function has only 1 responsibility? | |
| **O** — Open/Closed | Can be extended without modifying existing code? | |
| **L** — Liskov Substitution | Subclasses can replace parent classes? | |
| **I** — Interface Segregation | Clients are not forced to depend on unused interfaces? | |
| **D** — Dependency Inversion | Depend on abstractions, not concretions? | |

### 5B. Clean Code (/5)

| Check | Pass? |
|-------|-------|
| Short functions (recommended ≤ 50 lines, max 80 lines) | |
| Short files (recommended ≤ 200 lines) | |
| Max 3 nesting levels (no deep nesting) | |
| Use **early returns** instead of nested if-else statements | |
| No duplicate code (DRY principle) | |

### 5C. Anti-patterns Detection (/5)

| Anti-pattern | Detected? | Description |
|--------------|-----------|-------------|
| **Generic naming** — `utils.js`, `helpers.js`, `common.js` with mixed functions | | |
| **God Object** — 1 class/file handling too many responsibilities | | |
| **Tight Coupling** — Modules are highly dependent on each other | | |
| **NIH Syndrome** — Rewriting what existing good libraries can do | | |
| **Magic Numbers/Strings** — Hardcoded values without using constants | | |

## 🔒 SECURITY CHECKLIST (Criterion #6 — Details)

### 6A. Authentication & Authorization (/4)

| Check | Pass? |
|-------|-------|
| Correct JWT implementation (secret, expiry, refresh token) | |
| Password hashing (bcrypt/argon2, NO md5/sha1) | |
| Role-based Access Control (RBAC) implemented | |
| Protected routes have auth guard middlewares | |

### 6B. Input & API Security (/3)

| Check | Pass? |
|-------|-------|
| Input validation on both client AND server | |
| SQL injection prevention (parameterized queries / ORM) | |
| Rate limiting on sensitive API endpoints (login, register, OTP) | |

### 6C. Configuration Security (/3)

| Check | Pass? |
|-------|-------|
| Secrets in `.env` (NOT hardcoded in source) | |
| `.env` is included in `.gitignore` | |
| CORS is configured correctly (no wildcard `*` in production) | |
