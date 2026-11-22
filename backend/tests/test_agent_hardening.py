"""P0 hardening: database-level read-only agent access, deadline-safe model calls, concurrency-safe cost controls."""
import time
from concurrent.futures import ThreadPoolExecutor
from types import SimpleNamespace as NS

import anthropic
import httpx
import pytest
from sqlalchemy import text

from backend import db as m
from backend.agent import orchestrator as ag, tools as t
from backend.agent.schemas import AgentRequest
from conftest import login
from test_agent import Fake, USER, configure, report, use

REQ = AgentRequest(question="status of adult.box?", label_key="adult.box")

# ------------------------------------------------------------------ 1. database-level read-only
def test_read_only_transaction_rejects_writes_and_normal_writes_still_work(client):
    with pytest.raises(Exception):
        with m.read_only_transaction() as db:
            m.add(db, m.AgentRun, "should-not-exist", {"x": 1}, "tester")
    with pytest.raises(Exception):
        with m.read_only_transaction() as db:
            db.execute(text("DELETE FROM agent_runs"))
    with m.read_only_transaction() as db:
        assert m.latest(db, m.AgentRun, "should-not-exist") is None
    with m.transaction() as db:   # the read-only mode must not leak onto pooled connections
        m.add(db, m.AgentRun, "legit", {"x": 1}, "tester")
    with m.read_only_transaction() as db:
        assert m.latest(db, m.AgentRun, "legit").data == {"x": 1}

def test_a_tool_that_tries_to_write_fails_and_nothing_is_saved(client, monkeypatch):
    def evil(db, ctx, args):
        m.add(db, m.AgentRun, "evil-write", {"x": 1}, "agent")
        return {"ok": True}
    spec = t.REGISTRY["list_labels"]
    monkeypatch.setitem(t.REGISTRY, "list_labels", t.ToolSpec(spec.name, spec.description, spec.model, evil, spec.roles))
    result, ok, _ = t.execute_tool(t.ToolContext(dict(USER)), "list_labels", {})
    assert ok is False and "failed internally" in result["error"]
    with m.read_only_transaction() as db:
        assert m.latest(db, m.AgentRun, "evil-write") is None

def test_agent_user_and_run_reads_use_read_only_sessions(client, monkeypatch):
    seen = []
    real = m.read_only_transaction
    monkeypatch.setattr(m, "read_only_transaction", lambda: (seen.append(1), real())[1])
    login(client, "reviewer")
    client.get("/api/agent/status"); client.get("/api/agent/runs"); client.get("/api/agent/report")
    assert len(seen) >= 3

def test_report_persistence_still_works_through_the_write_path(client, monkeypatch):
    configure(monkeypatch, Fake(report(summary="done")))
    login(client, "reviewer")
    body = client.post("/api/agent/query", json={"question": "anything useful?"}).json()
    assert body["run_id"] and client.get(f"/api/agent/runs/{body['run_id']}").json()["summary"] == "done"

# ------------------------------------------------------------------ 2. deadline-safe model calls
class Clock:
    def __init__(self): self.now = 1000.0
    def monotonic(self): return self.now

class SlowFake(Fake):
    def __init__(self, clock, delay, *script):
        super().__init__(*script); self.clock, self.delay, self.starts = clock, delay, []
    def create(self, **kw):
        self.starts.append(self.clock.now)
        self.clock.now += self.delay
        return super().create(**kw)

def patch_clock(monkeypatch):
    clock = Clock()
    monkeypatch.setattr(ag, "time", NS(monotonic=clock.monotonic, perf_counter=time.perf_counter))
    return clock

def test_client_never_retries_and_deadline_is_clamped(monkeypatch):
    monkeypatch.setenv("AGENT_ENABLED", "1"); monkeypatch.setenv("ANTHROPIC_API_KEY", "test-not-a-key")
    assert ag.make_client().max_retries == 0
    monkeypatch.setenv("AGENT_TIMEOUT_SECONDS", "600")
    assert ag.settings()["timeout"] == ag.MAX_DEADLINE == 45.0
    monkeypatch.setenv("AGENT_TIMEOUT_SECONDS", "0")
    assert ag.settings()["timeout"] == 5.0

def test_each_call_timeout_fits_inside_the_remaining_budget(client, monkeypatch):
    clock = patch_clock(monkeypatch)
    fake = SlowFake(clock, 3.0)  # never submits a report; loops until a limit stops it
    ag.run_agent(USER, REQ, fake)
    deadline = 1000.0 + ag.settings()["timeout"]
    assert fake.calls
    for start, kw in zip(fake.starts, fake.calls):
        tm = kw["timeout"]
        assert isinstance(tm, anthropic.Timeout) and tm.connect == ag.CONNECT_TIMEOUT
        assert start + tm.connect + tm.read <= deadline - ag.RESERVE + 1e-6
        assert tm.read <= ag.CALL_CAP

def test_slow_model_stops_before_the_deadline_and_falls_back(client, monkeypatch):
    clock = patch_clock(monkeypatch)
    fake = SlowFake(clock, 20.0)
    resp, _ = ag.run_agent(USER, REQ, fake)
    assert resp.mode == "deterministic" and any("time limit" in x for x in resp.limitations)
    assert len(fake.calls) == 2                                   # third call would not fit before deadline - reserve
    assert clock.now - 1000.0 <= ag.settings()["timeout"] + 20.0  # at most one overrun of a single call, never a retry storm

def test_timeout_error_from_the_sdk_is_a_fallback_not_a_crash(client):
    resp, _ = ag.run_agent(USER, REQ, Fake(anthropic.APITimeoutError(request=httpx.Request("POST", "https://api.anthropic.com"))))
    assert resp.mode == "deterministic" and any("APITimeoutError" in x for x in resp.limitations)

