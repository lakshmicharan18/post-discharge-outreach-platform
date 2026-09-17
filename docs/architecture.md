# Architecture

```text
Discharge
  → Campaign Eligibility
  → Outreach Queue
  → Voice Intake
  → Controlled Tools / Tenant RAG
  → Clinical Triage
  → 3 Independent Assessments
  → Conservative Consensus
  → Human Escalation
  → Mock EHR
```

The system uses FastAPI services over PostgreSQL/SQLAlchemy, with a Next.js
frontend. Routes are intentionally thin: authenticated request context enters a
tenant-scoped service, which persists durable workflow state and audit records.

## Workflow

Discharges are evaluated against campaign eligibility rules and create durable,
explainable outreach tasks. The queue prioritizes due work while applying capacity
and concurrency constraints. Workers use leases so stale reservations can be
recovered safely.

Voice Intake persists its staged conversation. Controlled tools retrieve only
tenant-safe patient, task, discharge, and hospital knowledge facts. Tenant RAG is
limited to the requesting hospital. The model has no direct database or repository
access.

Clinical triage produces a structured assessment. Three independent passes use
the same controlled context without receiving one another's output. The application
then applies explicit severity ordering and conservative consensus rules: urgent
findings are never downgraded, and material disagreement or insufficient context
can require human review.

Human-review decisions create one durable escalation case. Completion and case
resolution invoke the local Mock EHR abstraction, which records idempotent outreach
notes, follow-up references, and resolution references without contacting an
external EHR.

## Tenant boundary and security

JWT authentication reloads the active user, role, and hospital into
`RequestContext`. Hospital scope is never accepted from client payloads. Clinical
services filter reads and writes by this context; foreign IDs fail closed. Platform
Admin handles platform metadata and has no unrestricted clinical access.

## Reliability and auditability

UUID identities, timezone-aware timestamps, PostgreSQL constraints, and service
transactions provide durable workflow state. EHR operation records use tenant-local
idempotency keys, so retries do not duplicate successful writes. Safe audit events
record case creation/review/resolution and Mock EHR outcomes without unnecessary
PHI.

The deterministic simulation and safety benchmark reuse application policy paths
to make regression behavior reproducible. They are demonstration and test tools,
not clinical validation.
