# Milestone 3 verification

Verified on 2026-09-16 with Python 3.13, PostgreSQL 14.24, Node.js 20.20.2, and Next.js 16.3.5.

| Check | Result |
| --- | --- |
| Full PostgreSQL-backed backend suite | **156 passed** |
| Milestone 1–2 regression suite | All prior **113** tests passed in the full run |
| Milestone 3 coverage | **43** configuration, healthcare, ingestion, timeline, CSV, audit, and isolation tests passed |
| Alembic upgrade | Passed on working and test databases |
| Populated Milestone 2 → 3 upgrade | Passed with existing legacy user/data |
| Milestone 3 downgrade and re-upgrade | Passed on a separate disposable database |
| Alembic model/schema check | No new upgrade operations detected |
| Deterministic generator | 240/240 imported across two hospitals |
| Generator rerun | Same two import IDs; table counts unchanged |
| Dataset after demo + generator | 246 patients/encounters/discharges, 240 each conditions/observations/medications/care plans, 120 procedures |
| Ruff lint/format | Passed |
| Frontend TypeScript and production build | Passed; 10 routes generated |
| Live Milestone 3 smoke | Configuration, partial/idempotent import, safe errors, context/timeline, pages, and authenticated proxy passed |
| Docker Compose configuration | Standalone Compose v2.29.7 validation passed; runtime unavailable |

The original Milestone 1 and Milestone 2 migrations are unchanged. Migration `10c82d1fbab4` was applied to a database already at Milestone 2, downgraded back to `2a0000000001`, reapplied, and checked against SQLAlchemy metadata. Existing hospitals received default configuration rows during migration.

The full tests use actual PostgreSQL, signed bearer tokens, tenant-scoped repositories, and per-test savepoints. New coverage includes:

- hospital-admin configuration updates and data-minimized audit events;
- platform configuration access without clinical access;
- all five healthcare resources, both nested and direct UUID reads;
- Hospital A/B isolation for every new resource and patient timeline;
- JSON and CSV imports, partial success, graph rollback, and validation errors;
- batch digest, patient/encounter/resource upserts, and duplicate prevention;
- client-supplied hospital identifiers and guessed cross-tenant encounter UUIDs;
- chronological timeline and structured patient-context responses;
- unauthenticated and non-admin import rejection;
- errors/import records that do not echo submitted patient values.

Live verification ran against Uvicorn and the Next.js production server on loopback ports 8000 and 3000. `scripts/smoke_m3.py` logged in through the real JWT endpoint, performed one valid plus one invalid record import, repeated it to confirm the same import ID, loaded the resulting patient context/timeline, and exercised the browser session proxy and new page routes. The invalid phone value did not appear in responses.

The generator uses fixed seed `20260916` and an anchored synthetic timeline. Its second run returned the same completed import IDs and left record counts unchanged. The live smoke adds one extra obviously synthetic patient to the ignored local development database; distributed seed output remains 240 generated plus six small demo patients.

Docker is not installed in this environment. Compose configuration is valid, but image build/container startup were not executed. Compose targets PostgreSQL 16; executed checks used PostgreSQL 14.24. Frontend verification used production build/typecheck plus automated HTTP calls, rather than browser automation. This prototype does not claim FHIR compliance or regulatory compliance.

Reproduce the checks:

```bash
export TEST_DATABASE_URL='postgresql+psycopg://outreach:YOUR_PASSWORD@localhost:5432/outreach_test'
bash scripts/test.sh -q

cd backend
uv run alembic check
uv run python ../seed/demo.py
uv run python ../seed/synthetic.py
uv run python ../scripts/smoke_m3.py  # with both apps running

cd ../frontend
npm run typecheck
npm run build
```
