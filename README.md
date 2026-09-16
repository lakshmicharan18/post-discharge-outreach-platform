# Multi-Hospital Post-Discharge Outreach Platform

Milestone 1 implements the project foundation and multi-tenant core. FastAPI owns data access and tenant authorization; Next.js provides a minimal TypeScript landing page. All demonstration records are synthetic.

## Architecture

```text
backend/
  app/
    api/             HTTP routes and dependency wiring
    core/            configuration, database sessions, identity context, errors
    models/          SQLAlchemy entities and database constraints
    schemas/         Pydantic input/output models
    repositories/    mandatory hospital-scoped clinical queries
    services/        relationship validation and transaction boundaries
    queue/ workers/ ai/ ehr/ retrieval/ events/ observability/
                     reserved packages only
  alembic/           versioned PostgreSQL migrations
  tests/             PostgreSQL-backed API/repository/constraint tests
frontend/            Next.js App Router and TypeScript
seed/                repeatable synthetic seed
scripts/             verification helper
docs/               architecture and verification notes
```

Request flow: route → service → repository → PostgreSQL. Services own commits and rollbacks. Each request uses an async SQLAlchemy session. Routes contain no business logic.

Hospital, User, Patient, Encounter, and Discharge have UUID primary keys. Patient, Encounter, and Discharge require `hospital_id`. Timestamps use PostgreSQL `TIMESTAMP WITH TIME ZONE`; incoming encounter/discharge timestamps must include an offset. Creation/update timestamps on hospitals, users, and patients are database-initialized, with SQLAlchemy updating `updated_at` on ORM writes.

Clinical repositories require a `RequestContext(user_id, hospital_id, role)` and apply hospital predicates to both list and individual-record queries. Create operations assign the hospital from context. Composite foreign keys also prevent cross-hospital patient/encounter/discharge relationships and discharges referencing the wrong patient. External identifiers are unique per hospital; their composite unique indexes support tenant-local lookups. Platform administration only exposes hospital metadata; platform admins receive 403 from clinical repositories even if given a hospital ID. See [tenant design](docs/architecture.md).

## Prerequisites and configuration

Use Python 3.12+ (Docker uses 3.13), `uv`, Node.js 20.9+, npm, and Docker with Compose v2. PostgreSQL 16 is configured in Compose. Backend dependencies are locked in `backend/uv.lock`; frontend dependencies in `frontend/package-lock.json`.

From the repository root:

```bash
cp .env.example .env
```

Replace both password placeholders in `.env` with the same local password. A random hexadecimal password avoids URL escaping issues. Do not commit `.env`.

| Variable | Purpose |
| --- | --- |
| `DATABASE_URL` | Required for local backend/migrations; `postgresql+psycopg://USER:PASSWORD@HOST:PORT/DB`. URL-encode reserved password characters. |
| `POSTGRES_USER` | Compose database user; default `outreach`. |
| `POSTGRES_PASSWORD` | Required Compose database password. |
| `POSTGRES_DB` | Compose database; default `outreach`. |
| `POSTGRES_PORT` | Host database port; default `5432`. |
| `BACKEND_PORT` | Host API port; default `8000`. |
| `ENVIRONMENT` | `development`, `test`, or `production`. |
| `ENABLE_DEV_AUTH` | Default `false`; explicitly enable only for local synthetic-data demos. |
| `TEST_DATABASE_URL` | Explicit disposable database ending in `_test`, used by the tests. |

Backend settings read the root `.env` when run from `backend/`; process environment variables take precedence. Compose constructs its own backend database URL using service hostname `postgres`; local commands use `DATABASE_URL`.

## Start with Docker Compose

```bash
docker compose up --build -d
docker compose logs backend
curl http://localhost:8000/api/v1/health
docker compose exec backend .venv/bin/python seed/demo.py
```

The backend waits for PostgreSQL readiness, runs `alembic upgrade head`, then starts Uvicorn. Database data persists in a named volume. Services bind to loopback. For future multi-replica deployment, run migrations as a separate deployment step.

Start the frontend separately:

```bash
cd frontend
npm ci
npm run dev
```

Frontend: http://localhost:3000. API health: http://localhost:8000/api/v1/health. OpenAPI UI: http://localhost:8000/docs. Health checks database connectivity and returns 503 with the standard error envelope if unavailable. The frontend is a foundation page, without clinical data access or dashboards.

