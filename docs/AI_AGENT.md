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

## Setup
```bash
pip install -r backend/requirements-lock.txt
cp .env.example .env     # set AGENT_ENABLED=1 and ANTHROPIC_API_KEY, or export them
python manage.py start   # existing launcher; open the "AI Intelligence" page
```
The key is read only on the server and is never sent to the browser.

## Vercel deployment (not performed here)
1. In the Vercel project settings add encrypted environment variables: `ANTHROPIC_API_KEY`, `AGENT_ENABLED=1`, optionally `AGENT_MODEL` and the `AGENT_*` limits above. Never commit them.
2. **Function duration:** the agent timeout defaults to 40 s. Confirm your plan's function limit covers it (the repo's own notes cite 60 s for non-Fluid Hobby functions); if the platform default is lower, raise `maxDuration` for `backend/main.py` in `vercel.json` or lower `AGENT_TIMEOUT_SECONDS`. This was not tested on Vercel.
3. **Database:** startup calls `create_all`, which adds the missing `agent_runs` table to an existing database without touching other tables. Verified on SQLite only; for PostgreSQL either let startup create it or run `python manage.py migrate`. Back up first. `agent_runs` uses the same schema shape as the other evidence tables.
4. **Cost/abuse:** the hosted demo shows shared demo credentials. Keep the per-user and daily limits low, or leave `AGENT_ENABLED` unset to keep the deterministic panels only.
5. Redeploy, then verify (below). Do not point tests at production data.

### Post-deploy verification checklist
- `GET /api/health` is `ok`; sign in as a demo role.
- `GET /api/agent/status` → `configured: true`; the AI page shows "Claude · <model>".
- Ask "Can adult.box be released now?" → the status pill equals the Releases page gate; every cited `E#` opens in the Evidence Explorer.
- Check the timeline lists only tool calls; confirm no workflow record changed (revisions, approvals, releases).
- Temporarily unset the key → chat shows the 503 message while the Release Intelligence panel still works.

## Verification status
See the implementation report: backend 87 tests, frontend 7 tests, `tsc` and the production build were run locally on SQLite. **Not verified:** any real Anthropic API call (tests use a scripted fake client), PostgreSQL behaviour, Vercel deployment, browser rendering/accessibility of the new page, behaviour under real-model variability.

## Known limitations
Synthetic data only; four seeded labels; QR/text checks are rendered-data consistency (no print quality, no UDI); approval "invalidation" is derived by the freshness check, not a stored event; the hypothetical impact tool does not evaluate a proposed value beyond reporting it; the prompt-injection filter is heuristic defence in depth (the real protection is that the tools are read-only and status is server-derived); no per-organisation tenancy or SSO.
