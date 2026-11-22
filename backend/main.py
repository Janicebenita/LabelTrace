import os
import uuid
from contextlib import asynccontextmanager
from typing import Literal
from fastapi import FastAPI, Depends, File, Form, Query, Request, Response, UploadFile
from fastapi.responses import JSONResponse, Response as BinaryResponse
from pydantic import BaseModel, Field
from urllib.parse import urlparse
from . import db as m, workflow as w
from .auth import login, user_from_request
from .seed import initialize
from .storage import store, digest
from .agent import orchestrator as ag
from .agent.schemas import AgentRequest, LABEL_KEY
from .agent.tools import KEY as FACT_KEY, ToolContext, execute_tool

@asynccontextmanager
async def lifespan(app):
    initialize()
    yield

app = FastAPI(title="LabelTrace", version="0.1.0", lifespan=lifespan,
    description="Synthetic demonstration. Authoritative facts, immutable artwork, exact-artifact approval and controlled evidence release. No regulatory certification.")

@app.middleware("http")
async def security(request, call_next):
    origin = request.headers.get("origin")
    allowed = os.getenv("ALLOWED_ORIGINS", "http://localhost:5173,http://127.0.0.1:5173,http://localhost:8000,http://127.0.0.1:8000").split(",")
    same_vercel_origin = False
    if origin and os.getenv("VERCEL") == "1":
        parsed = urlparse(origin)
        same_vercel_origin = parsed.scheme == "https" and parsed.netloc == request.headers.get("host")
    if request.method not in {"GET", "HEAD", "OPTIONS"} and origin and origin not in allowed and not same_vercel_origin:
        return JSONResponse({"detail": "Untrusted request origin"}, status_code=403)
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["Cache-Control"] = "no-store"
    return response

def context(request: Request):
    with m.transaction(write=request.method not in {"GET", "HEAD"}) as db:
        yield db, user_from_request(db, request)

class Credentials(BaseModel):
    email: str
    password: str

class Review(BaseModel):
    approve: bool = True
    reason: str = Field(default="", max_length=1000)

class Propose(BaseModel):
    candidate_id: str
    reason: str = Field(min_length=1, max_length=1000)

class Generate(BaseModel):
    change_id: str | None = None
    force: bool = False

class DemoDefect(Generate):
    defect: Literal["barcode", "missing", "identifier", "text", "overflow", "applicability"]

class VersionBump(BaseModel):
    reason: str = Field(min_length=1, max_length=500)

@app.get("/api/health/live")
def liveness():
    return {"status": "ok", "service": "labeltrace-api"}

@app.get("/api/health")
@app.get("/api/health/ready")
def health():
    try:
        with m.transaction(False) as db:
            if db.get(m.Gate, 1) is None:
                raise RuntimeError("Schema not initialized")
        store.healthcheck()
    except Exception:
        return JSONResponse({"status":"unavailable","detail":"Database or private artifact storage is not ready"},status_code=503)
    return {"status": "ok", "database": m.engine.dialect.name,
            "storage": os.getenv("STORAGE_BACKEND","local"), "synthetic": True}

@app.post("/api/login")
def signin(body: Credentials, response: Response):
    with m.transaction() as db:
        token, user = login(db, body.email, body.password)
        response.set_cookie("labeltrace_session", token, httponly=True, samesite="lax", secure=os.getenv("COOKIE_SECURE") == "1", max_age=28800)
        return {"name": user.data["name"], "role": user.data["role"]}

@app.post("/api/logout")
def logout(request: Request, response: Response, ctx=Depends(context)):
    import hashlib
    db,user=ctx
    session=m.latest(db,m.LoginSession,hashlib.sha256(request.cookies.get("labeltrace_session", "").encode()).hexdigest())
    if session:
        session.data={**session.data,"expires":"2000-01-01T00:00:00+00:00"}
    response.delete_cookie("labeltrace_session")
    return {"ok": True}

@app.get("/api/workspace")
def workspace(ctx=Depends(context)):
    return w.state(*ctx)

@app.post("/api/sources")
def upload_source(product: str=Form(...), file: UploadFile=File(...), ctx=Depends(context)):
    db,user=ctx
    data=file.file.read(int(os.getenv("MAX_SOURCE_BYTES", str(5*1024*1024)))+1)
    source=w.upload(db,product,file.filename or "",data,user)
    return m.dump(source)