## Run the backend locally

Start PostgreSQL with `docker compose up -d postgres`, or use an existing UTF-8 PostgreSQL database and adjust `DATABASE_URL`.

```bash
cd backend
uv sync --frozen
uv run alembic upgrade head
uv run python ../seed/demo.py
uv run uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

## Development identity and endpoints

Real authentication is deferred. With the default `ENABLE_DEV_AUTH=false`, every protected route returns 401. In production, enabling development authentication fails configuration validation. To exercise synthetic data locally, set `ENABLE_DEV_AUTH=true` and restart the backend (`docker compose up -d backend` for Compose).

The local adapter accepts `X-Dev-User-ID` and resolves the user's hospital, role, active flag, and hospital status from PostgreSQL. This header is **not a credential**: anyone with local API access can select a seeded identity. Replace `get_context` with a verified authentication dependency before exposing clinical data. `X-Hospital-ID` and `X-Role` do not affect authorization.

Seed creates Hospital A and B, three role-specific users and three patients per hospital, one encounter/discharge per patient, and a separate platform admin. Running it twice does not duplicate the demo records.

| Identity | Demo UUID |
| --- | --- |
| Hospital A admin | `00000000-0000-0000-0000-000000000064` |
| Hospital B admin | `00000000-0000-0000-0000-0000000000c8` |
| Platform admin | `00000000-0000-0000-0000-0000000003e7` |

```bash
curl -H 'X-Dev-User-ID: 00000000-0000-0000-0000-000000000064' \
  http://localhost:8000/api/v1/patients
```

Clinical routes support `GET` list, `GET /{id}`, and `POST` at `/api/v1/patients`, `/api/v1/encounters`, and `/api/v1/discharges`. Lists accept `limit` (1–100, default 50) and `offset` (default 0). POST schemas reject extra fields, including client-supplied `hospital_id`. Cross-tenant IDs return the same 404 as nonexistent records. All three hospital roles currently share these foundation operations; finer workflow permissions are deferred. `/api/v1/platform/hospitals` supports platform-admin-only GET and POST. Users are seeded; user-management endpoints are deferred.

Errors follow `{"error":{"code":"not_found","message":"Record not found","request_id":"UUID"}}`. Responses include `X-Request-ID`. Error responses/logs exclude request values, SQL, and exception messages that might contain sensitive data.

## Migrations

Run from `backend/`:

```bash
uv run alembic upgrade head
uv run alembic current
uv run alembic check
# After model changes, generate and review the migration:
uv run alembic revision --autogenerate -m "describe change"
```

The initial migration creates all five tables, the role enum, indexes, and tenant relationship constraints. Rollback is supported with `uv run alembic downgrade base`, which **deletes all application tables and data**; use only on a disposable database.

## Tests and checks

Tests require real PostgreSQL and an explicitly selected, migrated test database. They use per-test transactions/savepoints and roll back their fixtures. They never create/drop application tables themselves and do not use SQLite.

Create the test database once (with the default Compose user):

```bash
docker compose exec postgres createdb -U outreach outreach_test
```

From the repository root, set its URL with your local password and run:

```bash
export TEST_DATABASE_URL='postgresql+psycopg://outreach:YOUR_PASSWORD@localhost:5432/outreach_test'
bash scripts/test.sh
```

The helper requires a database name ending in `_test`, applies migrations to that database, then runs Pytest. Coverage includes both hospitals' reads and lists for all clinical entities, cross-tenant writes, direct database constraint enforcement, platform restrictions, tenant-header spoofing, disabled/inactive identities, pagination, validation, and redacted database errors.

Other checks:

```bash
cd backend
uv run ruff check app tests ../seed alembic
uv run ruff format --check app tests ../seed alembic
cd ../frontend
npm run typecheck
npm run build
npm run start
```

## Milestone boundary

Reserved packages are empty. Campaigns, scheduling, Redis/workers, AI/voice agents, RAG, triage, escalation, mock EHR, dashboards, telephony, audit pipelines, and observability systems are not implemented. This milestone supplies request IDs and safe operational errors, not a clinical audit system.

See [verification results](docs/verification.md) for checks performed in the development environment and the Docker runtime limitation.
