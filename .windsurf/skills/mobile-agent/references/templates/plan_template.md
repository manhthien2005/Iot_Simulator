# 📐 UI Plan Template

> Use this template when running **mode PLAN**. Fill in specifics for each screen.
> Save the output file to: `PM_REVIEW/REVIEW_MOBILE/Screen/build-plan/[MODULE]_[ScreenName]_plan.md`

```markdown
# 📐 UI Plan: [Screen Name]

## 1. Description
- **SRS Ref**: UC0XX
- **User Role**: Patient / Caregiver
- **Purpose**: [1 sentence]

## 2. User Flow
1. User opens app → ...
2. User taps ... → ...
3. System displays ... → ...

## 3. UI States
| State   | Description       | Display               |
| ------- | ----------------- | --------------------- |
| Loading | Fetching data     | Skeleton shimmer      |
| Empty   | No data available | Illustration + CTA    |
| Success | Data loaded       | List/Card/Chart       |
| Error   | API/network error | Error message + Retry |

## 4. Widget Tree (proposed)
- `Scaffold`
  - `AppBar` → title, back button
  - `Body` → ...

## 4.5. Visual Design Spec
### Colors
| Role       | Token / Value       | Usage in this screen |
| ---------- | ------------------- | -------------------- |
| Primary BG | `Colors.surface`    | Scaffold background  |
| Accent     | `AppColors.primary` | CTA button           |

### Typography
| Element    | Size | Weight  | Color            |
| ---------- | ---- | ------- | ---------------- |
| Page title | 24sp | Bold    | onSurface        |
| Body text  | 16sp | Regular | onSurfaceVariant |

### Spacing
- Screen padding: `16dp` horizontal
- Card gap: `12dp`
- Section gap: `24dp`

## 4.6. Interaction & Animation Spec
| Trigger            | Animation / Behavior  | Duration |
| ------------------ | --------------------- | -------- |
| Screen enter       | Slide from right      | 300ms    |
| Button press       | Scale 0.95 + ripple   | 150ms    |
| Swipe left on card | Dismiss with fade-out | 200ms    |

## 4.7. Accessibility Checklist
- [ ] Min font 16sp (body), 14sp (caption) — no exceptions
- [ ] Min touch target 48dp × 48dp for all interactive elements
- [ ] Contrast ratio ≥ 4.5:1 (text), ≥ 3:1 (icons/graphics)
- [ ] TalkBack/VoiceOver: all interactive elements have semantic label
- [ ] No information conveyed by color alone
- [ ] Elderly UX: key actions reachable with one thumb (bottom half of screen)

## 4.8. Design Rationale
| Decision | Reason |
| -------- | ------ |
| [e.g., Red background] | [e.g., Universal emergency color] |

## 5. Edge Cases Handled
- [ ] Network loss mid-operation
- [ ] Data too long / too short

## 6. Dependencies
- Shared widgets needed: [list]
- API endpoints: [list]

## 7. Confidence Score
- **Plan Confidence: X%**
- Reasoning: [Brief explanation of confidence level]
- Uncertainties: [List any areas where more info would help]
```
