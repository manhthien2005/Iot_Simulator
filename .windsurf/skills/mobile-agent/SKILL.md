---
name: mobile-agent
description: |
  Manage screen spec lifecycle for VSmartwatch mobile app — generate from UC/SRS,
  edit, cross-link, and maintain the Screen Index. Use when user says
  "list all screens", "quản lý màn hình", "scan screens", "generate screen spec",
  "kiểm tra screen index", "sync screens", or "TASK <subcommand>".
risk: safe
source: custom
date_added: "2026-03-10"
date_updated: "2026-05-11"
version: "4.0"
---

# Goal

Maintain a **complete, gap-free, cross-linked inventory** of mobile screens — auto-generated from UC/SRS, kept in sync with code reality.

> **v4.0 scope reduction (2026-05-11):** Previously had PLAN/BUILD/REVIEW modes — those duplicated `/build` and `/review` workflows + `flutter-mobile-patterns` skill. Removed. **Keep TASK mode only** as it has unique screen-spec-management value.

## When to use

- Scan UC/SRS to discover required screens.
- Generate spec file for a new screen.
- Sync existing screen specs after UC changes (call `/sync-spec` workflow first).
- Cross-link integrity check (no orphan screens, no broken navigation links).
- Update Screen Index (`PM_REVIEW/REVIEW_MOBILE/Screen/README.md`).

**For UI design → use `/spec` workflow + skill `flutter-mobile-patterns`.**
**For UI implementation → use `/build` workflow.**
**For UI review → use `/review` workflow + `code-review-five-axis` skill.**

## Sub-commands

| Sub-command | What it does | Steps |
|---|---|---|
| `TASK scan` | Discover screens from SRS, report gaps | 1 only |
| `TASK generate [module]` | Create missing screen specs for module | 1 → 2 |
| `TASK update [screen]` | Edit specific screen spec | 3 only |
| `TASK sync` | Validate cross-links, fix issues | 4 only |
| `TASK full` | Complete pipeline (default if no sub-command) | 1 → 2 → 3 → 4 → 5 |

> ⚡ **Special permission:** TASK mode is the ONLY skill with write access to screen `.md` files in `PM_REVIEW/REVIEW_MOBILE/Screen/`.

## Process

### Step 1: Scan & Discover

1. Read `PM_REVIEW/MASTER_INDEX.md` (project GPS).
2. Read `PM_REVIEW/Resources/SRS_INDEX.md` (system context).
3. Read `PM_REVIEW/Resources/UC/00_DANH_SACH_USE_CASE.md` (UC inventory).
4. For each module (AUTH, DEVICE, MONITORING, EMERGENCY, NOTIFICATION, ANALYSIS, SLEEP, ADMIN):
   - List every UC.
   - Identify every screen required (1 UC may need multiple — main + dialog + error overlay).
   - Detect hidden screens (confirmation dialogs, error states, empty illustrations).
5. Compare discovered list vs existing files in `PM_REVIEW/REVIEW_MOBILE/Screen/`.
6. Report: total found, exist, missing.

### Step 2: Generate Screen Specs

For each screen without a file:

- **Path:** `PM_REVIEW/REVIEW_MOBILE/Screen/[MODULE]_[ScreenName].md`
- **Naming:** `AUTH_Login.md`, `EMERGENCY_SOSConfirm.md`, `MONITORING_VitalDetail.md`
- **Template:** `references/templates/screen_spec_template.md`

⚠️ **Architecture rule:** Use unified `User` role + `Linked Profiles` (Profile Switcher) mechanism. **Cấm** dùng deprecated `patient`/`caregiver` functional roles.

### Step 3: Edit & Update Screen Specs

When user requests update or `/sync-spec` detected UC change:

1. Read current screen file + compare against latest UC/SRS.
2. Update content directly (fix flows, states, API endpoints).
3. Update navigation links — when adding new screen, scan related screens and add **bidirectional cross-links**.
4. Log changes in screen file's `## Sync Notes` section.

### Step 4: Sync Validation (cross-link integrity)

Scan all files in `Screen/`:

| Check | Description | Action on failure |
|---|---|---|
| **Orphan Screen** | Screen file exists but no UC references it | ⚠️ Warn — may be obsolete |
| **Missing Screen** | UC requires it but no screen file exists | 🔴 Create immediately |
| **Broken Link** | Screen A links to Screen B but B doesn't exist | 🔴 Create B or fix link |
| **One-way Link** | A → B but B doesn't link back | 🟡 Add reverse link |
| **Stale API** | Endpoint in screen file doesn't match `Project_Structure.md` | 🟡 Update |

### Step 5: Update Screen Index README

**Mandatory** on every TASK run. Update `PM_REVIEW/REVIEW_MOBILE/Screen/README.md`.

**Template:** `references/templates/screen_index_template.md`

Index includes:
- Total screens per module + status
- UC mapping (which UC each screen serves)
- Cross-references (linked screens)
- Last-updated dates

## Output report

After TASK run, display:

```
## TASK Report — YYYY-MM-DD

- Total screens discovered from SRS: 40
- Screen specs already exist: 38/40
- Newly created: 2 (EMERGENCY_FallAlert, NOTIFICATION_FCMInbox)
- Updated: 1 (AUTH_Login — fixed AF1 reference)
- Broken links found: 0
- Orphan screens: 1 (DEVICE_LegacyConnect — flag for removal)
- README.md updated: ✅
```

## Constraints

### Code safety
- 🚫 **NEVER** overwrite existing screen file without showing diff preview when changes affect ≥ 5 lines.
- 🚫 **NEVER** delete screen file — only create or modify. Mark obsolete with `## Status: ⚠️ Obsolete` instead.

### Architecture
- ✅ **ALWAYS** use unified `User` role + `Linked Profiles` (Profile Switcher) mechanism.
- 🚫 **NEVER** use deprecated `patient`/`caregiver` terminology.

### Spec consistency
- ✅ **ALWAYS** include all 4 UI States (Loading, Empty, Success, Error) in screen spec.
- ✅ **ALWAYS** handle network-loss edge case (medical app = critical).

### Accessibility (medical app — mandatory)
- Min font size: **16sp** (body), **14sp** (caption)
- Min touch target: **48dp × 48dp** (56dp for emergency UI)
- Min contrast ratio: **4.5:1** (WCAG AA)
- TalkBack/VoiceOver semantic labels for all interactive elements

## References

| File | Purpose |
|---|---|
| [screen_spec_template.md](./references/templates/screen_spec_template.md) | Template for individual screen spec |
| [screen_index_template.md](./references/templates/screen_index_template.md) | Template for Screen Index README |

## Cross-skill / cross-workflow

| Need | Use |
|---|---|
| Design UI for screen | `/spec` workflow + `flutter-mobile-patterns` skill |
| Implement screen | `/build` workflow + `flutter-mobile-patterns` skill |
| Review screen code | `/review` workflow + `code-review-five-axis` skill |
| Audit feature quality | `detailed-feature-review` skill |
| Project-level mobile overview | `TongQuan` skill (mode MOBILE) |
| Sync screens after UC change | `/sync-spec` workflow → THEN `mobile-agent TASK update` |
