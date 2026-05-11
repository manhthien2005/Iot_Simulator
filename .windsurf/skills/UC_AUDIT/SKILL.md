---
name: uc-audit-cross-check
description: "Batch audit all Use Cases, evaluate relevance to SRS, cross-check UC-SQL-JIRA gaps. Triggers: audit UC, cross-check, use case coverage, gap analysis, UC inventory, UC relevance, UC SQL check, missing UC, missing task, orphan column, UC completeness, SRS alignment, check UC, evaluate UC."
category: project-management
risk: safe
source: custom
date_added: "2026-03-05"
---

# Skill: UC_AUDIT — Use Case Audit & Cross-Check

## Purpose

Batch-read and audit **all 26 Use Cases**, evaluate each UC's relevance to the SRS, and cross-check the triad **UC ↔ SQL Schema ↔ JIRA Tasks** to find gaps, orphans, and inconsistencies. This is the only skill designed to work with the **entire UC corpus** at once.

## When to Use

- Verify UC completeness: Are all needed UCs written? Are any redundant?
- Evaluate UC-SRS alignment: Does every UC trace back to an SRS functional requirement (HG-FUNC)?
- Cross-check UC ↔ SQL: Does every data field mentioned in UCs have a corresponding DB column? Are there orphan DB columns not covered by any UC?
- Cross-check UC ↔ JIRA: Does every UC have at least one JIRA Story? Are there JIRA Stories without a UC?
- After SRS changes, new UCs, or DB schema updates

---

## Context Loading Protocol (MANDATORY)

> [!IMPORTANT]
> Follow this strict 4-tier loading protocol. DO NOT skip tiers. DO NOT read full SRS.

### Tier 1: Navigation (ALWAYS)
1. **Read `PM_REVIEW/MASTER_INDEX.md`** — Project GPS map
2. **Read `PM_REVIEW/Resources/SRS_INDEX.md`** — System-level context, HG-FUNC requirements

### Tier 2: UC Corpus Overview
3. **Read `PM_REVIEW/Resources/UC/00_DANH_SACH_USE_CASE.md`** — Master UC list (26 UCs), platform mapping, relationships
4. Note UC count, module groupings, deleted UCs, and inter-UC relationships (include/extend/trigger chains)

### Tier 3: Cross-Reference Sources
5. **Read `PM_REVIEW/Resources/TASK/JIRA/README.md`** — JIRA Index (16 Epics, 61 Stories, UC→Epic lookup)
6. **Read `PM_REVIEW/SQL SCRIPTS/README.md`** — DB Architecture overview (6 layers, ~20 tables)

### Tier 4: Deep Dive (Progressive — per phase)
7. Read individual UC files only during Phase 1 analysis
8. Read specific SQL files only during Phase 3 cross-check
9. Read JIRA Sprint/Epic STORIES.md only when verifying task coverage

### ⛔ WHAT NOT TO DO
- ❌ DO NOT read the full SRS document — use SRS_INDEX
- ❌ DO NOT read the full JIRA CSV — use JIRA Index
- ❌ DO NOT read all SQL files at once — read per-layer as needed
- ❌ DO NOT read all UC files in a single batch — process module by module

---

## Phase 1: UC Inventory & Quality Check

**Goal**: Build a structured inventory of ALL UCs with quality assessment.

### Process

**Step 1 — Read UC files module by module:**

Read UCs in this order (8 modules, 26 files total):
1. `Authentication/` (6 files: UC001, UC002, UC003, UC004, UC005, UC009)
2. `Monitoring/` (3 files: UC006, UC007, UC008)
3. `Emergency/` (4 files: UC010, UC011, UC014, UC015)
4. `Analysis/` (2 files: UC016, UC017)
5. `Sleep/` (2 files: UC020, UC021)
6. `Admin/` (4 files: UC022, UC024, UC025, UC026)
7. `Notification/` (2 files: UC030, UC031)
8. `Device/` (3 files: UC040, UC041, UC042)

**Step 2 — For each UC, extract and record:**

| Field                | What to Extract                                     |
| -------------------- | --------------------------------------------------- |
| UC ID                | From spec table header (e.g., UC001)                |
| Name                 | UC title from spec table                            |
| Module               | Parent folder name                                  |
| Actors               | Primary actors from spec table                      |
| Platform             | Mobile / Admin Web / Both                           |
| Main Flow Steps      | Count of steps in main flow table                   |
| Alt Flow Count       | Count of alternative flow sections                  |
| Business Rules       | List of BR codes (e.g., BR-001, BR-040-01)          |
| Data Fields          | Fields mentioned (email, password, device_id, etc.) |
| DB Tables Referenced | Tables explicitly mentioned in the UC text          |
| NFR Categories       | Performance / Security / Usability                  |

**Step 3 — Quality check per UC:**

Read `references/uc-analysis-checklist.md` for detailed per-UC quality criteria.

Key checks:
- Does the UC have all required sections? (Spec table, Main Flow, Alt Flows, Business Rules, NFR)
- Is the actor an external entity (not "System")?
- Are main flow steps ≤ 10?
- Are alt flows properly numbered (referencing main flow step)?
- Are business rules specific (not generic copy-paste)?

---

## Phase 2: SRS Relevance Assessment

**Goal**: Score each UC's alignment with SRS functional requirements.

### Process

**Step 1 — Build SRS→UC mapping:**
1. Read `SRS_INDEX.md` → extract the **Feature → Functional Requirement Mapping** table (HG-FUNC-01 to HG-FUNC-11)
2. For each HG-FUNC, identify which UCs implement it
3. Background processes (HG-FUNC-01, 04, 10) correctly have no UC — mark as N/A

