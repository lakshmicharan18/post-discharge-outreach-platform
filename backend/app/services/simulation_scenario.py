"""Fixed, synthetic data for the Milestone 6B queue demonstration."""

from dataclasses import dataclass

SCENARIO_NAME = "deterministic-25-patient-queue"
SCENARIO_START_ISO = "2026-01-05T10:00:00+00:00"
SCENARIO_CAPACITY = 3


@dataclass(frozen=True)
class ScenarioPatient:
    scenario_key: str
    risk: str
    discharge_offset_hours: int
    deadline_offset_minutes: int
    outcomes: tuple[str, ...]
    callback_offset_minutes: int | None = None
    dropped_partial_context: dict | None = None


SCENARIO_PATIENTS: tuple[ScenarioPatient, ...] = (
    ScenarioPatient("S01", "HIGH", -72, 72 * 60, ("COMPLETED",)),
    ScenarioPatient("S02", "MEDIUM", -60, 60 * 60, ("NO_ANSWER", "COMPLETED")),
    ScenarioPatient("S03", "HIGH", -48, 36 * 60, ("BUSY", "NO_ANSWER", "VOICEMAIL")),
    ScenarioPatient("S04", "LOW", -42, 72 * 60, ("CALLBACK_REQUESTED", "COMPLETED"), 30),
    ScenarioPatient(
        "S05",
        "MEDIUM",
        -36,
        48 * 60,
        ("DROPPED", "COMPLETED"),
        dropped_partial_context={"completed_questions": ["identity_confirmed"]},
    ),
    ScenarioPatient("S06", "HIGH", -30, 24 * 60, ("TECHNICAL_FAILURE", "COMPLETED")),
    ScenarioPatient("S07", "LOW", -24, 72 * 60, ("INVALID_NUMBER",)),
    ScenarioPatient("S08", "MEDIUM", -22, 12 * 60, ("VOICEMAIL", "COMPLETED")),
    ScenarioPatient("S09", "HIGH", -20, 18 * 60, ("BUSY", "COMPLETED")),
    ScenarioPatient("S10", "LOW", -18, 96 * 60, ("NO_ANSWER", "COMPLETED")),
    ScenarioPatient("S11", "MEDIUM", -16, 30 * 60, ("COMPLETED",)),
    ScenarioPatient("S12", "HIGH", -14, 8 * 60, ("NO_ANSWER", "BUSY", "VOICEMAIL")),
    ScenarioPatient(
        "S13",
        "LOW",
        -12,
        60 * 60,
        ("DROPPED", "COMPLETED"),
        dropped_partial_context={"completed_questions": ["reason_for_call"]},
    ),
    ScenarioPatient("S14", "MEDIUM", -10, 40 * 60, ("CALLBACK_REQUESTED", "COMPLETED"), 45),
    ScenarioPatient("S15", "HIGH", -9, 6 * 60, ("TECHNICAL_FAILURE", "COMPLETED")),
    ScenarioPatient("S16", "LOW", -8, 80 * 60, ("COMPLETED",)),
    ScenarioPatient("S17", "MEDIUM", -7, 26 * 60, ("BUSY", "COMPLETED")),
    ScenarioPatient("S18", "HIGH", -6, 15 * 60, ("NO_ANSWER", "COMPLETED")),
    ScenarioPatient("S19", "LOW", -5, 90 * 60, ("VOICEMAIL", "COMPLETED")),
    ScenarioPatient("S20", "MEDIUM", -4, 20 * 60, ("COMPLETED",)),
    ScenarioPatient("S21", "HIGH", -3, 4 * 60, ("INVALID_NUMBER",)),
    ScenarioPatient("S22", "LOW", -2, 100 * 60, ("NO_ANSWER", "COMPLETED")),
    ScenarioPatient(
        "S23",
        "MEDIUM",
        -1,
        10 * 60,
        ("DROPPED", "COMPLETED"),
        dropped_partial_context={"completed_questions": ["callback_preference"]},
    ),
    ScenarioPatient("S24", "HIGH", -1, 90, ("BUSY", "COMPLETED")),
    ScenarioPatient("S25", "LOW", 0, 120 * 60, ("COMPLETED",)),
)


def scenario_payload() -> list[dict]:
    """Return JSON-safe logical scenario data; never include patient identifiers or PHI."""
    return [
        {
            "scenario_key": patient.scenario_key,
            "risk": patient.risk,
            "discharge_offset_hours": patient.discharge_offset_hours,
            "deadline_offset_minutes": patient.deadline_offset_minutes,
            "outcomes": list(patient.outcomes),
            "callback_offset_minutes": patient.callback_offset_minutes,
            "dropped_partial_context": patient.dropped_partial_context,
        }
        for patient in SCENARIO_PATIENTS
    ]
