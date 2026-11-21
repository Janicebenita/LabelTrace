# Actual verification — 22 October 2026

## Environment

Windows host; Python 3.12.14 in a project virtual environment; Node.js 26.0.0 / npm 11.12.1; FastAPI and Vite started directly. No usable running local PostgreSQL service/process was found. Docker was unavailable after the user reported its inference-manager crash; it was not reset, reinstalled or made a prerequisite. Persistent SQLite was used. No AI provider was configured.

## Automated results

- **28 backend tests passed, 0 failed** in the final full run (117.50 seconds). Machine-readable evidence: `artifacts/backend-test-results.xml`.
- **5 frontend projection/diff tests passed, 0 failed** using Vitest. Evidence: `artifacts/frontend-test-results.json`.
- **TypeScript production build passed** with Vite 6.4.5 after the final UI changes.
- **npm audit: 0 reported vulnerabilities** after dependency updates. This is the registry audit result, not a general security certification. The initial dependency audit is retained separately.
- Fresh SQLite Alembic migration, synthetic seed and `alembic check` passed. The documented `manage.py start` command was exercised, restarting both services with existing state retained.
- Isolated backend tests cover permissions/self-approval, missing/conflicting evidence, real decoded barcode and six artwork defects, stale approvals, source metadata-only changes, template/rule version changes, artifact/source tampering, rejection after historical approval, idempotency, unauthorized browser origins, provider failure/ungrounded output, environment-restricted fixtures/reset, successful release/ZIP hash verification and a two-thread SQLite edit/release race.

The first test attempts encountered a Windows temporary-directory permission error before test setup; the runner now uses a workspace-local temporary directory. Those attempts were not counted as passed. Subsequent complete runs passed. Frontend dependency versions were updated after the initial npm audit reported vulnerabilities. No unresolved current test failure remains.

## Independent synthetic fixture measurements

`fixtures/expected-results.json` is a human-authored oracle; expected selections do not call the runtime dependency selector. The scenario changes adult manufacturer address, with 2 affected and 2 unaffected labels.

| Measurement | Actual result | Sample boundary |
|---|---|---|
| Impact precision | 2/2 = 1.0 | One address-change scenario |
| Impact recall | 2/2 = 1.0 | Two expected affected labels |
| Missed affected variants | 0 | Same four-label family |
| Defect fixture detection | 6/6 | Barcode, missing manufacturer, wrong identifier, unsupported text, overflow, applicability |
| False alarms | 0/4 clean baselines | No inference about unseen labels |
| Element evidence completeness | 7/7 | Latest clean adult-box revision in the fixture evaluation |
| Validation latency | 78.63–168.12 ms | Six defect runs on this host; includes rasterization and QR decode |
| Automated scenario elapsed | 5,378.82 ms | Includes API role switches; **not human review time** |

Full values are in `artifacts/evaluation-results.json`. No human time-saving, clinical-benefit, general accuracy, cost-saving or production-readiness claim is made.

## Genuine browser workflow

The approved in-app browser tool operated the actual running frontend and API. It used the supported file-chooser mechanism to upload the local synthetic PDFs; no generated mockup or fixture success response was used as UI evidence.

1. Signed in as author, uploaded `SYNTHETIC-adult-spec-v2.pdf`, and inspected page/text-span extraction.
2. Switched to the separate reviewer account and approved the changed address candidate.
3. Switched to author, proposed the fact change, then reviewer approved it.
4. Inspected inclusion paths for adult box/carton and exclusion reasons for pediatric box/carton.
5. Generated adult box r2, inspected actual before/after PDF artwork and field-level source evidence.
6. Created barcode defect r3; PDFium/ZXing decoded `DEMO-WRONG-CODE`, producing a blocking finding.
7. Signed in as release manager and attempted release: API returned 409, persisted `RELEASE_BLOCKED` for missing successful validation/exact approval.
8. Regenerated clean r4, validated and approved it as the reviewer. Also approved the unchanged pediatric box baseline.
9. Uploaded `SYNTHETIC-adult-spec-v3.pdf` without editing the approved artwork. Repeated evidence review, change proposal and independent fact-change approval.
10. Adult box r4 became **Stale** with its original approval retained; pediatric box r1 remained **Approved**. The release manager's attempt was rejected specifically because the adult manufacturer-address fact had a newer approved version.
11. Generated adult box r5 from current facts, validated, approved and released it. Downloaded the ZIP through the browser. Reloaded the page and verified the persistent release.
12. Restarted the backend/frontend using the documented direct-start command, then completed adult carton r2 generation, validation, separate approval and release through the UI.
13. Downloaded both ZIPs through real browser download events. Compared the downloaded bytes with API export bytes and checked **every file hash** in each manifest against ZIP contents; both matched. The original released box package remained unchanged after the later evidence-export history enhancement.
14. Inspected desktop and narrow-screen layouts. The 390-pixel source view had no page-level horizontal overflow. Fixed mobile sign-out accessibility and route scroll reset. Browser console inspection returned no captured errors. Temporary viewport overrides were reset.

