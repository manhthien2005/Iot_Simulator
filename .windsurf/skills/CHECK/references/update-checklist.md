# Update Checklist — CHECK Skill

> Checklist for AI executing the CHECK skill. Ensures no steps are missed.

---

## Phase 1: Project_Structure.md

### Tree Structure
- [ ] Scan actual folder structure using `list_dir` (depth 3-4)
- [ ] Compare tree in file vs actual
- [ ] Add new folders/files to tree
- [ ] Remove folders/files that no longer exist
- [ ] Update comments/annotations in tree

### Modules & Features
- [ ] Verify each module: name, SRS Ref, Sprint
- [ ] Replace "Trello" → "JIRA: {Epic Name}" (lookup from JIRA Index)
- [ ] Read route files → confirm endpoints actually exist
- [ ] Update status (✅/⬜/⚠️) based on actual code
- [ ] Update "Related Files" — add new files, remove missing ones

### Metadata
- [ ] Update "Last Updated" → current date
- [ ] Update "Review Progress" if new reviews exist
- [ ] Add new entry to changelog table

---

## Phase 2: Summaries

### For EACH summary file:
- [ ] Read current summary
- [ ] Scan corresponding source code (view_file_outline, list_dir)
- [ ] Confirm actual API endpoints
- [ ] Confirm actual file paths + update LOC
- [ ] Map Trello → JIRA Epic Name (use JIRA Index)
- [ ] Rewrite using `references/summary-template.md`
- [ ] Remove: Trello checklist, verbose SRS, generic NFRs, emoji headers, empty sections
- [ ] Keep: identity, JIRA refs, purpose/technique, API index, file index, issues, cross-refs
- [ ] Add Known Issues if new problems discovered
- [ ] **OVERWRITE the old summary file directly**

### After all summaries are done:
- [ ] Check MASTER_INDEX.md — any modules need updating?
- [ ] Produce changelog summary for user

---

## JIRA Mapping Quick Reference

> Quick lookup: Module → JIRA Epic Name.
> Source: `PM_REVIEW/Resources/TASK/JIRA/README.md`

### ADMIN Modules
| Module      | JIRA Epics                               |
| ----------- | ---------------------------------------- |
| AUTH        | EP04-Login, EP05-Register, EP12-Password |
| ADMIN_USERS | EP15-AdminManage                         |
| DEVICES     | EP15-AdminManage                         |
| CONFIG      | EP16-AdminConfig                         |
| LOGS        | EP16-AdminConfig                         |
| INFRA       | EP01-Database, EP02-AdminBE              |

### MOBILE Modules
| Module       | JIRA Epics                                   |
| ------------ | -------------------------------------------- |
| AUTH         | EP04-Login, EP05-Register, EP12-Password     |
| DEVICE       | EP07-Device                                  |
| INFRA        | EP01-Database, EP03-MobileBE, EP06-Ingestion |
| MONITORING   | EP08-Monitoring                              |
| EMERGENCY    | EP09-FallDetect, EP10-SOS                    |
| NOTIFICATION | EP11-Notification                            |
| ANALYSIS     | EP13-RiskScore                               |
| SLEEP        | EP14-Sleep                                   |