@app.post("/api/candidates/{id}/review")
def review_candidate(id: str, body: Review, ctx=Depends(context)):
    db,user=ctx
    return m.dump(w.candidate_decision(db,w.get(db,m.Candidate,id),body.approve,body.reason,user))

@app.post("/api/changes")
def propose(body: Propose, ctx=Depends(context)):
    db,user=ctx
    return m.dump(w.propose_change(db,body.candidate_id,body.reason,user))

@app.post("/api/changes/{id}/approve")
def approve_change(id: str, ctx=Depends(context)):
    db,user=ctx
    return m.dump(w.approve_change(db,w.get(db,m.Change,id),user))

@app.post("/api/changes/{id}/impact")
def assess(id: str, ctx=Depends(context)):
    db,user=ctx
    w.role(user,"author","reviewer")
    return m.dump(w.impact(db,w.get(db,m.Change,id),user))

@app.get("/api/changes/{id}/explanation")
def explanation(id: str, ctx=Depends(context)):
    from .azure_assistance import explain_change
    db,user=ctx
    return explain_change(w.get(db,m.Change,id))

@app.post("/api/labels/{id}/generate")
def generate(id: str, body: Generate, ctx=Depends(context)):
    db,user=ctx
    return m.dump(w.generate(db,w.get(db,m.Label,id),body.change_id,user,force=body.force))

@app.post("/api/demo/labels/{id}/defect")
def inject(id: str, body: DemoDefect, ctx=Depends(context)):
    if os.getenv("APP_ENV","development") not in {"development","demo","test"}:
        w.fail("Defect fixtures disabled outside demo/development",404)
    db,user=ctx
    w.role(user,"author")
    return m.dump(w.generate(db,w.get(db,m.Label,id),body.change_id,user,defect=body.defect,force=True))

@app.post("/api/revisions/{id}/validate")
def validate(id: str, ctx=Depends(context)):
    db,user=ctx
    return m.dump(w.validate(db,w.get(db,m.Revision,id),user))

@app.post("/api/revisions/{id}/review")
def review(id: str, body: Review, ctx=Depends(context)):
    db,user=ctx
    return m.dump(w.approve_revision(db,w.get(db,m.Revision,id),user,body.approve,body.reason))

@app.post("/api/revisions/{id}/release")
def release(id: str, ctx=Depends(context)):
    db,user=ctx
    result, errors=w.release(db,w.get(db,m.Revision,id),user)
    if errors:
        return JSONResponse({"detail":"Release blocked", "reasons":errors},status_code=409)
    return m.dump(result)

@app.post("/api/templates/{key}/version")
def bump_template(key: str, body: VersionBump, ctx=Depends(context)):
    db,user=ctx
    w.role(user,"reviewer")
    old=m.latest(db,m.Template,key)
    if not old: w.fail("Template not found",404)
    result=m.add(db,m.Template,key,{**old.data,"revision_reason":body.reason},user.id)
    m.audit(db,"TEMPLATE_VERSION_APPROVED",result.id,user.id)
    return m.dump(result)

@app.post("/api/rules/{key}/version")
def bump_rules(key: str, body: VersionBump, ctx=Depends(context)):
    db,user=ctx
    w.role(user,"reviewer")
    old=m.latest(db,m.RuleSet,key)
    if not old: w.fail("Rules not found",404)
    result=m.add(db,m.RuleSet,key,{**old.data,"revision_reason":body.reason},user.id)
    m.audit(db,"RULESET_VERSION_APPROVED",result.id,user.id)
    return m.dump(result)

@app.post("/api/sources/{id}/rename")
def rename(id: str, body: VersionBump, ctx=Depends(context)):
    db,user=ctx
    w.role(user,"author")
    source=w.get(db,m.Source,id)
    source.data={**source.data,"display_name":body.reason}
    m.audit(db,"SOURCE_METADATA_UPDATED",id,user.id,{"display_name":body.reason,"material_change":False})
    return m.dump(source)

