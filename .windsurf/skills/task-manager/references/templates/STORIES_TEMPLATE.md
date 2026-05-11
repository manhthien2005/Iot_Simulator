# Stories Template

Use this exact format when creating `STORIES.md` files.

```markdown
# {EpicCode}-{EpicName} — Stories

## S{NN}: [{Component}] {Story Title Vietnamese}
- **Assignee:** {Role} | **SP:** {N} | **Priority:** {Level} | **Component:** {Component}
- **Labels:** {Label1}, {Label2}, Sprint-{N}

**Description:** {Concise technical description in Vietnamese. Include API endpoints, key behaviors, and constraints.}

**Acceptance Criteria:**
- [ ] {Testable criterion 1}
- [ ] {Testable criterion 2}
- [ ] {Testable criterion 3}

---
```

## Rules

### Story Numbering
- Sequential within the Epic: S01, S02, S03...
- Pad to 2 digits

### Component Tags
- `[Admin BE]` — Admin backend API
- `[Admin FE]` — Admin frontend React
- `[Mobile BE]` — Mobile backend API
- `[Mobile FE]` — Mobile frontend Flutter
- `[QA]` — Testing
- `[Infra]` — Infrastructure, DevOps
- `[Fullstack]` — Cross-layer work

### Story Structure Pattern
For each UC, generate stories in this order:
1. **Backend API story** (Component: {platform}-BE)
2. **Frontend UI story** (Component: {platform}-FE)
3. **QA test story** (Component: QA)

### Acceptance Criteria
- Each criterion MUST be a checkbox `- [ ]`
- Each criterion MUST be independently testable
- Minimum 3 criteria per story
- Include both positive and negative cases where relevant
- Use specific values (e.g., "JWT hạn 8h" not "JWT có hạn")

### Priority Levels
- **Highest** — Blockers, critical infrastructure
- **High** — Core business features
- **Medium** — Important supplementary
- **Low** — Nice-to-have

### Labels Convention
- Platform: `Backend`, `Frontend`, `Mobile`
- Module: `Auth`, `Device`, `Monitoring`, `Emergency`, etc.
- Sprint: `Sprint-{N}`
- Special: `Test`, `Infra`, `Security`

## Example (from EP04-Login)

```markdown
# EP04-Login — Stories

## S01: [Admin BE] API Đăng nhập cho Web Dashboard
- **Assignee:** Admin BE Dev | **SP:** 2 | **Priority:** Highest | **Component:** Admin-BE
- **Labels:** Backend, Auth, Sprint-1

**Description:** POST /api/auth/login. Xác thực bcrypt. JWT iss=healthguard-admin role=ADMIN hạn=8h. Rate limit 5 lần/15 phút. Kiểm tra is_active. Cập nhật last_login_at. Ghi audit log.

**Acceptance Criteria:**
- [ ] POST /api/auth/login hoạt động
- [ ] JWT token iss=healthguard-admin, role=ADMIN, hạn=8h
- [ ] Rate limit 5 lần/15 phút
- [ ] Kiểm tra is_active trước khi cho login
- [ ] Cập nhật last_login_at
- [ ] Ghi audit log

---

## S02: [Mobile BE] API Đăng nhập + Refresh Token
- **Assignee:** Mobile BE Dev | **SP:** 3 | **Priority:** Highest | **Component:** Mobile-BE
- **Labels:** Backend, Auth, Sprint-1

**Description:** POST /api/auth/login. Xác thực bcrypt. JWT iss=healthguard-mobile roles=PATIENT/CAREGIVER hạn=30 ngày. Cơ chế refresh token. Rate limit 5 lần/15 phút. Ghi audit log.

**Acceptance Criteria:**
- [ ] POST /api/auth/login hoạt động
- [ ] JWT iss=healthguard-mobile, roles=PATIENT/CAREGIVER, hạn=30 ngày
- [ ] Refresh token mechanism
- [ ] Rate limit 5 lần/15 phút
- [ ] Ghi audit log
```
