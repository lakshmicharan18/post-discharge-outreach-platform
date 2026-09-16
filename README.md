# Multi-Hospital Post-Discharge Outreach Platform

Milestones 1–3 implement the multi-tenant foundation, JWT/RBAC, structured healthcare data, hospital operational configuration, and discharge ingestion. All demo records are synthetic. Campaigns, eligibility, queues, AI, telephony, and dashboards remain deferred.

## Architecture

```text
backend/app/
  api/             thin HTTP routes and reusable dependency wiring
  core/            configuration, async database, JWT/password security, context, errors
  models/          SQLAlchemy entities and database constraints
  schemas/         Pydantic request/public response schemas
  repositories/    scoped data access; separate identity/platform lookup
  services/        authentication, authorization, relationships, transactions
  queue/ workers/ ai/ ehr/ retrieval/ events/ observability/   reserved packages
backend/alembic/    versioned PostgreSQL migrations
backend/tests/      PostgreSQL-backed auth/RBAC/tenant/regression tests
frontend/           Next.js login, configuration, patient context, import pages
seed/               demo identities plus deterministic 240-patient generator
scripts/            test helper
docs/               architecture, authentication, verification
```

Requests flow through route → service → repository → PostgreSQL. UUID keys, timezone-aware timestamps, tenant-scoped repositories, and composite foreign keys from Milestone 1 are preserved. The product source is [Project_Requirements.pdf](Project_Requirements.pdf), which is stored at the repository root.

Authentication uses Argon2id (`pwdlib`) and signed, expiring JWTs (`PyJWT`). Each protected request validates the token and reloads the user's active status, role, and hospital from the database. `X-Dev-User-ID`, `X-Role`, and `X-Hospital-ID` cannot authenticate or change scope. The former development identity path is removed. Details: [authentication](docs/authentication.md), [tenant architecture](docs/architecture.md).

The healthcare layer separates Patient, Encounter, Discharge, Condition, Observation, Medication, CarePlan, and Procedure. **This prototype uses a simplified FHIR-like domain model and does not claim full FHIR compliance.** Configuration, relationships, import schemas, idempotency, CSV format, transaction boundaries, timeline behavior, campaign lifecycle, dynamic eligibility, and limitations are documented in [healthcare data and ingestion](docs/healthcare-data.md) and [campaign eligibility](docs/campaign-eligibility.md).

## Roles and tenant isolation

| Role | Scope | Allowed |
| --- | --- | --- |
| PLATFORM_ADMIN | Platform | List/create hospital metadata; own identity |
| HOSPITAL_ADMIN | Own hospital | Read/create clinical records; list/create hospital users; own identity |
| CAMPAIGN_MANAGER | Own hospital | Read patient/encounter/discharge data; own identity |
| CLINICAL_REVIEWER | Own hospital | Read patient/encounter/discharge data; own identity |

**Platform Admin does not automatically have unrestricted patient clinical access.** It receives 403 from clinical endpoints/repositories, including individual record retrieval. Hospital-bound requests derive their tenant from authenticated identity. Foreign-tenant record lookups return the same 404 as nonexistent records. Hospital/user creation inputs cannot override the authenticated tenant; hospital admins cannot create platform admins.

## Setup and environment

Prerequisites: Python 3.12+ (Docker uses 3.13), uv, Node.js 20.9+, npm, PostgreSQL, and optionally Docker with Compose v2. Compose targets PostgreSQL 16. Dependencies are locked in `backend/uv.lock` and `frontend/package-lock.json`.

From the repository root, for a **fresh installation**:

```bash
cp .env.example .env
python -c 'import secrets; print(secrets.token_urlsafe(48))'
```

Paste the generated value into `JWT_SECRET` in `.env`. Replace the two database password placeholders with the same local password. Do not overwrite an existing configured `.env`; add the JWT settings to it instead. Do not commit secrets. A hexadecimal database password avoids URL encoding issues.

| Variable | Purpose |
| --- | --- |
| `DATABASE_URL` | Local backend/Alembic connection using `postgresql+psycopg://USER:PASSWORD@HOST:PORT/DB`; URL-encode reserved password characters. |
| `JWT_SECRET` | Required random signing key, at least 32 bytes; no default. |
| `JWT_ACCESS_TOKEN_EXPIRE_MINUTES` | Token lifetime, default 30; permitted range 1–1440. |
| `ENVIRONMENT` | `development`, `test`, or `production`; production disables demo seeding. |
| `POSTGRES_USER`, `POSTGRES_DB` | Compose database identity; defaults `outreach`. |
| `POSTGRES_PASSWORD` | Required Compose database password. |
| `POSTGRES_PORT`, `BACKEND_PORT` | Host ports; defaults 5432 and 8000. |
| `TEST_DATABASE_URL` | Disposable PostgreSQL test database ending in `_test`. |

