# Queue design: Milestone 5B atomic reservations

`OutreachTask` is the durable, tenant-scoped representation of one campaign/discharge outreach obligation. It has a database-enforced unique key `(hospital_id, campaign_id, discharge_id)`, so repeated start/resume evaluation can only create a single logical task. The record remains after completion or other terminal states; it is never recreated for the same campaign/discharge.

Creation is dynamic and transactional with campaign start or resume. Eligibility is recalculated, only eligible results create missing `PENDING` tasks, and failure rolls back both task creation and the campaign transition. A single batch audit event records counts without patient data.

States are `PENDING`, `SCHEDULED`, `CALLING`, `CONNECTED`, `COMPLETED`, `NO_ANSWER`, `BUSY`, `VOICEMAIL`, `DROPPED`, `RETRY_SCHEDULED`, `CALLBACK_SCHEDULED`, `ESCALATED`, `MANUAL_FOLLOW_UP`, and `FAILED`. Milestone 5B adds only the `PENDING` to `SCHEDULED` reservation transition. Outcome, retry, callback, worker, and call execution transitions remain deferred.

The scheduler locks the hospital's `HospitalConfiguration` row with PostgreSQL `FOR UPDATE` before it reads capacity, releases expired reservations, refreshes candidates, and creates reservations. This makes capacity accounting serial for one hospital without imposing a global lock. Candidate task rows are also selected with `FOR UPDATE SKIP LOCKED`, so concurrent schedulers do not wait on an already examined task.

Capacity uses two independent constraints: total hospital active work must be below `hospital.max_concurrent_calls`; when configured, active work for each campaign must be below that campaign's `outbound_capacity`. The hospital count is never compared to a campaign limit. Thus, a campaign with capacity two can reserve two tasks while another campaign consumes hospital capacity, provided the hospital still has slots. `SCHEDULED`, `CALLING`, and `CONNECTED` tasks consume capacity. The scheduler only considers running campaigns, tasks due at `next_eligible_at`, tasks before their clinical deadline, tasks inside both hospital and campaign local calling windows, and tasks that do not require manual follow-up.

Every eligible candidate is rescored inside the reservation transaction. Selection orders by total priority descending, then earliest clinical deadline, then earliest eligible time, then task UUID. The score components are clinical risk (0–40), deadline urgency (0–50), campaign priority (0–20), waiting-age anti-starvation (0–20), retry penalty (-5 per attempt), and callback bonus (+25 only once callback time is due). `now` is explicit, making scoring deterministic and testable.

A reservation stores a random reservation token, reservation time, and a five-minute expiry. Before a new reservation for a hospital, expired `SCHEDULED` reservations are returned to `PENDING` in the same transaction. This is bounded lease reclamation for unclaimed scheduling reservations; it is not worker recovery or call execution.

The reservation transaction is: lock hospital configuration; return expired scheduling leases; count active capacity; stop if no slot exists; lock eligible candidate rows with `SKIP LOCKED`; recalculate their scores; choose the deterministic winner; write its `SCHEDULED` state, token, and expiry; write one aggregate audit event; commit. A concurrent scheduler for the same hospital blocks at the configuration lock, then observes the first transaction's reservation and capacity count. Schedulers for different hospitals lock different configuration rows and proceed independently.

Expired clinical deadlines are never selected or discarded. They remain `PENDING` for later clinical/manual handling and are exposed as `deadline_missed_count` by queue status. Tasks within six hours of the deadline are exposed as `approaching_deadline_count`. Existing deadline and waiting-age score components make urgent and aged work rise ahead of less urgent work; deterministic ordering prevents arbitrary ties. This is the prototype's fairness mechanism, without a separate weighted-fair-queue layer.

`POST /api/v1/queue/reserve-next` reserves one task and may return `null` when no capacity or eligible work exists. `POST /api/v1/queue/reserve-available?limit=N` reserves up to `N` tasks. `GET /api/v1/queue/status` returns hospital-scoped active, available, pending, deadline, and oldest-pending indicators. Only hospital administrators and campaign managers may reserve work; clinical reviewers may inspect status. All three operations require a clinical tenant context, so platform administrators never receive clinical queue access by default.

Milestone 6 will add call execution, terminal outcomes, retry/backoff and callback scheduling, worker heartbeats and crash recovery, and any workflow that consumes or releases capacity after a call begins.

## Queue operations UI

`/queue` uses the authenticated frontend proxy to show tenant-scoped queue status, campaign task lists, and patient names. It displays configured and available capacity, active reservations, pending and scheduled work, oldest pending work, deadline pressure, and backend-provided priority components. Reservation tokens and lease expiry values are not displayed.

Hospital administrators and campaign managers can use **Reserve next** and **Fill available capacity** as a prototype demonstration of the existing reservation API. Clinical reviewers have read-only visibility. The backend remains the RBAC authority. The campaign detail page includes a compact task-state summary and link to queue operations.

Milestone 5 schedules and reserves outreach work but does not execute calls. Milestone 6 retains responsibility for call execution, outcomes, retries, callbacks, maximum-retry/manual follow-up, worker crash recovery, and queue simulation.

## Milestone 6A outcomes

Each started call creates an `OutreachAttempt`, scoped to the hospital and linked to the outreach task, campaign, patient, and discharge. An outcome event key is unique per hospital, so duplicate delivery returns the already-processed task without creating another attempt, retry, manual follow-up, or audit event. `ManualFollowUp` is a one-per-outreach-task operational record.

A scheduled task may move to `CALLING`. `COMPLETED` and `DECLINED` end in `COMPLETED`. `NO_ANSWER`, `BUSY`, `VOICEMAIL`, `DROPPED`, and `TECHNICAL_FAILURE` move to `RETRY_SCHEDULED` when an attempt remains; otherwise they become `MANUAL_FOLLOW_UP`. `INVALID_NUMBER` becomes manual follow-up immediately. `CALLBACK_REQUESTED` requires a future callback time and becomes `CALLBACK_SCHEDULED`, never a generic retry. Dropped attempts retain only safe structured partial context.

Retry delay is `retry_initial_delay_minutes * retry_backoff_multiplier^(attempt_count - 1)`. The result is adjusted into the intersection of hospital and campaign calling windows in the hospital timezone. If that window does not exist or cannot occur before the clinical deadline, automatic outreach stops and a manual follow-up is created. The scheduler may reserve due `RETRY_SCHEDULED` and `CALLBACK_SCHEDULED` tasks using its existing atomic reservation path.

Milestone 6A does not run workers, simulate calls, recover stale `CALLING`/`CONNECTED` tasks, deliver notifications, connect telephony, or perform AI conversation or clinical triage.
