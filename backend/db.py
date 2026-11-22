"""SQLite demo: BEGIN IMMEDIATE. PostgreSQL: singleton transaction gate FOR UPDATE.

All writes use this gate; concurrency is deliberately coarse for this small POC.
JSON snapshots are immutable evidence; dependencies themselves are relational rows.
"""
import os
import uuid
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlsplit

from sqlalchemy import JSON, Integer, String, UniqueConstraint, create_engine, event, select, text
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, sessionmaker
from sqlalchemy.pool import NullPool

ROOT = Path(__file__).resolve().parents[1]
DATA = Path(os.getenv("LABELTRACE_DATA", str(ROOT / "data"))).resolve()
DATA.mkdir(parents=True, exist_ok=True)
AZURE_DATABASE = os.getenv("DATABASE_AUTH") == "azure_identity"
URL = "postgresql+psycopg://" if AZURE_DATABASE else (
    os.getenv("DATABASE_URL")
    or os.getenv("POSTGRES_URL")
    or os.getenv("POSTGRES_PRISMA_URL")
    or "sqlite:///" + (DATA / "labeltrace.db").as_posix()
)
if not AZURE_DATABASE and URL.startswith(("postgres://", "postgresql://")):
    URL = URL.replace("postgres://", "postgresql+psycopg://", 1).replace("postgresql://", "postgresql+psycopg://", 1)
if os.getenv("APP_ENV") == "production" and not AZURE_DATABASE:
    if not URL.startswith("postgresql+psycopg://"):
        raise ValueError("Production requires PostgreSQL; SQLite is development-only")
    if not AZURE_DATABASE and "sslmode=" not in URL:
        raise ValueError("Production PostgreSQL URL must explicitly configure TLS with sslmode")
is_sqlite = URL.startswith("sqlite")
is_vercel = os.getenv("VERCEL") == "1"
parsed_url = urlsplit(URL)
is_serverless_transaction_pooler = (
    is_vercel
    and not is_sqlite
    and parsed_url.hostname is not None
    and (
        (parsed_url.hostname.endswith(".pooler.supabase.com") and parsed_url.port == 6543)
        or "-pooler." in parsed_url.hostname
    )
)
connect_args = {"check_same_thread": False, "timeout": 30} if is_sqlite else {}
if is_serverless_transaction_pooler:
    # Keep the serverless transaction-pooler path conservative. Neon supports
    # protocol prepared statements, but disabling client-side auto-prepare also
    # works across pooled provider modes and avoids session-state assumptions.
    connect_args["prepare_threshold"] = None
engine_options = {"connect_args": connect_args, "pool_pre_ping": True}
if is_serverless_transaction_pooler:
    # Do not hold a second pool of connections in ephemeral serverless workers.
    engine_options["poolclass"] = NullPool
elif is_vercel and not is_sqlite:
    # Keep a single connection per function instance for direct/session URLs.
    engine_options.update(pool_size=1, max_overflow=0, pool_recycle=300)
engine = create_engine(URL, **engine_options)
Session = sessionmaker(engine, expire_on_commit=False)

if AZURE_DATABASE:
    @event.listens_for(engine, "do_connect")
    def token_connection(dialect, connection_record, args, params):
        from .azure_auth import postgres_connect_parameters
        # Obtain a token for each new physical connection; never freeze an expired
        # token in DATABASE_URL or log a credential-bearing connection string.
        args.clear()
        params.clear()
        params.update(postgres_connect_parameters())

if URL.startswith("sqlite"):
    @event.listens_for(engine, "connect")
    def pragmas(conn, _):
        conn.execute("PRAGMA foreign_keys=ON")
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA busy_timeout=30000")

def now():
    return datetime.now(timezone.utc).isoformat()

class Base(DeclarativeBase):
    pass

class Gate(Base):
    __tablename__ = "workflow_gate"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)

