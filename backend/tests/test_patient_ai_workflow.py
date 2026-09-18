from datetime import datetime, timezone
from uuid import UUID, uuid4

from conftest import auth_headers
from test_triage import completed_session

from app.models.campaigns import VoiceIntakeSession
from app.models.ehr import EHROperationRecord
from app.models.notifications import Notification, NotificationSeverity
from app.models.triage import ClinicalTriageRecord, EscalationCase, EscalationDecisionRecord


async def test_patient_ai_workflow_returns_partial_workflow(client, session):
    response = await client.get(
        f"/api/v1/patients/{UUID(int=100)}/ai-workflow", headers=auth_headers(10)
    )

    assert response.status_code == 200
    body = response.json()
    assert body["patient"]["id"] == str(UUID(int=100))
    assert body["latest_encounter"]["id"] == str(UUID(int=1000))
    assert body["latest_discharge"]["id"] == str(UUID(int=10000))
    assert body["voice_intake"] is None
    assert body["triage_assessment"] is None
    assert body["independent_assessments"] == []
    assert body["consensus"] is None
    assert body["escalation"] is None
    assert body["notification"] is None
    assert body["mock_ehr_operation"] is None


async def test_patient_ai_workflow_is_tenant_scoped(client, session):
    response = await client.get(
        f"/api/v1/patients/{UUID(int=100)}/ai-workflow", headers=auth_headers(20)
    )

    assert response.status_code == 404


async def test_patient_ai_workflow_aggregates_safe_persisted_stages(client, session):
    intake_session_id = UUID(await completed_session(client, session))
    intake = await session.get(VoiceIntakeSession, intake_session_id)
    assert intake is not None
    assessments = [
        ClinicalTriageRecord(
            hospital_id=UUID(int=1),
            intake_session_id=intake.id,
            outreach_task_id=intake.outreach_task_id,
            classification="URGENT",
            requires_human_review=True,
            assessment={
                "patient_reported_findings": ["shortness of breath"],
                "clinical_context_facts": ["recent discharge"],
                "protocol_references": ["protocol-1"],
                "recommended_next_action": "HUMAN_REVIEW",
                "requires_human_review": True,
                "reasoning_summary": "hidden reasoning",
                "raw_provider_response": "not for display",
            },
            execution_metadata={"secret": "not for display"},
        )
        for _ in range(3)
    ]
    session.add_all(assessments)
    await session.flush()
    decision = EscalationDecisionRecord(
        hospital_id=UUID(int=1),
        intake_session_id=intake.id,
        assessment_ids=[str(assessment.id) for assessment in assessments],
        final_classification="URGENT",
        agreement_status="DISAGREEMENT",
        requires_human_review=True,
        disagreement_reason="Urgent assessment present",
        recommended_action="HUMAN_REVIEW",
        execution_metadata={"internal": "not for display"},
    )
    session.add(decision)
    await session.flush()
    case = EscalationCase(
        hospital_id=UUID(int=1),
        escalation_decision_id=decision.id,
        intake_session_id=intake.id,
        priority="URGENT",
        reviewer_notes="not for display",
        resolution="PENDING_REVIEW",
    )
    session.add(case)
    await session.flush()
    notification = Notification(
        hospital_id=UUID(int=1),
        notification_type="ESCALATION_REQUIRES_REVIEW",
        title="Urgent escalation review",
        message="An escalation requires clinical review.",
        severity=NotificationSeverity.URGENT,
        related_escalation_id=case.id,
    )
    ehr_operation = EHROperationRecord(
        hospital_id=UUID(int=1),
        outreach_task_id=intake.outreach_task_id,
        reference_id=case.id,
        operation_type="ESCALATION_REFERENCE",
        idempotency_key=f"test-ehr:{uuid4()}",
        safe_payload={"internal_payload": "not for display"},
        status="SUCCEEDED",
        completed_at=datetime.now(timezone.utc),
    )
    session.add_all((notification, ehr_operation))
    await session.commit()

    response = await client.get(
        f"/api/v1/patients/{UUID(int=100)}/ai-workflow", headers=auth_headers(10)
    )

    assert response.status_code == 200
    body = response.json()
    assert body["voice_intake"]["id"] == str(intake.id)
    assert body["triage_assessment"]["id"] in {str(assessment.id) for assessment in assessments}
    assert [item["id"] for item in body["independent_assessments"]] == [
        str(assessment.id) for assessment in assessments
    ]
    assert body["consensus"]["id"] == str(decision.id)
    assert body["consensus"]["assessment_ids"] == [str(assessment.id) for assessment in assessments]
    assert body["escalation"]["id"] == str(case.id)
    assert body["notification"]["id"] == str(notification.id)
    assert body["notification"]["severity"] == "URGENT"
    assert body["mock_ehr_operation"]["id"] == str(ehr_operation.id)
    assert body["mock_ehr_operation"]["status"] == "SUCCEEDED"
    serialized = response.text
    assert "hidden reasoning" not in serialized
    assert "raw_provider_response" not in serialized
    assert "not for display" not in serialized
