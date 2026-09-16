# Milestone 2 verification

Verified on 2026-09-16 with Python 3.13, PostgreSQL 14.24, Node.js 20.20.2, and Next.js 16.3.5.

| Check | Result |
| --- | --- |
| Full PostgreSQL-backed backend suite | **113 passed** (38 adapted Milestone 1 cases + 75 auth/RBAC cases) |
| Alembic upgrade | Passed on working and test databases |
| Populated Milestone 1 upgrade | Legacy user preserved; password remains null/unprovisioned |
| Milestone 2 downgrade and re-upgrade | Passed on a separate disposable database |
| Alembic model/schema check | No new upgrade operations detected |
| Seed idempotency | Two hospitals, seven users, six patients/encounters/discharges; existing hashes unchanged |
| Ruff lint/format and git whitespace check | Passed |
| Frontend TypeScript and production build | Passed |
| Live API | All seven demo accounts logged in; identity/tenant/role boundaries passed |
| Live frontend session | Login, HttpOnly/SameSite cookie, current user, logout, Origin rejection passed |
| Expired browser session | Rejected with 401; cookie cleared |
| Docker Compose configuration | Standalone Compose validation passed |

The original Milestone 1 migration is unchanged. Existing tenant/data tests now use signed bearer tokens through the actual authentication dependency. The removed development identity is tested for rejection. New coverage includes malformed/expired/incorrectly signed tokens, algorithm/issuer/audience restrictions, disabled and unprovisioned accounts, refreshed database roles, role-specific clinical reads/writes, user administration, password hashing, credential redaction, case-insensitive uniqueness, and platform clinical restrictions.

Two issues found during verification were fixed: refreshing identity state after a stored role change, and Next.js internal hostname normalization causing valid local Origin checks to fail. The backend suite and frontend build/live session checks passed after the fixes.

The backend and frontend were started on loopback ports 8000 and 3000. The workspace's ignored `.env` points to the local temporary PostgreSQL instance on port 55432 and contains a generated signing key. That key is not committed or printed. PostgreSQL uses a temporary loopback trust-authenticated instance under `/tmp/outreach-pg-data`; the distributed Compose setup requires a password.

Docker is not installed in this environment. Compose schema/configuration was validated, but Docker image build and container startup were not executed. Compose targets PostgreSQL 16; executed database checks used PostgreSQL 14.24. Frontend verification used automated HTTP requests against the production server, not browser automation. Local production-build testing used `SESSION_COOKIE_SECURE=false`; deployment over HTTPS must use secure cookies.

Reproduce the API/session smoke checks with both applications running:

```bash
cd backend
uv run python ../scripts/smoke_auth.py
```

The prior Milestone 1 verification passed 38 tests, initial migration upgrade/rollback, seed idempotency, frontend build/typecheck, and live health/tenant checks. Its temporary identity mechanism has now been replaced by JWT authentication.
