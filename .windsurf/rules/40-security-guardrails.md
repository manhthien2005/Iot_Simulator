---
trigger: always_on
---

# Security Guardrails

Hệ thống VSmartwatch xử lý **dữ liệu sức khỏe** + **PII** + **emergency contact info**. Leak = nghiêm trọng.

## Secrets handling

- **NEVER hardcode** API key, password, JWT secret, DB credential trong source.
- **Use `.env` + load via dotenv** (Node) / `pydantic-settings` (Python) / `flutter_dotenv` (mobile).
- **`.env.example` checked-in**, `.env*` (actual) **gitignored**.
- Pre-write hook `protect_secrets.py` scan file mới — nếu phát hiện pattern giống secret, em sẽ stop và hỏi anh.

## Authentication

- **JWT** cho mobile + admin. Khác `iss` (`healthguard-mobile`, `healthguard-admin`).
- **Refresh token rotation** — đừng cấp access token long-lived (> 1h là bad).
- **Internal service-to-service:** dùng `X-Internal-Secret` header với secret riêng. Khác với user JWT.
- **Account lockout** sau N lần fail (theo UC001 — verify trong PM_REVIEW).

## Authorization

- **Role-based:** user / admin / clinician. Linked profiles cho family share.
- **Mọi endpoint** phải có middleware check auth + role. Mặc định: deny.
- **Resource ownership check** — user A không xem được data của user B (trừ khi linked).

## Input validation

- **Validate ở boundary** (controller/router) trước khi pass vào service.
- **Use schema validator** (zod cho Node, pydantic cho Python, custom validator cho Dart).
- **SQL Injection:** dùng ORM/parameterized query. Cấm string concat SQL.
- **XSS:** escape output ở admin web. React mặc định escape, nhưng `dangerouslySetInnerHTML` = cấm.

## Output sanitization

- **API error response:** không expose stack trace / internal error tới client.
  - Reference: `healthguard-model-api/app/routers/` đã sanitize 500 errors — keep pattern này.
- **Log sensitive data:** không log password/token/health vitals raw. Dùng mask (`***`).

## CORS

- **Explicit allowlist origin.** Cấm `*` trong production.
- Admin BE đã có CORS config — verify trong `HealthGuard/backend/src/`.

## Rate limiting

- **Auth endpoint** (login, register, forgot-password): tightest rate limit.
- **Public endpoint** (vitals submit từ smartwatch): moderate.
- **Internal endpoint:** trust internal secret + IP allowlist nếu deploy production.

## Data minimization

- **Mobile app** chỉ lưu data cần thiết. Không cache health history dài hạn trong local DB.
- **Admin dashboard** queries: chỉ select column cần thiết, không `SELECT *`.

## Personal Health Information (PHI) — đặc thù

- **Encrypt at rest:** Postgres `pgcrypto` hoặc app-layer cho field nhạy cảm.
- **Encrypt in transit:** HTTPS mandatory production. Dev local có thể HTTP.
- **Audit log:** mọi access PHI phải log (user_id, action, timestamp). Xem `PM_REVIEW/Audit_Log_Specification.md`.

## Khi anh request "skip auth tạm thời"

Em sẽ push back:
- Auth bypass trong code = vulnerability vĩnh viễn (anh sẽ quên gỡ).
- Better: env flag `DEV_BYPASS_AUTH=true` chỉ load trong development environment + log warning loud.

## Dependency security

- **`npm audit` / `pip-audit`** trước khi merge feature có thêm dep.
- **Pin versions** — không dùng `^` cho production dep.
- **Update lockfile** cùng commit nào thêm dep.

## Things em SẼ flag tự động

Khi em đọc/viết code mà phát hiện những thứ này, em sẽ stop và báo anh:
- `eval()`, `exec()` với user input
- SQL string concat
- `dangerouslySetInnerHTML` với user input
- Password trong plaintext bất kỳ đâu
- CORS `*` trong production config
- Disabled SSL verification (`verify=False`, `rejectUnauthorized: false`)
- `localStorage` lưu token nhạy cảm (XSS risk — dùng httpOnly cookie thay)
