Source of truth: Project_Requirements.pdf

Architecture:
FastAPI + PostgreSQL + SQLAlchemy + Next.js

Always preserve:
- tenant isolation
- JWT/RBAC
- repository/service layering
- UUIDs
- timezone-aware timestamps
- auditability
- no unrestricted AI database access

Completed:
M1 Foundation
M2 Auth/RBAC
M3 Healthcare model/ingestion

Do not rewrite previous migrations.
Do not weaken tenant isolation.
Run relevant regression tests.