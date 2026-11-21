# Azure implementation and deployment runbook

**Status: local prototype verified; Azure infrastructure and CI prepared. No cloud resources, role assignments, deployments, subscription changes or paid AI services were created.** Read and approve `AZURE_RESOURCE_PLAN.md` before any apply operation. No Docker Desktop or inference service is needed.

## Architecture

React/TypeScript/Vite assets are served by **Azure Static Web Apps Standard**. Its linked backend proxies same-origin `/api/*` to **Azure App Service Linux**, running FastAPI from a source ZIP built by Oryx. FastAPI authenticates the application session, checks roles and owns every database/release decision. Static Web Apps does not talk directly to PostgreSQL or Blob Storage. Same-origin routing avoids cross-site session-cookie dependencies; production cookies are HttpOnly, SameSite=Lax and Secure.

**Azure Database for PostgreSQL Flexible Server** stores versioned records and enforces the shared workflow transaction gate. **Azure Blob Storage** holds original sources, PDFs, rendered previews and evidence ZIPs. The container denies anonymous access and account-key authentication; its public network endpoint is disabled. App Service reaches it through VNet integration, a Blob private endpoint and private DNS. PostgreSQL uses a delegated private subnet and a second private DNS zone. No public database firewall exception is created.

The App Service system-assigned managed identity gets **Storage Blob Data Contributor at container scope**. Blob writes are create-only, content-addressed and verify an existing object before treating retries as successful. Versioning and 7-day soft deletion add recovery, but are not a WORM policy or electronic signature. Browser downloads are authenticated FastAPI responses, not public Blob URLs or SAS tokens. This also means a browser does not need private-endpoint network access.

PostgreSQL uses Entra-only authentication. A fresh access token is obtained for every new physical SQLAlchemy connection, passed as the PostgreSQL password in memory, and never embedded in `DATABASE_URL`. TLS uses `verify-full` and the system trust store. The managed identity must separately be mapped to a database principal; a Blob IAM assignment does not grant SQL access. The runtime identity is not the Entra database administrator.

## Local execution remains the default

From `labeltrace`:

```powershell
.\.venv\Scripts\python.exe -m pip install -r backend/requirements-lock.txt
.\.venv\Scripts\python.exe manage.py start
```

Open http://127.0.0.1:5173 and http://127.0.0.1:8000/docs. Defaults: persistent SQLite, local filesystem storage, deterministic extraction, local synthetic demo accounts. Use existing local PostgreSQL by configuring `DATABASE_URL` as documented in README. No local PostgreSQL installation was available in this verification, so **PostgreSQL behavior was not verified locally**.

The existing prototype keeps all source versions and approval/release histories. Local demo reset remains CLI-only and environment-restricted. Production refuses the local-storage/SQLite fallback and does not automatically seed the committed local demo passwords.

## Configuration and health

`.env.example` describes local settings; `.env.azure.example` describes backend Azure settings without credentials. The manager reads untracked `.env` locally. Azure settings are supplied by Bicep/App Service, not loaded from committed files. `VITE_*` values are public frontend build configuration: **never put Azure/database credentials in them**.

| Setting | Azure value / purpose |
|---|---|
| `APP_ENV=production`, `SEED_DEMO=0` | No automatic shared-password seed; reset/defect fixtures disabled |
| `DATABASE_AUTH=azure_identity` | PostgreSQL with fresh managed-identity tokens |
| `PGHOST`, `PGDATABASE`, `PGUSER` | Database host, dedicated DB and exact mapped identity-role name |
| `PGSSLROOTCERT=system` | Verify server hostname and trusted TLS certificate |
| `STORAGE_BACKEND=azure` | Private Blob adapter; errors never fall back to disk |
| `AZURE_STORAGE_ACCOUNT_URL`, `AZURE_STORAGE_CONTAINER` | Private container location, not a credential |
| `AZURE_AUTH_MODE=managed_identity` | Use App Service identity; no developer-credential chain in Azure |
| `COOKIE_SECURE=1`, `ALLOWED_ORIGINS` | Secure session and exact SWA origin; add approved custom origins explicitly |
| `AI_MODE=deterministic`, `DOCUMENT_EXTRACTOR=local` | No optional AI calls or charges |
| `LABELTRACE_DATA=/tmp/labeltrace` | Scratch directory only in Azure; authoritative artifacts are in Blob |
| Frontend `VITE_DEMO_CREDENTIALS=false` | No prefilled/displayed local demo password in the deployed UI |

`/api/health/live` checks that FastAPI responds. `/api/health/ready` (and `/api/health`) checks schema initialization, DB connectivity and private artifact-storage access, returning 503 without credential-bearing exceptions if unavailable. App Service probes readiness. Microsoft documents Health Check integration with built-in App Service Authentication; do not disable backend authentication to fix a probe. One worker is deliberate for this POC.

## Before approved provisioning

