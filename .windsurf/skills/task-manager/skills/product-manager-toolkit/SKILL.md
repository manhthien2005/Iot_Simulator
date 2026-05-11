---
name: product-manager-toolkit
description: "Prioritization frameworks (RICE, MoSCoW) and capacity planning tools for Sprint structuring. Determines optimal Sprint groupings based on team velocity and dependency constraints."
---

# Product Manager Toolkit — Prioritization & Capacity Planning

## Goal

Apply structured prioritization frameworks to rank tasks, group them into optimal Sprints, and ensure capacity constraints are respected.

## Instructions

### RICE Scoring (When detailed prioritization is needed)

```
RICE Score = (Reach × Impact × Confidence) / Effort

Reach: Number of users affected per Sprint
Impact: 
  - Massive = 3x (core product functionality)
  - High = 2x (important feature)
  - Medium = 1x (useful addition)
  - Low = 0.5x (minor improvement)
  - Minimal = 0.25x (cosmetic)
Confidence:
  - High = 100% (well-defined UC, clear requirements)
  - Medium = 80% (some ambiguity)
  - Low = 50% (exploratory, unclear scope)
Effort: Story Points
```

### MoSCoW Classification

| Category        | Description                                | Action     |
| --------------- | ------------------------------------------ | ---------- |
| **Must Have**   | MVP-critical, system won't work without it | Sprint 1-2 |
| **Should Have** | Important but system works without it      | Sprint 2-3 |
| **Could Have**  | Nice to have, enhances experience          | Sprint 3-4 |
| **Won't Have**  | Out of scope for current release           | Backlog    |

### Sprint Capacity Planning

**Inputs:**
- Team velocity: ~32 SP/Sprint (from historical data)
- Sprint duration: 2 weeks
- Buffer: 20% for unexpected work

**Capacity formula:**
```
Available SP = Team Velocity × 0.8 (buffer)
             = 32 × 0.8 = ~26 effective SP

If Sprint has heavy infra tasks: allow up to 42 SP (Sprint 1 pattern)
If Sprint has integration-heavy tasks: cap at 26 SP
```

**Grouping rules:**
1. Never split an Epic across Sprints (all stories of one Epic in same Sprint)
2. Dependencies must be in earlier Sprints
3. Mix BE + FE + QA stories for balanced workload
4. Max 6 Epics per Sprint (cognitive load limit)

## Output

Sprint allocation table:
```markdown
| Sprint | Theme           | Epics     | Total SP | Rationale                      |
| ------ | --------------- | --------- | -------- | ------------------------------ |
| 5      | Admin Dashboard | EP17-EP19 | ~38      | Dependencies resolved in S1-S4 |
```
