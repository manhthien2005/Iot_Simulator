---
name: project-overview-assessment
description: "High-level assessment for the HealthGuard project. Triggers on keywords: project structure, project overview, tong quan, review architecture, assess structure. Uses MASTER_INDEX to optimize context."
risk: safe
source: custom
date_added: "2026-03-03"
date_updated: "2026-03-04"
---

# Skill: Project Overview Assessment (TongQuan)

## Purpose

Evaluate the **holistic structure and progress** of the HealthGuard project to ensure it aligns with the SRS, follows industry-standard architecture, and stays on track with JIRA sprint tasks (Epics/Stories).

## Cross-skill / when to use vs others

| Need | Use |
|---|---|
| Project-level overview (admin OR mobile, holistic) — THIS SKILL | `TongQuan` |
| Module-level code health audit | `/audit` workflow |
| Feature-level deep audit with 8-criteria score | `detailed-feature-review` skill |
| Quick PR/commit review | `code-review-five-axis` skill |
| Sync PM_REVIEW docs với code reality | `CHECK` skill |

## When to Use This Skill

Automatically activates when the user wants to:
- Evaluate the overall project or a specific large section
- Verify if the existing codebase structure reflects the SRS correctly
- Review progress against JIRA sprints (Epics & Stories)
- Report the project status to stakeholders

## Context Loading Protocol (MANDATORY)

> [!IMPORTANT]
> The Agent MUST strictly follow this 3-tier loading protocol to optimize token limits and prevent getting lost in context.

### Tier 1: Navigation (ALWAYS read first)
1. **Read `PM_REVIEW/MASTER_INDEX.md`** — The overall GPS map of the project.
2. **Read `PM_REVIEW/Resources/SRS_INDEX.md`** — System-level context (architecture, features, thresholds).
3. Determine the assessment scope (Admin / Mobile / or both).

### Tier 2: Prepare Integrated Skills
3. **CRITICAL:** Before evaluating, read the internal bundled skills under `skills/` to inherit their high-level structural rules:
   - `skills/architect-review/SKILL.md`
   - `skills/software-architecture/SKILL.md`
   - `skills/backend-architect/SKILL.md`
   - `skills/architecture-patterns/SKILL.md`

### Tier 3: Structure (Read based on scope)
4. **Read the corresponding `Project_Structure.md`** (Admin or Mobile).

### Tier 4: Summaries (Read ONLY relevant summaries)
5. **Read related summary files** from the `summaries/` folder.

### ⛔ WHAT NOT TO DO
- ❌ **DO NOT** read the full SRS document — use the summary files instead. If more detail is needed, read the specific Use Case (UC) file in `PM_REVIEW/Resources/UC/`.
- ❌ **DO NOT** read the full JIRA CSV — use `PM_REVIEW/Resources/TASK/JIRA/README.md` (JIRA Index) to quickly locate Epics/Stories, then read only relevant rows from the CSV.
- ❌ **DO NOT** read the entire source code — only scan the folder structure for overviews.

## Evaluation Process (Progressive Deepening)

**Step 1:** Complete the Context Loading Protocol.
**Step 2:** Source Code Scan (Surface Level). Browse folder structure without reading file contents, comparing against `Project_Structure.md`.
**Step 3:** Evaluate against 6 Criteria: SRS Compliance, Architecture, Consistency, Progress vs JIRA, Code Quality, Security. **READ `references/evaluation-criteria.md` for specific check details.**
**Step 4:** Cross-check with JIRA Stories from the JIRA Index.

## Output File Protocol (MANDATORY)

### File Naming Convention
The review file MUST follow this naming pattern:
```
TONGQUAN_{PROJECT}_review.md
```
- **PROJECT**: Project name, UPPERCASE (e.g., `ADMIN`, `MOBILE`)
- If reviewing both projects → create 2 separate files or `TONGQUAN_ALL_review.md`

### Output Location
- Admin project → `PM_REVIEW/REVIEW_ADMIN/TONGQUAN_ADMIN_review.md`
- Mobile project → `PM_REVIEW/REVIEW_MOBILE/TONGQUAN_MOBILE_review.md`

### Examples
| User Request                            | File Output                               |
| --------------------------------------- | ----------------------------------------- |
| "Overview assessment for Admin project" | `REVIEW_ADMIN/TONGQUAN_ADMIN_review.md`   |
| "Overview assessment for Mobile"        | `REVIEW_MOBILE/TONGQUAN_MOBILE_review.md` |

## Re-review Protocol (2nd review and beyond)

