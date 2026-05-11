# Summary Template — Token-Optimized Standard

> This template is the MANDATORY format for all summary files in `summaries/`.
> Goal: ~60% token reduction vs old format, keeping only what AI needs most.
> Old summary files MUST be overwritten with this new format.

---

## Standard Format

```markdown
# {MODULE_NAME} ({PROJECT: Admin/Mobile})

> Sprint {N} | JIRA: {Epic Names} | UC: {UC_IDs}

## Purpose & Technique
- [1-3 bullet points: what the module does, core techniques used]

## API Index
| Endpoint | Method       | Note              |
| -------- | ------------ | ----------------- |
| /api/... | POST/GET/... | Short description |

## File Index
| Path                  | Role                |
| --------------------- | ------------------- |
| relative/path/to/file | Role (LOC if known) |

## Known Issues
- 🔴 Critical issues
- 🟡 Warnings
(Omit this section entirely if no issues exist)

## Cross-References
| Type           | Ref                          |
| -------------- | ---------------------------- |
| DB Tables      | table1, table2               |
| UC Files       | BA/UC/.../UCxxx              |
| Related Module | REVIEW_{OTHER}/summaries/... |

## Review
| Date       | Score  | Detail              |
| ---------- | ------ | ------------------- |
| yyyy-mm-dd | XX/100 | link_to_review_file |
(Omit this section entirely if not yet reviewed)
```

---

## Rules

1. **NO Trello Checklists** — AI queries JIRA Index when task details are needed
2. **NO verbose SRS extraction** — summarize in 2-3 bullets under "Purpose & Technique"
3. **NO emoji in headers** — saves characters
4. **NO empty sections** — omit entirely if no data
5. **API Index must be compact** — 1 line per endpoint, no response schemas
6. **File Index must include LOC** — helps AI estimate complexity
7. **JIRA Epic Names must be exact** — copy from JIRA Index (e.g., `EP04-Login`)
8. **OVERWRITE old summary files** — do not create new versions or backups
