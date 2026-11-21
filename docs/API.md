# API guide

Base URL `http://127.0.0.1:8000`. Interactive OpenAPI: `/docs`; schema `/openapi.json`. Vite proxies same-origin `/api` calls. Login sets an HttpOnly session cookie. Supply that cookie for every other endpoint except health. `GET` endpoints require an authenticated account unless stated otherwise.

| Method and endpoint | Role | Meaning |
|---|---|---|
| GET `/api/health` | Public | Real DB connectivity and backend health |
| GET `/api/health/live` | Public | FastAPI liveness, no dependency call |
| GET `/api/health/ready` | Public | DB/schema and local/private storage readiness, 503 if unavailable |
| POST `/api/login` | Public | `{email,password}` creates an 8-hour session |
| POST `/api/logout` | Any | Expires server session and removes cookie |
| GET `/api/workspace` | Any | Persistent evidence and derived workflow state |
| POST `/api/sources` | Author | Multipart `product=adult/pediatric`, `file=.pdf/.txt`, <=5 MiB |
| POST `/api/candidates/{id}/review` | Reviewer | `{approve,reason}`; ambiguity blocks approval |
| POST `/api/changes` | Author | `{candidate_id,reason}`; reviewed source evidence required |
| POST `/api/changes/{id}/approve` | Reviewer | Approves a new fact version; base-version conflicts rejected |
| POST `/api/changes/{id}/impact` | Author/reviewer | Idempotent persisted applicability assessment |
| GET `/api/changes/{id}/explanation` | Any authenticated | Deterministic evidence explanation; optional bounded Azure assistance |
| POST `/api/labels/{id}/generate` | Author | `{change_id?,force?}`; immutable PDF generation |
| POST `/api/demo/labels/{id}/defect` | Author, dev/demo/test only | `{change_id?,defect}` where defect is a fixed fixture enum |
| POST `/api/revisions/{id}/validate` | Author/reviewer | Real PDF, pixel-decoded QR and dependency checks |
| POST `/api/revisions/{id}/review` | Reviewer | `{approve,reason}`; approval binds exact validated artifact |
| POST `/api/revisions/{id}/release` | Releaser | Atomic eligibility gate, persistent release record and ZIP |
| POST `/api/templates/{key}/version` | Reviewer | `{reason}` creates a controlled template version |
| POST `/api/rules/{key}/version` | Reviewer | `{reason}` creates a controlled rule-set version |
| POST `/api/sources/{id}/rename` | Author | `{reason}` sets display metadata without material fact change |
| GET `/api/files/source/{id}` | Any | Preserved original source bytes |
| GET `/api/files/label/{revision_id}` | Any | Actual generated PDF |
| GET `/api/files/preview/{revision_id}` | Any | Actual PDFium-rendered PNG |
| GET `/api/files/evidence/{release_id}` | Any | Integrity-checked released evidence ZIP |

Conflicts return 409 with a concrete `detail`; blocked release also returns a `reasons` list and records `RELEASE_BLOCKED`. Permissions return 403; absent records 404; unsupported file type 415; unreadable/scanned/conflicting evidence 422; oversized upload 413. No endpoint accepts a user-supplied storage path, artifact hash, arbitrary status change or approval identity.

Azure keeps these routes behind the same-origin SWA `/api` proxy and authenticated FastAPI session. Artifact downloads never disclose public Blob URLs, account keys or SAS tokens. Optional OCR changes transcript extraction only when explicitly configured; text/provenance and human-review requirements remain visible.

The evidence ZIP includes the exact released PDF, manifest with file hashes, source/fact versions and original sources, revision and template/rule snapshots, change summary, successful validation, label approval history, relevant review decisions and audit events. Store the ZIP as the released package; historical PDFs are not overwritten.