> [!IMPORTANT]
> Before starting a review, the AI MUST check if a previous review file already exists. If found → perform comparison.

### Step 1: Find previous review file
1. Determine the filename using the **Output File Protocol** above.
2. Check if the file exists in `REVIEW_ADMIN/` or `REVIEW_MOBILE/`.

### Step 2: Read previous review file (if exists)
3. Read the old review file and extract:
   - **Old score**: Total score + score per criterion.
   - **Old weaknesses**: List of all weaknesses.
   - **Old recommendations**: List of action recommendations.
   - **Old review date**: From the "Thông tin chung" section.
   - **Old review count**: From the "Thông tin chung" section (if present).

### Step 3: Perform new review as normal
4. Execute the review following the Evaluation Process above (Step 1–4).

### Step 4: Compare and evaluate changes
5. Compare new results with data extracted from the old file:
   - Score increase/decrease per criterion.
   - Weaknesses that have been **fixed** (present in old, absent in new).
   - Weaknesses that **still exist** (present in both old and new).
   - Weaknesses that are **newly introduced** (absent in old, present in new).

### Step 5: Overwrite old file
6. **OVERWRITE** the old review file with the complete new report, including the "🔄 SO SÁNH VỚI LẦN ĐÁNH GIÁ TRƯỚC" section (per template `references/report-template.md`).
7. Increment the **Lần đánh giá** counter by 1.

### Important Notes
- If **NO previous file found** → this is the first review → do NOT add comparison section, set `Lần đánh giá: 1`.
- If **previous file found** → MUST add comparison section and increment `Lần đánh giá`.

## Output Formatting

**MANDATORY:** You must use the Vietnamese markdown reporting template located at `references/report-template.md`. You must not deviate from this template.

## After Review: Update MASTER_INDEX (MANDATORY)

When the overview review concludes, you **MUST** update `MASTER_INDEX.md`:

1. Set `Review Status` → ✅ Done (for each module assessed)
2. Set `Score` → XX/100 (if individual module scores are given)
3. Set `Quality` → Determined by score (see `DanhGiaChiTiet/references/evaluation-criteria.md` → Score Classification):
   - **76–100** → ✅ Pass
   - **51–75** → ⚠️ Needs Fix
   - **0–50** → ❌ Fail
4. Set `Review File` → Link to the overview review file (e.g., `[View](REVIEW_ADMIN/TONGQUAN_ADMIN_review.md)`)
5. Set `Last Review` → Current date (ISO format)

## Edge Cases

| Scenario                                     | Action                                                                            |
| -------------------------------------------- | --------------------------------------------------------------------------------- |
| Summary file does not exist for a module     | Note as "Missing summary" in the report, skip detailed assessment for that module |
| Source code folder is empty / not built      | Mark as "⬜ Not built" in report, score = N/A                                      |
| MASTER_INDEX row missing for a module        | Add the row with available info                                                   |
| Previous review file is corrupted/unreadable | Treat as first review, set `Lần đánh giá: 1`                                      |

## Reference Documents

| Name             | Path                                                | When to read                                   |
| ---------------- | --------------------------------------------------- | ---------------------------------------------- |
| **MASTER INDEX** | `PM_REVIEW/MASTER_INDEX.md`                         | **ALWAYS**                                     |
| **SRS Index**    | `PM_REVIEW/Resources/SRS_INDEX.md`                  | **ALWAYS** — System-level context              |
| Admin Structure  | `PM_REVIEW/REVIEW_ADMIN/Project_Structure.md`       | When reviewing Admin                           |
| Mobile Structure | `PM_REVIEW/REVIEW_MOBILE/Project_Structure.md`      | When reviewing Mobile                          |
| Admin Summaries  | `PM_REVIEW/REVIEW_ADMIN/summaries/*.md`             | Based on module                                |
| Mobile Summaries | `PM_REVIEW/REVIEW_MOBILE/summaries/*.md`            | Based on module                                |
| DB Summary       | `PM_REVIEW/SQL SCRIPTS/README.md`                   | When reviewing database design                 |
| Use Cases (UC)   | `PM_REVIEW/Resources/UC/**/*.md`                    | When explicit detail is missing from summaries |
| **JIRA Index**   | `PM_REVIEW/Resources/TASK/JIRA/README.md`           | **ALWAYS** — Quick lookup for Epics/Stories    |
| JIRA Full CSV    | `PM_REVIEW/Resources/TASK/JIRA/JIRA_IMPORT_ALL.csv` | Only when need full Story details              |
