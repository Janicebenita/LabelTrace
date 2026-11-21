# Azure-targeted prototype verification

Verified locally on **22 October 2026**, Windows, direct Python/npm. Docker Desktop was not required or modified. No Azure resources were provisioned, deployed or billed by this task.

## Actual checks

| Check | Result | Evidence |
|---|---|---|
| Backend full suite, persistent workflow and Azure adapter contracts | **47 passed, 0 failed; 101.51 seconds** | `artifacts/azure/backend-test-results.xml` |
| Frontend projection tests | **5 passed, 0 failed** | `artifacts/azure/frontend-test-results.json` |
| TypeScript + production Vite build, cloud demo credential prefill disabled | Passed | `artifacts/azure/frontend-production-build.txt` |
| Bicep build/lint, official compiler v0.48.1 | Passed without diagnostics | `artifacts/azure/main.arm.json` |
| Three GitHub workflow YAML files and deployment/configuration JSON | Parsed successfully locally | `.github/workflows/`, `infra/`, `frontend/public/` |
| Source ZIP entrypoints and exclusion of secrets/local databases | Three tests passed, also included in full suite | `artifacts/azure/deployment-package-tests.xml` |
| New browser PDF upload through native supported file chooser | Passed | `artifacts/azure/screenshots/01-genuine-pdf-upload.jpg` |
| Review → approved change → impact → PDF → validation → exact revision approval → release → downloaded evidence | Passed locally | `artifacts/azure/local-browser-verification.json` |
| Downloaded release ZIP versus backend bytes, all 17 manifest object hashes | Matched | `artifacts/azure/samples/LabelTrace-adult.box-r6-evidence.zip` |
| Reload preserves source, revision, approvals, releases and separate role session | Passed; final overview inspected | `artifacts/azure/screenshots/03-verified-overview.jpg` |

The new browser source `SYNTHETIC-adult-spec-azure-smoke-v4.pdf` changed the adult manufacturer address from 300 to 400 Research Way. The dependency assessment selected adult box/carton and excluded both pediatric labels. Adult box r6 was validated, independently approved and released. Existing releases were retained; the old adult carton release showed follow-up required, while the pediatric approval stayed current. The earlier complete local browser demonstration, including injected defect and stale approval rejection, remains documented in `VERIFICATION.md` and the original screenshots. Those controls also pass the current automated suite.

The browser console retained one Vite hot-reload `createRoot` warning from development editing. The subsequent full reload rendered the persisted workspace correctly; no production browser execution is claimed.

## Synthetic measurements

`artifacts/azure/evaluation-results.json` records the actual reproducible four-label impact oracle and six defect fixtures: precision/recall 1.0 on that oracle, zero missed affected variants, all six seeded defects detected, no alarms on four clean baselines, and complete recorded element traceability. Timings are in that file. These tiny synthetic results do not establish general accuracy, clinical performance, regulatory compliance or time savings. Manual review time has not been measured.

## Limits and unexecuted checks

- Local database was **SQLite** with WAL and serialized write transactions. No PostgreSQL installation was available. PostgreSQL 17 integration/concurrency checks are configured in GitHub Actions, but that job has not run. SQLite success does not establish PostgreSQL isolation guarantees.
- Blob SDK, identity token refresh, provider failures and bounded AI grounding were exercised with offline test doubles. Live managed identity, Blob networking, PostgreSQL Entra login, Azure OpenAI and Document Intelligence were **not** tested against Azure.
- Bicep compilation validates syntax/types, not subscription policy, quotas, SKU availability, IAM, private DNS or successful provisioning. Azure What-If and cloud deployment were not executed. All GitHub workflows remain unexecuted remotely.
- Source deployment must still be tested with App Service Oryx, SWA backend linking, secure cookies, private-network access and cloud authenticated downloads after approval and provisioning. Follow `AZURE_DEPLOYMENT.md` acceptance steps.
- The optional AI adapters are disabled by default. Deterministic text extraction/explanations need no paid keys; scanned sources explicitly require working optional OCR. Approved facts control artwork and humans authorize release.
- PLM/ERP/manufacturing handoffs remain simulated. This is a synthetic POC with selected labeling checks, not a validated medical-device quality system or FDA certification.

## Reproduce

From the application directory:

```powershell
$env:EVALUATION_RESULTS_PATH='artifacts/azure/evaluation-results.json'
.\.venv\Scripts\python.exe -m pytest backend/tests -q --junitxml=artifacts/azure/backend-test-results.xml
cd frontend
npm test
$env:VITE_DEMO_CREDENTIALS='false'
npm run build
```

`python scripts/package_azure.py` produces the deployable FastAPI source ZIP without local data. Start the direct local app with `.\.venv\Scripts\python.exe manage.py start`; use `docs/DEMO.md` for the resettable human workflow. Reset is local/demo-only and was not used to erase the existing history during this Azure update.
