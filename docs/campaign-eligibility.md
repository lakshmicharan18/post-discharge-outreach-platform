# Campaign eligibility

Milestone 4B evaluates eligibility dynamically from the current tenant-scoped patient, encounter, discharge, and condition data. Results are not persisted: this avoids stale eligibility and allows a later queue milestone to recalculate on campaign start or resume before creating work.

Supported `eligibility_criteria` fields are `risk_levels`, `care_settings`, `discharge_after`, `discharge_before`, `discharge_status` (`PENDING`), `condition_codes`, `communication_eligible` (`true`), and `required_communication_preferences`. Unknown fields and invalid ranges are rejected by Pydantic validation.

Every candidate receives an explicit result. Stable reason codes cover campaign configuration/state, discharge status and date, follow-up window and deadline, communication eligibility/preferences, risk, care setting, discharge range, and condition-code mismatch. The estimate endpoint evaluates the same result objects and aggregates eligible/ineligible counts, attempts, risk levels, and ineligibility reasons.

There are no outreach tasks, queue reservations, retries, or background jobs in this milestone.