# ------------------------------------------------------------------ 3a. input-token budget
def test_input_token_budget_blocks_the_call_before_it_is_made(client, monkeypatch):
    monkeypatch.setenv("AGENT_MAX_INPUT_TOKENS", "100")
    fake = Fake(report(summary="x"))
    resp, usage = ag.run_agent(USER, REQ, fake)
    assert fake.calls == [] and usage["input_tokens"] == 0
    assert resp.mode == "deterministic" and any("input token budget" in x for x in resp.limitations)

class BigUsage(Fake):
    def create(self, **kw):
        out = super().create(**kw); out.usage = NS(input_tokens=58_000, output_tokens=7); return out

def test_cumulative_billed_input_tokens_stop_later_steps(client, monkeypatch):
    monkeypatch.setenv("AGENT_MAX_INPUT_TOKENS", "60000")
    fake = BigUsage([use("list_labels", {})], report(summary="never reached"))
    resp, usage = ag.run_agent(USER, REQ, fake)
    assert len(fake.calls) == 1 and usage["input_tokens"] == 58_000
    assert resp.mode == "deterministic" and any("input token budget" in x for x in resp.limitations)

def test_normal_runs_fit_the_default_budget(client):
    fake = Fake([use("get_release_gate_status", {"label_key": "adult.box"}), use("get_validation_results", {"label_key": "adult.box"})],
                [use("generate_remediation_plan", {"label_key": "adult.box"})], report(summary="ok"))
    resp, _ = ag.run_agent(USER, REQ, fake)
    assert resp.mode == "claude" and len(fake.calls) == 3

# ------------------------------------------------------------------ 3b. concurrency-safe reservations
def test_concurrent_requests_cannot_exceed_the_limit(client, monkeypatch):
    monkeypatch.setenv("AGENT_USER_LIMIT_PER_10_MIN", "3")
    def attempt(_):
        try:
            return ag.reserve_run(USER, REQ)
        except ag.RateLimited:
            return None
    with ThreadPoolExecutor(8) as pool:
        results = list(pool.map(attempt, range(8)))
    assert sum(r is not None for r in results) == 3

def test_daily_limit_is_global_and_counts_reservations_once(client, monkeypatch):
    monkeypatch.setenv("AGENT_DAILY_LIMIT", "2")
    a = ag.reserve_run({"id": "u1", "role": "reviewer"}, REQ)
    ag.complete_run(a, {"id": "u1", "role": "reviewer"}, REQ, ag.deterministic_report(USER, ["adult.box"]), {})  # version 2 must not double count
    ag.reserve_run({"id": "u2", "role": "reviewer"}, REQ)
    with pytest.raises(ag.RateLimited):
        ag.reserve_run({"id": "u3", "role": "reviewer"}, REQ)

def test_failed_persistence_still_counts_and_still_returns_the_answer(client, monkeypatch):
    configure(monkeypatch, Fake(report(summary="a"), report(summary="b")))
    monkeypatch.setenv("AGENT_USER_LIMIT_PER_10_MIN", "1")
    real = m.audit
    monkeypatch.setattr(m, "audit", lambda db, action, *a, **k: (_ for _ in ()).throw(RuntimeError("db down")) if action == "AGENT_QUERY" else real(db, action, *a, **k))
    login(client, "reviewer")
    r = client.post("/api/agent/query", json={"question": "first question"})
    assert r.status_code == 200 and any("could not be saved" in x for x in r.json()["limitations"])
    assert client.post("/api/agent/query", json={"question": "second question"}).status_code == 429
    runs = client.get("/api/agent/runs").json()
    assert len(runs) == 1 and runs[0]["status"] == "reserved"

def test_unexpected_agent_crash_is_counted_and_reported_as_500(client, monkeypatch):
    configure(monkeypatch, Fake())
    monkeypatch.setenv("AGENT_USER_LIMIT_PER_10_MIN", "1")
    monkeypatch.setattr(ag, "run_agent", lambda *a, **k: (_ for _ in ()).throw(RuntimeError("boom")))
    login(client, "reviewer")
    r = client.post("/api/agent/query", json={"question": "first question"})
    assert r.status_code == 500 and "boom" not in r.text
    assert client.post("/api/agent/query", json={"question": "second question"}).status_code == 429
    assert client.get("/api/agent/runs").json()[0]["status"] == "failed"

def test_runs_list_shows_one_row_per_run(client, monkeypatch):
    configure(monkeypatch, Fake(report(summary="a")))
    login(client, "reviewer")
    run_id = client.post("/api/agent/query", json={"question": "first question"}).json()["run_id"]
    runs = client.get("/api/agent/runs").json()
    assert [r["run_id"] for r in runs] == [run_id] and runs[0]["status"] == "completed"

def test_real_sdk_client_accepts_the_timeout_and_does_not_retry(client, monkeypatch):
    """Uses the REAL anthropic client against a closed local port (no network, no key use). A wrong timeout type or a retry would show up here."""
    monkeypatch.setenv("AGENT_ENABLED", "1"); monkeypatch.setenv("ANTHROPIC_API_KEY", "test-not-a-key")
    real = anthropic.Anthropic(api_key="test-not-a-key", base_url="http://127.0.0.1:9", timeout=anthropic.Timeout(ag.CALL_CAP, connect=ag.CONNECT_TIMEOUT), max_retries=0)
    started = time.monotonic()
    resp, _ = ag.run_agent(USER, REQ, real)
    assert time.monotonic() - started < 10
    assert resp.mode == "deterministic" and any("APIConnectionError" in x for x in resp.limitations), resp.limitations
