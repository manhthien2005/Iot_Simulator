# 📱 Screen Spec Template

> Use this template in **mode TASK** to create spec files for each screen.
> Save to: `PM_REVIEW/REVIEW_MOBILE/Screen/[MODULE]_[ScreenName].md`
> Naming: `AUTH_Login.md`, `EMERGENCY_SOSConfirm.md`, `MONITORING_VitalDetail.md`

```markdown
# 📱 [MODULE] — [Screen Name]

> **UC Ref**: UC0XX, UC0YY
> **Module**: [AUTH/DEVICE/MONITORING/...]
> **Status**: ⬜ Draft | 🔄 In Progress | ✅ Done

## Purpose
[1-2 sentences clearly describing what this screen DOES]

## Navigation Links (🔗 Related Screens)
| From Screen                           | Action            | To Screen                                               |
| ------------------------------------- | ----------------- | ------------------------------------------------------- |
| [HOME_Dashboard](./HOME_Dashboard.md) | Tap "Vital Signs" | → This screen                                           |
| This screen                           | Tap item detail   | → [MONITORING_VitalDetail](./MONITORING_VitalDetail.md) |
| This screen                           | Back button       | → [HOME_Dashboard](./HOME_Dashboard.md)                 |

## User Flow
1. ...
2. ...

## UI States
| State   | Description | Display |
| ------- | ----------- | ------- |
| Loading | ...         | ...     |
| Empty   | ...         | ...     |
| Success | ...         | ...     |
| Error   | ...         | ...     |

## Edge Cases
- [ ] ...

## Data Requirements
- API endpoint: `GET /api/mobile/...`
- Input: ...
- Output: ...

## Sync Notes
- When [Screen A] changes X → This screen needs to update Y
- Shared widgets used: ...

## Design Context
- **Target audience**: [Elderly patient / All users / Caregiver only]
- **Usage context**: [Emergency / Routine monitoring / Setup / Configuration]
- **Key UX priority**: [Speed / Clarity / Calm / Trust]
- **Specific constraints**: [e.g., "Used while panicking", "Dark room possible", "Hands may be trembling"]

## Pipeline Status
| Stage  | Status        | File      |
| ------ | ------------- | --------- |
| TASK   | ✅ Done        | This file |
| PLAN   | ⬜ Not started | —         |
| BUILD  | ⬜ Not started | —         |
| REVIEW | ⬜ Not started | —         |

## Changelog
| Version | Date       | Author  | Changes          |
| ------- | ---------- | ------- | ---------------- |
| v1.0    | YYYY-MM-DD | AI/User | Initial creation |
```
