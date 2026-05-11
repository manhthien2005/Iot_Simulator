# Software Design Description (SDD)

## 1. Document Information
- **Project:** [Tên dự án]
- **System / Service:** [Tên hệ thống hoặc service]
- **Version:** [v0.1]
- **Status:** [Draft / Review / Approved]
- **Date:** [YYYY-MM-DD]
- **Author(s):** [Tên]
- **Reviewer(s):** [Tên]
- **Related Docs:** [SRS / PRD / API spec / ADR link]

---

## 2. Purpose and Scope

### 2.1 Purpose
Tài liệu này mô tả thiết kế của `[Tên hệ thống/service]` để team dev, QA, và người maintain có cùng cách hiểu trước khi implement.

### 2.2 Scope
- **In scope:**
  - [Chức năng / module 1]
  - [Chức năng / module 2]

- **Out of scope:**
  - [Không bao gồm phần nào]

### 2.3 Context
Hệ thống này nằm trong bối cảnh nào:
- Ai sử dụng?
- Kết nối với hệ thống nào?
- Phụ thuộc bên ngoài nào quan trọng?

---

## 3. Stakeholders and Design Concerns

| Stakeholder           | Concern                            | Priority |
| --------------------- | ---------------------------------- | -------- |
| Backend Dev           | Code dễ maintain, dễ test          | High     |
| Frontend / Mobile Dev | API rõ ràng, response ổn định      | High     |
| QA                    | Flow rõ ràng để test integration   | High     |
| DevOps                | Deploy đơn giản, có log/monitoring | Medium   |
| Product Owner         | Dễ mở rộng tính năng               | Medium   |

---

## 4. Design Summary

### 4.1 Architecture Style
- [Monolith / Modular monolith / Microservice / Serverless]

### 4.2 Tech Stack
- **Backend:** [FastAPI / Node.js / ...]
- **Database:** [PostgreSQL / MySQL / MongoDB]
- **Cache:** [Redis / None]
- **Messaging:** [RabbitMQ / Kafka / None]
- **Deployment:** [Docker / Heroku / AWS / VPS]

### 4.3 Key Design Decisions
- [Decision 1]
- [Decision 2]
- [Decision 3]

---

## 5. Architecture View

### 5.1 System Components

| Component    | Responsibility             |
| ------------ | -------------------------- |
| API Gateway  | Routing, auth, rate limit  |
| Auth Service | Đăng nhập, phát token      |
| User Service | Quản lý user               |
| Admin Web    | Quản trị hệ thống          |
| Mobile App   | Client cho người dùng cuối |

### 5.2 High-Level Diagram

```text
[Mobile App] ----\
                  --> [API Gateway] --> [Backend Service] --> [Database]
[Admin Web] -----/
```

### 5.3 External Integrations

| External System | Purpose           | Protocol |
| --------------- | ----------------- | -------- |
| [Firebase]      | Push notification | HTTP     |
| [Email Service] | Gửi email         | REST API |

---

## 6. Module / Component Design

### 6.1 Main Modules

#### Module: [Tên module]
- **Purpose:** [Mục đích]
- **Responsibilities:**
  - [Trách nhiệm 1]
  - [Trách nhiệm 2]
- **Inputs:** [Nhận gì]
- **Outputs:** [Trả gì]
- **Dependencies:** [Phụ thuộc gì]

#### Module: [Tên module]
- **Purpose:** [Mục đích]
- **Responsibilities:**
  - [Trách nhiệm 1]
  - [Trách nhiệm 2]
- **Inputs:** [Nhận gì]
- **Outputs:** [Trả gì]
- **Dependencies:** [Phụ thuộc gì]

---

## 7. Data Design

### 7.1 Main Entities

| Entity   | Description         | Important Fields        |
| -------- | ------------------- | ----------------------- |
| users    | Người dùng hệ thống | id, email, status       |
| devices  | Thiết bị của user   | id, user_id, serial_no  |
| sessions | Phiên đăng nhập     | id, user_id, expires_at |

### 7.2 Relationships
- Một `user` có nhiều `devices`
- Một `user` có nhiều `sessions`

### 7.3 Data Rules
- Soft delete hay hard delete: [Chọn]
- Audit fields: [created_at, updated_at, ...]
- Sensitive data: [hash / encrypt trường nào]

---

## 8. Interface Design

### 8.1 Public APIs

| Endpoint             | Method | Description          | Auth |
| -------------------- | ------ | -------------------- | ---- |
| `/api/v1/auth/login` | POST   | Đăng nhập            | No   |
| `/api/v1/users/me`   | GET    | Lấy profile hiện tại | Yes  |
| `/api/v1/devices`    | GET    | Danh sách thiết bị   | Yes  |

### 8.2 Request / Response Rules

Response format chuẩn:

```json
{
  "success": true,
  "data": {},
  "message": ""
}
```

Error format chuẩn:

```json
{
  "success": false,
  "error_code": "USER_404",
  "message": "User not found"
}
```

### 8.3 Internal Interfaces

| Provider     | Consumer    | Contract             |
| ------------ | ----------- | -------------------- |
| Auth Service | API Gateway | Verify token         |
| User Service | Admin Web   | User management APIs |

---

## 9. Key Interaction Flows

### 9.1 Login Flow
1. User gửi email/password
2. API Gateway forward request tới Auth Service
3. Auth Service validate credentials
4. Auth Service tạo access token
5. Trả token về client

### 9.2 Example Sequence

```text
Client -> API Gateway -> Auth Service -> Database
Client <- API Gateway <- Auth Service <- Database
```

### 9.3 Other Important Flows
- [User registration]
- [Refresh token]
- [Create order / create device / submit form]
- [Admin update data]

---

## 10. Non-Functional Design

### 10.1 Security
- Authentication: [JWT / Session / OAuth2]
- Authorization: [RBAC / simple role check]
- HTTPS: [Required / Not required in dev]
- Rate limiting: [Có / Không]

### 10.2 Performance
- Target latency: [vd. P95 < 300ms]
- Peak load assumption: [vd. 100 req/s]
- Cache strategy: [Có / Không]

### 10.3 Reliability / Operations
- Logging: [structured logs]
- Monitoring: [Sentry / Grafana / none]
- Backup: [daily / weekly / none]
- Retry policy: [nếu có]

---

## 11. Constraints and Assumptions

### 11.1 Constraints
- [Phải chạy trên Heroku]
- [Dùng PostgreSQL có sẵn]
- [Không dùng thêm message queue ở phase 1]

### 11.2 Assumptions
- [Số lượng user ban đầu nhỏ]
- [Mobile app dùng JWT]
- [Admin traffic thấp]

---

## 12. Design Rationale

| Decision         | Why                    | Alternative Considered   |
| ---------------- | ---------------------- | ------------------------ |
| Dùng API Gateway | Tập trung auth/routing | Client gọi thẳng service |
| Dùng FastAPI     | Code nhanh, async tốt  | Django / Express         |
| Dùng PostgreSQL  | Quan hệ dữ liệu rõ     | MongoDB                  |

---

## 13. Risks / Open Issues

| Issue / Risk                   | Impact | Mitigation / Next Step |
| ------------------------------ | ------ | ---------------------- |
| Chưa rõ auth đa thiết bị       | Medium | Làm rõ ở phase API     |
| Có thể bottleneck ở gateway    | Medium | Theo dõi metrics       |
| Chưa có retry cho external API | Low    | Bổ sung nếu cần        |

---

## 14. Change History

| Version | Date         | Author | Changes       |
| ------- | ------------ | ------ | ------------- |
| 0.1     | [YYYY-MM-DD] | [Tên]  | Initial draft |