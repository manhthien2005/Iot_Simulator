---
description: Deploy VSmartwatch services per stack (Flutter store, Express BE, FastAPI BE, React frontend, DB migration). Stack-aware checklist with rollback.
---

# /deploy — Deploy Workflow (VSmartwatch)

> **Deploy = production impact.** Always: pre-flight → staging → smoke test → production → monitor. Never skip steps.

> **Solo dev note:** Anh chưa khoá deploy strategy cho từng stack (đồ án 2). Workflow này là **skeleton** — verify actual commands per anh's hosting choice. Mark TODO trong ADR (`PM_REVIEW/ADR/`).

## Pre-flight (ALL deploys)

### 1. Verify branch + working tree

```pwsh
git -C <repo> branch --show-current
git -C <repo> status --short          # MUST be empty
git -C <repo> log -1 --oneline
```

### 2. Sanity checks

- [ ] All tests pass (per stack — see `/test` workflow):
  - Flutter: `flutter test ; flutter analyze`
  - FastAPI: `pytest`
  - Express: `npm test ; npm run lint`
  - React: `npm test ; npm run lint`
- [ ] No secret committed:
  ```pwsh
  git -C <repo> ls-files | Select-String -Pattern "(\.env$|prod\.env|serviceaccount|\.keystore$|\.jks$|google-services\.json|GoogleService-Info\.plist)"
  # Empty = OK. If anh's stack drops Firebase later, remove google-services entries.
  # Expect: empty
  ```
- [ ] Migration / schema change committed (if applicable) — see Path E.
- [ ] CHANGELOG / release note updated.
- [ ] Rollback plan written (commit hash to revert to + DB rollback script).

### 3. Backup tag

```pwsh
git -C <repo> tag pre-deploy-$(Get-Date -Format yyyy-MM-dd-HHmm)
git -C <repo> push origin --tags
```

## Path A: Mobile app (Flutter — health_system)

### Build release

```pwsh
cd d:\DoAn2\VSmartwatch\health_system

# Bump version in pubspec.yaml first: version: X.Y.Z+build
flutter clean   # only if pubspec or platform/native changed (per anh's rule, confirm before run)
flutter pub get

# Android
flutter build apk --release
flutter build appbundle --release

# iOS (requires macOS + Xcode)
flutter build ipa --release
```

### Pre-store checklist

- [ ] App icon + splash updated.
- [ ] Manifest permissions reviewed (location, FCM, sensor, full-screen intent).
- [ ] ProGuard/R8 rules don't strip needed classes (test release APK on device).
- [ ] Release notes drafted (Vietnamese + English).
- [ ] Screenshots updated for store listing.

### Submit

**TODO (anh fill in):** anh's chosen track — Internal testing → Closed beta → Production?

```pwsh
# Google Play (TODO: chosen workflow — Play Console upload manual hay fastlane?)
# fastlane supply --apk build/app/outputs/bundle/release/app-release.aab --track internal

# App Store (TODO: chosen workflow)
# fastlane pilot upload
```

### Post-deploy

- Monitor crash reports (FCM error, native crash) for 24h.
- Smoke test: install fresh on test device, login, trigger fall, confirm SOS.
- Rollback: previous version on Play Console (re-promote old AAB).

## Path B: Admin Backend (Express+Prisma — HealthGuard/backend)

```pwsh
cd d:\DoAn2\VSmartwatch\HealthGuard\backend
npm install
npm run lint
npm test
```

### Migration first (if schema change)

```pwsh
# Production migration — verify staging worked
npx prisma migrate deploy
```

⚠️ **Cấm:** `prisma migrate dev` against production. `dev` shadow-DB pattern is destructive.

### Deploy

**TODO (anh fill in):** anh's chosen hosting:
- Option 1: VPS + PM2 + Nginx reverse proxy
- Option 2: Docker + Docker Compose
- Option 3: Render / Railway / Fly.io PaaS
- Option 4: AWS EC2 / ECS

```pwsh
# Example for PM2 (placeholder)
# ssh user@server
# git pull
# npm ci --production
# npx prisma migrate deploy
# npx prisma generate
# pm2 reload ecosystem.config.js --env production
```

### Post-deploy

- [ ] Endpoint smoke test:
  ```pwsh
  curl -i https://<api-domain>/health
  curl -i -H "Authorization: Bearer <admin-jwt>" https://<api-domain>/api/admin/users
  ```
- [ ] Log monitor 15-30 min: no new error patterns.
- [ ] DB connection healthy (Prisma logs no `Cannot reach database`).
- [ ] Audit log entries normal rate.

### Rollback

```pwsh
# Revert app code
git -C <repo> revert <bad-commit>
# OR redeploy previous tag

# Revert migration (if needed — DESTRUCTIVE)
# Manual SQL rollback per migration file
```

## Path C: Admin Frontend (React+Vite — HealthGuard/frontend)

```pwsh
cd d:\DoAn2\VSmartwatch\HealthGuard\frontend
npm install
npm run lint
npm test
npm run build           # outputs dist/
```

**TODO (anh fill in):** static host:
- Option 1: Nginx serve dist/ on same VPS as backend
- Option 2: S3 + CloudFront
- Option 3: Vercel / Netlify

```pwsh
# Example — rsync to VPS
# rsync -av --delete dist/ user@server:/var/www/healthguard-admin/
# Or: aws s3 sync dist/ s3://<bucket> --delete --cache-control "max-age=31536000"
```

