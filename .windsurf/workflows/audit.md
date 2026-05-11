---
description: Audit a module's current state — code health, test coverage, cross-repo integration, debt — before refactoring or completing.
---

# /audit — Module Health Audit

> "Trước khi sửa, biết rõ đang ở đâu."

Workflow này dành cho mục tiêu **đi lại từng module** của hệ thống VSmartwatch, đánh giá hiện trạng để có roadmap hoàn thiện.

## Khi nào dùng

- Bắt đầu work trên 1 module mà anh đã code lâu không động đến
- Trước khi refactor lớn
- Để báo cáo tiến độ (capstone defense, sprint review)
- Sau khi merge nhiều branch, muốn kiểm tra ride-along damage

## Pre-flight

1. **Identify module + scope:** module nào, ở repo nào (có thể cross-repo).
2. **Branch:** `chore/audit-<module>` từ trunk. Read-only mode default, không sửa code.
3. **Read `topology.md`** để biết module này chạm repo nào.

## Phase 1 — Spec coverage

**Goal:** Module này được spec đúng chưa?

1. **Locate UC** trong `PM_REVIEW/Resources/UC/{Module}/`. List UCs.
2. **Match UC → code:**
   - Main flow steps → handler/method tồn tại?
   - Alt flows → có xử lý error case không?
   - Business Rules → có validator không?
   - NFR → có rate limit/auth/perf check không?
3. **Match UC → JIRA Story** trong `PM_REVIEW/Resources/TASK/JIRA/`. Story chưa done?
4. **Cross-check với SQL schema** trong `PM_REVIEW/SQL SCRIPTS/`. Field UC mention có trong DB không?

Optionally invoke skill `UC_AUDIT` cho full corpus check.

**Output:** Spec coverage table:

```markdown
| UC | Main Flow | Alt Flows | BR | NFR | JIRA Story | Status |
|----|-----------|-----------|-----|-----|------------|--------|
| UC001 | 3/3 ✅ | 2/3 ⚠️ | 5/5 ✅ | Rate limit ❌ | VS-001 ✅ | 80% |
```

## Phase 2 — Code health

**Per repo touched bởi module:**

### Stack-agnostic

1. **File inventory:** list source files trong module folder. Note LOC, last modified.
2. **Dead code:** function/class không được import từ đâu (`grep -r "<name>"`)
3. **TODO/FIXME audit:** `grep -rn "TODO\|FIXME\|XXX" <module>/`
4. **Naming consistency:** match convention?
5. **Magic numbers/strings:** hardcode mà nên const?

### Per-stack

**Flutter (`health_system/lib/features/<module>`):**
- `flutter analyze` — bao nhiêu warning?
- Riverpod usage consistent?
- Widget tree depth (deep = re-render hell)
- `print()` còn sót không?

**FastAPI BE:**
- `mypy` errors
- `pytest --collect-only tests/test_<module>.py` — tests có chạy không?
- Endpoint contract match Pydantic schema?
- Service layer có business logic hay leak qua router?

**Express BE:**
- `npm run lint` errors
- Prisma query có `select` explicit không?
- Auth middleware có gắn đủ endpoint không?

**Vite/React FE:**
- `npm run lint` errors
- Component prop validation
- WebSocket subscription cleanup
- localStorage chứa sensitive data?

## Phase 3 — Test coverage

1. **List test files** cho module: `test/features/<module>/`, `__tests__/<module>/`, `tests/test_<module>*.py`.
2. **Run tests scoped:**
   - Flutter: `flutter test test/features/<module>/`
   - Node: `npm test -- <module>`
   - Python: `pytest tests/test_<module>*.py`
3. **Coverage:** `--coverage` flag nếu stack hỗ trợ.
4. **Identify gaps:**
   - Main flow có test happy path không?
   - Alt flow có test edge case không?
   - Boundary value (min/max input) có test không?
   - Security (auth bypass, injection) có test không?

Optionally invoke skill `TEST_CASE_GEN` (mode GENERATE) để bổ sung test cases.

**Output:** Test coverage table:

```markdown
| Feature | Happy | Edge | Boundary | Security | Coverage |
|---------|-------|------|----------|----------|----------|
| Login   | ✅    | ⚠️   | ❌       | ❌       | 45%      |
```

## Phase 4 — Cross-repo integration

**Per topology.md:**
1. **List endpoint** module gọi sang repo khác.
2. **Verify contract:** mobile call mobile-BE endpoint nào? BE gọi model-API endpoint nào?
3. **E2E test status:** có smoke test trong `Iot_Simulator_clean/scripts/e2e_*.ps1` không?
4. **Recent breaking change:** `git log --since="1 month ago"` trên endpoint file.

## Phase 5 — Security audit

Per `40-security-guardrails.md`:
- Hardcode secret/credential?
- SQL injection vector?
- Missing auth middleware?
- PHI logging?
- CORS `*` trong production config?

Invoke skill `detailed-feature-review` cho Security criterion (12 points) nếu muốn formal score.

## Phase 6 — Debt log

Compile list of issues found theo severity:

```markdown
## Tech Debt — <Module>

### 🔴 Critical (block release)
- [ ] Missing auth on POST /api/admin/devices (src/routes/devices.js:12)
- [ ] SQL injection in deviceController.list (src/controllers/deviceController.js:45)

### 🟡 High (fix in next sprint)
- [ ] Alt flow AF3 not implemented (UC001)
- [ ] No regression test for password reset

### 🟢 Medium/Low (track)
- [ ] God function authService.login() (85 lines)
- [ ] TODO comments x12
```

## Phase 7 — Output report

Save audit report:

```
PM_REVIEW/Task/Audit_<Module>_<YYYY-MM-DD>.md
```

Format:

```markdown
# Audit: <Module> — <Date>

## Summary
- Spec coverage: X/Y UCs implemented
- Code health: <flutter analyze errors>, <LOC>, <TODO count>
- Test coverage: X%
- Cross-repo integration: <status>
- Security issues: <count>

## Findings
<Tables from Phase 1-5>

## Tech Debt
<List from Phase 6>

## Recommended Plan
1. [P0] <Critical item> — est. <SP>
2. [P1] <High item> — est. <SP>
3. [P2] <Medium item> — est. <SP>

## Next Step
Run `/plan <module>-stabilization` to break tech debt into tasks.
```

## Phase 8 — Commit + handoff

```pwsh
git add PM_REVIEW/Task/Audit_<Module>_*.md
git commit -m "docs(audit): module <module> health audit"
```

Notify anh:

> "Audit xong. Report tại `PM_REVIEW/Task/Audit_<Module>_<date>.md`. Found X critical, Y high, Z medium issues. Want me to start `/plan` cho phần stabilization?"

## Anti-patterns

- ❌ Fix code trong khi audit — sai workflow. Audit chỉ là read + analyze.
- ❌ Skip Phase 1 (spec coverage) — code có thể "đúng kỹ thuật" nhưng sai requirement.
- ❌ "While I'm here" refactor — không, đợi `/plan` rồi `/build`.

## Output checklist

- ✅ Spec coverage table
- ✅ Code health per stack
- ✅ Test coverage table
- ✅ Cross-repo dependency list
- ✅ Security audit checklist
- ✅ Prioritized tech debt list
- ✅ Audit report committed to PM_REVIEW

## Next step

Sau audit → `/plan <module>-stabilization` để break tech debt thành executable tasks → `/build` task-by-task với TDD.