Backend settings read root `.env` when run from `backend/`; environment variables take precedence. Compose constructs its internal URL using hostname `postgres`.

Frontend configuration goes in `frontend/.env.local` (copy `frontend/.env.example`):

| Variable | Purpose |
| --- | --- |
| `BACKEND_URL` | Server-side API address; default `http://127.0.0.1:8000`. |
| `SESSION_COOKIE_SECURE` | Set `false` for local HTTP, `true` for HTTPS deployments; defaults true in production builds. |

The signing key is never needed by the frontend. Its server handlers store the access token in an HttpOnly, SameSite=Strict cookie and forward it as Bearer authorization. Browser JavaScript never receives the JWT. Login/logout require a matching Origin header. Logout clears the browser session; JWT revocation is not implemented.

## Start locally

With PostgreSQL already running and `.env` configured:

```bash
# Terminal 1, from repository root
cd backend
uv sync --frozen
uv run alembic upgrade head
uv run python ../seed/demo.py
uv run python ../seed/synthetic.py
uv run uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload
```

```bash
# Terminal 2, from repository root
cd frontend
cp .env.example .env.local  # first run only
npm ci
npm run dev -- --hostname 127.0.0.1
```

Open http://127.0.0.1:3000/login. Authenticated pages include `/configuration`, `/patients`, patient detail/context, `/import`, `/campaigns`, and campaign detail/eligibility. API docs: http://127.0.0.1:8000/docs. Health: http://127.0.0.1:8000/api/v1/health.

For a production-build smoke test over local HTTP, run `npm run build`, then `SESSION_COOKIE_SECURE=false npm run start -- --hostname 127.0.0.1` from `frontend/`.

## Docker Compose backend/database

With root `.env` configured:

```bash
docker compose up --build -d
docker compose logs backend
docker compose exec backend .venv/bin/python seed/demo.py
docker compose exec backend .venv/bin/python seed/synthetic.py
curl http://127.0.0.1:8000/api/v1/health
```

Compose waits for database health, migrates, and starts Uvicorn; data persists in a named volume. Both services bind to loopback. Start the frontend separately with the commands above. For future multi-replica deployment, run migrations as a separate deployment step.

## Demo credentials — development only

All seven seeded accounts use **`DemoOnly-ChangeMe-2026!`**. These are public demonstration credentials for synthetic data only; never enable these accounts with real patient data. Seeding is blocked when `ENVIRONMENT=production`.

| Scope | Role | Email |
| --- | --- | --- |
| Platform | PLATFORM_ADMIN | `platform.admin@example.test` |
| Hospital A | HOSPITAL_ADMIN | `hospital_admin.1@example.test` |
| Hospital A | CAMPAIGN_MANAGER | `campaign_manager.1@example.test` |
| Hospital A | CLINICAL_REVIEWER | `clinical_reviewer.1@example.test` |
| Hospital B | HOSPITAL_ADMIN | `hospital_admin.2@example.test` |
| Hospital B | CAMPAIGN_MANAGER | `campaign_manager.2@example.test` |
| Hospital B | CLINICAL_REVIEWER | `clinical_reviewer.2@example.test` |

The seed retains two hospitals, three patients and encounters/discharges per hospital, and seven users. Reruns do not duplicate data or overwrite existing passwords. Existing known demo users with no hash receive the demo password during seeding.

`seed/synthetic.py` deterministically imports 120 additional patients per hospital (240 total) using seed `20260916`. It varies discharge age, clinical risk, follow-up windows, care setting, condition, medication, language, and communication preferences. Reruns return the same import jobs and do not create duplicate records. Run `seed/demo.py` first.

## API usage

```bash
curl -sS http://127.0.0.1:8000/api/v1/auth/login \
  -H 'Content-Type: application/json' \
  -d '{"email":"hospital_admin.1@example.test","password":"DemoOnly-ChangeMe-2026!"}'
```

Login returns `access_token`, `token_type`, `expires_in` (seconds), and public `user` information. Use the returned access token:

```bash
curl http://127.0.0.1:8000/api/v1/users/me -H 'Authorization: Bearer YOUR_ACCESS_TOKEN'
curl http://127.0.0.1:8000/api/v1/patients -H 'Authorization: Bearer YOUR_ACCESS_TOKEN'
```

