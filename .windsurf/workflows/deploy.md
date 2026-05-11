---
description: Build + deploy app (Flutter store, Firebase Hosting, Cloud Functions, Firestore rules) — careful checklist, with rollback plan.
---

# /deploy — Deploy Workflow

> "Pre-deploy verification > rollback firefighting."

Deploys carry production-impact risk — always checklist before, monitor after.

## Pre-flight

1. **Make sure the branch is `deploy`** (production) or `develop` (staging). DON'T deploy directly from a feature branch.
2. **Working tree clean:** `git status` empty.
3. **Up-to-date:** `git pull origin deploy` (or `develop` for staging).
4. **Read the spec/plan of the feature being deployed** — know its acceptance criteria.
5. **Apply skill `verification-before-completion`** — every step verifies for real, doesn't assume.

## Pre-deploy checklist

### Universal

- [ ] All tests pass:
  ```bash
  flutter test
  npm test --prefix functions
  npm test --prefix services/api  # if exists
  ```
- [ ] Lint clean:
  ```bash
  flutter analyze
  npm run lint --prefix functions
  ```
- [ ] No `console.log` / `print` debug left over:
  ```bash
  grep -rn "console.log\|print(" --include="*.dart" --include="*.ts" lib/ functions/src/ services/
  ```
- [ ] No TODO without a linked issue:
  ```bash
  grep -rn "TODO\|FIXME" --include="*.dart" --include="*.ts" lib/ functions/src/
  ```
- [ ] Version bump correct (if release):
  - Flutter: `pubspec.yaml` `version: x.y.z+build`
  - Functions: `package.json` version
- [ ] Changelog updated (if maintained).
- [ ] Spec/plan marked "Implemented".

### Security

- [ ] No hardcoded secrets:
  ```bash
  grep -rEn "(api[_-]?key|secret|password|token)\s*=\s*['\"][^'\"]{10,}" --include="*.dart" --include="*.ts" lib/ functions/src/
  ```
- [ ] `.env*` not staged:
  ```bash
  git ls-files | grep -E "\.env($|\.)"
  # Expect: empty (only .env.example allowed)
  ```
- [ ] Service account JSON, keystore not staged:
  ```bash
  git ls-files | grep -iE "(serviceaccount|firebase-adminsdk|\.keystore$|\.jks$|google-services\.json|GoogleService-Info\.plist)"
  # Expect: empty
  ```

## Path A: Flutter mobile app

### A.1 Android (Play Store / APK)

```bash
# Build release APK
flutter build apk --release

# Or App Bundle for Play Store
flutter build appbundle --release
```

**Verify:**
- [ ] Exit 0.
- [ ] Output `build/app/outputs/bundle/release/app-release.aab` reasonable size.
- [ ] Test the AAB on emulator/device:
  ```bash
  flutter install
  ```
- [ ] Smoke test: login, post, feed, push notification.

**Upload to Play Console:**
- Manual upload via dashboard, or use `fastlane` if set up.
- **Internal testing track** before production.
- Release notes: use a template, link to spec.

### A.2 iOS (App Store / TestFlight) — _DEFERRED per ADR-0002_

> **Skip this section for MVP.** iOS targeting is out of scope until post-MVP. Content kept as future reference. Do **NOT** run `flutter build ipa` in CI or locally during MVP.

<details>
<summary>Future reference (post-MVP, after ADR-0002 is revisited)</summary>

```bash
# Build release IPA
flutter build ipa --release
```

**Verify:**
- [ ] Exit 0.
- [ ] Output `build/ios/ipa/*.ipa`.
- [ ] Open Xcode → Window → Organizer → Validate.
- [ ] Distribute App → App Store Connect.

**TestFlight:**
- Upload via Xcode or `Transporter` app.
- **TestFlight internal** test before public release.
- App Review usually 1-3 days.

</details>

## Path B: Firebase Cloud Functions

```bash
cd firebase/functions
npm install
npm run build
npm test
```

