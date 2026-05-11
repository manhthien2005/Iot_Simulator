---
description: Orchestrate a feature spanning multiple VSmartwatch repos. Build dependency DAG, sequence work producer-first, manage cross-repo branches and contracts.
---

# /cross-repo-feature — Cross-Repo Feature Orchestration

> "Producer ships before consumer." VSmartwatch là distributed system — feature thường touch 2-4 repos. Workflow này manage sequencing để tránh broken contracts in transit.

Use when:
- Feature affects ≥ 2 repos (vd: fall detection touches mobile + BE + model API + IoT sim).
- API contract change ripples cross-repo.
- DB schema change requires producer + consumer + migration coordination.

## Pre-flight

1. **Invoke skills:** `writing-plans`, `decision-log` (ADR for cross-repo contract).
2. **Inputs:**
   - UC ID: `UC<XXX>` (must exist in `PM_REVIEW/Resources/UC/`)
   - Spec doc (if non-trivial): `<repo>/docs/specs/<file>.md`
3. **Read** `PM_REVIEW/tooling/.windsurf-template/topology.md` — boundary contracts cheat sheet.

## Phase 1 — Map repo impact

For each repo in workspace, classify role:

| Role | Question | Examples |
|---|---|---|
| **Spec owner** | Where is canonical UC/SQL? | PM_REVIEW |
| **Schema owner** | Who owns DB migration? | HealthGuard (Prisma) — sync với PM_REVIEW SQL canonical |
| **Producer** | Who exposes new contract (API/event)? | health_system/backend, healthguard-model-api |
| **Consumer** | Who calls the new contract? | health_system/lib (mobile), HealthGuard/frontend, Iot_Simulator_clean |
| **No change** | Repo not affected? | Skip |

Output: matrix table.

```markdown
| Repo | Role | Files affected | Notes |
|---|---|---|---|
| PM_REVIEW | Spec owner | Resources/UC/Emergency/UC011.md, SQL SCRIPTS/.../fall_events.sql | Update first |
| HealthGuard | Schema owner | backend/prisma/schema.prisma | Migration `add_fall_severity` |
| health_system/backend | Producer | app/routers/fall.py, app/services/fall_service.py | New endpoint POST /api/mobile/fall/severity |
| healthguard-model-api | Producer | app/routers/predict.py | New severity field in response |
| health_system/lib | Consumer | lib/features/emergency/data/repositories/fall_repository.dart | Update repo call + UI |
| Iot_Simulator_clean | Consumer | transport/http_publisher.py | New field in trigger payload |
```

## Phase 2 — Build dependency DAG

Order:

```
1. PM_REVIEW (spec/UC/SQL canonical)
   ↓
2. DB migration (Prisma + sync SQL canonical)
   ↓
3. Producer side (Python BE / model API)
   ↓
4. Consumer side (mobile / admin frontend / IoT sim)
   ↓
5. E2E smoke test
   ↓
6. Tag release across all repos
```

**Rule:** producer ships + verified BEFORE consumer migrates to new contract. Otherwise consumer crashes on launch.

## Phase 3 — Define cross-repo contract

Document the contract IN ONE PLACE — `PM_REVIEW/CONTRACTS/<feature>-<version>.md`:

```markdown
# Contract: <Feature> v<X>

**Date:** YYYY-MM-DD
**Status:** Draft → Locked → Implemented → Live

## Endpoint
POST `/api/mobile/fall/severity`

## Request
```json
{
  "user_id": "string (UUID)",
  "event_id": "string (UUID)",
  "raw_severity_score": "number (0.0-1.0)"
}
```

## Response 200
```json
{
  "event_id": "string",
  "classified_severity": "low | medium | high",
  "recommended_action": "monitor | alert | sos"
}
```

## Errors
- 400: validation
- 401: missing X-Internal-Secret
- 500: prediction failure (sanitized)

## Producer contract
- Pydantic schema: `health_system/backend/app/models/fall.py::FallSeverityRequest`
- Service: `app/services/fall_service.py::classify_severity`

## Consumer contract
- Mobile: `lib/features/emergency/data/models/fall_severity.dart`
- IoT sim: `transport/http_publisher.py::publish_fall_severity`

## Versioning
- v1: this version
- Backward compat: 30 days after v2 ships
```

