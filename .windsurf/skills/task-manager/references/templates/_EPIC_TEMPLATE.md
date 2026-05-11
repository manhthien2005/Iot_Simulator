# Epic Template

Use this exact format when creating `_EPIC.md` files.

```markdown
# {EpicCode}-{EpicName} | Sprint {N} | {Priority}

{One-line Vietnamese description of the Epic scope and key deliverables.}

- Stories: {count} | SP: {total} | UCs: {UC list or "—"}
```

## Rules

- Header format: `# {Code}-{Name} | Sprint {N} | {Priority}`
- Priority from: Highest, High, Medium, Low
- Description is ONE concise sentence in Vietnamese
- Stats line: Stories count, total SP, and associated UC codes
- If no UC (infra Epic), use `—` for UCs

## Example (from EP04-Login)

```markdown
# EP04-Login | Sprint 1 | Highest

Người dùng đăng nhập bằng email/password nhận JWT token. Tách riêng Admin login (Node.js) và Mobile login (FastAPI).

- Stories: 5 | SP: 11 | UCs: UC001
```