@app.get("/api/files/{kind}/{id}")
def download(kind: str, id: str, ctx=Depends(context)):
    db,user=ctx
    if kind=="source":
        obj=w.get(db,m.Source,id); key=obj.data["storage_key"]; name=obj.data["filename"]
        media="application/pdf" if name.lower().endswith(".pdf") else "text/plain"
    elif kind in {"label","preview"}:
        obj=w.get(db,m.Revision,id); key=obj.data["preview_key" if kind=="preview" else "artifact_key"]
        name=obj.data["label_key"]+f"-r{obj.version}"+(".png" if kind=="preview" else ".pdf")
        media="image/png" if kind=="preview" else "application/pdf"
    elif kind=="evidence":
        obj=w.get(db,m.Release,id); key=obj.data["evidence_key"]; name="LabelTrace-"+obj.data["label_key"]+f"-r{obj.data['revision_version']}-evidence.zip";media="application/zip"
    else:
        w.fail("Unknown artifact type",404)
    try:
        content=store.get(key)
    except OSError:
        w.fail("Stored artifact missing",404)
    if kind=="evidence" and digest(content)!=obj.data["evidence_hash"]:
        w.fail("Evidence integrity check failed")
    if kind in {"source","label","preview"} and digest(content) != key.split(".")[0]:
        w.fail("Artifact integrity check failed")
    import re
    safe_name=re.sub(r'[^A-Za-z0-9._-]','_',name)[:180]
    return BinaryResponse(content,media_type=media,headers={"Content-Disposition":("inline" if kind=="preview" else "attachment")+f'; filename="{safe_name}"'})


# ---- LabelTrace AI (read-only analysis agent). It never takes the global write gate while a model call is in flight.
def agent_user(request: Request):
    with m.read_only_transaction() as db:
        user = user_from_request(db, request)
        return {"id": user.id, "name": user.data["name"], "role": user.data["role"]}

@app.get("/api/agent/status")
def agent_status(request: Request):
    agent_user(request)
    configured = ag.agent_configured()
    return {"configured": configured, "model": ag.settings()["model"] if configured else None,
            "mode": "claude" if configured else "deterministic-only", "read_only": True}

@app.get("/api/agent/report")
def agent_report(request: Request, label_key: str | None = Query(default=None, pattern=LABEL_KEY)):
    """Deterministic gate/validation/remediation report. Uses no LLM and works without an API key."""
    return ag.deterministic_report(agent_user(request), [label_key] if label_key else None)

@app.get("/api/agent/impact")
def agent_impact(request: Request, fact_key: str = Query(pattern=FACT_KEY)):
    """Hypothetical dependency/approval impact of a new version of a fact. Read-only, no LLM."""
    result, ok, error = execute_tool(ToolContext(agent_user(request)), "analyze_change_impact", {"fact_key": fact_key})
    if not ok:
        return JSONResponse({"detail": result["error"]}, status_code=404)
    return {"data": result["data"], "evidence": result["evidence"]}

@app.post("/api/agent/query")
def agent_query(body: AgentRequest, request: Request):
    user = agent_user(request)
    try:
        client = ag.make_client()
    except ag.AgentUnavailable as exc:
        return JSONResponse({"detail": str(exc) + ". Deterministic reports remain available."}, status_code=503)
    try:
        run_id = ag.reserve_run(user, body)  # atomic limit check + counted reservation, before any paid call
    except ag.RateLimited as exc:
        return JSONResponse({"detail": str(exc)}, status_code=429)
    try:
        response, usage = ag.run_agent(user, body, client)
    except Exception as exc:
        ag.fail_run(run_id, user, body, type(exc).__name__)
        return JSONResponse({"detail": "The AI analysis failed unexpectedly. Deterministic reports remain available."}, status_code=500)
    ag.complete_run(run_id, user, body, response, usage)
    return response

@app.get("/api/agent/runs")
def agent_runs(request: Request):
    user = agent_user(request)
    from sqlalchemy import select
    with m.read_only_transaction() as db:
        latest_by_key = {}
        for r in db.scalars(select(m.AgentRun).where(m.AgentRun.actor == user["id"]).order_by(m.AgentRun.created.desc()).limit(80)):
            latest_by_key.setdefault(r.key, r)  # newest version of each run (reservation -> completed)
        return [{"run_id": r.key, "created": r.created, "question": r.data["question"], "mode": r.data.get("mode", "pending"),
                 "release_status": r.data.get("release_status", "UNKNOWN"), "status": r.data.get("status", "completed")}
                for r in list(latest_by_key.values())[:20]]

@app.get("/api/agent/runs/{run_id}")
def agent_run(run_id: str, request: Request):
    user = agent_user(request)
    with m.read_only_transaction() as db:
        run = m.latest(db, m.AgentRun, run_id)
        if not run or run.actor != user["id"]:
            return JSONResponse({"detail": "Run not found"}, status_code=404)
        if "response" not in run.data:
            return JSONResponse({"detail": f"Run has no completed response (status: {run.data.get('status', 'unknown')})"}, status_code=404)
        return {**run.data["response"], "run_id": run.key}