Obtain the nonsecret subscription/tenant/resource-group/region/admin details in the resource plan. Confirm Azure resource-provider registration for Microsoft.Web, Microsoft.Network, Microsoft.Storage and Microsoft.DBforPostgreSQL, permitted regions, Basic Linux/Burstable PostgreSQL capacity, Python 3.12 runtime availability and naming availability. None of these subscription-specific conditions has been verified.

Deployment requires resource creation privileges and narrowly scoped role-assignment privileges in a dedicated resource group. The configured existing Entra administrator group/user must be approved by its tenant owner. Arrange an operator host that already has private VNet connectivity for the SQL-principal bootstrap. Ordinary public Cloud Shell and GitHub-hosted runners do **not** automatically reach the private database. A new VM, VPN, Bastion or self-hosted runner would need a separately priced/approved plan; none is included in the baseline template.

## Reviewed infrastructure

`infra/main.bicep` compiles offline using the official Bicep CLI. `artifacts/azure/main.arm.json` is the compiled template. Compilation/linting is **not** an Azure What-If, quota check, subscription validation or deployment.

After receiving explicit cost/resource approval, an authorized operator can copy `infra/main.parameters.example.json` to untracked `infra/main.parameters.json`, set the approved admin and region parameters, sign in to the intended subscription and preview:

```bash
az account set --subscription APPROVED_SUBSCRIPTION_ID
az deployment group what-if --resource-group APPROVED_EXISTING_RESOURCE_GROUP --template-file infra/main.bicep --parameters @infra/main.parameters.json
```

Review the What-If output. Only after the resource plan and preview are approved:

```bash
az deployment group create --resource-group APPROVED_EXISTING_RESOURCE_GROUP --name labeltrace --template-file infra/main.bicep --parameters @infra/main.parameters.json
```

**Neither command was run here.** Do not turn placeholders into real resource creation without approval. The template creates no AI resource, public artifact container, shared-key credential or public database-access rule. It does not create a subscription, an Entra administrator group or an operator VM.

## Database identity bootstrap and first use

Use deployment outputs `appServicePrincipalId`, `postgresIdentityRole`, `postgresHost` and `postgresDatabase`. From a VNet-connected authorized host, connect as the configured Entra PostgreSQL administrator using a current token for `https://ossrdbms-aad.database.windows.net`. Keep the token in the process environment, not the command line or repository. Run the provided `infra/bootstrap-postgres.sql` once with psql variables `app_role` and `principal_id`. It calls `pgaadauth_create_principal_with_oid`, grants database CONNECT and schema USAGE/CREATE, and gives the application no Entra-admin privilege. Do not silently remap an existing role to a different identity.

The App Service startup script waits for DB and private-storage access with a bounded retry, runs Alembic and starts Uvicorn. It fails rather than using SQLite or public storage. The deployment remains unready until private DNS, identity grants and SQL-role setup work. RBAC propagation may require waiting/retry. No migration/identity success is claimed until observed in the deployed environment.

Next, open an interactive SSH session inside App Service and run `python -m backend.bootstrap`. It prompts for **three distinct passwords of at least 16 characters**, never logs or writes them, and initializes the synthetic family and role accounts. It refuses the documented local demo password and refuses to overwrite an initialized database. This is an operator task; no account passwords are requested in this chat. Enterprise identity/SSO and production medical-device qualification are not implemented by this POC.

## Source deployment and GitHub Actions

Treat `labeltrace/` as the eventual repository root. No repository was pushed or GitHub workflow executed here. The existing `checks.yml` verifies SQLite/frontend and provides a PostgreSQL 17 service job. The PostgreSQL job is configured for the full workflow suite with per-test isolated schemas, including the concurrent edit/release test; **that job has not been run remotely**.

Configure a deployment service principal using **GitHub OIDC federation**, limited to the repository/environment. It is separate from the runtime managed identity. Create/protect the `azure-poc` GitHub environment and configure repository variables:

`AZURE_SUBSCRIPTION_ID`, `AZURE_TENANT_ID`, `AZURE_CLIENT_ID` (deployment OIDC client), `AZURE_RESOURCE_GROUP`, `AZURE_LOCATION`, `LABELTRACE_PREFIX`, `ENTRA_DB_ADMIN_OBJECT_ID`, `ENTRA_DB_ADMIN_NAME`, and after provisioning `AZURE_APP_SERVICE_NAME`, `AZURE_STATIC_WEB_APP_NAME`.

Only after explicit approval set repository variable `AZURE_COST_APPROVED=true`. Use required environment reviewers where supported by the GitHub plan; verify those controls before enabling apply. No free GitHub/Azure entitlement is assumed. The boolean/variable gates are configuration controls, not a substitute for the user's actual approval.

