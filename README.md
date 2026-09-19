# Multi-Hospital Post-Discharge Outreach Platform

A PostgreSQL, FastAPI, and Next.js prototype for coordinating safe,
tenant-isolated post-discharge outreach. It demonstrates how hospitals can
ingest discharge data, configure outreach campaigns, prioritize follow-up work,
run constrained scheduling, document structured patient intake, ground AI
workflows in hospital knowledge, route uncertain or concerning cases to human
review, record follow-up through a local Mock EHR boundary, and monitor system
health.

All demonstration data is synthetic.

---

## Live Deployment

- **Application:** https://post-discharge-outreach-platform-flame.vercel.app
- **Backend API:** https://post-discharge-outreach-api.onrender.com
- **Backend health:** https://post-discharge-outreach-api.onrender.com/api/v1/health

### Demo credentials

Use the Hospital A administrator account:

- **Email:** `hospital_admin.1@example.test`
- **Password:** `DemoOnly-ChangeMe-2026!`

Additional synthetic demo accounts:

| Hospital A role | Email |
| --- | --- |
| Hospital Admin | `hospital_admin.1@example.test` |
| Campaign Manager | `campaign_manager.1@example.test` |
| Clinical Reviewer | `clinical_reviewer.1@example.test` |

Hospital B has equivalent `.2@example.test` accounts.

Platform metadata account:

- `platform.admin@example.test`

> The Render backend uses a free-tier service and may take approximately
> 30–60 seconds to wake after a period of inactivity.

---

## What It Solves

Post-discharge follow-up is operationally complex. Hospitals need to:

- identify which recently discharged patients need outreach,
- prioritize limited outreach capacity,
- avoid duplicate or conflicting work,
- handle retries and callbacks safely,
- escalate concerning responses,
- preserve tenant isolation,
- make AI-assisted decisions explainable,
- keep humans in the loop for uncertain or higher-risk cases, and
- document resulting actions through an EHR boundary.

This project demonstrates those workflows end to end in a synthetic,
assignment-safe environment.

---

## Key Capabilities

- Strict multi-hospital tenant isolation.
- JWT authentication and role-based access control.
- Argon2 password hashing.
- Hospital configuration and operational capacity controls.
- Structured patient and discharge ingestion.
- Idempotent JSON/CSV imports.
- Campaign creation and lifecycle management.
- Explainable patient eligibility with reason codes.
- Durable outreach-task creation.
- Priority-based scheduling with hospital and campaign capacity constraints.
- Clinical deadlines and next-eligible scheduling.
- Callback scheduling and retry handling.
- Manual follow-up routing.
- Stale-reservation recovery.
- PostgreSQL `FOR UPDATE SKIP LOCKED` concurrency control.
- Deterministic 25-patient simulation for reproducible workflow demonstration.
- Persistent Voice Intake workflow.
- OpenAI-compatible runtime LLM integration.
- Tenant-scoped hospital knowledge retrieval.
- Structured clinical triage.
- Three independent escalation assessments.
- Deterministic conservative consensus.
- Human-in-the-loop escalation cases.
- Audit events.
- Durable PostgreSQL workflow events.
- Automatic asynchronous workflow-event runner.
- Urgent escalation notifications.
- Idempotent Mock EHR writes.
- Operational dashboard for queue, workflow, escalation, notification, and AI telemetry.
- Deterministic 21-case safety benchmark.

---

## Architecture

The application is split into a Next.js frontend, FastAPI backend, PostgreSQL
database, hosted LLM provider, durable workflow runner, and local Mock EHR
boundary.

```text
Hospital User
     |
     v
Next.js Frontend (Vercel)
     |
     | same-origin backend proxy
     v
FastAPI Backend (Render)
     |
     +----------------------+----------------------+-------------------+
     |                      |                      |                   |
     v                      v                      v                   v
PostgreSQL            AI Orchestration      Queue Scheduler      Mock EHR
     |                      |
     |                      v
     |                 Groq / OpenAI-
     |                 compatible model
     |
     v
Workflow Events
     |
     v
Async Workflow Runner
```

