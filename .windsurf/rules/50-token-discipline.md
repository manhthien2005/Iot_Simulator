---
trigger: model_decision
description: Context efficiency guidelines - read smart not greedy, batch tool calls, prefer diffs over full files. Apply when exploring large codebases, doing multi-step searches, or when context is getting heavy.
---

# Token Discipline

Be efficient with the user's context window. Long sessions and big diffs eat tokens fast.

## Read smart, not greedy

- **Search before reading.** Use `grep` / `code_search` / `find_by_name` để locate symbol trước khi mở file. 30-line read beats a 1500-line read.
- **Read with offset + limit** khi chỉ cần một region. Không đọc 1000 lines nếu chỉ cần lines 200-260.
- **Don't re-read** file đã shown trong conversation trừ khi nó đã được edit.
- **Don't list whole large directories.** Filter theo extension, name pattern, hoặc path scope.

## Output smart, not chatty

- No filler ("Sure!", "Great question!", "Let me start by ...").
- No restating what anh just said.
- No re-summarizing what em just did ở turn trước.
- Code blocks **chỉ khi** code là part của answer hoặc snippet anh cần action. Không echo lại file vừa edit.
- **Diffs > full files.** Khi show changes, chỉ show changed lines + context.

## Tool calls

- Batch independent reads + searches **song song** khi không có dependency.
- Don't open same tool twice với args tương tự — fold thành 1 call.
- Prefer `code_search` (subagent) over many `grep` rounds cho exploratory questions.

## Plans, todos, progress notes

- Keep todo list short — checkbox, không paragraph.
- Don't auto-create progress notes trừ khi chúng save next-session time. Plan file trong `docs/plans/` đã có detail.
- Don't paste same paragraph trong 3 nơi (rules, AGENTS.md, spec). Pick one home.

## Long-running shell output

Common noisy commands và quieter equivalents:

| Noisy | Quieter |
|---|---|
| `git status` | `git status --short` |
| `git log` | `git log -n 10 --oneline` |
| `git diff` | `git diff --stat` rồi `git diff <file>` nếu cần |
| `flutter test` (full) | `flutter test test/<feature>/` trước |
| `npm test` (full) | `npm test -- <file>` trước |
| `pytest` (full) | `pytest tests/<file>::<test>` trước |
| `find` / `ls -R` | `find_by_name` tool với extension filter |

## Khi in doubt

Nếu single response sẽ rất dài, hỏi anh muốn:

- Short summary giờ + details on demand, hoặc
- Full long version.

Don't dump 2000 lines code/output "phòng khi cần".
