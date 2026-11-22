# LabelTrace

### Traceable change control for medical-device labels

![LabelTrace hero banner: source evidence flows through affected variants, validated artwork, human approval, and a controlled release gate](docs/images/labeltrace-hero.png)

> **Every edit has a source. Every release has proof.**

[![Live demo](https://img.shields.io/badge/Live_demo-Open_LabelTrace-087E78?style=for-the-badge)](https://labeltrace-virid.vercel.app)
![React](https://img.shields.io/badge/React-19-149ECA?logo=react&logoColor=white)
![TypeScript](https://img.shields.io/badge/TypeScript-5-3178C6?logo=typescript&logoColor=white)
![FastAPI](https://img.shields.io/badge/FastAPI-API-009688?logo=fastapi&logoColor=white)
![SQLAlchemy](https://img.shields.io/badge/SQLAlchemy-data%20layer-D71F00)
![Demo scope](https://img.shields.io/badge/data-synthetic%20demo-8157A8)

**LabelTrace is a working full-stack prototype** for following a product-information change through label variants, evidence, validation, human approval, and controlled release. A reviewer approves a specific immutable artifact and its dependency snapshot. If a relevant fact, template, rule, or artifact changes, that old approval remains visible in history but cannot authorize release of the new state.

> **Scope:** synthetic demonstration only. Not for clinical use, manufacturing, or production labeling. The prototype does not certify FDA compliance, determine UDI obligations, verify physical print quality, or replace validated enterprise systems.

---

## 🔎 The problem

When approved product information changes, labeling teams must reconcile source documents, facts, packaging configurations, artwork, review comments, and release records. Manual coordination can miss a dependent variant, revise an unaffected label, or carry an approval forward after the underlying evidence has changed. Reviewers need to know not only *what changed*, but *why this variant changed*, *why another did not*, and *whether the released file is the exact file they approved*.

## 🔁 The LabelTrace workflow

```mermaid
flowchart LR
  A[Source document and version] --> B[Candidate fact with evidence span]
  B --> C{Checker approves fact}
  C -->|Approved| D[Dependency-based impact assessment]
  D --> E[Processor creates immutable label PDFs]
  E --> F[Validate rendered artwork and dependencies]
  F --> G{Checker approves exact artifact}
  G --> H{Releaser checks current evidence}
  H --> I[Release PDF and evidence ZIP]
  D --> J[Unaffected variants and exclusion reasons]
  K[Relevant upstream edit] --> L[Approval becomes stale for release]
  L --> E
```

### What the system records

**Source document/version → candidate evidence → approved fact/version → label field and dependency → immutable PDF revision/hash → validation run → exact-artifact approval → release manifest.**

Each impact assessment records both included and excluded variants with reasons. An API-side release check re-evaluates the current dependencies, artifact bytes, successful validation, and required approvals before release.

## 🧪 Demonstration scope

- One clearly synthetic family of nonsterile birch-wood tongue depressors: adult 150 mm and pediatric 140 mm.
- Two packaging levels per product (box and carton), giving four US-English label variants.
- A controlled manufacturer-address update affects the two adult labels; the two pediatric labels remain unchanged because they use separate approved facts.
- Versioned product facts and source evidence, element-level dependencies, immutable PDF revisions, versioned rules, review decisions, approvals, releases, and audit events.
- A seeded rendered-QR defect and other bounded defect fixtures show validation failures. A QR here is a synthetic internal code, **not a UDI**.

Expected variant outcomes are defined separately in [`fixtures/expected-results.json`](fixtures/expected-results.json). This is a small reproducible fixture demonstration, not a production performance study. Do not infer measured time savings, cost reductions, safety outcomes, or regulatory compliance from it.

## 👥 Demo profiles

The workspace uses three separate accounts and permission sets. Names are role profiles rather than team members' personal names.

| Workspace profile | Internal permission | Main actions |
| --- | --- | --- |
| **Processor** · Labeling engineer | `author` | Upload sources, propose changes, assess impact, generate and validate draft revisions |
| **Checker** · Quality reviewer | `reviewer` | Review source evidence, approve facts, approve/reject exact label revisions |
| **Releaser** · Release manager | `releaser` | Attempt the controlled release and download the released evidence package |

For local synthetic data, the sign-in screen shows the demo password. The local defaults are `author-1234`, `reviewer-1234`, and `releaser-1234`. These public demo credentials are for disposable synthetic data only. Cloud deployments must use separately configured credentials; do not reuse these passwords for real accounts or data.

## 🏗️ Application architecture

![LabelTrace architecture: React and TypeScript call the FastAPI control plane, which enforces workflow permissions and connects to versioned relational storage, private artifact storage, and optional advisory AI adapters](docs/images/labeltrace-architecture.png)

The browser is the workflow interface; **FastAPI remains the authority** for permissions, evidence freshness, approval, and release. The optional AI path is advisory and cannot update authoritative label fields.

| Area | Implementation |
| --- | --- |
| Frontend | React 19, TypeScript, Vite, Tailwind CSS, Lucide icons |
| Backend | Python 3.12+, FastAPI, Pydantic, SQLAlchemy |
| Database | PostgreSQL configuration for hosted deployments; persistent SQLite development fallback |
| Schema changes | Alembic migrations |
| Local artifacts | Filesystem storage under `data/objects/` |
| Hosted artifact adapters | Private Azure Blob Storage and Vercel Blob |
| Label output | Generated PDF; text/layout inspection and QR decoding from rendered pixels |
| Optional assistance | Azure OpenAI and Azure AI Document Intelligence adapters; not required |

## 💻 Frontend and backend code

The browser is a workflow client. It does not make an approval or release authoritative. For example, the shared frontend API helper sends same-origin requests with the session cookie and surfaces server errors:

```ts
// frontend/src/model.ts — excerpt
export async function api(path: string, body?: unknown, method?: string) {
  const response = await fetch('/api' + path, {
    method: method ?? (body === undefined ? 'GET' : 'POST'),
    credentials: 'same-origin',
    headers: body instanceof FormData ? {} : { 'Content-Type': 'application/json' },
    body: body === undefined
      ? undefined
      : body instanceof FormData ? body : JSON.stringify(body),
  });
  const data = await response.json();
  if (!response.ok) {
    const detail = typeof data.detail === 'string'
      ? data.detail + (data.reasons ? ' · ' + data.reasons.join(' · ') : '')
      : JSON.stringify(data.detail);
    throw new Error(detail);
  }
  return data;
}
```

FastAPI performs the release decision on the server. A blocked release returns a conflict response with the reason; a successful decision is persisted by the workflow layer:

```python
# backend/main.py — excerpt
@app.post("/api/revisions/{id}/release")
def release(id: str, ctx=Depends(context)):
    db, user = ctx
    result, errors = w.release(db, w.get(db, m.Revision, id), user)
    if errors:
        return JSONResponse(
            {"detail": "Release blocked", "reasons": errors},
            status_code=409,
        )
    return m.dump(result)
```

The actual request/response contract and permissions are documented in [`docs/API.md`](docs/API.md). For the complete implementation, see [`frontend/src/`](frontend/src/) and [`backend/`](backend/).

## 🚀 Run locally

Docker Desktop is optional. The direct local path uses Python, npm, persistent SQLite, and local filesystem storage. No paid API key or AI provider is needed.

### Requirements

- Python 3.12 or newer
- Node.js and npm compatible with the checked-in lockfile (Node.js 22 or newer recommended)
- PowerShell on Windows, or a POSIX shell on macOS/Linux

### Install and start

From the repository root (`labeltrace/`):

```powershell
python -m venv .venv
\.venv\Scripts\python.exe -m pip install -r backend/requirements-lock.txt
\.venv\Scripts\python.exe manage.py start
```

Open [http://127.0.0.1:5173](http://127.0.0.1:5173). FastAPI's interactive API documentation is at [http://127.0.0.1:8000/docs](http://127.0.0.1:8000/docs). Stop both processes with **Ctrl+C**.

`manage.py start` applies migrations, initializes synthetic seed data when configured, installs frontend packages with `npm ci` when needed, then starts FastAPI and Vite. Local SQLite data lives in `data/labeltrace.db`; local documents and artifacts live under `data/objects/`.

macOS/Linux virtual-environment command:

```bash
python3 -m venv .venv
.venv/bin/python -m pip install -r backend/requirements-lock.txt
.venv/bin/python manage.py start
```

### Reset the disposable demonstration

Stop the application first, then run from the repository root:

```powershell
\.venv\Scripts\python.exe manage.py reset
```

Reset is restricted to `development`, `demo`, or `test`. It rebuilds application database tables from synthetic fixtures; it does not delete stored object files. Do not run it against data you need to retain.

### Optional local PostgreSQL

If a PostgreSQL instance is already available, create a dedicated database and set the connection string in an untracked `.env` file:

```dotenv
DATABASE_URL=postgresql+psycopg://labeltrace:replace-me@127.0.0.1:5432/labeltrace
```

Then use the same start command. SQLite is the documented local fallback. Its serialized-write behavior is **not evidence of PostgreSQL locking or multi-instance concurrency**. See [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) and [`docs/VERIFICATION.md`](docs/VERIFICATION.md) for the database-specific verification boundaries. Docker Compose is also available as an optional route in [`compose.yaml`](compose.yaml).

## ⚙️ Configuration

Copy [`.env.example`](.env.example) to `.env` for local overrides. Never commit `.env`, cloud credentials, database passwords, or private storage tokens.

| Setting | Local default | Purpose |
| --- | --- | --- |
| `APP_ENV` | `development` | Enables safe local/demo-only reset and defect fixtures |
| `DATABASE_URL` | `sqlite:///data/labeltrace.db` | SQLAlchemy database connection |
| `LABELTRACE_DATA` | `./data` | Local database and object root |
| `STORAGE_BACKEND` | `local` | `local`, `azure`, or hosted `vercel_blob` adapter |
| `AI_MODE` | `deterministic` | No provider calls; optional Azure OpenAI requires explicit configuration |
| `DOCUMENT_EXTRACTOR` | `local` | Deterministic text-PDF/text extraction by default |
| `SEED_DEMO` | `1` locally | Initialize only the synthetic workspace |

The app rejects unsupported extraction cases such as scanned PDFs when OCR is not configured; it does not invent transcription results. Document text is treated as untrusted input, never as application instructions.

## 🛡️ Integrity, permissions, and automation boundaries

- Product facts and templates—not generated suggestions—control authoritative label fields.
- Variant impact uses explicit relational field dependencies and applicability conditions, with recorded inclusion and exclusion explanations.
- Reprocessing is idempotent. Label revisions are immutable; a correction creates another revision.
- Validation is tied to an artifact hash, dependency snapshot, and rule version. A selected QR check decodes the rendered artwork; it does not establish physical print quality.
- Review approval binds to the exact revision, artifact hash, dependency snapshot, validation run, reviewer, and time. Role permissions and separation-of-duties checks are enforced by FastAPI.
- The release endpoint rechecks that evidence is current before it records a release and packages evidence. Old approvals and released artifacts remain in history.
- SHA-256 supports byte-integrity checks; it is **not an electronic signature**.
- AI may assist extraction or explanations only when explicitly configured. It cannot approve facts or releases, invent identifiers or safety statements, or decide UDI obligations. Deterministic mode remains fully usable without AI credentials.

## ✅ Validation and project evidence

Run the repository's automated checks with:

```powershell
\.venv\Scripts\python.exe manage.py test
```

This command runs the backend test suite, frontend Vitest checks, and frontend production build. Existing machine-readable reports and the recorded browser workflow are linked from [`docs/VERIFICATION.md`](docs/VERIFICATION.md); review their dates and limitations before quoting results. Do not treat the synthetic fixture outcomes as general accuracy, cost savings, clinical benefits, or compliance evidence.

The step-by-step resettable walkthrough is in [`docs/DEMO.md`](docs/DEMO.md). The architecture and selected regulatory references are in [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) and [`docs/regulatory-sources.json`](docs/regulatory-sources.json). API roles, paths, status codes, and evidence export are in [`docs/API.md`](docs/API.md).

## ☁️ Deployment paths

- **Current hosted demonstration:** [labeltrace-virid.vercel.app](https://labeltrace-virid.vercel.app), using PostgreSQL and private Vercel Blob storage. Availability and free-tier terms can change.
- **Azure target:** Azure Static Web Apps, Linux App Service source deployment, PostgreSQL Flexible Server, and private Blob Storage. Optional AI adapters use managed identity where configured. See [`docs/AZURE_DEPLOYMENT.md`](docs/AZURE_DEPLOYMENT.md), [`infra/`](infra/), and [`.env.azure.example`](.env.azure.example).
- **Docker Compose:** optional local container setup only; Docker is not needed for direct local development.

Do not provision cloud resources without reviewing the region, current pricing, subscription, and identity requirements. The deployment notes distinguish configured infrastructure from cloud behavior that still requires verification.

## 🗂️ Repository map

```text
backend/                 FastAPI routes, workflow, SQLAlchemy models, storage, AI adapters
frontend/src/            React/TypeScript workspace and API client
migrations/              Alembic database migrations
fixtures/                Synthetic source documents and independent expected outcomes
docs/                    API, architecture, demo, Azure, regulatory, verification notes
docs/images/             README hero and architecture visuals (PNG embeds + SVG sources)
infra/                   Azure deployment templates and CI workflow
artifacts/               Sample labels, evidence exports, reports, and genuine screenshots
manage.py                Direct local start, init, reset, migrate, and test commands
```

## 👩‍💻 Developed by

**Janice Benita F.**  
B.Tech, Information Technology

Areas of interest: Artificial Intelligence, Explainable AI, Data Analytics, Quality Engineering, Industrial AI Applications, and Digital Transformation.

- [GitHub](https://github.com/Janicebenita)
- [LinkedIn](https://linkedin.com/in/janice13)

## 🤝 Feedback and collaboration

Quality professionals, labeling and quality engineers, laboratory specialists, healthcare operations teams, researchers, and digital-transformation practitioners are invited to review the **synthetic LabelTrace workflow** and share feedback.

**Which labeling or quality-control workflow should be explored next?**

Please do not submit patient information, confidential company documents, or real regulated product records through the public demonstration.

## 📜 License

This project is licensed under the [MIT License](LICENSE). Domain standards, regulatory materials, and referenced publications remain the property of their respective organizations.

---

**LabelTrace** · A prototype for source-backed change control and evidence-bound release.  
Built around one principle: **Every edit has a source. Every release has proof.**
