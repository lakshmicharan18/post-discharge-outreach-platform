# Testing and verification

The backend test suite is PostgreSQL-backed. `TEST_DATABASE_URL` must point to a
disposable PostgreSQL database whose name ends in `_test`.

```bash
export TEST_DATABASE_URL='postgresql+psycopg://USER:PASSWORD@localhost:5432/outreach_test'
bash scripts/test.sh -q
```

Current verified result: **235 passed**.

Run formatting and lint checks from `backend/`:

```bash
uv run ruff check app tests ../seed alembic
uv run ruff format --check app tests ../seed alembic
```

Verify schema state and, only on a disposable database, a migration rollback:

```bash
uv run alembic upgrade head
uv run alembic current
uv run alembic downgrade -1
uv run alembic upgrade head
```

The verified Alembic head is `a91e2c4d7b10`.

Run the deterministic safety benchmark tests:

```bash
cd backend
PYTHONPATH=. uv run pytest -q tests/test_safety_evaluation.py
```

Those tests validate the fixed synthetic dataset, reproducibility, confusion
matrix calculation, FNR calculation, and conservative treatment of adversarial,
ambiguous, incomplete, and conflicting scenarios. They do not establish
real-world clinical safety or regulatory compliance.
