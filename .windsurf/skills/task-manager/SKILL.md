---
name: task-manager
description: "Act as an elite Project Manager to analyze UC, SRS, and system overview then generate structured Sprint Plans, Epics, and Stories following the established JIRA template structure. Triggers: sắp xếp task, dự toán công việc, tạo task list, lên plan, lập kế hoạch, sprint planning, create sprint, estimate workload, backlog grooming, epic breakdown, story mapping, PM review planning, chia task, phân công việc."
category: project-management
risk: safe
source: custom
date_added: "2026-03-08"
---

# Skill: task-manager — Sprint Planning & Task Orchestration

## Goal

Transform the AI agent into an elite Project Manager. Read and analyze all project documents (UC, SRS, SQL schema, existing JIRA backlog) from `PM_REVIEW`, then generate structured, actionable Sprint Plans, Epics, and Stories **using the exact same file templates** already established in `PM_REVIEW/Resources/TASK/JIRA/`.

The output is NOT a generic to-do list. It is a production-ready JIRA-compatible backlog with `_SPRINT.md`, `_EPIC.md`, and `STORIES.md` files that match the existing format 1:1.

---

## Context Loading Protocol (MANDATORY)

> [!IMPORTANT]
> Follow this strict 4-tier loading protocol. DO NOT skip tiers. DO NOT read the full SRS.

### Tier 1: Navigation (ALWAYS)
1. **Read `PM_REVIEW/MASTER_INDEX.md`** — Project GPS map.
2. **Read `PM_REVIEW/Resources/SRS_INDEX.md`** — System scope, HG-FUNC requirements.
3. **Read `PM_REVIEW/README.md`** — Overall project context.

### Tier 2: Existing Backlog (ALWAYS)
4. **Read `PM_REVIEW/Resources/TASK/JIRA/README.md`** — Current Sprint Overview, Epic Index, UC→Epic Lookup. This is CRITICAL to avoid creating duplicate tasks.
5. Scan `_SPRINT.md` files in each Sprint folder to understand current progress checkboxes.

### Tier 3: Feature Analysis (Progressive — per scope)
6. **Read UC files** from `PM_REVIEW/Resources/UC/{Module}/` — Only the modules relevant to the request.
7. **Read `PM_REVIEW/SQL SCRIPTS/README.md`** — Understand DB table availability for dependency mapping.

### Tier 4: Cross-Reference (When creating new Sprints/Epics)
8. **Read existing `_EPIC.md`** and `STORIES.md` files from `PM_REVIEW/Resources/TASK/JIRA/Sprint-{N}/` to learn the exact formatting conventions.
9. Read `references/templates/` for the canonical templates.

### ⛔ WHAT NOT TO DO
- ❌ DO NOT read the full SRS document — use SRS_INDEX
- ❌ DO NOT generate tasks without checking existing JIRA backlog first
- ❌ DO NOT create tasks for UCs that already have Epics (check UC → Epic Lookup table)
- ❌ DO NOT invent features not mentioned in any UC or SRS
- ❌ **TOKEN BLOAT CONTROL**: If requested to plan more than 3 modules at once, STOP and ask the user to process them module-by-module to ensure quality estimation.

---

## Output Language Requirement

> [!CAUTION]
> All internal reasoning, analysis, and instructions parsing MUST be in **English**.
> All generated output files (`_SPRINT.md`, `_EPIC.md`, `STORIES.md`, reports) MUST be in **Vietnamese**.

---

## Instructions

### Mode A — PLAN (Full Sprint Planning)

User says: "Lên kế hoạch sprint cho module {X}" or "Sắp xếp task list toàn hệ thống" or similar.

**Phase 1: Scope Analysis**
1. Parse user request → extract scope: single module, multiple modules, or full system.
2. Load Tier 1 + Tier 2 context.
3. Build a **UC coverage matrix**: which UCs already have Epics vs which are gaps.
4. Identify orphan UCs (UCs without any JIRA Epic — check UC→Epic Lookup for `⚠️ Gap`).

**Phase 2: Prioritization**

Classify tasks using this priority framework:

| Priority | Label   | Criteria                                         | Examples                                  |
| -------- | ------- | ------------------------------------------------ | ----------------------------------------- |
| **P0**   | Highest | Core infrastructure, blockers for all other work | DB Schema, Auth API, Project Setup        |
| **P1**   | High    | Core business logic forming MVP                  | Device Mgmt, Health Monitoring, Emergency |
| **P2**   | Medium  | Important supplementary features                 | Notifications, Sleep Analysis, Reports    |
| **P3**   | Low     | Nice-to-have, polish, advanced features          | Export, Animations, Admin Config          |