### Major boundaries

- **Browser → Next.js frontend**
- **Frontend → FastAPI backend**
- **Hospital tenant → hospital tenant**
- **Backend → LLM provider**
- **AI recommendation → application-controlled clinical action**
- **Backend → Mock EHR**
- **Synchronous API → durable asynchronous workflow**

FastAPI routes delegate to tenant-scoped services and SQLAlchemy/PostgreSQL.
Clinical queries are explicitly restricted by hospital context.

AI models do not receive unrestricted database access. Application-defined tools,
schemas, RBAC checks, and tenant boundaries control what information and actions
are available.

See:

- [Architecture Documentation](docs/architecture.md)
- [Queue Design](docs/queue-design.md)
- [Safety Evaluation](docs/safety-evaluation.md)
- [AI Usage Documentation](docs/ai-usage.md)
- [Testing](docs/testing.md)
- [Demo Guide](docs/demo-guide.md)

---

## Technology Stack

### Backend

- Python
- FastAPI
- SQLAlchemy async
- Alembic
- PostgreSQL
- Pydantic
- Pytest
- Ruff

### Frontend

- Next.js
- React
- TypeScript

### Security

- Signed JWT authentication
- Argon2 password hashing
- Role-based authorization
- Explicit tenant context

### AI

- OpenAI-compatible provider adapter
- Groq hosted inference
- Model: `openai/gpt-oss-120b`
- Pydantic-validated structured outputs
- Controlled AI tools
- Tenant-scoped knowledge retrieval
- Deterministic consensus logic

### Deployment

- Frontend: Vercel
- Backend: Render
- Database: Render PostgreSQL

---

## Runtime AI

The deployed application uses an OpenAI-compatible model adapter.

- **Provider:** Groq
- **Model:** `openai/gpt-oss-120b`
- **AI workflows:** Voice Intake, structured clinical triage, and independent escalation assessments
- **Prompt versions:** versioned per AI purpose
- **Structured output:** Pydantic-validated JSON contracts
- **Consensus:** deterministic application logic over three independent assessments
- **Failure handling:** bounded retries and repair attempts
- **Observability:** provider, model, purpose, prompt version, latency, success/failure,
  token counts, and safe error type

Raw patient prompts, full provider responses, secrets, and clinical payloads are
not stored in operational AI telemetry.

---

## Voice Intake

Voice Intake is represented as a persistent structured conversation workflow.

The conversation tracks information such as:

- stage,
- identity and consent status,
- reported symptoms,
- medication concerns,
- follow-up concerns,
- patient questions,
- callback requests,
- red-flag indicators,
- uncertainty,
- grounded references, and
- completion status.

The explicit `/complete` endpoint deterministically normalizes the final state to:

```text
stage = COMPLETION
completed = true
status = COMPLETED
```

This prevents final workflow state from depending only on the model's chosen
stage.

The prototype represents voice outreach through structured text interaction.
Production PSTN/WebRTC/STT/TTS integration is intentionally outside the scope of
this assignment implementation.

---

## Clinical Triage and Consensus

After Voice Intake, the system produces a structured clinical triage assessment.

The assessment includes:

- classification,
- patient-reported findings,
- clinical-context facts,
- protocol references,
- uncertainty,
- missing information,
- recommended next action,
- confidence, and
- human-review requirement.

For escalation, the platform generates **three independent assessments**.

A deterministic application-level consensus function evaluates those assessments
rather than asking another LLM to freely decide which answer is correct.

The consensus logic is intentionally conservative. It does not silently average
severity downward.

Cases that require human judgment are persisted as escalation cases for review.

---

## Human-in-the-Loop Review

Authorized Hospital Admins and Clinical Reviewers can review escalation cases.

The workflow supports:

