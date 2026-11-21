# Vercel free demo deployment plan

**Deployment choice:** Vercel serves the existing React/Vite frontend and FastAPI API from one same-origin project, with Neon PostgreSQL and private Vercel Blob. This preserves the SQLAlchemy workflow and supports a small competition demonstration. It remains a prototype, not a production medical-device quality system.

**Status (1 November 2026):** production is live at [https://labeltrace-virid.vercel.app](https://labeltrace-virid.vercel.app) in project `labeltrace` (`prj_YRmVfuXUyPE39pCERdWnbqbuAbFT`). Neon Free PostgreSQL is provisioned in Singapore (`sin1`); private Vercel Blob store `labeltrace-private-artifacts` (`store_s0bi5030RYzkrgVp`, Mumbai `bom1`) holds source files, generated PDFs/previews and evidence ZIPs. The account owner accepted Neon terms. Production health was verified as `PostgreSQL + vercel_blob`, and the hosted synthetic workflow was exercised end to end. The deployment was uploaded directly from the workspace; no GitHub repository was created. Selected services are on their free tiers; no paid resources were provisioned. Local development remains at `http://127.0.0.1:5173`.

## Proposed free-tier architecture

- **React/Vite:** build the existing frontend as static assets on Vercel. Route `/api/*` to the Python function in the same project so the current HttpOnly session cookie remains same-origin.
- **FastAPI:** expose the existing FastAPI `app` through a Vercel Python Function entry point. Vercel documents FastAPI and Python functions as supported. Keep every database query, role check, validation, approval, and release decision in FastAPI.
- **PostgreSQL:** Neon Free PostgreSQL with SQLAlchemy/psycopg and Neon's pooled endpoint over TLS. The backend detects Neon `-pooler` URLs, disables psycopg automatic prepared statements, and uses `NullPool` for serverless functions. PostgreSQL startup and the complete hosted release workflow have been verified. A concurrency stress test against PostgreSQL was not run; SQLite test results do not establish PostgreSQL concurrency behavior.
- **Private files:** add a Vercel Blob adapter for source documents, generated PDFs, and evidence packages. Use a private store. The FastAPI authorization boundary must check the session and role before retrieving or streaming any artifact. Never expose the Blob token or an unauthenticated URL to the browser.
- **AI:** keep deterministic extraction and explanation enabled. Azure AI adapters stay disabled unless separately configured; no Docker inference service is needed.

## Free-tier fit and limits

Vercel Hobby is free for **personal, non-commercial use only**. Whether a competition prototype meets the provider's usage terms should be checked against the team's intended use. Hobby includes free function usage within quotas; over-limit Hobby projects pause until the usage window resets rather than automatically accepting paid overage. Current documented limits include 1 million function invocations, 4 active CPU-hours, 360 GB-hours provisioned memory, and up to 60 seconds for non-Fluid Functions (Fluid Compute documents up to 300 seconds on Hobby). Do not make a long OCR task synchronous; keep deterministic, text-based extraction in the demo path.

Vercel Functions have a **4.5 MB request-body and response-body limit**. Local development defaults to a 5 MiB upload cap; production sets the cap to 4 MiB so multipart overhead stays below the platform limit. Evidence downloads are proxied through FastAPI and must remain below the response limit; larger artifacts would require authorized direct-to-Blob transfers with server-side hash, content-type, size, and object-ownership verification.

Neon Free is $0/month and currently includes 100 CU-hours per project/month, 1 GB storage per project, and 5 GB public network transfer per project/month. Its compute scales to zero after five minutes; a later request can incur a cold-start delay. Free usage caps do not produce overage charges: compute suspends at its compute or transfer cap, and writes that would exceed the storage cap fail until storage is freed or the account is upgraded. Neon paid plans are usage-based, so do not switch plans or add paid branches. Keep this project on Free and use Neon's pooled endpoint with TLS. These are provider plan limits, not measured capacity for this application.

Vercel Blob is available on Hobby; the current published free allowance includes 1 GB storage and 10 GB Blob Data Transfer/month. Private downloads pass through authenticated application functions and consume transfer/function resources. Keep the demo artifacts small and monitor usage. Free quotas and plan rules can change.

## Deployment work completed and remaining

1. Done and hosted: Vercel Services route `/api/*` to FastAPI and all other requests to React/Vite. `vercel.json` deploys both in one project and one origin.
2. Done and hosted: private Vercel Blob through its Python SDK; this store is connected with a Vercel-managed read/write environment token because the Python function did not receive a usable OIDC token. The token is stored only in Vercel's encrypted environment settings, not source. Paths are content-addressed and SHA-256 checked; private downloads pass through FastAPI authorization.
3. Done and hosted: TLS PostgreSQL through SQLAlchemy/psycopg. Neon `-pooler` URLs disable psycopg automatic prepared statements and use SQLAlchemy `NullPool`; a PostgreSQL advisory transaction lock serializes first schema creation. Neon Free is provisioned in `sin1`. The hosted happy path and stale-release rejection ran against PostgreSQL; no separate PostgreSQL concurrency stress test was conducted. Azure managed identity remains a separate mode.
4. Done and hosted: same-origin request checks, Secure cookies, 4 MiB upload limit, deterministic extraction, and production role-password safeguards are configured. Role passwords are unique encrypted Vercel environment variables and are not embedded in the UI.
5. Done: production build and deployment are READY. Hosted checks verified deterministic text extraction, PDF generation and validation, private source/artifact read/write, affected/unaffected selection, approval invalidation, release denial for stale approval, successful current revision release, and evidence ZIP manifest/artifact hashes. The production-only defect injection endpoint correctly returns 404. The approved Windows browser-control helper failed to initialize (`failed to write kernel assets: The system cannot find the path specified`), so hosted verification used authenticated API requests and Vercel's web fetch/production logs; no UI automation or browser screenshot is claimed.
6. A GitHub repository was not found in the linked account/organization, so this deployment is configured for direct Vercel CLI upload from the local workspace. No repository was created or modified.

### Free-tier and account notes

Neon terms acceptance and provisioning are complete. Keep Neon on Free and the project on Vercel Hobby. Do not add paid integrations or upgrade plans without first reviewing the provider's then-current limits, eligibility, and price. The Vercel Hobby non-commercial-use condition still applies; the team should confirm its competition/demo use is eligible. The hosted UI intentionally displays simple demo credentials for synthetic accounts; these accounts must never be reused with real data. Set `VITE_DEMO_CREDENTIALS=false` and rotate the encrypted role-password variables if credential display should be disabled. Because the browser automation helper did not initialize, use the app's UI manually for visual inspection before broader sharing.

## Honest trade-off versus Google Cloud

Vercel + Neon + Blob offers a faster path to a shareable prototype and avoids a Firestore rewrite. It remains subject to Hobby's personal/non-commercial restriction, serverless payload/runtime limits, cold starts, and provider free-tier terms. The Google Cloud plan offers more control over deployment/runtime but Cloud Run requires a billing-enabled project and the documented no-cost quotas are not a hard billing cap; the current GCP alternative also needs a Firestore persistence rewrite. For this competition demo, Vercel is the better first deployment target **if** the use is eligible for Hobby and the 4.5 MB artifact limits are acceptable or direct private Blob transfer is implemented.

## Primary sources checked 1 November 2026

- Vercel [Hobby plan and terms](https://vercel.com/docs/plans/hobby)
- Vercel [Function limits](https://vercel.com/docs/functions/limitations)
- Vercel [Python runtime / FastAPI support](https://vercel.com/docs/functions/runtimes/python)
- Vercel [Services full-stack deployment configuration](https://vercel.com/changelog/python-on-vercel-is-now-generally-available)
- Vercel Blob [private storage](https://vercel.com/docs/vercel-blob/private-storage) and [Blob general availability/free allowance](https://vercel.com/changelog/vercel-blob-is-now-generally-available)
- Neon [plans and billing](https://neon.com/docs/introduction/plans)
- Neon [Free plan quotas](https://neon.com/docs/introduction/free-tier)
- Neon [connection pooling](https://neon.com/docs/connect/connection-pooling)