- `azure-infrastructure.yml`: **manual dispatch only**, defaults to What-If. Apply additionally requires the explicit cost-confirmation input, approval variable and configured environment gate. It assumes the dedicated resource group already exists.
- `azure-deploy.yml`: **manual dispatch only**, tests/builds first, then requires the approval variable/environment. It deploys a source ZIP with Oryx, links SWA `/api` to App Service and uploads prebuilt React assets. No Docker image is built for FastAPI. Microsoft's SWA upload action may use a hosted-runner container; local Docker Desktop is unrelated.
- Deployment uses Azure OIDC. The SWA action's deployment token is retrieved at runtime, masked and passed directly to the action; it is not committed or stored as a repository secret in this design. This token is a credential despite OIDC login; protect action logs/environment permissions and rotate it using Azure controls as needed.

`python scripts/package_azure.py` creates `artifacts/azure/appservice-source.zip`. It includes only application code, migrations, fixtures, scripts and dependency manifests, excluding `.env`, local data, virtual environments, frontend dependencies and compiler binaries. The source workflow builds the frontend with `VITE_DEMO_CREDENTIALS=false` and includes `staticwebapp.config.json`, which excludes `/api/*` from SPA fallback and sets restrictive content headers.

Backend linking configures the Azure Static Web Apps linked identity provider. Retain that restriction; then independently verify direct App Service access cannot bypass the linked gateway and that FastAPI still requires its application session. SWA portal/CLI linking, Secure cookie forwarding, private DNS/RBAC and source deployment require actual cloud testing and are not established by offline tests.

## Optional Azure AI adapters

Both are disabled by default and provision **no resources automatically**. After separate approval and resource/quota setup:

1. For Azure OpenAI, grant the runtime identity **Cognitive Services OpenAI User** on an approved resource, configure an exact HTTPS `AZURE_OPENAI_ENDPOINT` and a structured-output-capable `AZURE_OPENAI_DEPLOYMENT`, then set `AI_MODE=azure_openai`. Facts must exactly match independently extracted allowlisted source spans; duplicated, omitted or invented facts are rejected. Explanations let the model select only a known reason/evidence reference; the server renders approved values, preventing invented medical prose. No AI response can update a fact or approve release.
2. For Document Intelligence, grant the runtime identity the appropriate **Cognitive Services User** role, configure `AZURE_DOCUMENT_INTELLIGENCE_ENDPOINT` with a custom resource subdomain, and explicitly set `DOCUMENT_EXTRACTOR=azure_document_intelligence`. Original PDF bytes are submitted to `prebuilt-read` with the 2024-11-30 API; a bounded poll stays on the same resource hostname. Transcript/provenance hashes are recorded and clearly displayed; reviewers must verify OCR against the original.

Enabling either sends source content to that approved Azure service and can incur usage charges. No AI resource, deployment, capacity or price is assumed. Managed identity is default; optional API-key environment settings exist for local integration only and must never be committed. If Azure AI fails, text-based PDFs use deterministic extraction and explanations; a scanned PDF with unavailable OCR fails explicitly. No fake provider response is represented as live output. Offline tests exercised request contracts, provenance, output rejection and failure paths; **no live Azure AI call was made**.

## Cloud acceptance after approval

Confirm HTTPS/Secure session persistence, distinct account permissions, private Blob/network access, Entra DB token refresh, fresh migrations, successful original-document upload, exact spans/OCR provenance, immutable PDF generation, independently decoded QR, defect and stale-release rejection, preserved unaffected approvals, evidence ZIP/hash verification, restart persistence and concurrent PostgreSQL edit/release behavior. Check readiness and diagnostic logs without logging tokens. Until these pass on Azure, label the deployment **prepared, cloud-unverified**, not production ready.

## Primary sources accessed 22 October 2026

- [Static Web Apps API overview](https://learn.microsoft.com/en-us/azure/static-web-apps/apis-overview) and [App Service backend linking](https://learn.microsoft.com/en-us/azure/static-web-apps/apis-app-service): Standard tier, `/api` proxy and linked-backend access behavior.
- [Python App Service configuration](https://learn.microsoft.com/en-us/azure/app-service/configure-language-python): Linux/source build and startup configuration.
- [App Service Health Check](https://learn.microsoft.com/en-us/azure/app-service/monitor-instances-health-check): readiness probing/authentication integration.
- [Blob upload with Python](https://learn.microsoft.com/en-us/azure/storage/blobs/storage-blob-upload-python): Entra credentials, data role and create/update behavior.
- [PostgreSQL managed identity](https://learn.microsoft.com/en-us/azure/postgresql/flexible-server/security-connect-with-managed-identity) and [Entra role management](https://learn.microsoft.com/en-us/azure/postgresql/security/security-manage-entra-users): token authentication and OID-based SQL mapping.
- [Document Intelligence API/SDK](https://learn.microsoft.com/en-gb/azure/ai-services/document-intelligence/how-to-guides/use-sdk-rest-api?view=doc-intel-4.0.0) and [Azure OpenAI structured outputs](https://learn.microsoft.com/en-us/azure/ai-foundry/openai/how-to/structured-outputs): optional adapter contracts; actual deployment/model support must be checked.