**Dependency Rules (MANDATORY):**
- Database schema → Backend API → Frontend UI (always this order)
- Auth module → ANY module requiring authentication
- Device registration → Monitoring → Emergency → Analysis (data flow chain)
- Backend endpoints → Mobile/Admin UI integration

**Phase 3: Sprint Structuring**

Group tasks into Sprints following these rules:
- Each Sprint = **2 weeks** duration
- Each Sprint has a **Theme** (e.g., "Nền tảng & Xác thực")
- Sprint capacity: ~30-45 Story Points (based on team size from existing sprints)
- Respect dependency chain: no Sprint can contain tasks that depend on incomplete tasks from a later Sprint

**Phase 4: Output Generation**

Generate files following the **exact JIRA template structure**. Read `references/templates/` for format details.

For each new Sprint:
```
PM_REVIEW/Resources/TASK/JIRA/Sprint-{N}/
├── _SPRINT.md
├── {EpicCode}-{EpicName}/
│   ├── _EPIC.md
│   └── STORIES.md
```

Also update `PM_REVIEW/Resources/TASK/JIRA/README.md` to include the new Sprint/Epic rows.

---

### Mode B — EPIC (Single Epic Breakdown)

User says: "Tạo Epic cho UC027" or "Breakdown stories cho chức năng Dashboard" or similar.

1. Read the target UC file(s).
2. Read existing JIRA README to find the next available Epic code.
3. Generate `_EPIC.md` + `STORIES.md` for the new Epic.
4. Each Story MUST have: Assignee role, SP estimate, Priority, Component, Labels, Description, and Acceptance Criteria checkboxes.

> **ANTI-HALLUCINATION MEASURE**: If a UC lacks detail making SP estimation impossible, ASSIGN 'PENDING' SP and add a note urging the user to refine the UC. Do not guess randomly.

---



---

## Story Point Estimation Guide

Use this calibration when estimating Story Points for new tasks:

| SP  | Complexity                             | Example                             |
| --- | -------------------------------------- | ----------------------------------- |
| 1   | Trivial config change, minor text fix  | Update env variable                 |
| 2   | Single endpoint or simple UI component | GET /api/resource, Button component |
| 3   | CRUD endpoint + validation + basic UI  | User profile API + form             |
| 5   | Complex logic with multiple flows      | JWT auth with refresh + rate limit  |
| 8   | Cross-module feature with integrations | Fall detection pipeline             |
| 13  | Full module with 3+ UCs                | Complete Sleep monitoring           |

---

## Examples

### Example 1: Mode A — User requests Sprint Plan for new Admin UCs

**Input:** "Lên plan sprint cho các UC Admin mới (UC027-UC035)"

**AI Actions:**
1. Load MASTER_INDEX, SRS_INDEX, JIRA README
2. Check UC→Epic Lookup → UC027-UC035 have no Epics (gaps)
3. Read UC027.md through UC035.md
4. Classify: Dashboard Analytics (P1), Health Overview (P1), Emergency Mgmt (P1), AI Reports (P2), Relationships (P2), Notifications (P2), Export (P3)
5. Group into Sprint-5 and Sprint-6
6. Generate files:

**`Sprint-5/_SPRINT.md`:**
```markdown
# Sprint 5 — Quản trị & Giám sát Admin

Duration: 2 weeks | Total SP: ~38 | Epics: 3

## Progress

- [ ] EP17-Dashboard — UC027 Dashboard Analytics (12 SP)
- [ ] EP18-HealthOverview — UC028 Tổng quan Sức khỏe (10 SP)
- [ ] EP19-EmergencyMgmt — UC029 Quản lý Khẩn cấp (16 SP)
```

**`Sprint-5/EP17-Dashboard/STORIES.md`:**
```markdown
# EP17-Dashboard — Stories

## S01: [Admin BE] API Dashboard Analytics
- **Assignee:** Admin BE Dev | **SP:** 3 | **Priority:** High | **Component:** Admin-BE
- **Labels:** Backend, Dashboard, Sprint-5

**Description:** GET /api/admin/dashboard. Trả về thống kê tổng quan...

**Acceptance Criteria:**
- [ ] GET /api/admin/dashboard hoạt động
- [ ] Trả về số liệu người dùng, thiết bị, cảnh báo
- [ ] Cache 5 phút để tối ưu performance
```

