"""Bounded cloud startup retry; no credentials or provider responses in logs."""
import time
from sqlalchemy import text
from .db import engine
from .storage import store

def main(timeout_seconds=180):
    deadline=time.monotonic()+timeout_seconds
    while True:
        try:
            with engine.connect() as db:
                db.execute(text('SELECT 1'))
            store.healthcheck()
            return
        except Exception:
            if time.monotonic()>=deadline:
                raise SystemExit('Configured database/private storage unavailable. Check Entra SQL role, RBAC and private DNS; no fallback enabled.')
            print('Waiting for configured database and private storage...',flush=True)
            time.sleep(5)
if __name__=='__main__':main()
