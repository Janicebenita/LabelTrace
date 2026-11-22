"""Migration 0002 must work whether it runs before or after the app's startup create_all()."""
import os
import sqlite3
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]

def alembic(db, *args):
    env = {**os.environ, "APP_ENV": "test", "DATABASE_URL": f"sqlite:///{db}", "LABELTRACE_DATA": str(db.parent)}
    return subprocess.run([sys.executable, "-m", "alembic", *args], cwd=ROOT, env=env, capture_output=True, text=True)

def info(db):
    c = sqlite3.connect(db)
    has = bool(c.execute("select 1 from sqlite_master where name='agent_runs'").fetchone())
    return has, c.execute("select version_num from alembic_version").fetchone()[0]

def test_upgrade_from_0001_preserves_data_and_adds_table(tmp_path):
    db = tmp_path / "a.db"
    assert alembic(db, "upgrade", "0001").returncode == 0
    c = sqlite3.connect(db)
    c.execute("insert into users (id,key,version,data,actor,created) values ('u1','k',1,'{}','system','2026-01-01')"); c.commit(); c.close()
    r = alembic(db, "upgrade", "head")
    assert r.returncode == 0, r.stderr
    assert info(db) == (True, "0002")
    assert sqlite3.connect(db).execute("select count(*) from users").fetchone()[0] == 1

def test_upgrade_succeeds_when_startup_already_created_the_table(tmp_path):
    db = tmp_path / "b.db"
    assert alembic(db, "upgrade", "0001").returncode == 0
    sqlite3.connect(db).executescript("""create table agent_runs (id varchar(40) primary key, key varchar(200) not null,
        version integer not null, data json not null, actor varchar(80) not null, created varchar(50) not null);""")
    r = alembic(db, "upgrade", "head")
    assert r.returncode == 0, r.stderr
    assert info(db) == (True, "0002")

def test_downgrade_removes_only_the_agent_table(tmp_path):
    db = tmp_path / "c.db"
    assert alembic(db, "upgrade", "head").returncode == 0
    assert alembic(db, "downgrade", "0001").returncode == 0
    assert info(db) == (False, "0001")
