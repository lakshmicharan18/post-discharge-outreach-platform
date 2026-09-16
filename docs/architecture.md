# Tenant boundary and extension points

The trusted `CurrentUserContext` carries `user_id`, `hospital_id`, `role`, and `is_active`. JWT authentication resolves identity, then reloads hospital and role from stored users. Only authentication/current-user resolution accesses users globally. There is no caller-controlled tenant selector. See [authentication](authentication.md) for token, session, and RBAC details.

ClinicalRepository requires context at construction. It rejects platform scope and missing hospital scope, filters each read by hospital, and assigns context hospital on inserts. ClinicalService checks referenced patients and encounters through the same scoped repository before writing. Service transactions roll back on failures. No clinical list-all method or admin bypass exists.

Database constraints provide an additional relationship boundary:

- `patients(hospital_id, id)` uniquely identifies a patient in its hospital.
- `encounters(hospital_id, patient_id)` references that patient key.
- `encounters(hospital_id, patient_id, id)` is a unique target for discharges.
- `discharges(hospital_id, patient_id, encounter_id)` references that complete encounter key.
- Users have a hospital exactly when their role is not PLATFORM_ADMIN.

The shared database uses application-enforced row filtering, not PostgreSQL row-level security. Raw SQL/database credentials bypass read filtering, so clinical application code must use scoped repositories. Foreign keys protect relationships even when writes bypass services. Future jobs must carry explicit tenant context and reuse these boundaries.

Platform HospitalRepository is separate, checks PLATFORM_ADMIN, and only exposes hospital metadata. Hospital creation is a foundation operation; onboarding workflows remain deferred. Hospital admins can read/create clinical records and list/create their own hospital users. Campaign managers and clinical reviewers can read clinical records only. These checks also run in services/repositories.

Pydantic rejects unknown input fields and validates timezone offsets, chronological ordering, IANA hospital timezone names, status values, and basic patient fields. Database checks duplicate key chronology and enum-like constraints. Encounter/discharge workflow transitions and eligibility are future work. `communication_preferences` is a boolean preference map; no outreach consent decision is implemented.

Alembic owns schema creation. ORM defaults assign UUIDs, statuses, and initial preferences; timestamps are initialized by PostgreSQL. `updated_at` changes on SQLAlchemy updates, not arbitrary external SQL. External identifiers are unique within each hospital and may repeat across hospitals.

The Next.js login/session page contains no clinical records. All data authorization remains in the backend. No future workflow is implemented in the reserved packages.