**Step 2 — Score each UC's relevance:**

Read `references/uc-analysis-checklist.md` → **Relevance Scoring Rubric** for detailed criteria.

| Level          | Criteria                                         |
| -------------- | ------------------------------------------------ |
| **CORE**       | UC directly implements a HG-FUNC requirement     |
| **SUPPORTING** | UC enables core features (auth, config, profile) |
| **MANAGEMENT** | UC is for system admin/management                |
| **LOW**        | UC has weak connection to system goals           |

**Step 3 — Flag issues:**
- HG-FUNC without any covering UC → **UNCOVERED_REQUIREMENT**
- UC without any HG-FUNC connection and not SUPPORTING/MANAGEMENT → **ORPHAN_UC**

---

## Phase 3: Cross-Check Matrix (UC ↔ SQL ↔ JIRA)

**Goal**: Find gaps and inconsistencies across the three pillars.

### Process

Read `references/cross-check-matrix.md` for the detailed matrix template and gap classification.

**Check A — UC ↔ JIRA:**
1. Use JIRA Index `UC → Epic Lookup` table
2. For EVERY UC in the inventory, verify it appears in the lookup
3. For every JIRA Epic/Story, verify it has a corresponding UC (unless infra/setup tasks)

Flag types:
- `UC_NO_TASK` — UC exists but no JIRA Story covers it
- `TASK_NO_UC` — JIRA Story references a UC that doesn't exist
- `EPIC_NO_UC` — JIRA Epic has no UC mapping (acceptable for infra Epics: EP01, EP02, EP03, EP06)

**Check B — UC ↔ SQL:**
1. For each UC, identify the data fields mentioned in Main Flow + Business Rules
2. Map those fields to SQL table columns (using SQL README + actual SQL files)
3. Verify the column exists and the data type is compatible

Flag types:
- `MISSING_COLUMN` — UC mentions a field not present in any SQL table
- `ORPHAN_COLUMN` — SQL column not referenced (directly or indirectly) by any UC
- `TYPE_MISMATCH` — UC implies a data type different from the SQL column

**Check C — Internal UC Consistency:**
1. `00_DANH_SACH_USE_CASE.md` vs actual files in `UC/` folders — any mismatch?
2. `UC/README.md` stats vs `00_DANH_SACH_USE_CASE.md` stats — any desync?
3. MASTER_INDEX UC Refs vs actual UC files — any missing references?
4. Inter-UC relationships (include/extend) — are referenced UCs present?

---

## Output Protocol (MANDATORY)

- **File**: `PM_REVIEW/UC_AUDIT_report.md` (project-wide, not per Admin/Mobile)
- **Template**: Read `references/report-template.md` — MUST follow exactly
- **Language**: Vietnamese section headers
- **Overwrite**: If file exists → overwrite, add comparison section (see template)
- **Sections**: Summary → UC Inventory table → SRS Alignment → Cross-Check → Recommendations

---

## Reference Documents

| Name               | Path                                              | When to read               |
| ------------------ | ------------------------------------------------- | -------------------------- |
| **MASTER INDEX**   | `PM_REVIEW/MASTER_INDEX.md`                       | **ALWAYS**                 |
| **SRS Index**      | `PM_REVIEW/Resources/SRS_INDEX.md`                | **ALWAYS**                 |
| **UC Master List** | `PM_REVIEW/Resources/UC/00_DANH_SACH_USE_CASE.md` | **ALWAYS**                 |
| UC README          | `PM_REVIEW/Resources/UC/README.md`                | Phase 1                    |
| UC Files           | `PM_REVIEW/Resources/UC/{Module}/*.md`            | Phase 1 (module by module) |
| **JIRA Index**     | `PM_REVIEW/Resources/TASK/JIRA/README.md`         | **ALWAYS**                 |
| **SQL README**     | `PM_REVIEW/SQL SCRIPTS/README.md`                 | Phase 3                    |
| SQL Files          | `PM_REVIEW/SQL SCRIPTS/0{N}_*.sql`                | Phase 3 (per-layer)        |
| Analysis Checklist | `references/uc-analysis-checklist.md`             | Phase 1                    |
| Cross-Check Matrix | `references/cross-check-matrix.md`                | Phase 3                    |
| Report Template    | `references/report-template.md`                   | Output phase               |

## Integrated Skills (Bundled)

**CRITICAL:** Before executing any phase, read the relevant bundled skills from the `skills/` subdirectory to inherit their analysis methodology:

| Bundled Skill           | Path                                      | Use in Phase                                                |
| ----------------------- | ----------------------------------------- | ----------------------------------------------------------- |
| Business Analyst        | `skills/business-analyst/SKILL.md`        | Phase 1 (structured analysis), Phase 3 (gap identification) |
| Product Manager Toolkit | `skills/product-manager-toolkit/SKILL.md` | Phase 2 (prioritization), Phase 3 (coverage analysis)       |

---

## Rules

- **Process UCs module by module** — never dump all 26 at once
- **Every UC must be read** — do NOT skip any UC, even if it looks trivial
- **Compare multiple sources** — always triangulate (UC list vs files vs MASTER_INDEX vs JIRA)
- **Flag ALL discrepancies** — count mismatches, desync, missing items
- **Report in Vietnamese** — final report uses Vietnamese section headers
- **Overwrite old report** — if re-auditing, overwrite `UC_AUDIT_report.md` directly
- **Update MASTER_INDEX** — if UCs are found missing from module rows, flag for update
