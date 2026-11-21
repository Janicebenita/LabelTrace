# Google Cloud browser deployment plan

**Status: design only. No Google Cloud project was selected, APIs enabled, IAM changed, resource provisioned, or deployment performed.** This plan targets the Google Cloud Console shown in the supplied screenshot. The screenshot identifies an organization, not a billable project ID; the organization label alone is insufficient to deploy.

## Free-allowance architecture (only while within quotas)

- **Firebase Hosting** serves the built React application and rewrites `/api/**` to Cloud Run, keeping the browser and API same-origin.
- **Cloud Run** runs the FastAPI application from source using Google buildpacks/Cloud Build. This avoids requiring Docker Desktop on the developer machine. Request-based billing, minimum instances zero, and authenticated artifact endpoints are the starting settings.
- **Cloud Firestore Standard** holds workflow state. This requires replacing the current SQLAlchemy/PostgreSQL persistence layer with a Firestore repository and redesigning atomic release and idempotency transactions; the current app cannot use Firestore without code changes.
- **Cloud Storage** stores original documents, generated PDFs, previews, and evidence ZIPs in a private bucket with uniform bucket-level access, public access prevention, and service-account-only object permissions. FastAPI remains the authorization boundary for browser downloads. The published Cloud Storage always-free allowance is limited to three US regions, so use `us-central1` for the no-cost target if data geography permits.
- A dedicated runtime service account receives only Firestore and bucket-scoped Storage Object permissions required by the implementation. CI deploy identity is separate and uses Workload Identity Federation rather than a committed service-account key.
- Optional Vertex AI / Document AI adapters can be added later. Deterministic extraction remains the default; approved facts populate labels and humans authorize release.

**Region proposal:** `us-central1` for Cloud Run, Firestore, and Cloud Storage to match the published Cloud Storage free allowance. This sends demo data outside India; if that is unacceptable, Mumbai may be selected but GCS's always-free allowance will not apply. Firebase Hosting uses Google's global edge network. This is a proposal, not a guarantee of residency for every control-plane or build artifact.

### What “free deployment” means

On **Firebase Spark with no billing account**, Firebase Hosting and Firestore provide no-cost quotas, but paid Google Cloud products such as Cloud Run are unavailable. Firebase Hosting rewrites to Cloud Run require a billing account and automatically move a Spark project to Blaze. On **Blaze with billing enabled**, Cloud Run has published no-cost quotas (currently 2 million requests, 180,000 vCPU-seconds and 360,000 GiB-seconds monthly for request-based billing); Firestore includes 1 GiB storage, 50,000 reads/day, 20,000 writes/day and 20,000 deletes/day; Firebase Hosting includes 10 GB storage and 10 GB/month egress. Cloud Storage's 5 GB-month always-free allowance applies only in `us-east1`, `us-west1` and `us-central1`. These are usage quotas, not a hard spend cap; overage is billable on Blaze. Cloud Run requires an attached billing account even if usage stays within its no-cost allowance.

## Console workflow

1. Confirm whether the project is Spark (no billing) or Blaze/free-trial credits (billing enabled). Cloud Run does not run on Spark alone.
2. Select a dedicated project under the visible organization. For Cloud Run, attach billing, set a budget alert, and confirm charges beyond no-cost allowances are acceptable.
3. Convert SQLAlchemy state to a Firestore repository while preserving permissions, immutable records, atomic release gates, idempotency, and evidence. Keep Firestore Admin SDK access behind FastAPI.
4. Create the private GCS bucket and least-privilege runtime service account. Build React and deploy FastAPI source to Cloud Run using buildpacks (`gcloud run deploy --source`), which invokes Cloud Build and Artifact Registry without local Docker. Configure deterministic mode, health probe and zero minimum instances.
5. Deploy the static bundle to Firebase Hosting, configure the `/api/**` rewrite to the Cloud Run URL, and verify session cookies, authenticated source upload, role permissions, private artifact download, stale approval rejection, and release evidence in the hosted environment.
6. Add CI only after the target project, deployment identity, Firebase site, cost budget, and reviewer access are approved. Use Workload Identity Federation and a protected deployment environment.

## Cost and approval gate

At low traffic, service usage can be **US$0 while every applicable quota is respected** on Blaze. This is not a billing cap. Cloud Build/Artifact Registry, logs, egress, AI/OCR, and usage beyond quotas may incur charges. Cloud SQL is excluded from the free architecture. If PostgreSQL must remain, Cloud SQL is billable after any applicable credits expire; Google's listed shared-core `db-g1-small` starts at $0.035/hour in some regions (~$25.55 for 730 hours) before storage/backups.

The official free limits are documented in [Google Cloud Free Tier](https://docs.cloud.google.com/free/docs/free-cloud-features), [Cloud Run pricing](https://cloud.google.com/run/pricing), [Firestore pricing](https://cloud.google.com/firestore/pricing), and [Firebase Hosting quotas](https://firebase.google.com/docs/hosting/usage-quotas-pricing). [Firebase Hosting → Cloud Run](https://firebase.google.com/docs/hosting/cloud-run) requires billing; associating billing automatically changes Spark to Blaze. Cloud Run source deployment uses Cloud Build and Artifact Registry and does not require local Docker.

## Details required before deployment

- Exact Google Cloud **project ID** and organization/folder policy approval; the screenshot only shows an organization selector.
- If Cloud Run is intended: billing account state (Blaze or credits), billing owner approval, budget alert amount and allowed duration.
- Confirmed deployment region and data residency requirements; the proposed free GCS region is in the United States.
- Authorized project IAM administrator and approved service-account/IAM bindings.
- Firebase Hosting project/site authorization and the intended audience/domain/authentication policy.
- Approval to enable APIs and create the listed billable resources. No API key or service-account key should be pasted into chat.

Until the free-plan type and project are confirmed, keep using the working local app at `http://127.0.0.1:5173` with SQLite, local filesystem storage, and deterministic mode. The Firestore path requires implementation and verification before deployment; existing SQLite/PostgreSQL test results do not prove Firestore transaction behavior.
