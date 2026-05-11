---
name: project-check-update
description: |
  Quét mã nguồn thực tế và cập nhật Project_Structure.md + summaries/ để
  PM_REVIEW luôn khớp với code hiện tại. Dành cho PM/AI agent quản lý
  cấu trúc dự án HealthGuard.
  Kích hoạt khi: "check project", "cập nhật cấu trúc", "kiểm tra source",
  "project thay đổi chưa?", "sync lại PM", "update summaries",
  "review structure", "kiểm tra project", "project còn đúng không?",
  "check source", "update structure".
---

# Goal

Ensure PM_REVIEW always reflects the true state of source code by scanning
actual project files and updating `Project_Structure.md` + `summaries/*.md`.
One command replaces 30–60 minutes of manual cross-referencing.

## Cross-skill / when to use vs others

| Need | Use |
|---|---|
| Sync PM_REVIEW docs với code reality (THIS SKILL — utility, no scoring) | `CHECK` |
| Project-level overview với scoring | `TongQuan` skill |
| Module-level code health audit | `/audit` workflow |
| Feature-level deep audit with score | `detailed-feature-review` skill |
| Quick PR/commit review | `code-review-five-axis` skill |

---

# Instructions

## Step 0: Project Detection (MANDATORY)

### Detect project folders

| Project   | Path                                 | Target                     |
| --------- | ------------------------------------ | -------------------------- |
| ADMIN WEB | `d:\DoAn2\VSmartwatch\HealthGuard`   | `PM_REVIEW/REVIEW_ADMIN/`  |
| MOBILE    | `d:\DoAn2\VSmartwatch\health_system` | `PM_REVIEW/REVIEW_MOBILE/` |

### Handle detection result

| Scenario              | Action                                                            |
| --------------------- | ----------------------------------------------------------------- |
| Only 1 project exists | Proceed with that project                                         |
| Both projects exist   | **MUST ask user to choose one**. NEVER update both simultaneously |
| Neither exists        | Report error, stop                                                |

> [!CAUTION]
> When both projects exist, **STOP and ask:** "Both ADMIN and MOBILE projects exist. Which one do you want to check & update?" — NEVER auto-select.

---

## Step 1: Context Loading (Tiered — Lazy)

Load context in tiers. Read ONLY what is needed at each stage.

| Tier      | What                                      | When                               |
| --------- | ----------------------------------------- | ---------------------------------- |
| Tier 1    | `PM_REVIEW/MASTER_INDEX.md`               | ALWAYS — read first                |
| Tier 2    | Current `Project_Structure.md`            | After project is selected          |
| Tier 3    | `references/update-checklist.md`          | Before starting Phase 1            |
| On-demand | `PM_REVIEW/Resources/TASK/JIRA/README.md` | ONLY when mapping Trello → JIRA    |
| On-demand | `PM_REVIEW/Resources/SRS_INDEX.md`        | ONLY when verifying SRS references |
| On-demand | `references/summary-template.md`          | ONLY during Phase 2                |

---

## Step 2: Phase 1 — Update Project_Structure.md

**2a — Scan actual structure:**
- Use `list_dir` and `find_by_name` to scan the full project folder structure
- Record: new folders, new files, deleted files, LOC changes
- Scan `package.json` / `pubspec.yaml` / `requirements.txt` for dependencies

**2b — Compare with current Project_Structure.md:**
- Compare actual tree vs tree in file
- Compare module/feature list
- Read route files → confirm API endpoints actually exist

**2c — Update the file:**
- Update tree structure to match reality
- Update module statuses (✅ Done / ⬜ Not reviewed / ⚠️ Issues found)
- Replace all "Trello" refs → "JIRA" with correct Epic Names (from JIRA Index)
- Update date + version in changelog section

**2d — VERIFY Phase 1:**
- Count folders in updated file vs `list_dir` output — must match 100%
- `grep` for "Trello" in file — must return 0 results
- Display: `"📍 Phase 1 ✅ — {N} changes applied to Project_Structure.md"`

### Rules for Project_Structure updates
- **Preserve existing format** — only update content
- Tree must match actual folder structure 100%
- Every module must have `SRS Ref` + `JIRA` (replace Trello)
- Review status must match MASTER_INDEX

---

## Step 3: Phase 2 — Update Summaries

**3a — Read summary template:**
- Read `references/summary-template.md` (required template)

**3b — For EACH summary file:**
1. Read current `summaries/*.md` file
2. Scan corresponding source code (`view_file_outline`, `list_dir`)
3. Confirm actual API endpoints from route files
4. Confirm actual file paths + update LOC
5. Map Trello → JIRA Epic Name (use JIRA Index)
6. Rewrite using template from `references/summary-template.md`
7. **OVERWRITE** the old summary file directly

**3c — What to REMOVE (wastes tokens):**

