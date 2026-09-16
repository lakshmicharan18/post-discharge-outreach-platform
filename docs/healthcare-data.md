# Healthcare data, configuration, and discharge ingestion

This prototype uses a simplified FHIR-like domain model and does not claim full FHIR compliance. The model separates clinical concepts so later eligibility, queueing, triage, and EHR work can retrieve only the data needed for a task.

## Domain model

```text
Hospital 1──1 HospitalConfiguration
    │
    ├──* Patient 1──* Encounter 1──0..1 Discharge
    │       │             │
    │       ├─────────────┼──* Condition
    │       ├─────────────┼──* Observation
    │       ├─────────────┼──* Medication
    │       ├─────────────┼──* CarePlan
    │       └─────────────┼──* Procedure
    │
    ├──* DischargeImport
    └──* AuditEvent
```

Every patient-related table carries `hospital_id`. Composite foreign keys require resources, encounters, and discharges to refer to a patient/encounter in the same hospital. Repositories add the authenticated hospital predicate to list/get operations; there is no platform-admin clinical bypass.

Patient stores only prototype demographics and contact preferences. Condition represents diagnoses/problems; Observation represents timestamped measured or coded values; Medication represents medication use; CarePlan represents structured follow-up intent; Procedure represents performed/planned clinical activity. Each resource has a tenant-scoped `external_id`, optional encounter link, timestamps, and its own typed fields.

Discharge adds a typed follow-up window, deadline, disposition, risk level/indicators, communication eligibility, instructions, and source reference. Medication/care-plan details remain in their respective resources.

HospitalConfiguration uses typed columns for scheduling/retry constraints and JSONB only for flexible notification preferences, escalation contacts, and mock-EHR adapter settings. Hospital admins update their own configuration; hospital roles can read it. Platform admins can read/update a selected hospital's nonclinical configuration and remain blocked from clinical APIs.

## Import contract

`POST /api/v1/discharges/import` accepts a JSON object with `source` and 1–1000 raw records. Each record is independently validated against the explicit `DischargeImportRecord` schema. See [the complete JSON example](example-discharge-import.json).

`POST /api/v1/discharges/import/csv` accepts a UTF-8 CSV file up to 5 MiB. Required scalar columns are:

```text
external_patient_id,first_name,last_name,date_of_birth,phone,preferred_language,
external_encounter_id,care_setting,admit_at,discharge_at,
discharge_instructions
```

Optional scalar columns are `encounter_status`, `follow_up_deadline`, `follow_up_window_hours`, `disposition`, `risk_level`, `communication_eligible`, `discharge_status`, and `source_reference`. These columns contain JSON text: `communication_preferences`, `risk_indicators`, `conditions`, `observations`, `medications`, `care_plans`, and `procedures`. The nested array objects use the same fields shown in the JSON example.

The request must not contain `hospital_id`; nested schemas reject extra fields. The backend assigns the authenticated hospital to every created or updated object. Client-supplied nested `encounter_id` must match the encounter resolved within the same record, which prevents UUID guessing from linking another tenant's data.

## Idempotency and transaction policy

The importer computes a SHA-256 digest of canonical record content inside the authenticated hospital. Submitting an identical batch returns the existing DischargeImport result, even if the filename/source label changes.

Within a new batch:

- Patient is upserted by `(hospital_id, external_patient_id)`.
- Encounter is upserted by `(hospital_id, external_encounter_id)` and cannot change patients.
- Discharge is upserted by `(hospital_id, encounter_id)`; source reference is unique within the hospital.
- Each clinical resource is upserted by `(hospital_id, external_id)` and cannot change patients.
- Missing nested arrays leave existing resources intact. The importer does not interpret absence as deletion.

Each logical record runs in a PostgreSQL savepoint. A mid-record error rolls back its entire graph while later records continue. The import job and successful records commit together after processing. Status is `COMPLETED`, `PARTIALLY_COMPLETED`, or `FAILED`; errors store only record index, error code, field path, and a validation reason. Submitted patient values are excluded from error storage and logs.

DischargeImport records include total/success/failure counts and timestamps. An append-only AuditEvent is written for each completed import and hospital-configuration update. There are no audit mutation/delete endpoints.

## Timeline

`GET /api/v1/patients/{id}/timeline` combines admissions, observations, procedures, medication starts, care-plan starts, and discharges into chronological events. `GET /api/v1/patients/{id}/context` returns the patient plus all current Milestone 3 resource sections and the same timeline. Later milestones can append calls, callbacks, escalations, and documentation without changing this response concept.

## Prototype limits

The resources are healthcare-oriented but omit terminology validation, FHIR profiles, version history, provenance chains, clinical coding services, consent policy evaluation, and real EHR synchronization. JSONB observation values are type-labelled but do not implement FHIR choice types. Imports are synchronous and capped; large production feeds should become background jobs with object storage, malware scanning, durable events, and retention policies. CSV JSON columns favor a compact prototype contract over friendly spreadsheet authoring.
