# Sprint Template

Use this exact format when creating `_SPRINT.md` files.

```markdown
# Sprint {N} — {Theme Vietnamese}

Duration: 2 weeks | Total SP: ~{total} | Epics: {count}

## Progress

- [ ] {EpicCode}-{EpicName} — {UC Ref} {Short Description} ({SP} SP)
- [ ] {EpicCode}-{EpicName} — {UC Ref} {Short Description} ({SP} SP)
```

## Rules

- Theme must be concise and descriptive (Vietnamese)
- Each Epic listed as a checkbox item for progress tracking
- SP totals should be approximate (~)
- List Epics in order of priority (Highest → Low)
- Include UC references where applicable
- Infrastructure Epics (no UC) use `—` for UC Ref

## Example (from Sprint 1)

```markdown
# Sprint 1 — Nền tảng & Xác thực

Duration: 2 weeks | Total SP: ~42 | Epics: 6

## Progress

- [ ] EP01-Database — Thiết lập Database & TimescaleDB (6 SP)
- [ ] EP02-AdminBE — Khởi tạo Admin Backend (3 SP)
- [ ] EP03-MobileBE — Khởi tạo Mobile Backend (3 SP)
- [ ] EP04-Login — UC001 Đăng Nhập (11 SP)
- [ ] EP05-Register — UC002 Đăng Ký (9 SP)
- [ ] EP12-Password — UC003/UC004 Mật Khẩu (10 SP)
```