- open escalation cases,
- reviewer assignment,
- review state,
- reviewer notes,
- resolution state, and
- audit history.

The application deliberately separates AI recommendations from final human review
for cases where human involvement is required.

---

## Hospital Knowledge Retrieval

The platform supports tenant-scoped hospital knowledge retrieval.

Retrieved knowledge is limited to the current hospital context so knowledge from
one tenant is not exposed to another tenant.

The retrieval layer is intentionally lightweight for the prototype and is used to
demonstrate grounded AI workflows rather than unrestricted free-form model
reasoning.

---

## Mock EHR

The project includes a local Mock EHR abstraction.

Supported operations include:

- outreach notes,
- escalation references, and
- follow-up tasks.

Each operation:

- is tenant-scoped,
- is persisted,
- uses an idempotency key,
- records success/failure state, and
- can be retried safely.

Example deployed workflow:

```text
FOLLOW_UP_TASK
Status: SUCCEEDED
```

The abstraction demonstrates EHR integration behavior without requiring access to
Epic, Cerner, or a live FHIR server.

---

## Queue Design

Outreach work is persisted as durable outreach tasks rather than held only in
memory.

The queue considers:

- eligibility,
- clinical deadline,
- next eligible time,
- retry state,
- callback timing,
- priority score,
- hospital capacity, and
- campaign capacity.

### Priority

Each task stores:

- a `priority_score`, and
- explainable `priority_components`.

The frontend displays the backend-calculated components instead of recomputing
priority in the browser.

### Concurrency control

Reservation uses PostgreSQL row locking with:

```text
FOR UPDATE SKIP LOCKED
```

This prevents competing scheduler executions from claiming the same task.

Hospital-level and campaign-level capacity are enforced independently.

### Retries

Retryable outreach outcomes are persisted rather than immediately looping.

Retry behavior includes:

- attempt count,
- bounded maximum attempts,
- configured initial delay,
- configured multiplier,
- future next-eligible time, and
- escalation to manual follow-up when no safe retry remains.

### Callbacks

Callback requests transition tasks to a future callback schedule instead of
creating duplicate outreach tasks.

### Clinical deadlines

Tasks have clinical deadlines. Operational views expose:

- approaching-cutoff counts, and
- missed-deadline counts.

If work can no longer be safely scheduled before the deadline, the workflow can
route to manual follow-up.

### Failure recovery

Reservation leases and stale-work recovery prevent abandoned reservations from
permanently consuming capacity.

See [Queue Design](docs/queue-design.md) for the detailed queue-state and
scheduling design.

---

## Durable Workflow Events

The platform uses PostgreSQL-backed `WorkflowEvent` records for asynchronous
operational work.

Typical successful flow:

```text
PENDING
  -> PROCESSING
  -> SUCCEEDED
```

Retry flow:

```text
PENDING
  -> PROCESSING
  -> RETRY_SCHEDULED
  -> PROCESSING
  -> SUCCEEDED / FAILED
```

Workflow events include:

- tenant ID,
- event type,
- status,
- attempt count,
- maximum attempts,
- next-attempt time,
- processing timestamps,
- idempotency key, and
- safe error type.

A lightweight async worker runs with the FastAPI application lifecycle and claims
due events.

For urgent escalation notifications:

```text
URGENT escalation
      |
      v
SEND_NOTIFICATION WorkflowEvent
      |
      v
Workflow Event Runner
      |
      v
Notification
```

The deployed worker was verified end to end against the production Render
environment using synthetic demo data.

---

## Operations Dashboard

The `/operations` page provides hospital-scoped operational observability.

It includes:

- pending queue,
- available capacity,
- open escalations,
- urgent open escalations,
- unread notifications,
- failed workflow events,
- AI success/failure counts,
- average AI latency,
- recent workflow events,
- recent escalation cases,
- recent notifications, and
- recent AI executions.

AI execution records expose only safe operational metadata such as:

- purpose,
- provider,
- model,
- prompt version,
- latency,
- success/failure,
- token counts, and
- safe error type.

Workflow payloads, idempotency keys, raw clinical prompts, provider responses,
reviewer notes, and secrets are not exposed by this dashboard.

---

## Deterministic Simulation

The project includes a deterministic 25-patient simulation to demonstrate:

- queue creation,
- priority ordering,
- constrained capacity,
- scheduling,
- retries,
- callbacks,
- state transitions, and
- reproducible operational behavior.

This allows queue behavior to be tested without depending on external telephony
or other nondeterministic infrastructure.

---

## Safety Evaluation

The safety benchmark contains **21 fixed synthetic scenarios**:

- 3 routine,
- 3 concerning,
- 3 urgent,
- 3 ambiguous,
- 3 incomplete,
- 3 conflicting,
- 3 adversarial.

Current deterministic synthetic benchmark:

- **True Positives:** 18
- **False Positives:** 1
- **True Negatives:** 2
- **False Negatives:** 0
- **Accuracy:** 95.24%
- **Precision:** 94.74%
- **Recall:** 100%
- **False-Negative Rate:** 0%

> **FNR = 0 applies only to this fixed deterministic synthetic benchmark.**
> It is not a real-world clinical safety guarantee.

The safety report also documents disagreement examples, limitations, and future
improvements.

See [Safety Evaluation](docs/safety-evaluation.md).

---

## Local Setup

### Prerequisites

- Python 3.12+
- `uv`
- Node.js 20+
- npm
- PostgreSQL

### 1. Configure environment

From the repository root:

```bash
cp .env.example .env
```

Set the required values, including:

```text
DATABASE_URL
TEST_DATABASE_URL
POSTGRES_PASSWORD
JWT_SECRET
```

For real hosted LLM usage, also configure the provider values documented in
`.env.example`.

Never commit real credentials or secrets.

### 2. Backend

```bash
cd backend
uv sync --frozen
uv run alembic upgrade head
uv run python ../seed/demo.py
uv run python ../seed/synthetic.py
uv run uvicorn app.main:app --reload
```

Backend API:

```text
http://127.0.0.1:8000
```

FastAPI documentation:

```text
http://127.0.0.1:8000/docs
```

### 3. Frontend

In another terminal:

```bash
cd frontend
cp .env.example .env.local
npm ci
npm run dev
```

Open:

```text
http://127.0.0.1:3000/login
```

---

## PostgreSQL and Migrations

`DATABASE_URL` and `TEST_DATABASE_URL` use the SQLAlchemy Psycopg format:

```text
postgresql+psycopg://USER:PASSWORD@HOST:PORT/DB
```

The test database must end in `_test`.

Run migrations with:

```bash
cd backend
uv run alembic upgrade head
uv run alembic current
```

`seed/demo.py` creates synthetic demonstration users.

`seed/synthetic.py` creates deterministic synthetic patient/discharge data.

---

## Testing and Quality Checks

### Backend tests

```bash
cd backend
python -m pytest tests
```

Current verified backend result:

```text
266 passed
```

### Ruff

```bash
cd backend
ruff check .
ruff format --check .
```

Current validation:

```text
All checks passed!
```

### Frontend type checking and production build

```bash
cd frontend
npm run typecheck
npm run build
```

The final TypeScript validation and Next.js production build complete
successfully.

See [Testing](docs/testing.md) for additional testing details.

---

## Environment Configuration

The repository contains `.env.example` files rather than production secrets.

Typical backend configuration includes:

```text
DATABASE_URL
TEST_DATABASE_URL
JWT_SECRET
ENVIRONMENT
LLM_PROVIDER
LLM_BASE_URL
LLM_MODEL
LLM_API_KEY
LLM_TIMEOUT_SECONDS
LLM_MAX_RETRIES
```

The deployed frontend uses a backend URL configuration and secure session-cookie
settings.

Never commit:

- database passwords,
- production database URLs,
- provider API keys,
- JWT secrets, or
- real patient information.

---

## Deployment

### Frontend

The Next.js frontend is deployed on Vercel.

```text
https://post-discharge-outreach-platform-flame.vercel.app
```

### Backend

The FastAPI backend is deployed on Render.

```text
https://post-discharge-outreach-api.onrender.com
```

### Database

The deployed backend uses PostgreSQL.

### Important deployment note

The Render service is hosted on the free tier and may spin down after inactivity.
The first request after inactivity can therefore take longer than normal.

Frontend-only commits may redeploy Vercel without triggering a Render deployment
when no backend files changed.

---

## Documentation

Submission documentation includes:

- [Architecture Documentation](docs/architecture.md)
- [Queue Design](docs/queue-design.md)
- [Safety Evaluation Report](docs/safety-evaluation.md)
- [Product AI / AI Usage Documentation](docs/ai-usage.md)
- [Testing](docs/testing.md)
- [Demo Guide](docs/demo-guide.md)

Additional submission documents cover:

- AI tools used during development,
- important AI-development prompts, and
- known limitations and tradeoffs.

---

## Development AI Usage

AI-assisted development tools, including ChatGPT and Codex, were used as
pair-programming and review tools during development.

They were used to assist with:

- architecture planning,
- database design,
- backend implementation,
- frontend implementation,
- queue/concurrency design,
- retry behavior,
- Voice Intake,
- triage,
- consensus logic,
- Mock EHR integration,
- workflow-event processing,
- testing,
- debugging,
- deployment review, and
- documentation.

AI-generated changes were reviewed before commit and validated through automated
tests, Ruff, TypeScript checking, Next.js production builds, and deployed smoke
tests.

Secrets, production database credentials, provider API keys, and real patient data
were not intentionally included in development prompts or committed to the
repository.

---

## Known Limitations and Tradeoffs

This project is an assignment prototype and is not a production clinical system.

### Telephony

Real PSTN, WebRTC, STT, and TTS integration is not implemented. Voice outreach is
represented through a structured text-based Voice Intake workflow.

### EHR integration

The project uses a local Mock EHR rather than Epic, Cerner, or a live FHIR
endpoint.

### Healthcare resources

Healthcare resources are intentionally simplified and do not implement the full
FHIR specification.

### Clinical validation

The triage logic and safety benchmark use synthetic scenarios and do not
constitute clinical validation.

### AI

The application uses a real hosted LLM provider, but model outputs remain
probabilistic. Structured validation, conservative consensus, and human review
reduce risk but cannot eliminate model error.

### Worker deployment

Durable workflow state is persisted in PostgreSQL, but the asynchronous worker
runs inside the FastAPI web-service lifecycle rather than as a separately
deployed worker service.

### Hosting

The Render free-tier backend can sleep during inactivity, so background workflow
processing occurs while the backend service is running.

### Scale

The project demonstrates concurrency-safe design with locking, idempotency, and
durable state, but it has not undergone production-scale load testing.

### Security

Authentication, RBAC, password hashing, and tenant isolation are implemented,
but the prototype has not undergone a formal production security audit.

### Compliance

No HIPAA, regulatory, or production-clinical-readiness claim is made.

### Data

The deployed environment contains synthetic demonstration data only.

---

## Repository Structure

```text
.
├── backend/          FastAPI application, services, models, migrations, tests
├── frontend/         Next.js application
├── docs/             Architecture, testing, safety, queue, AI, and demo documentation
├── seed/             Synthetic demonstration data
├── scripts/          Test and project utility scripts
├── .env.example      Environment configuration example
├── compose.yaml      Local PostgreSQL/application support
└── README.md
```

---

## Disclaimer

This software is a technical prototype created for an engineering assignment.

It is not intended for real patient care, diagnosis, treatment, emergency
decision-making, or production clinical deployment.

All demonstration data is synthetic.