ADR if contract represents big architectural choice (e.g., REST vs gRPC, push vs pull).

## Phase 4 — Branch strategy across repos

Same branch name in each affected repo (sync via convention):

```
feat/fall-severity-classification
```

In each repo:
```pwsh
git -C <repo> checkout <trunk>
git -C <repo> pull origin <trunk>
git -C <repo> checkout -b feat/fall-severity-classification
```

**Cấm:** start coding before all branches created (avoid trunk drift).

## Phase 5 — Sequenced execution

### Step 5.1 — Spec/UC update (PM_REVIEW)

Run `/spec` if UC needs update.
Commit + push branch in PM_REVIEW.

### Step 5.2 — DB migration (HealthGuard or PM_REVIEW SQL)

```pwsh
cd HealthGuard\backend
npx prisma migrate dev --name add_fall_severity
# Migration auto-generated in prisma/migrations/

# Sync canonical
# Update PM_REVIEW/SQL SCRIPTS/init_full_setup.sql to reflect post-migration state
# Add PM_REVIEW/SQL SCRIPTS/migrations/YYYYMMDD_add_fall_severity.sql for non-Prisma backends
```

Test against test DB. Commit migration.

### Step 5.3 — Producer side

Implement Pydantic schema + service + router per `/build` workflow + skill `fastapi-patterns`.

**Verification:**
```pwsh
cd <producer-repo>
pytest tests/test_fall_severity.py
uvicorn app.main:app --port 8000
# Manual: curl test endpoint with valid X-Internal-Secret + sample payload
```

Commit + push producer branch. **Do not merge yet.** Consumer needs to test against producer first.

### Step 5.4 — Consumer side

Implement mobile/admin/IoT sim repo to call new contract.

**Verification:** producer running locally → consumer makes real call → assert response shape.

Commit + push consumer branch.

### Step 5.5 — E2E smoke test

End-to-end flow:
- IoT sim trigger → mobile backend → model API → mobile app → confirms display.
- Run via `Iot_Simulator_clean/scripts/e2e_*.ps1` if available.

### Step 5.6 — Tag release across repos

```pwsh
$tag = "release/fall-severity-$(Get-Date -Format yyyy-MM-dd)"
foreach ($r in @('PM_REVIEW','HealthGuard','health_system','healthguard-model-api','Iot_Simulator_clean')) {
  git -C "d:\DoAn2\VSmartwatch\$r" tag $tag
  git -C "d:\DoAn2\VSmartwatch\$r" push origin $tag
}
```

## Phase 6 — Merge order

Merge PRs in dependency order:
1. PM_REVIEW (no runtime impact, safe first)
2. HealthGuard (Prisma migration applied to dev DB on merge — verify staging first)
3. Producer repos
4. Consumer repos

DON'T merge consumer before producer is live in target environment.

## Phase 7 — Decision log

Write ADR if cross-repo contract represents significant choice:
- ADR-<NNN>: why this contract shape.
- Why versioning strategy (no version vs URL prefix vs header).
- How rollback works.

## Phase 8 — Output

- ✅ Repo impact matrix in plan doc
- ✅ Contract documented in `PM_REVIEW/CONTRACTS/<feature>-<version>.md`
- ✅ Branches sync-named across affected repos
- ✅ Producer ships + verified before consumer
- ✅ E2E smoke test pass
- ✅ Tag release across all affected repos
- ✅ ADR if architectural decision made

## Anti-patterns

| Pattern | Risk |
|---|---|
| Consumer ships before producer | Consumer crashes on launch (404 endpoint) |
| Skip contract doc | Producer + consumer drift; integration breaks silently |
| Different branch names per repo | Hard to track which branches belong to feature |
| Skip E2E smoke test | Integration bugs discovered by users |
| Merge consumer before producer staging-verified | Production drift |
| Hardcode endpoint URL in consumer | URL change ripples to consumer; use config |
| DB migration without producer + consumer ready | Schema mismatch crashes |

## Recovery if integration fails mid-feature

If consumer fails against producer:
1. Hold consumer at last working version on its branch.
2. Fix producer + re-deploy producer staging.
3. Resume consumer development.
4. Document in `PM_REVIEW/BUGS/XR-<NUM>.md` if non-trivial.
