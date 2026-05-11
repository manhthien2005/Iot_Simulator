# Cross-Check Matrix — UC ↔ SQL ↔ JIRA

> Reference for Phase 3 of UC_AUDIT. Read when performing cross-checks.

---

## Check A: UC ↔ JIRA Task Coverage

### Step-by-step Process

1. Open JIRA Index → `UC → Epic Lookup` table
2. For each UC in the 26-UC inventory:
   - Search for the UC ID in the lookup table
   - If found → record the Epic Name
   - If NOT found → flag as `UC_NO_TASK`
3. For each JIRA Epic:
   - Check if it has UC references in the Epic Index
   - Infrastructure Epics (EP01-Database, EP02-AdminBE, EP03-MobileBE, EP06-Ingestion) are EXEMPT from needing UCs
   - If a non-infra Epic has no UC → flag as `EPIC_NO_UC`

### UC → JIRA Matrix Template

```markdown
| UC    | Epic            | Stories | Status       |
| ----- | --------------- | ------- | ------------ |
| UC001 | EP04-Login      | 5       | ✅            |
| UC002 | EP05-Register   | 5       | ✅            |
| UC003 | EP12-Password   | 5       | ✅            |
| UC004 | EP12-Password   | 5       | ✅            |
| UC005 | ???             | ???     | ❌ UC_NO_TASK |
| UC006 | EP08-Monitoring | 3       | ✅            |
| ...   | ...             | ...     | ...          |
```

### Known Issues (Pre-identified)

> [!WARNING]
> The following gaps were already identified during skill creation (2026-03-05):
> - **UC005** (Manage Profile) — NOT present in JIRA UC→Epic Lookup
> - **UC009** (Logout) — NOT present in JIRA UC→Epic Lookup
> These MUST be flagged in every UC_AUDIT report.

---

## Check B: UC ↔ SQL Column Coverage

### Step-by-step Process

1. From Phase 1 inventory, collect all data fields per UC
2. Map fields to SQL tables using the guide in `uc-analysis-checklist.md`
3. For each UC field:
   - Locate the corresponding SQL column in the relevant SQL file
   - If found → mark as covered
   - If NOT found → flag as `MISSING_COLUMN`
4. For each SQL table, walk through all columns:
   - Check if any UC references this column (directly or indirectly)
   - If no UC uses it → flag as `ORPHAN_COLUMN`
   - Exception: metadata columns (`created_at`, `updated_at`, `deleted_at`, `id`, `uuid`) are EXEMPT

### SQL Layer → Files Reference

| Layer        | SQL File                               | Tables                                              |
| ------------ | -------------------------------------- | --------------------------------------------------- |
| 1-Users      | `02_create_tables_user_management.sql` | `users`, `user_relationships`, `emergency_contacts` |
| 2-Devices    | `03_create_tables_devices.sql`         | `devices`                                           |
| 3-TimeSeries | `04_create_tables_timeseries.sql`      | `vitals`, `motion_data`, aggregates                 |
| 4-Events     | `05_create_tables_events_alerts.sql`   | `fall_events`, `sos_events`, `alerts`               |
| 5-AI         | `06_create_tables_ai_analytics.sql`    | `risk_scores`, `risk_explanations`                  |
| 6-System     | `07_create_tables_system.sql`          | `audit_logs`, `system_config`                       |

### Column Coverage Matrix Template

Use this format for EACH table. Fill dynamically by reading the actual SQL file:

```markdown
### Table: `{table_name}` ({sql_file})

| Column | Type   | Covered by UC    | Status                |
| ------ | ------ | ---------------- | --------------------- |
| {col}  | {type} | UC{NNN}, UC{NNN} | ✅ / ⚠️ ORPHAN / ⚠️ WEAK |
```

**Rules for filling:**
- Read each column from the SQL CREATE TABLE statement
- Search all UC inventories for references to that column
- `✅` = at least one UC explicitly uses this field
- `⚠️ ORPHAN_COLUMN` = no UC references it (exempt: `id`, `uuid`, `created_at`, `updated_at`, `deleted_at`)
- `⚠️ WEAK_COVERAGE` = UC mentions the topic but not the specific field

> [!IMPORTANT]
> DO NOT use pre-filled data. The AI MUST verify each column against actual UC text during the audit.

---

## Check C: Internal UC Consistency

### Checks to Perform

