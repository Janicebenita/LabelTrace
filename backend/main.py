import os
import uuid
from contextlib import asynccontextmanager
from typing import Literal
from fastapi import FastAPI, Depends, File, Form, Request, Response, UploadFile
from fastapi.responses import JSONResponse, Response as BinaryResponse
from pydantic import BaseModel, Field
from urllib.parse import urlparse
from . import db as m, workflow as w
from .auth import login, user_from_request
from .seed import initialize
from .storage import store, digest

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
