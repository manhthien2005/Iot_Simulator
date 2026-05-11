# 📱 Screen Index Template (README.md)

> Use this template in **mode TASK** to create/update `README.md` in the `Screen` folder.
> MANDATORY update on every TASK run.

```markdown
# 📱 Screen Index — HealthGuard Mobile

> Last updated: [date]
> Total screens: X | Designed: Y | In development: Z | Reviewed: W

## Navigation Overview
[Mermaid flowchart showing main flow between screens — if needed]

## AUTH Module (UC001-UC004)
| #   | Screen   | File                                   | UC Ref | Status | Linked Screens           |
| --- | -------- | -------------------------------------- | ------ | ------ | ------------------------ |
| 1   | Login    | [AUTH_Login.md](./AUTH_Login.md)       | UC001  | ✅ Done | → Dashboard, → ForgotPwd |
| 2   | Register | [AUTH_Register.md](./AUTH_Register.md) | UC002  | 🔄 WIP  | → VerifyEmail            |

## DEVICE Module (UC040-UC042)
| #   | Screen | File | UC Ref | Status | Linked Screens |
| --- | ------ | ---- | ------ | ------ | -------------- |
| ... | ...    | ...  | ...    | ...    | ...            |

## MONITORING Module (UC006-UC008)
| #   | Screen | File | UC Ref | Status | Linked Screens |
| --- | ------ | ---- | ------ | ------ | -------------- |
| ... | ...    | ...  | ...    | ...    | ...            |

## EMERGENCY Module (UC010-UC015)
| #   | Screen | File | UC Ref | Status | Linked Screens |
| --- | ------ | ---- | ------ | ------ | -------------- |
| ... | ...    | ...  | ...    | ...    | ...            |

## NOTIFICATION Module (UC030-UC031)
| #   | Screen | File | UC Ref | Status | Linked Screens |
| --- | ------ | ---- | ------ | ------ | -------------- |
| ... | ...    | ...  | ...    | ...    | ...            |

## ANALYSIS Module (UC016-UC017)
| #   | Screen | File | UC Ref | Status | Linked Screens |
| --- | ------ | ---- | ------ | ------ | -------------- |
| ... | ...    | ...  | ...    | ...    | ...            |

## SLEEP Module (UC020-UC021)
| #   | Screen | File | UC Ref | Status | Linked Screens |
| --- | ------ | ---- | ------ | ------ | -------------- |
| ... | ...    | ...  | ...    | ...    | ...            |
```

---

## TASK Report Template

> Output this report after EVERY TASK mode run.

```
📋 TASK Report:
- Total screens discovered from SRS: X
- Screen specs already exist: Y/X
- Newly created this run: Z (list names)
- Edited this run: W (list names + reason)
- Sync issues found: ... (fixed / needs user decision)
- README.md updated: ✅

Which module's screen specs should I create next?
```
