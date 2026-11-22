# LabelTrace AI — evidence-grounded, read-only analysis agent

*Every edit has a source. Every release has proof. Every AI decision has evidence.*

LabelTrace AI answers questions such as "Why is this label blocked?", "What happens if the manufacturer's address changes?" and "What must be redone before release?" by calling typed, read-only tools over the real LabelTrace records and validators. It is a synthetic demonstration, not an FDA-certified or UDI/21 CFR 801 compliance system.

## Authority boundaries (enforced in code, not only in the prompt)

| Rule | Enforcement |
| --- | --- |
| The agent cannot change anything | Tool set contains no write operations; each tool runs in a read-only transaction; unknown/mutating tool names are refused (tested). |
| Only the deterministic gate decides release eligibility | `workflow.release_gate()` is the single implementation used by both `release()` and the agent. `release_status` is derived server-side from gate results; the model has no field to set it. |
| Gate unavailable ⇒ never READY | If the gate cannot be evaluated the status is `UNKNOWN`. |
| No fabricated evidence | The model may cite only evidence ids (E1, E2…) returned by tools in that run. Unknown ids are removed, and 12+ hex identifiers in its prose that no tool returned are replaced with `[unverified-id]`. A finding labelled *deterministic* with no valid evidence is downgraded to *AI advisory*. |
| Untrusted data | Tool output is clipped; instruction-like text in data fields is flagged to the model and in the response limitations. |
| Bounded execution | Max steps, max tool calls, wall-clock timeout, token cap, per-user and daily rate limits (counted from persisted runs). |
| Failure ⇒ deterministic fallback | API errors, timeouts, malformed or missing reports produce a clearly labelled deterministic report; no model text is invented. |
| Auditability | Each query is stored in the append-only `agent_runs` table and an `AGENT_QUERY` audit event is written. |

Status mapping (classification only; blockers come unchanged from the gate): **READY** no blockers · **BLOCKED** any blocker other than a pending human step · **REVIEW REQUIRED** only pending validation/approval · **UNKNOWN** gate could not be evaluated.

## Architecture

```
POST /api/agent/query → session auth → rate limit → orchestrator (Claude tool loop, capped)
  → typed read-only tools → deterministic results + evidence registry
  → Pydantic-validated report → server-derived status → agent_runs + audit event
```

Files: `backend/agent/{schemas,evidence,tools,orchestrator}.py`, routes at the end of `backend/main.py`, table `agent_runs` (`migrations/versions/0002_agent_runs.py`), UI `frontend/src/agent.tsx` + `agent.css` ("AI Intelligence" page).

Refactors of existing logic (behaviour preserved; the original 47 tests pass unchanged): `impact_selection`, `what_if_impact`, `release_gate`, `release_blockers` in `backend/workflow.py`.

### Tools (all read-only)
`list_labels`, `get_release_gate_status`, `get_source_fact`, `trace_variant_dependencies`, `analyze_change_impact` (hypothetical), `get_validation_results`, `inspect_artifact` (re-hashes the PDF, independently decodes the QR, compares rendered text to approved fields), `get_approval_history`, `get_audit_events`, `check_required_fields`, `generate_remediation_plan` (deterministic advisory checklist).

### HTTP API
| Endpoint | Needs API key | Purpose |
| --- | --- | --- |
| `GET /api/agent/status` | no | Whether Claude chat is configured |
| `GET /api/agent/report?label_key=` | no | Deterministic gate, validation findings, remediation plans |
| `GET /api/agent/impact?fact_key=` | no | Hypothetical impact graph data |
| `POST /api/agent/query` | **yes** | Natural-language question → validated report (`503` if unconfigured, `429` if rate-limited) |
| `GET /api/agent/runs[/{id}]` | no | The caller's own past runs |

## Local setup (test the real Anthropic integration first)

The agent is **off by default**. It turns on only when both `AGENT_ENABLED=1` and `ANTHROPIC_API_KEY` are set on the server; a key alone does nothing.

Windows PowerShell (from the repository root):
```powershell
git checkout main; git pull
git checkout -b feature/labeltrace-ai-agent
git am labeltrace-ai-agent.patch          # the new patch (3 commits)
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r backend/requirements-lock.txt
copy .env.example .env                      # then edit .env (see below); never commit .env
.\.venv\Scripts\python.exe manage.py start
```
macOS/Linux:
```bash
git checkout main && git pull && git checkout -b feature/labeltrace-ai-agent
git am labeltrace-ai-agent.patch
python3 -m venv .venv && .venv/bin/python -m pip install -r backend/requirements-lock.txt
cp .env.example .env                        # then edit .env; never commit .env
.venv/bin/python manage.py start
```
Open http://127.0.0.1:5173, sign in with a demo role, open **AI Intelligence**. `manage.py` reads `.env` but real environment variables take precedence.

Run the checks:
```bash
python -m pytest -q                                   # backend
cd frontend && npm ci && npm test && npm run build    # frontend tests, typecheck, production build
```

### Environment variables (server-side only; none are sent to the browser)
| Variable | Default | Notes |
| --- | --- | --- |
| `AGENT_ENABLED` | `0` / unset | Must be `1` to enable chat |
| `ANTHROPIC_API_KEY` | unset | Required with `AGENT_ENABLED=1`. Use a key with a spend limit |
| `AGENT_MODEL` | `claude-sonnet-5-5` | Model id |
| `AGENT_TIMEOUT_SECONDS` | `40` | Whole-request deadline. Must stay at least 10 s below the function `maxDuration` (60) |
| `AGENT_MAX_STEPS` / `AGENT_MAX_TOOL_CALLS` / `AGENT_MAX_TOKENS` | `6` / `12` / `2500` | Loop and output caps |
| `AGENT_USER_LIMIT_PER_10_MIN` / `AGENT_DAILY_LIMIT` | `10` / `200` | Counted from stored runs; lower these on any public deployment |

