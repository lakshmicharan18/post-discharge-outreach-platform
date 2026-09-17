from uuid import UUID

from conftest import auth_headers
from sqlalchemy import func, select
from test_triage import completed_session

from app.core.context import CurrentUserContext
from app.models.entities import Role
from app.models.triage import EscalationCase, EscalationDecisionRecord
from app.services.escalations import EscalationCaseService


async def create_case(client, session):
    intake_session_id = await completed_session(client, session)
    decision = EscalationDecisionRecord(
        hospital_id=UUID(int=1),
        intake_session_id=UUID(intake_session_id),
        assessment_ids=[],
        final_classification="URGENT",
        agreement_status="DISAGREEMENT",
        requires_human_review=True,
        recommended_action="HUMAN_REVIEW",
        execution_metadata={},
    )
    session.add(decision)
    await session.commit()
    context = CurrentUserContext(UUID(int=10), UUID(int=1), Role.HOSPITAL_ADMIN)
    await EscalationCaseService(session, context).create_for_decision(decision.id)
    cases = await client.get("/api/v1/escalations", headers=auth_headers(10))
    assert cases.status_code == 200
    assert len(cases.json()) == 1
    return decision, cases.json()[0]


async def test_human_review_decision_creates_one_open_case_idempotently(client, session):
    decision, case = await create_case(client, session)
    assert case["status"] == "OPEN"
    context = CurrentUserContext(UUID(int=10), UUID(int=1), Role.HOSPITAL_ADMIN)
    repeated = await EscalationCaseService(session, context).create_for_decision(decision.id)
    assert repeated.id == UUID(case["id"])
    count = await session.scalar(select(func.count()).select_from(EscalationCase))
    assert count == 1


async def test_reviewer_lifecycle_persists_and_cannot_resolve_twice(client, session):
    _, case = await create_case(client, session)
    started = await client.post(
        f"/api/v1/escalations/{case['id']}/start-review", headers=auth_headers(12)
    )
    assert started.status_code == 200
    assert started.json()["status"] == "IN_REVIEW"
    resolved = await client.post(
        f"/api/v1/escalations/{case['id']}/resolve",
        headers=auth_headers(12),
        json={"reviewer_notes": "Reviewed by clinician", "resolution": "FOLLOW_UP"},
    )
    assert resolved.status_code == 200
    assert resolved.json()["status"] == "RESOLVED"
    assert resolved.json()["reviewer_notes"] == "Reviewed by clinician"
    assert resolved.json()["resolution"] == "FOLLOW_UP"
    assert resolved.json()["resolved_at"]
    duplicate = await client.post(
        f"/api/v1/escalations/{case['id']}/resolve",
        headers=auth_headers(12),
        json={"reviewer_notes": "Again", "resolution": "FOLLOW_UP"},
    )
    assert duplicate.status_code == 409


async def test_non_review_decision_does_not_create_case(client, session):
    intake_session_id = await completed_session(client, session)
    decision = EscalationDecisionRecord(
        hospital_id=UUID(int=1),
        intake_session_id=UUID(intake_session_id),
        assessment_ids=[],
        final_classification="ROUTINE",
        agreement_status="CONSENSUS",
        requires_human_review=False,
        recommended_action="STANDARD_FOLLOW_UP",
        execution_metadata={},
    )
    session.add(decision)
    await session.commit()
    context = CurrentUserContext(UUID(int=10), UUID(int=1), Role.HOSPITAL_ADMIN)
    assert await EscalationCaseService(session, context).create_for_decision(decision.id) is None


async def test_foreign_tenant_and_platform_admin_are_denied(client, session):
    _, case = await create_case(client, session)
    foreign = await client.get(f"/api/v1/escalations/{case['id']}", headers=auth_headers(20))
    assert foreign.status_code == 404
    platform = await client.get(f"/api/v1/escalations/{case['id']}", headers=auth_headers(99))
    assert platform.status_code == 403
