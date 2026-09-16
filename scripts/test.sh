#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/../backend"
: "${TEST_DATABASE_URL:?Set TEST_DATABASE_URL to a disposable PostgreSQL database ending in _test}"
uv run python - <<'PY'
import os
from sqlalchemy.engine import make_url
url = make_url(os.environ["TEST_DATABASE_URL"])
if url.drivername != "postgresql+psycopg" or not (url.database or "").endswith("_test"):
    raise SystemExit("Refusing to migrate: expected postgresql+psycopg database ending in _test")
PY
DATABASE_URL="$TEST_DATABASE_URL" uv run alembic upgrade head
uv run python -m pytest "$@"
