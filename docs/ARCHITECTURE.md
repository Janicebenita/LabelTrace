# Architecture and boundaries

**Azure extension:** the deployment target is now SWA Standard + App Service Linux source code + PostgreSQL Flexible Server + private Blob Storage. This document describes the core workflow; `AZURE_DEPLOYMENT.md` adds storage/identity/AI/network controls and `AZURE_VERIFICATION.md` distinguishes tested local behavior from cloud-unverified configuration. Local execution remains Python/npm with SQLite or existing PostgreSQL, without Docker Desktop.

## Modules

React 19 + TypeScript + Vite + Tailwind form a single engineering workspace. FastAPI is the authority for all decisions. SQLAlchemy stores versioned evidence in PostgreSQL or persistent SQLite. Alembic defines the schema. A small local-storage interface provides append-only content-addressed objects. ReportLab creates actual vector PDFs; pypdf reads the complete rendered text; PDFium rasterizes the PDF; ZXing independently decodes QR pixels. No browser state is authoritative.

`backend/db.py` owns version envelopes, transaction gate and ORM immutability guards. `auth.py` owns password/session checks. `workflow.py` owns extraction, review, changes, applicability, generation, validation, approval, freshness and evidence export. `artwork.py` owns PDF rendering and inspection. `main.py` provides typed HTTP endpoints and request-level transaction boundaries. `seed.py` creates only synthetic evidence. `frontend/src/main.tsx` connects nine views to the same API-backed workspace; `model.ts` contains tested projection/diff helpers.

## Data model

Separate tables exist for users, sessions, products, packaging, source documents, candidates, approved facts, templates, label variants, changes, impact assessments, rule sets, revisions, validation runs, review decisions, approvals, releases and audit events. Each evidence envelope has a stable UUID, business key, version, actor, timestamp and JSON payload; `(key, version)` is unique. Explicit field dependencies are relational rows with label ID, element, fact key and applicability conditions. Version references live inside evidence snapshots rather than a graph database. JSON references are checked by application services; they do not have database foreign-key constraints. Schema/index constraints and a mandatory write gate protect version allocation through this API; direct privileged database writes are outside the threat model.

Approved facts identify original document ID/version, SHA-256 and page/text-span evidence. A source upload creates candidates; candidate approval alone does not alter authoritative label information. An approved change appends a fact version and preserves the previous fact. Label revisions record exact fact IDs, template ID, rule-set ID, dependency configuration, element evidence, semantic fields, PDF/preview keys and SHA-256. All artwork content, validations, decisions, approvals and releases are immutable through the ORM/API. State is derived from these records; it is not a browser-editable status flag.

## Impact and freshness

Impact selection matches fact keys through explicit label-element dependencies and checks product, packaging level, market and language conditions. Inclusion and exclusion explanations are retained. Missing dependency configuration or a contradictory condition yields **Needs assessment**, not a silent exclusion. An unchanged pediatric variant is never regenerated for the adult change. Reprocessing the same change/snapshot returns the same assessment and revision; an explicit regenerate action intentionally creates a new revision.

Freshness compares relevant approved fact versions, template/rule versions and the dependency map. Uploading a newer document alone does not invalidate labels; a reviewer-approved material fact change does. Renaming the display metadata of a source does not change fact IDs. Historical approvals remain visible while release becomes ineligible. Released artifacts are retained with a follow-up flag if later impacted; there is no automatic recall decision.

## Validation and release

Validation includes controlled required fields, product/pack IDs, unsupported elements, whole-PDF text comparison, QR decode, fixed field bounds, actual rendered glyph page bounds, artifact integrity, original-source integrity and dependency freshness. Findings include rule/version, severity, expected/observed, field/location, evidence and correction. Bounds are prototype engineering thresholds, not invented regulatory font-size requirements. Barcodes are decoded from PDFium pixels by ZXing, independent of their generating fields; no physical scanner/print-quality claim is made.

Approval requires a separate reviewer, the latest revision, a successful current validation, current evidence and intact artifact bytes. It binds to revision ID, artifact SHA-256, dependency snapshot hash, validation ID, reviewer and timestamp. SHA-256 is an integrity check, **not an electronic signature**. Revalidating after approval creates a new validation record; the conservative release gate rejects an approval tied to an older run, requiring a newly generated/reviewed revision. Previous decisions remain intact.

