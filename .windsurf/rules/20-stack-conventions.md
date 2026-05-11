---
trigger: model_decision
description: Branch naming, commit message format (Conventional Commits), versioning, and migration discipline. Apply when creating branches, writing commit messages, opening PRs, or running migrations.
---

# Stack Conventions — Branching, Commits, Versioning

Universal conventions cho 5 repo. Stack-specific rules ở overlay (21-25).

## Branch naming

**Format:** `<type>/<short-desc>`

- `feat/<desc>` — feature mới (ví dụ: `feat/fall-detection-survey`)
- `fix/<desc>` — bug fix (ví dụ: `fix/sos-countdown-timer`)
- `chore/<desc>` — infra, config, hygiene (ví dụ: `chore/workspace-hygiene`, `chore/update-deps`)
- `refactor/<desc>` — refactor không thay đổi behavior
- `docs/<desc>` — chỉ thay đổi docs

**Cấm:**
- Branch tên không có type prefix (`fix-bug`, `new-feature`)
- Tên Việt-có-dấu hoặc viết hoa lung tung
- Branch name > 50 ký tự

**Trunk per repo:** xem `10-project-context.md`.

## Commit message — Conventional Commits

**Format:** `<type>(<scope>): <subject in Vietnamese>`

- **type**: `feat`, `fix`, `chore`, `refactor`, `docs`, `test`, `style`, `perf`, `build`, `ci`
- **scope** (optional): module name viết tắt, ví dụ `auth`, `fall`, `sleep`, `device`
- **subject**: tiếng Việt, không dấu chấm cuối, viết thường

### Ví dụ tốt

```
feat(fall): thêm full-screen alert khi phát hiện ngã
fix(sos): countdown reset khi user nhấn cancel
chore: dọn dẹp file rác AI tooling
refactor(risk): tách model loading ra service riêng
docs(uc): cập nhật UC010 với alt flow cho mất mạng
```

### Body (khi non-trivial)

Giải thích **WHY** (lý do), không phải **WHAT** (diff đã thấy):

```
fix(sos): countdown reset khi user nhấn cancel

Trước: nhấn cancel chỉ ẩn dialog nhưng timer vẫn chạy → SOS gửi đi
nhầm sau khi user đã cancel.
Fix: clear timer + reset state trong onCancel handler.
Test: regression test trong test/features/emergency/sos_test.dart
reproduces bug bằng cách advance time sau cancel.
```

## PR flow

1. Branch từ trunk (`develop`/`deploy`/`master`/`main` tùy repo)
2. Code + test
3. Self-review bằng workflow `/review`
4. Push branch
5. Open PR (tựa đề + body tiếng Việt, type prefix English)
6. Merge sau khi pass

**Cấm push trực tiếp lên trunk.**

## Versioning

- **Mobile (Flutter):** semver trong `pubspec.yaml` `version: X.Y.Z+build`
- **Admin BE/FE (Node):** semver trong `package.json`
- **Python repos:** không strict semver; tag release `v1.0.0` khi ship.

## Migration discipline

- **Prisma migrations** (HealthGuard): luôn `npx prisma migrate dev --name <desc>`. Không edit `_init.sql` thủ công.
- **FastAPI/Python:** dùng raw SQL scripts trong `PM_REVIEW/SQL SCRIPTS/`. Khi schema thay đổi, viết script migration mới với date prefix `YYYYMMDD_<desc>.sql`.
- **Canonical schema:** `PM_REVIEW/SQL SCRIPTS/init_full_setup.sql`. Sửa nó cuối cùng (sau khi migration đã chạy ổn).

## `.gitignore` discipline

Universal patterns (đã có trong mọi repo sau Phase 1 cleanup):

```
# === AI tooling artifacts (managed by .windsurf-template) ===
.claude/
.code-review-graph/
.codex_appdata/
.codex
.cursor/
.gitnexus/
.roo/
.rooignore
.roomodes
.worktrees/
roo-code-settings-optimized.json
AGENTS.md
CLAUDE.md
progress.md
task_plan.md
```

Plus stack-specific: `.env*` (production), `node_modules/`, `__pycache__/`, `build/`, `dist/`, `.dart_tool/`, `.venv/`.

## Naming code (universal)

- **var/function:** `camelCase` (JS/Dart), `snake_case` (Python)
- **class:** `PascalCase` (all)
- **constant:** `UPPER_SNAKE_CASE`
- **file:** `snake_case.py`, `kebab-case.dart`, `camelCase.js` hoặc `PascalCase.tsx` (tùy stack convention)
- **DB:** `snake_case` table + column, plural table name (`users`, `fall_events`)