| Endpoint | Behavior |
| --- | --- |
| `GET /api/v1/health` | Public database health check. |
| `POST /api/v1/auth/login` | Public JSON email/password login. |
| `GET /api/v1/users/me` | Current identity, role, hospital metadata. |
| `GET /api/v1/users` | Hospital-admin-only tenant user list. |
| `POST /api/v1/users` | Hospital-admin-only create; fields `email`, `full_name`, `role`, `password`. |
| `GET /api/v1/{patients,encounters,discharges}` | Hospital-scoped lists. |
| `GET /api/v1/{patients,encounters,discharges}/{id}` | Hospital-scoped retrieval. |
| `POST /api/v1/{patients,encounters,discharges}` | Hospital-admin-only create. |
| `GET/POST /api/v1/platform/hospitals` | Platform-admin-only hospital metadata. |
| `GET/PUT /api/v1/hospital/configuration` | Hospital-scoped read; hospital-admin-only update. |
| `GET/PUT /api/v1/platform/hospitals/{id}/configuration` | Platform-admin nonclinical configuration. |
| `GET/POST /api/v1/patients/{id}/{conditions,observations,medications,care-plans,procedures}` | Tenant-scoped resource read; hospital-admin-only create. |
| `GET /api/v1/patients/{id}/context` | Structured patient context for the authenticated hospital. |
| `GET /api/v1/patients/{id}/timeline` | Chronological healthcare events. |
| `POST /api/v1/discharges/import` | Hospital-admin JSON batch import. |
| `POST /api/v1/discharges/import/csv` | Hospital-admin UTF-8 CSV upload, max 5 MiB. |
| `GET /api/v1/discharges/imports/{id}` | Tenant-scoped import result. |

List endpoints support `limit` (1–100, default 50) and `offset` (default 0). Unauthenticated/invalid-token requests return 401 with `WWW-Authenticate: Bearer`; role failures return 403. Password hashes never appear in responses. Errors retain the existing `{"error":{"code":"...","message":"...","request_id":"UUID"}}` envelope. Validation errors do not echo submitted credentials.

## Database migrations

```bash
cd backend
uv run alembic upgrade head
uv run alembic current
uv run alembic check
```

Milestone 1 and 2 migrations remain unchanged. Migration `10c82d1fbab4` creates configuration, five clinical-resource tables, import/audit records, enriched discharge fields, indexes, and configurations for existing hospitals.

On a **disposable database only**, verify the Milestone 3 rollback with `uv run alembic downgrade 2a0000000001`, then `uv run alembic upgrade head`. To verify the older Milestone 2 rollback, downgrade to `e18e73d6e369`; that rollback preserves user records but deletes password hashes. Do not run either downgrade on the working database.

## Tests and verification

Tests require real PostgreSQL and use per-test transactions/savepoints. Create a test database once; for the default Compose setup:

```bash
docker compose exec postgres createdb -U outreach outreach_test
export TEST_DATABASE_URL='postgresql+psycopg://outreach:YOUR_PASSWORD@localhost:5432/outreach_test'
bash scripts/test.sh -q
# Authentication/RBAC tests only:
bash scripts/test.sh -q tests/test_auth.py
# Milestone 3 tests only:
bash scripts/test.sh -q tests/test_configuration.py tests/test_healthcare.py tests/test_ingestion.py
# Milestone 1 regression coverage, now using bearer authentication:
bash scripts/test.sh -q tests/test_api.py tests/test_tenant_isolation.py
```

The helper checks the `_test` database suffix, applies migrations there, and runs Pytest. Tests generate an isolated signing key and use the actual token-validation dependency, not an authorization bypass. The original development-header tests are adapted to assert its removal and secure key configuration; existing tenant/data behavior remains covered.

```bash
cd backend
uv run ruff check app tests ../seed alembic
uv run ruff format --check app tests ../seed alembic
cd ../frontend
npm run typecheck
npm run build
```

With both seeded applications running, verify the real HTTP/cookie flow from `backend/`:

```bash
uv run python ../scripts/smoke_auth.py
```

This checks all seven demo logins, tenant and platform boundaries, session-cookie attributes, same-origin enforcement, and logout. It expects local HTTP cookies (`SESSION_COOKIE_SECURE=false`). For Milestone 3 live verification run `uv run python ../scripts/smoke_m3.py`; it checks configuration, partial/idempotent import, timeline/context, the authenticated proxy, and all new pages.

[Verification results](docs/verification.md) record actual executed checks. An import example is available at [docs/example-discharge-import.json](docs/example-discharge-import.json). Refresh tokens, MFA, password reset/invitations, login throttling, server-side logout revocation, terminology validation, and production deployment hardening remain outside this prototype milestone. No queue, AI, telephony, mock-EHR sync, or dashboard workflows were added.

Campaign activation currently validates configuration and evaluates dynamic eligibility only. It does not create or schedule outbound work; queue creation and scheduling are implemented in Milestone 5.