class Entity:
    id: Mapped[str] = mapped_column(String(40), primary_key=True, default=lambda: uuid.uuid4().hex)
    key: Mapped[str] = mapped_column(String(200), index=True)
    version: Mapped[int] = mapped_column(Integer, default=1)
    data: Mapped[dict] = mapped_column(JSON)
    actor: Mapped[str] = mapped_column(String(80), default="system")
    created: Mapped[str] = mapped_column(String(50), default=now)

def table(name):
    return type(name.title().replace("_", ""), (Entity, Base), {
        "__tablename__": name,
        "__table_args__": (UniqueConstraint("key", "version", name=f"uq_{name}_key_version"),),
    })

User = table("users")
LoginSession = table("login_sessions")
Product = table("products")
Packaging = table("packaging")
Source = table("source_documents")
Candidate = table("candidate_facts")
Fact = table("approved_facts")
Template = table("label_templates")
RuleSet = table("rule_sets")
Label = table("label_variants")
Change = table("change_requests")
Impact = table("impact_assessments")
Revision = table("label_revisions")
Validation = table("validation_runs")
Decision = table("review_decisions")
Approval = table("approvals")
Release = table("releases")
Audit = table("audit_events")
AgentRun = table("agent_runs")

class Dependency(Base):
    __tablename__ = "field_dependencies"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    label_id: Mapped[str] = mapped_column(String(40), index=True)
    field: Mapped[str] = mapped_column(String(80))
    fact_key: Mapped[str] = mapped_column(String(200), index=True)
    condition: Mapped[dict] = mapped_column(JSON, default=dict)
    __table_args__ = (UniqueConstraint("label_id", "field"),)

IMMUTABLE = (Fact, Template, RuleSet, Revision, Validation, Decision, Approval, Release, Audit, Impact, AgentRun)
for cls in IMMUTABLE:
    @event.listens_for(cls, "before_update")
    def prevent_update(mapper, connection, target):
        raise ValueError("Historical evidence records are immutable; create a new version")
    @event.listens_for(cls, "before_delete")
    def prevent_delete(mapper, connection, target):
        raise ValueError("Historical evidence records cannot be deleted")

@contextmanager
def transaction(write=True):
    db = Session()
    try:
        if write:
            if engine.dialect.name == "sqlite":
                db.execute(text("BEGIN IMMEDIATE"))
            else:
                db.execute(select(Gate).where(Gate.id == 1).with_for_update())
        yield db
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()

@contextmanager
def read_only_transaction():
    """Session whose DATABASE transaction is read-only (used by every AI-agent read).

    PostgreSQL: SET TRANSACTION READ ONLY as the first statement, so any INSERT/UPDATE/DELETE/DDL raises.
    SQLite: PRAGMA query_only=ON on this connection, switched off again before the connection is reused.
    Nothing is ever committed. This does not take the global write gate.
    """
    db = Session()
    sqlite = engine.dialect.name == "sqlite"
    try:
        db.execute(text("PRAGMA query_only=ON" if sqlite else "SET TRANSACTION READ ONLY"))
        yield db
    finally:
        try:
            db.rollback()
            if sqlite:
                db.execute(text("PRAGMA query_only=OFF"))
                db.rollback()
        except Exception:
            try:
                db.connection().invalidate()  # never return a possibly query_only connection to the pool
            except Exception:
                pass
        db.close()

def latest(db, cls, key):
    return db.scalars(select(cls).where(cls.key == key).order_by(cls.version.desc())).first()

def rows(db, cls):
    return list(db.scalars(select(cls).order_by(cls.created, cls.version)))

def add(db, cls, key, data, actor="system"):
    old = latest(db, cls, key)
    obj = cls(key=key, version=old.version + 1 if old else 1, data=data, actor=actor)
    db.add(obj)
    db.flush()
    return obj

def dump(obj):
    return {"id": obj.id, "key": obj.key, "version": obj.version, "created": obj.created, "actor": obj.actor, **obj.data}

def audit(db, action, target, actor, detail=None):
    previous = rows(db, Audit)
    return add(db, Audit, uuid.uuid4().hex, {"action": action, "target": target, "detail": detail or {}, "previous_event": previous[-1].id if previous else None}, actor)
