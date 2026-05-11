---
name: business-analyst
description: "Structured analysis of Use Cases, requirements documents, and system specifications. Extracts complexity signals, identifies dependencies, and estimates effort for project planning."
---

# Business Analyst — UC Complexity Extraction

## Goal

Analyze UC documents to extract structured complexity signals that can be used for Story Point estimation and dependency mapping.

## Instructions

### Step 1: Parse UC Structure
For each UC file, extract:
- **Main Flow Step Count** — More steps = higher complexity
- **Alternative Flow Count** — Each alt flow adds ~1 SP
- **Business Rules Count** — Complex rules add ~0.5 SP each
- **Data Fields Count** — More fields = more validation work
- **External Integrations** — Each integration adds ~2-3 SP
- **NFR Requirements** — Performance/Security NFRs add testing overhead

### Step 2: Complexity Classification

| Signal          | Simple (1-2 SP) | Medium (3-5 SP) | Complex (8-13 SP) |
| --------------- | --------------- | --------------- | ----------------- |
| Main Flow Steps | ≤5              | 6-10            | >10               |
| Alt Flows       | 0-1             | 2-4             | >4                |
| Business Rules  | 0-2             | 3-5             | >5                |
| Data Fields     | ≤3              | 4-8             | >8                |
| Integrations    | 0               | 1               | 2+                |

### Step 3: Dependency Identification
Look for these patterns in UC text:
- **"<<include>>"** → Hard dependency (must complete first)
- **"<<extend>>"** → Soft dependency (optional enhancement)
- **"Tiền điều kiện" / Preconditions** → Implicit dependencies
- **Shared data tables** → Data-level dependency

## Output Format

```markdown
| UC    | Complexity | Est. SP | Dependencies | Key Signals                 |
| ----- | ---------- | ------- | ------------ | --------------------------- |
| UC001 | Medium     | 5       | None         | 8 steps, 3 alt flows, JWT   |
| UC002 | Medium     | 4       | UC001        | 7 steps, email verification |
```
