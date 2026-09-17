from datetime import datetime, timezone
from uuid import UUID, uuid4

import pytest

from conftest import auth_headers
from test_queue_scheduler import start_campaign

from app.ai.models import DeterministicFakeModel
from app.core.context import CurrentUserContext
from app.core.errors import APIError
from app.models.entities import Role
from app.services.triage import ClinicalTriageService


def context(tenant: int):
    return CurrentUserContext(UUID(int=tenant * 10), UUID(int=tenant), Role.HOSPITAL_ADMIN)


async def completed_session(client, session):
    _, task = await start_campaign(client, session)
    created = await client.post(
        "/api/v1/voice-intake/sessions",
        headers=auth_headers(10),
        json={"outreach_task_id": str(task.id)},
    )
    await client.post(
        f"/api/v1/voice-intake/sessions/{created.json()['id']}/complete",
        headers=auth_headers(10),
    )
    return created.json()["id"]


@pytest.mark.parametrize("classification", ["ROUTINE", "CONCERNING", "URGENT", "INSUFFICIENT_INFORMATION"])
async def test_deterministic_triage_classifications(client, session, classification):
    session_id = await completed_session(client, session)
    model = DeterministicFakeModel({"assessment_id": str(uuid4()), "classification": classification, "patient_reported_findings": ["reported symptom"], "clinical_context_facts": ["discharge record fact"], "protocol_references": [], "reasoning_summary": "Short auditable summary.", "recommended_next_action": "HUMAN_REVIEW", "confidence": 0.5, "requires_human_review": classification == "INSUFFICIENT_INFORMATION"})
    record = await ClinicalTriageService(session, context(1), model).assess(session_id, datetime.now(timezone.utc))
    assert record.classification == classification
    assert record.assessment["patient_reported_findings"] == ["reported symptom"]
    assert record.assessment["clinical_context_facts"] == ["discharge record fact"]
    assert record.assessment["protocol_references"] == []


async def test_malformed_output_and_foreign_session_fail_safely(client, session):
    session_id = await completed_session(client, session)
    with pytest.raises(Exception):
        await ClinicalTriageService(session, context(1), DeterministicFakeModel({})).assess(session_id, datetime.now(timezone.utc))
    with pytest.raises(APIError):
        await ClinicalTriageService(session, context(2), DeterministicFakeModel({})).assess(session_id, datetime.now(timezone.utc))
