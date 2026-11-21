# Implementation and acceptance checklist

- [x] Persistent SQLAlchemy records; versioned facts, documents, templates, rules and immutable label artifacts.
- [x] Separate authenticated author, reviewer and release users; no self-approval.
- [x] Text/PDF upload, evidence spans, candidate review and source-backed change approval.
- [x] Independent manifest selects adult box/carton and excludes pediatric box/carton.
- [x] Downloadable PDF artwork, rendered barcode decoding, semantic/layout/dependency checks.
- [x] Exact-artifact approval, freshness rejection, transactional release and evidence ZIP.
- [x] React workspace; meaningful error/permission states and reload persistence.
- [x] Direct startup/reset, optional PostgreSQL/Compose, migrations and CI configuration. PostgreSQL/Compose not locally executed.
- [x] Automated negative-path tests, measured fixtures and real browser workflow/screenshots.

Acceptance: the demo must reject a defective artifact, preserve prior approval history after an upstream fact update, reject release of that stale artifact, then release an updated validated and approved revision with its evidence package. All data and labels are synthetic. Database-specific guarantees must be reported accurately.

## Azure target and execution order

1. [x] Preserve existing application and data; verify direct Python/npm startup with persistent SQLite fallback.
2. [x] Add filesystem/private Blob storage adapters, authenticated downloads and DB/storage readiness checks.
3. [x] Add PostgreSQL identity-token connection support and fail-closed Azure production configuration.
4. [x] Add optional grounded Azure OpenAI and Document Intelligence adapters; keep deterministic mode fully functional.
5. [x] Reverify local workflow, actual PDF upload/download and exact-artifact release using the approved browser.
6. [x] Prepare App Service source packaging, SWA configuration, Bicep private networking/storage and PostgreSQL Flexible Server.
7. [x] Prepare manually gated OIDC GitHub workflows and PostgreSQL integration CI configuration; do not execute remote deployment.
8. [x] Present East US 2 resource plan, retail-rate cost worksheet and required subscription/admin/network details.
9. [ ] Obtain explicit cost/resource/region approval and subscription details before any paid provisioning.
10. [ ] Provision, map database identity, deploy, bootstrap private role accounts and verify all controls on Azure after approval.

Cloud gate: no Azure runtime success, networking, token renewal, PostgreSQL concurrency or AI-provider success is claimed from local SQLite and mocked-adapter tests. See `docs/AZURE_VERIFICATION.md` and `docs/AZURE_RESOURCE_PLAN.md`.