### Post-deploy

- [ ] Hard reload `/` — no console error, no 404 for assets.
- [ ] Login flow works.
- [ ] WebSocket reconnects (vital monitor page).
- [ ] No CORS error in browser console.

## Path D: FastAPI services (health_system/backend, healthguard-model-api, Iot_Simulator_clean)

```pwsh
cd d:\DoAn2\VSmartwatch\<repo>
pytest
black --check . ; isort --check-only .
```

### Build container (recommended)

```pwsh
# TODO: Dockerfile per repo not yet committed — anh chuẩn bị khi deploy
# docker build -t healthguard/<repo>:<version> .
# docker push <registry>/healthguard/<repo>:<version>
```

### Deploy

**TODO (anh fill in):** chosen hosting:
- Option 1: Docker on VPS (same as Path B)
- Option 2: PaaS (Render, Railway)
- Option 3: AWS Lambda (for stateless model-api)

```pwsh
# Generic systemd reload
# ssh user@server
# cd /opt/<repo>
# git pull
# pip install -r requirements.txt
# systemctl reload <repo>.service
```

### Post-deploy

- [ ] `/health` endpoint returns 200.
- [ ] Test endpoint with sample payload + valid auth header.
- [ ] Log monitor 15 min: no new error.
- [ ] Cross-repo dependency check:
  - mobile-backend deploys → check IoT sim still triggers correctly
  - model-api deploys → check mobile-backend can call predict endpoint

## Path E: Database migration (Postgres)

⚠️ **Schema change = highest risk.** Test against test DB first.

### Steps

1. **Write migration file:**
   - Prisma (HealthGuard): `npx prisma migrate dev --name <desc>` (creates `prisma/migrations/.../migration.sql`)
   - Raw SQL (FastAPI repos): write `PM_REVIEW/SQL SCRIPTS/migrations/YYYYMMDD_<desc>.sql`
2. **Update canonical schema:** `PM_REVIEW/SQL SCRIPTS/init_full_setup.sql` reflects post-migration state.
3. **Test against test DB:**
   ```pwsh
   psql -h localhost -U test -d test_db -f migration.sql
   ```
4. **Backup production DB:**
   ```pwsh
   pg_dump -h <host> -U <user> -d <db> -F c -f backup-$(Get-Date -Format yyyyMMdd-HHmm).dump
   ```
5. **Run on production:**
   ```pwsh
   # Prisma
   npx prisma migrate deploy
   
   # Raw SQL
   psql -h <host> -U <user> -d <db> -f migration.sql
   ```
6. **Verify:**
   ```pwsh
   psql -h <host> -U <user> -d <db> -c "\d <table>"
   psql -h <host> -U <user> -d <db> -c "SELECT COUNT(*) FROM <table>"
   ```

### Rollback (DESTRUCTIVE — verify backup first)

```pwsh
# Restore from dump
pg_restore -h <host> -U <user> -d <db> --clean backup.dump
```

OR write reverse migration SQL (preferable — non-destructive):
```sql
-- migrations/YYYYMMDD_revert_<desc>.sql
ALTER TABLE ... DROP COLUMN ...;
```

## Cross-repo deploy order (full system update)

When change affects multiple repos:

1. **PM_REVIEW** — UC, SRS, SQL canonical (no runtime impact, safe first).
2. **DB migration** — Path E, with backup.
3. **Producer side** — repo that EXPOSES the new contract:
   - Backend new endpoint → deploy backend first.
   - Model API new prediction → deploy model-api first.
4. **Consumer side** — repo that CALLS the new contract:
   - Mobile calls backend → deploy backend, THEN mobile.
   - Backend calls model-api → deploy model-api, THEN backend.
5. **E2E smoke test** — full flow from device → backend → model → response.
6. **Tag release:**
   ```pwsh
   foreach ($r in @('HealthGuard','health_system','...')) {
     git -C $r tag release-<feature>-$(date +%Y%m%d)
     git -C $r push origin --tags
   }
   ```

## Apply skill `verification-before-completion`

Before claiming "deployed":

| Claim | Required evidence |
|---|---|
| "Deployed to staging" | Smoke test endpoint returns 200 + correct shape |
| "Deployed to prod" | Same + log monitor 15-30 min clean |
| "Migration applied" | DB query confirms new column/index exists |
| "Rollback works" | Tested rollback on staging FIRST |

## Anti-patterns

| Anti-pattern | Risk |
|---|---|
| Deploy without staging | Bug discovered by users, not by you |
| Migration without backup | Data loss = catastrophe (medical app) |
| Deploy app before BE contract | Mobile app crashes on launch |
| Skip log monitor | Errors discovered hours later when escalated |
| Deploy on Friday evening | Weekend rollback nightmare |
| Hardcode prod URL/secret | Leaked = security breach |
| Skip rollback plan | "Hope" is not a strategy |

## Open TODOs for anh

When deploy strategy is finalized, update this workflow + write ADR:

- [ ] `PM_REVIEW/ADR/<num>-deploy-strategy.md` — record actual hosting + rationale.
- [ ] Replace TODO blocks with real commands.
- [ ] CI/CD pipeline (optional) — GitHub Actions per repo.
- [ ] Secret management — anh's chosen secret store (env file, AWS Secrets Manager, Doppler).
- [ ] Monitoring tool — anh's chosen (Sentry for Flutter? Sentry/Datadog for BE? simple log file?).