| Section                               | Reason                                                    |
| ------------------------------------- | --------------------------------------------------------- |
| Trello Checklist (Pre-Extracted)      | Duplicates JIRA CSV — AI can query JIRA Index when needed |
| SRS Requirements (verbose extraction) | AI reads UC files when detail is needed                   |
| Emoji in headers                      | Wastes characters, no logical value                       |
| Empty Review Notes                    | Empty section = wasted tokens                             |
| Generic Non-Functional Requirements   | Repeated in every module, provides no new info            |

**3d — What to KEEP (essential):**

| Section                         | Value for AI                                     |
| ------------------------------- | ------------------------------------------------ |
| Module identity + JIRA refs     | AI needs to know what module, which JIRA Epic    |
| Purpose & Technique (2-3 lines) | Shortest summary for AI to understand the module |
| API Index (compact)             | Endpoint map — most needed by AI                 |
| File Index (exact paths + LOC)  | AI knows what to read and where                  |
| Known Issues                    | Existing problems to be aware of                 |
| Cross-References                | DB tables, UC files, related modules             |
| Review (if reviewed)            | Score + link to review file                      |

**3e — VERIFY Phase 2:**
- For each summary: confirm all file paths in File Index exist using `find_by_name`
- Count updated files vs total summaries — report `"Updated X/Y summaries"`
- Display: `"📍 Phase 2 ✅ — {X}/{Y} summaries updated"`

### After all summaries are done:
- Check `MASTER_INDEX.md` — any modules need updating?
- Produce changelog summary for user

---

## Step 4: Output Changelog

After completion, display a summary to user (**do NOT save to file**):

```
## CHECK Report — {PROJECT_NAME} ({DATE})

### Project_Structure.md
- Added: [new files/folders]
- Removed: [deleted files/folders]
- Updated: [modules with changes]
- Trello → JIRA: [number of refs migrated]

### Summaries
- Updated: [list of updated files]
- Format: [files converted to new template]
- Trello → JIRA: [number of refs migrated]
```

---

## Progress Reporting

After EACH major step, display progress to user:
- `"📍 Step 1/4 — Detecting project..."`
- `"📍 Step 2/4 — Scanning actual structure..."`
- `"📍 Step 3/4 — Updating summary 3/7: AUTH..."`
- `"📍 Step 4/4 — Generating changelog..."`

## Recovery Protocol

If skill fails mid-execution:
1. Report: which files were already updated (committed changes)
2. Report: which files were NOT yet processed
3. User can re-run skill — idempotent, will skip already-correct files

---

# Examples

## Example 1: Happy Path — ADMIN project, normal update

**Context:** User says "check project". Both ADMIN and MOBILE folders exist.

**AI Actions:**
1. Detect both projects → Ask: "Both ADMIN and MOBILE exist. Which one?"
2. User: "ADMIN"
3. Load `MASTER_INDEX.md` → 6 modules listed
4. Load `REVIEW_ADMIN/Project_Structure.md` → last updated 2026-02-28
5. Scan `d:\DoAn2\VSmartwatch\HealthGuard\` with `list_dir`:
   - Found NEW: `src/modules/notification/` (not in tree)
   - Found DELETED: `src/modules/legacy-auth/` (in tree but gone)
   - Found CHANGED: `src/modules/auth/auth.controller.ts` (200 → 280 LOC)
6. Update `Project_Structure.md`:
   - Add `notification/` to tree
   - Remove `legacy-auth/` from tree
   - Update AUTH module LOC
   - Replace "Trello: Card #42" → "JIRA: EP04-Login"
7. **VERIFY:** Tree folder count = 14, `grep "Trello"` = 0 matches ✅
8. Display: `"📍 Phase 1 ✅ — 4 changes applied to Project_Structure.md"`
9. Load `references/summary-template.md`
10. Update `summaries/AUTH.md`: scan `auth/` → confirm 4 endpoints → rewrite
11. Create NEW `summaries/NOTIFICATION.md` using template
12. Remove `summaries/LEGACY_AUTH.md` reference from MASTER_INDEX
13. **VERIFY:** All file paths in File Index exist ✅
14. Display: `"📍 Phase 2 ✅ — 2/6 summaries updated, 1 created, 1 removed"`

**Output:**
```
## CHECK Report — ADMIN (2026-03-06)

### Project_Structure.md
- Added: src/modules/notification/
- Removed: src/modules/legacy-auth/
- Updated: AUTH (LOC 200→280)
- Trello → JIRA: 3 refs migrated