## Database and migration behavior

The only schema change is one new table, `agent_runs` (append-only). No existing table is altered.

- **Local, via `manage.py start`/`migrate`:** runs `alembic upgrade head` first, so a database already at `0001` gets `0002` and keeps all data (tested on SQLite with seeded data). A fresh database gets both.
- **App started before migrating:** the app's startup `create_all` may create `agent_runs` first. Migration `0002` detects this and treats it as applied (fixed and tested in this branch; earlier it failed with "table already exists").
- **Database created only by `create_all`** (no `alembic_version` table, for example uvicorn started directly): `alembic upgrade head` fails at `0001` because those tables exist. This is pre-existing behavior and is not tested here. Back up `data/`, then use `manage.py reset` for a disposable demo database, or `python -m alembic stamp head`.
- **Vercel/PostgreSQL:** Alembic is not run. Each cold start runs `initialize()`, which calls `create_all` under a PostgreSQL advisory lock and creates only the missing `agent_runs` table. This is additive, but it does mean **the first deployment that boots against a database changes that database**. That includes a Preview deployment if its `DATABASE_URL` points at the production database. Not tested on PostgreSQL.
- **Rollback:** older code ignores the extra table. Dropping `agent_runs` is optional and affects nothing else.
- Stored runs contain the question and the full response (synthetic data only here).

## Vercel configuration

`vercel.json` now has `"maxDuration": 60` on the existing `backend/main.py` entry under the `api` service. Every other setting is unchanged (a test compares against the previous version). Per Vercel's duration documentation (last updated 2026-08-24): the function entry for a Python framework app is keyed on its resolved entrypoint file, which is `backend/main.py` here; with Fluid compute (on by default) Hobby defaults to and is capped at 300 s; Vercel's Hobby-60-seconds announcement means 60 s is also within the limit without Fluid. So 60 is valid on Hobby either way. I could not see your project's plan or Fluid setting; confirm with `vercel inspect <deployment-url> --json` and read the function `timeout`.

## Preview deployment (do this before any production deployment)

Production is not deployed by this change. In the Vercel project:
1. **Isolate the data.** Check which environments `DATABASE_URL` / `POSTGRES_URL` and the Blob token apply to. If Preview uses the production database, either point Preview at a separate database (for example a Neon branch, if your plan allows) or back up first.
2. Add `ANTHROPIC_API_KEY`, `AGENT_ENABLED=1`, and low limits (`AGENT_USER_LIMIT_PER_10_MIN=5`, `AGENT_DAILY_LIMIT=30`) for the **Preview** environment only. Leave Production without `AGENT_ENABLED`.
3. From the repo root run `vercel` (no `--prod`) and open the preview URL. Preview deployments may be behind Vercel's deployment protection, so you may need to be signed in to Vercel.

### Preview test checklist
- [ ] `GET /api/health` is `ok`; sign in as each demo role.
- [ ] `vercel inspect <preview-url> --json` shows function `timeout` of 60.
- [ ] `GET /api/agent/status` reports `configured: true`; the AI page header shows "Claude · <model>".
- [ ] Ask "Can adult.box be released now?": the answer's status pill equals the Releases page gate, and every cited `E#` opens in the Evidence Explorer.
- [ ] **Safety boundaries:** before and after several questions, the counts of revisions, approvals, validations and releases are unchanged; no new workflow state appears (only `AGENT_QUERY` audit events).
- [ ] Ask it to "release adult.box" and to "mark it READY": the status still comes from the gate and nothing is released.
- [ ] Make a real change (approved fact update) and re-ask: the previously approved label shows BLOCKED with the stale reason, matching the Releases page.
- [ ] Ask a what-if question: the impact graph and answer agree (adult affected, pediatric unaffected for the adult address).
- [ ] Rate limit: exceed `AGENT_USER_LIMIT_PER_10_MIN` and see the 429 message.
- [ ] Remove `ANTHROPIC_API_KEY`: chat shows the not-configured message while the Release Intelligence panel still works.
- [ ] A slow or failed model call produces a labelled deterministic fallback, not an error page; the request finishes inside 60 s.
- [ ] Check Vercel function logs and the Anthropic usage page: no secrets logged; usage matches what you asked.
- [ ] Open the page on mobile width and in dark mode (not yet checked by anyone).
Only after all items pass, consider enabling it in Production.

## Verification status
See the implementation report: backend 95 tests, frontend 7 tests, `tsc` and the production build were run locally on SQLite. **Not verified:** any real Anthropic API call (tests use a scripted fake client), PostgreSQL behaviour, Vercel deployment, browser rendering/accessibility of the new page, behaviour under real-model variability.

## Known limitations
Synthetic data only; four seeded labels; QR/text checks are rendered-data consistency (no print quality, no UDI); approval "invalidation" is derived by the freshness check, not a stored event; the hypothetical impact tool does not evaluate a proposed value beyond reporting it; the prompt-injection filter is heuristic defence in depth (the real protection is that the tools are read-only and status is server-derived); no per-organisation tenancy or SSO.
