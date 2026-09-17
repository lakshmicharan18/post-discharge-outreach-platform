# Multi-Hospital Post-Discharge Outreach Platform

A PostgreSQL, FastAPI, and Next.js prototype for coordinating safe,
tenant-isolated post-discharge outreach. It demonstrates how hospitals can
prioritize follow-up work, document patient intake, ground clinical workflows in
hospital knowledge, route uncertain cases to human review, and record the result
through a local Mock EHR boundary. All demonstration data is synthetic.

## What it solves

Post-discharge follow-up is operationally complex: patients need timely contact,
staff need an explainable queue, and potentially concerning responses require
conservative handling. This project keeps hospital data separated while making
the workflow visible from discharge through documented review.

## Key capabilities

- Strict multi-hospital tenant isolation, JWT authentication, and RBAC.
- Patient/discharge records, campaign eligibility, prioritized queue capacity,
  callbacks, retries, manual follow-up, and worker lease recovery.
- Deterministic 25-patient simulation for workflow demonstration.
- Persistent Voice Intake with controlled AI tools and tenant-specific RAG.
- Structured clinical triage, three independent assessments, and application-level
  conservative consensus.
- Human escalation cases, audit events, and idempotent local Mock EHR writes.
- Deterministic safety benchmark with 21 synthetic scenarios.

## Architecture and safety

FastAPI routes delegate to tenant-scoped services and SQLAlchemy/PostgreSQL.
UUIDs, timezone-aware timestamps, audit records, and database constraints support
traceability. AI models receive controlled tool outputs only; they do not receive
direct database access. Consensus is deterministic application logic, not an LLM
instruction. Platform Admin does not receive unrestricted clinical access.

See [architecture](docs/architecture.md), [demo guide](docs/demo-guide.md),
[testing](docs/testing.md), and [safety evaluation](docs/safety-evaluation.md).

## Stack

- Backend: Python, FastAPI, SQLAlchemy async, Alembic, PostgreSQL
- Frontend: Next.js
- Security: signed JWTs, Argon2 password hashing, role and tenant context

## Local setup

Prerequisites: Python 3.12+, `uv`, Node.js 20+, npm, and PostgreSQL.

```bash
cp .env.example .env
# Set DATABASE_URL, TEST_DATABASE_URL, POSTGRES_PASSWORD, and a random JWT_SECRET.
cd backend
uv sync --frozen
uv run alembic upgrade head
uv run python ../seed/demo.py
uv run python ../seed/synthetic.py
uv run uvicorn app.main:app --reload
```

In another terminal:

```bash
cd frontend
cp .env.example .env.local
npm ci
npm run dev
```

Open `http://127.0.0.1:3000/login`; FastAPI docs are at
`http://127.0.0.1:8000/docs`.

### PostgreSQL and migrations

`DATABASE_URL` and `TEST_DATABASE_URL` use
`postgresql+psycopg://USER:PASSWORD@HOST:PORT/DB`. The test database must end in
`_test`.

```bash
cd backend
uv run alembic upgrade head
uv run alembic current  # verified head: a91e2c4d7b10
```

`seed/demo.py` creates demonstration users; `seed/synthetic.py` creates the
deterministic synthetic patient data set.

## Demo credentials

All seeded synthetic demo accounts use `DemoOnly-ChangeMe-2026!`.

| Hospital A role | Email |
| --- | --- |
| Hospital Admin | `hospital_admin.1@example.test` |
| Campaign Manager | `campaign_manager.1@example.test` |
| Clinical Reviewer | `clinical_reviewer.1@example.test` |

Hospital B has equivalent `.2@example.test` accounts. Platform metadata account:
`platform.admin@example.test`.

## Tests and quality checks

```bash
bash scripts/test.sh -q                 # PostgreSQL-backed backend suite
cd backend
uv run ruff check app tests ../seed alembic
uv run ruff format --check app tests ../seed alembic
```

Current verified backend result: **235 passed**. Details are in
[docs/testing.md](docs/testing.md).

## Deterministic simulation and safety evaluation

The simulation exercises a deterministic 25-patient scenario. The safety
benchmark has three fixed examples in each of seven categories: routine,
concerning, urgent, ambiguous, incomplete, conflicting, and adversarial.
Current synthetic benchmark: TP 18, FP 1, TN 2, FN 0; accuracy 95.24%, precision
94.74%, recall 100%, FNR 0%.

**FNR=0 applies only to this fixed deterministic synthetic benchmark. It is not a
real-world clinical safety guarantee.**

## Limitations

This is a prototype, not a production clinical system. It does not claim
regulatory compliance, clinical readiness, real-provider AI behavior, telephony,
or a real EHR/FHIR integration. The Mock EHR is local persistence used to
demonstrate idempotent, auditable workflow integration.
