# Milestone 1 verification

Verified on 2026-09-16 using Python 3.13, PostgreSQL 14.24, Node.js 20.20.2, and Next.js 16.3.5. Compose targets PostgreSQL 16; that container runtime was not exercised here.

- Installed backend dependencies with uv and frontend dependencies with npm; lockfiles included.
- Applied the initial Alembic migration to development and test databases.
- Ran `alembic check`: no model/schema differences.
- Downgraded the disposable test database to base, including removal of the role enum, then reapplied the migration successfully.
- Ran 38 tests against PostgreSQL: all passed.
- Ran Ruff lint and formatting checks successfully.
- Ran the synthetic seed repeatedly: two hospitals, seven users, six patients, six encounters, and six discharges remained stable.
- Built the Next.js production bundle and ran the TypeScript check successfully.
- Started Uvicorn and the Next.js production server; health and frontend returned HTTP 200.
- Live API checks returned three patients for each hospital, 404 for cross-tenant patient lookup, 403 for platform-admin clinical access, and 200 for OpenAPI.
- Downloaded a standalone Compose CLI and ran `config --quiet` successfully. No Docker engine is installed, so container image builds and `docker compose up` remain unverified.

The isolated verification database runs from `/tmp/outreach-pg-data` on loopback port 55432. An ignored local `.env` points to this disposable, synthetic-data environment with development identity enabled. This is specific to the current workspace, not the distributed defaults. For a fresh installation, copy `.env.example` and follow README setup; the example disables development identity.

The temporary PostgreSQL instance uses trust authentication on loopback for this local verification environment only. It is not the Compose configuration, which requires a password. Temporary binary and database directories are outside the repository.
