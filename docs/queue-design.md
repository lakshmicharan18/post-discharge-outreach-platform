# Queue design: Milestone 5A foundation

`OutreachTask` is the durable, tenant-scoped representation of one campaign/discharge outreach obligation. It has a database-enforced unique key `(hospital_id, campaign_id, discharge_id)`, so repeated start/resume evaluation can only create a single logical task. The record remains after completion or other terminal states; it is never recreated for the same campaign/discharge.

Creation is dynamic and transactional with campaign start or resume. Eligibility is recalculated, only eligible results create missing `PENDING` tasks, and failure rolls back both task creation and the campaign transition. A single batch audit event records counts without patient data.

States are `PENDING`, `SCHEDULED`, `CALLING`, `CONNECTED`, `COMPLETED`, `NO_ANSWER`, `BUSY`, `VOICEMAIL`, `DROPPED`, `RETRY_SCHEDULED`, `CALLBACK_SCHEDULED`, `ESCALATED`, `MANUAL_FOLLOW_UP`, and `FAILED`. In 5A, only `PENDING` is created; outcome, retry, callback, reservation, and worker transitions are deferred.

Higher priority scores are selected sooner in a future scheduler. Components are: clinical risk (0–40), deadline urgency (0–50), campaign priority (0–20), waiting-age anti-starvation (0–20), retry penalty (-5 per attempt), and callback bonus (+25 only once callback time is due). `now` is explicit, making scoring deterministic and testable. No scheduler, concurrency reservation, locking, retry execution, callbacks, workers, or calls exist in 5A.