All write endpoints enter the same transaction gate. Release checks permission, latest revision, fresh dependencies, original-source integrity, actual artifact bytes, current validation and exact approval while that gate is held. It reads verified bytes once and uses those same bytes in the ZIP. The database release row commits only after ZIP creation. Blocked release attempts are persisted audit events. Repeated release of the same already-released revision returns its original release; the artifact/history remain immutable, with subsequent impact shown separately.

## Database-specific concurrency

**SQLite development:** `BEGIN IMMEDIATE` acquires the single writer reservation before reading workflow eligibility. WAL and a 30-second busy timeout permit ordinary reads while serializing writes. The thread race test accepts only release-before-change or change-before-rejected-release. This is a local serialized-writer demonstration; it is not evidence for PostgreSQL behavior or multi-host scaling. SQLite data/objects must stay on a local disk, not a network share. Use one backend process for this POC.

**PostgreSQL configuration:** every write transaction locks row 1 of `workflow_gate` with `SELECT … FOR UPDATE` before eligibility reads. Initialization creates that row before serving requests. The isolation is intentionally coarse. PostgreSQL migration/seed is configured in CI; local PostgreSQL locks, concurrent workers, failures and performance were not verified because no usable PostgreSQL instance was found and Docker was unavailable. Validate these independently before claiming them.

The SQL transaction cannot atomically commit a filesystem object. A crash after writing but before database commit can leave an unreferenced content-addressed object; it cannot create a committed release without gate checks. No object garbage collector is included. Protect database and object directories together; direct disk/DB administrator tampering is not prevented by local storage. Hash checks catch tested artifact/source corruption but are not tamper-proof signing or external audit anchoring. Audit events are append-only through this API, linked by previous event ID, and not a cryptographic signature chain.

## Extraction and AI boundaries

Text PDFs and UTF-8 text are restricted to 5 MiB; PDFs to 30 pages; encrypted/image-only PDFs fail explicitly. Originals are preserved. Deterministic extraction only recognizes allowlisted `key: value` facts with exact evidence spans, rejecting contradictory duplicate values. Source prose/instructions never execute. Optional OpenAI-compatible structured outputs may select exactly grounded candidates. Unsupported fields, unsupported claims, fabricated quotes, omissions, network failure and missing configuration fall back to clearly labeled deterministic extraction. Human review remains mandatory. No live provider output was used in verification.

## Security and scope limits

Separate demo accounts, server-side RBAC, no self-approval, random hashed sessions, PBKDF2 passwords, same-site HttpOnly cookies, trusted write origins, bounded uploads, fixed artifact paths and server-guarded demo defect enums are implemented. Defect creation is disabled outside development/demo/test and never bypasses validation or release. Reset is CLI-only, environment-gated, and intentionally limited to disposable synthetic databases.

Production hardening is incomplete: no SSO/MFA, login rate limiting, antivirus scanning, external audit anchoring, immutable object-store policy, encrypted backup strategy, per-tenant access, accessibility certification, load qualification, e-signature/21 CFR Part 11 assessment, full document/configuration-control integration, multilingual/market expansion or physical printing. Rendering/extraction is synchronous and suitable for this small fixture set, not high-volume workloads. Templates have a fixed supported field set; configuration-version controls create reviewer-approved versions, not a general artwork designer. Change rejection is supported at candidate/artwork review; the source-fact change flow is approve-only in this POC and no enterprise change-board workflow is claimed.

## Case Study 4 requirement mapping

| Brief criterion | Implemented evidence | Boundary |
|---|---|---|
| Problem understanding / lifecycle | Sources → changes → impact → artwork → review → release | Market/gap assessment represented by fixed US scope |
| Regulatory awareness | Versioned source-backed rule subset | Complete compliance is explicitly excluded |
| AI / automation innovation | Grounded extraction adapter and deterministic evidence manifests | No live provider or autonomous regulatory decisions |
| End-to-end coverage | Actual PDF and ZIP downloads with source/fact/review history | PLM/ERP/manufacturing handoff simulated |
| Accuracy / validation | Independent oracle, negative fixtures, rendered QR decode | Small synthetic set; no general accuracy or savings claim |
| Traceability / auditability | Element sources, immutable histories, stale-release rejection | No externally anchored audit or e-signature |