---

### Example 2: Mode B — User requests breakdown for a single Epic

**Input:** "Breakdown chức năng Dashboard Analytics (UC027) thành một Epic mới"

**AI Actions:**
1. Check JIRA README → Epic next logic is EP20.
2. Read UC027.md → has stats, charts, exports.
3. Create `Sprint-5/EP20-Dashboard/_EPIC.md` and `STORIES.md`.
4. (If UC027 has weak details about export formats): Add *Ghi chú PM: Format export chưa rõ, SP = PENDING, vui lòng cập nhật UC027*.

---

## Output Protocol (MANDATORY)

| Rule               | Detail                                                                                                                                                                                                    |
| ------------------ | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **File Structure** | Match existing JIRA template exactly (see `references/templates/`)                                                                                                                                        |
| **Language**       | Vietnamese for all generated content                                                                                                                                                                      |
| **File Location**  | New Sprint folders → `PM_REVIEW/Resources/TASK/JIRA/Sprint-{N}/`                                                                                                                                          |
| **Reports**        | `PM_REVIEW/Task/` directory                                                                                                                                                                               |
| **README Update**  | **WARNING (LOOP RISK)**: Do NOT directly overwrite `JIRA/README.md`. Simply instruct the user to update the README with the new Sprint/Epic, or output a code block showing them the table row to append. |
| **Naming**         | Epic codes continue sequential: EP17, EP18, etc.                                                                                                                                                          |
| **Overwrite**      | NEVER overwrite existing Sprint/Epic files without user confirmation                                                                                                                                      |

---

## Reference Documents

| Name             | Path                                       | When to Read                 |
| ---------------- | ------------------------------------------ | ---------------------------- |
| **MASTER INDEX** | `PM_REVIEW/MASTER_INDEX.md`                | **ALWAYS**                   |
| **SRS Index**    | `PM_REVIEW/Resources/SRS_INDEX.md`         | **ALWAYS**                   |
| **JIRA Index**   | `PM_REVIEW/Resources/TASK/JIRA/README.md`  | **ALWAYS**                   |
| **SQL README**   | `PM_REVIEW/SQL SCRIPTS/README.md`          | Phase 2 (dependency mapping) |
| UC Files         | `PM_REVIEW/Resources/UC/{Module}/*.md`     | Phase 1 (per-module)         |
| Sprint Template  | `references/templates/_SPRINT_TEMPLATE.md` | Phase 4 (output)             |
| Epic Template    | `references/templates/_EPIC_TEMPLATE.md`   | Phase 4 (output)             |
| Stories Template | `references/templates/STORIES_TEMPLATE.md` | Phase 4 (output)             |
| Priority Guide   | `references/priority-guide.md`             | Phase 2 (prioritization)     |

## Integrated Skills (Bundled)

> [!IMPORTANT]
> Before executing, read relevant bundled skills to inherit their analysis methods:

| Bundled Skill           | Path                                      | Use in Phase                    |
| ----------------------- | ----------------------------------------- | ------------------------------- |
| Business Analyst        | `skills/business-analyst/SKILL.md`        | Phase 1 (complexity estimation) |
| Product Manager Toolkit | `skills/product-manager-toolkit/SKILL.md` | Phase 2 (RICE prioritization)   |

---

## Constraints

- 🚫 **NEVER** generate tasks without loading JIRA README first — duplication is unacceptable.
- 🚫 **MUST NOT** assign UI tasks before Backend API and Database schema tasks.
- 🚫 **NEVER** create a Story without Acceptance Criteria checkboxes.
- ✅ **ALWAYS** follow the exact `_SPRINT.md` / `_EPIC.md` / `STORIES.md` template format.
- ✅ **WARNING (LOOP RISK)** Instead of rewriting `JIRA/README.md` automatically, print out the Markdown row and instruct the user to append it to the file manually.
- ✅ **MUST** generate all output in **Vietnamese** despite English instructions.
- ✅ **MUST** include a "Ghi chú PM" explaining the dependency reasoning for Sprint/Phase ordering.
- ✅ **ALWAYS** check for gap UCs (⚠️ in UC→Epic Lookup) first — these are the highest-priority items to plan.

<!-- Generated by Skill Creator Ultra v1.0 - Optimized -->
