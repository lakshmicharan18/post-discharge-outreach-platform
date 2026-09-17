# Five-minute demo guide

Use Hospital A's Campaign Manager or Hospital Admin demo account. Emphasize that
all data is synthetic and that this is a prototype, not clinical decision support
for real patient care.

1. **Login (30 seconds).** Sign in and show the authenticated hospital context.
   Explain that identity supplies tenant scope; users cannot select another hospital
   from the request.
2. **Campaign and eligibility (30 seconds).** Open a campaign and its eligible
   discharges. Explain that eligibility is explainable and creates durable tasks.
3. **Queue (30 seconds).** Show priority, capacity, and reservation state. Explain
   the queue prevents unlimited concurrent outreach and supports lease recovery.
4. **Simulation (30 seconds).** Run or show the deterministic 25-patient scenario.
   Explain that it demonstrates workflow behavior reproducibly.
5. **Voice Intake (45 seconds).** Open a persisted session and process a turn.
   Explain the state machine, controlled tools, and hospital-only knowledge lookup.
6. **Triage and consensus (45 seconds).** Show structured triage and the three
   independent assessments. Explain that consensus is deterministic application
   code and does not allow an urgent assessment to be downgraded.
7. **Escalation review (30 seconds).** Open a human-review case, start review, and
   resolve it. Explain that a reviewer owns the resolution; no medication,
   diagnosis, or discharge record is modified.
8. **Mock EHR (20 seconds).** Show the auditable, idempotent local operation
   records. Explain this is an abstraction boundary, not a real EHR/FHIR server.
9. **Safety evaluation (20 seconds).** Show the fixed synthetic benchmark and
   category coverage. State clearly: FNR=0 is limited to the deterministic
   benchmark and is not a real-world clinical safety guarantee.