Screenshots: `artifacts/screenshots/01` through `11`. `03-label-comparison.jpg` shows the actual evidence-linked PDF comparison; `07-stale-approval-rejected.jpg` shows the central failure; `10-overview-desktop.jpg` shows final readiness. API/database summary: `artifacts/browser-verification.json`.

## Final persisted demonstration

4 source documents, 20 approved fact-version records, 2 approved source-backed changes, 9 immutable label revisions, 4 human approvals and 2 releases.

- Adult box **r5 Released**.
- Adult carton **r2 Released**.
- Pediatric box **r1 Approved**, unchanged.
- Pediatric carton **r1 Review Ready**, unchanged.
- Both blocked attempts and the superseded adult approval remain in history.

## Vercel hosted verification — 1 November 2026

- **Live app:** [https://labeltrace-virid.vercel.app](https://labeltrace-virid.vercel.app). `GET /api/health` returned HTTP 200 with `database=postgresql`, `storage=vercel_blob`, and `synthetic=true`. The root returned HTTP 200 and the React production bundle. Vercel production logs confirmed private Blob PUT/GET operations.
- **Hosted workflow:** authenticated API run uploaded synthetic UTF-8 text specifications. Deterministic candidate extraction was explicit. An approved address change selected `adult.box` and `adult.carton`; the pediatric labels were reported as unaffected. Generated PDFs passed validation and were approved for their exact revisions.
- **Stale release control:** a later approved source fact changed the adult address again. The prior approval remained in history, its revision became `Stale`, and release returned HTTP 409 with the newer approved fact as the reason. The current revision was regenerated, validated, separately approved and released.
- **Evidence export:** the downloaded API ZIP contained `label.pdf`, `release-manifest.json`, `approval-history.json` and `audit.json`; manifest artifact and file hashes matched the contents. Hosted release reference: `094b7c94d742490caf3d73e5048c8844`.
- **Production scope guard:** the development-only defect injection endpoint returned HTTP 404 in production. Defect fixtures and positive/negative validation results remain verified in the local SQLite suite; no defect was injected into the hosted data.
- **Automated local regression:** `uv run --project backend pytest -q` completed with **47 passed, 0 failed** (96.93 seconds). The focused Azure source-package regression completed with **3 passed** after excluding local `.venv` and `.test-tmp` files. Vercel production build passed, including `tsc -b` and Vite build.
- **Verification limits:** this was one hosted PostgreSQL workflow exercise, not a PostgreSQL concurrency stress test. The Windows browser-control helper could not initialize (`failed to write kernel assets: The system cannot find the path specified`), so no hosted UI interaction or screenshot is claimed. The hosted checks used authenticated HTTP requests, Vercel web fetch, and production logs. Previous screenshots show local UI only; inspect the live UI manually before broader sharing.
- **Demo sign-in update:** the hosted bundle now contains a role-specific password hint and visible **Switch role** control. All three new passwords authenticated successfully against the existing production database: `author-1234`, `reviewer-1234`, and `releaser-1234`. No database reset was performed.

## Not verified or not implemented

PostgreSQL concurrency/migrations were **not executed locally**; a CI smoke configuration is provided but no remote CI run is claimed. Docker Compose was not run. SQLite's tested serialized-writer behavior does not establish PostgreSQL guarantees. Live AI-provider success was not verified; provider failure and fabricated-output rejection were tested with mocks. OCR, real PLM/ERP/printing, translation, broad regulatory conformity, physical barcode grading, electronic signatures, enterprise deployment/load/security qualification and a human review-time study are outside this working POC. See `ARCHITECTURE.md` for remaining boundaries.
