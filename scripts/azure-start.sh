#!/usr/bin/env bash
set -euo pipefail
# Oryx activates the deployed virtual environment before invoking this script.
# One worker is deliberate. PostgreSQL's shared transaction gate remains authoritative.
python -m backend.wait_dependencies
python -m alembic upgrade head
exec python -m uvicorn backend.main:app --host 0.0.0.0 --port 8000 --workers 1