### Summaries
- Updated: AUTH.md, NOTIFICATION.md (new)
- Format: AUTH.md converted to new template
- Trello → JIRA: 2 refs migrated
```

---

## Example 2: Edge Case — Single project, missing data

**Context:** User says "kiểm tra project". Only MOBILE folder exists.

**AI Actions:**
1. Detect only MOBILE → proceed automatically (no need to ask)
2. Load `MASTER_INDEX.md` → 8 modules listed
3. Load `REVIEW_MOBILE/Project_Structure.md`
4. Scan `d:\DoAn2\VSmartwatch\health_system\`:
   - `lib/features/sleep/` exists but has only placeholder files (0 LOC)
   - `lib/features/analysis/` folder does NOT exist yet
5. Update `Project_Structure.md`:
   - SLEEP module → status ⬜ Not built (placeholder only)
   - ANALYSIS module → status ⬜ Not built (folder missing)
6. Load JIRA Index → no Epic found for SLEEP module
7. Mark SLEEP as "JIRA: TBD" and flag in changelog
8. **VERIFY:** Tree matches, "Trello" count = 0 ✅
9. Update `summaries/SLEEP.md`:
   - Rewrite with template, note "⬜ Not built — placeholder files only"
   - File Index: empty (no real source files)
10. Skip `summaries/ANALYSIS.md` — no source code, write minimal summary noting "⬜ Not built"
11. **VERIFY:** File paths verified ✅

**Output:**
```
## CHECK Report — MOBILE (2026-03-06)

### Project_Structure.md
- Updated: SLEEP (→ ⬜ Not built), ANALYSIS (→ ⬜ Not built)
- Trello → JIRA: 5 refs migrated

### Summaries
- Updated: SLEEP.md (minimal — not built)
- Created: ANALYSIS.md (minimal — not built)
- ⚠️ JIRA mapping missing: SLEEP → marked as "JIRA: TBD"
```

---

# Constraints

## 🔴 Safety (vi phạm = FAIL)
- 🚫 **NEVER update both projects simultaneously** — chọn lệch = corrupt data
- 🚫 **NEVER overwrite without showing diff preview** when >3 files affected — confirm trước
- ✅ **ALWAYS display progress** after each major step — user must see what's happening
- ✅ **ALWAYS report recovery state** if skill fails mid-execution

## 🟡 Operational (nên tuân thủ)
- Summaries MUST follow template in `references/summary-template.md`
- Preserve `Project_Structure.md` format — only update content
- After updating summaries → update `MASTER_INDEX.md` if modules changed
- OVERWRITE old files directly — no versioning, no backups

## 🟢 Convention (khuyến khích)
- DO NOT read full SRS — only read UC files when needed
- DO NOT read full JIRA CSV — use JIRA Index
- Keep Context Loading lazy — read on-demand, not all at once

---

## Dry-Run Mode

If user says "check --dry-run" or "check nhưng đừng sửa gì":
1. Run full scan (Phase 1 + Phase 2) as normal
2. Display all PROPOSED changes as diffs
3. **DO NOT write any files**
4. Ask user: "Apply these changes? (yes/no)"

---

## Edge Cases

| Scenario                                          | Action                                                    |
| ------------------------------------------------- | --------------------------------------------------------- |
| Summary file exists but module has no source code | Rewrite summary noting "⬜ Not built", keep JIRA/UC refs   |
| Source code exists but no summary file            | Create new summary using `references/summary-template.md` |
| Module folder was deleted since last check        | Remove from `Project_Structure.md`, update MASTER_INDEX   |
| `Project_Structure.md` does not exist             | Report error — user must create it first or run TongQuan  |
| JIRA Index has no matching Epic for a module      | Mark as "JIRA: TBD" and flag in changelog                 |
| User requests dry-run                             | Show diffs only, do not write — ask confirm before apply  |
| Skill fails mid-Phase 2                           | Report completed + remaining files, user can re-run       |

---

## Reference Documents

| Name              | Path                                        | When to read            |
| ----------------- | ------------------------------------------- | ----------------------- |
| MASTER INDEX      | `PM_REVIEW/MASTER_INDEX.md`                 | ALWAYS (Tier 1)         |
| Project Structure | `PM_REVIEW/REVIEW_{X}/Project_Structure.md` | After project selected  |
| Update Checklist  | `references/update-checklist.md`            | Before Phase 1          |
| JIRA Index        | `PM_REVIEW/Resources/TASK/JIRA/README.md`   | On-demand (Trello→JIRA) |
| SRS Index         | `PM_REVIEW/Resources/SRS_INDEX.md`          | On-demand (SRS verify)  |
| Summary Template  | `references/summary-template.md`            | Phase 2 only            |

---

## Completion Criteria

The CHECK scan is considered **DONE** when ALL of the following are true:

- [ ] `Project_Structure.md` tree matches actual folder structure 100%
- [ ] All `summaries/*.md` files use the new template from `references/summary-template.md`
- [ ] All Trello references replaced with JIRA Epic Names
- [ ] All file paths in summaries point to files that actually exist
- [ ] LOC counts are updated for implemented files
- [ ] MASTER_INDEX.md is updated if modules were added/removed
- [ ] Changelog summary displayed to user
- [ ] Progress was reported at every major step