**Pre-deploy:**
- [ ] Tests pass.
- [ ] TypeScript compiles clean (`npm run build` exit 0).
- [ ] Region correct in code (`asia-southeast1` for VN users).
- [ ] Secrets exist in Secret Manager:
  ```bash
  gcloud secrets list --project=meep-prod
  ```

**Deploy staging first:**

```bash
firebase deploy --only functions --project meep-staging
```

**Verify staging:**
- [ ] Deploy log: no errors.
- [ ] Function logs clean after a test request:
  ```bash
  firebase functions:log --project meep-staging --limit 50
  ```
- [ ] Smoke test: trigger a real function from the staging app.

**Deploy production:**

⚠️ **Confirm with the user before running:**

```bash
firebase deploy --only functions --project meep-prod
```

**Post-deploy production:**
- [ ] Monitor logs for 15-30 minutes:
  ```bash
  firebase functions:log --project meep-prod --limit 100
  ```
- [ ] Check error rate in Firebase Console > Functions.
- [ ] Smoke test critical functions from prod app.

## Path C: Firestore / Storage rules

⚠️ **Rules deploy = immediate production impact.**

```bash
# Test rules in emulator first
firebase emulators:exec --only firestore "npm run test:rules"
```

**Verify:**
- [ ] Rules unit tests pass.
- [ ] Re-read rules — any `allow ... if true`?

**Deploy staging:**

```bash
firebase deploy --only firestore:rules,storage --project meep-staging
```

**Verify staging:** test auth/post/friend flows on the staging app.

**Deploy production:**

⚠️ **Confirm with the user:**

```bash
firebase deploy --only firestore:rules,storage --project meep-prod
```

**Rollback if something goes wrong:**

```bash
# Get previous deployed rules
firebase firestore:rules:list --project meep-prod
# Restore old version via Firebase Console or redeploy the old file
```

## Path D: Firestore indexes

```bash
firebase deploy --only firestore:indexes --project meep-prod
```

Index build can be slow (minutes to hours depending on data size). Monitor:

```bash
firebase firestore:indexes --project meep-prod
```

## Post-deploy monitoring

**First 24 hours after deploy:**

- [ ] Crashlytics: no error spike.
- [ ] Firebase Analytics: new feature getting hits?
- [ ] Firestore reads/writes: no abnormal spikes.
- [ ] Function invocations: success rate, p99 latency.
- [ ] User feedback (if you have a channel).

## Rollback plan

**Mobile app:**
- Play Store: pause rollout, deploy old version with version bump.
- App Store: TestFlight not revertible; for production, expedited review of old version.

**Functions:**
```bash
git checkout <previous-good-sha> -- firebase/functions
cd firebase/functions
npm install && npm run build
firebase deploy --only functions --project meep-prod
git checkout develop -- firebase/functions  # restore code state (or deploy if production)
```

**Rules:**
- Restore from history via Firebase Console.
- Or commit a revert + redeploy:
  ```bash
  git revert <bad-sha>
  firebase deploy --only firestore:rules,storage --project meep-prod
  ```

## Tag the release

After confirming the deploy is stable (24h+):

```bash
git tag -a v1.2.0 -m "Release: feature X, fix Y"
git push origin v1.2.0
```

## Anti-patterns

| Anti-pattern | Problem |
|---|---|
| Deploy direct to prod, skip staging | Bugs land in users' hands |
| Deploy on Friday afternoon / weekend | No one to monitor |
| Skip post-deploy monitoring | Latent bugs go undetected |
| Force deploy bypassing tests | False confidence |
| `firebase deploy` without `--project` | Might deploy to the wrong project |
| Push uncommitted code to prod | Can't trace deployed code |

## Output

- ✅ Pre-deploy checklist 100% pass.
- ✅ Staging deploy + smoke test pass.
- ✅ Production deploy successful, logs clean for 30 minutes.
- ✅ Release tagged in git.
- ✅ Monitored 24h, no critical issues.