| #   | Check                 | Sources to Compare                                                              | Flag                |
| --- | --------------------- | ------------------------------------------------------------------------------- | ------------------- |
| 1   | UC count match        | `00_DANH_SACH_USE_CASE.md` vs actual files in `UC/` subfolders                  | `COUNT_MISMATCH`    |
| 2   | UC count stats        | `00_DANH_SACH_USE_CASE.md` (26 UCs) vs `UC/README.md` stats section             | `STATS_DESYNC`      |
| 3   | MASTER_INDEX UC Refs  | MASTER_INDEX module rows → UC Refs column vs actual UC files                    | `INDEX_MISMATCH`    |
| 4   | Include relationships | If UC006 includes UC007, does UC007 exist?                                      | `BROKEN_INCLUDE`    |
| 5   | Extend relationships  | If UC010 extends to UC014, does UC014 exist?                                    | `BROKEN_EXTEND`     |
| 6   | Deleted UCs           | UCs listed as deleted (UC005-old, UC018, UC023) should NOT have files           | `ZOMBIE_UC`         |
| 7   | Platform mapping      | `00_DANH_SACH_USE_CASE.md` platform mapping totals vs actual count per platform | `PLATFORM_MISMATCH` |

### Known Inconsistencies (Pre-identified)

> [!WARNING]
> Already identified during skill creation (2026-03-05):
> - `UC/README.md` counts **24 UCs** (stats section) while `00_DANH_SACH_USE_CASE.md` counts **26 UCs** — `STATS_DESYNC`
> - `UC/README.md` Mobile platform lists 20 UCs but misses UC005 and UC009 — `PLATFORM_MISMATCH`
> - MASTER_INDEX lists UC001-UC004 for AUTH module but Authentication folder has 6 files (UC001-UC005 + UC009) — `INDEX_MISMATCH`
> These MUST be flagged and tracked in every audit report.

---

## Gap Classification Summary

| Code                | Meaning                                   | Severity | Action                               |
| ------------------- | ----------------------------------------- | -------- | ------------------------------------ |
| `UC_NO_TASK`        | UC has no JIRA Story/Epic                 | HIGH     | Create JIRA task or justify omission |
| `TASK_NO_UC`        | JIRA Story refs missing UC                | MEDIUM   | Write missing UC or update Story     |
| `EPIC_NO_UC`        | Epic without UC (non-infra)               | MEDIUM   | Verify intentional or create UC      |
| `MISSING_COLUMN`    | UC field not in SQL schema                | HIGH     | Add column to SQL or update UC       |
| `ORPHAN_COLUMN`     | SQL column not used by any UC             | LOW      | Verify if indirect use or remove     |
| `WEAK_COVERAGE`     | UC mentions topic but not specific fields | MEDIUM   | Update UC to be explicit             |
| `TYPE_MISMATCH`     | Data type conflict UC vs SQL              | MEDIUM   | Align UC description or SQL type     |
| `COUNT_MISMATCH`    | UC count differs between sources          | HIGH     | Synchronize all sources              |
| `STATS_DESYNC`      | Statistics differ between index files     | MEDIUM   | Update outdated file                 |
| `INDEX_MISMATCH`    | MASTER_INDEX UC Refs are incomplete       | MEDIUM   | Update MASTER_INDEX                  |
| `BROKEN_INCLUDE`    | Included UC doesn't exist                 | HIGH     | Create missing UC or fix reference   |
| `BROKEN_EXTEND`     | Extended UC doesn't exist                 | HIGH     | Create missing UC or fix reference   |
| `ZOMBIE_UC`         | Deleted UC still has a file               | LOW      | Remove file or un-delete             |
| `PLATFORM_MISMATCH` | Platform UC count doesn't match           | MEDIUM   | Update platform mapping              |

---

## Report Priority Matrix

When generating recommendations, use this priority order:

1. **P0 — Urgent**: `BROKEN_INCLUDE`, `BROKEN_EXTEND`, `COUNT_MISMATCH` (data integrity)
2. **P1 — High**: `UC_NO_TASK`, `MISSING_COLUMN`, `STATS_DESYNC` (completeness gaps)
3. **P2 — Medium**: `TASK_NO_UC`, `EPIC_NO_UC`, `WEAK_COVERAGE`, `INDEX_MISMATCH`, `TYPE_MISMATCH`, `PLATFORM_MISMATCH`
4. **P3 — Low**: `ORPHAN_COLUMN`, `ZOMBIE_UC` (cleanup items)
