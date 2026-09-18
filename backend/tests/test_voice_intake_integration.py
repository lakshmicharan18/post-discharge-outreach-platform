from conftest import auth_headers
from sqlalchemy import select
from test_queue_scheduler import start_campaign

from app.models.campaigns import StructuredCallNote
from app.models.healthcare import Medication


async def create_task(client, session, user_id=10):
    _, task = await start_campaign(client, session, user_id=user_id)
    return task


async def create_session(client, task, user_id=10):
    response = await client.post(
        "/api/v1/voice-intake/sessions",
        headers=auth_headers(user_id),
        json={"outreach_task_id": str(task.id)},
    )
    assert response.status_code == 201, response.text
    return response.json()


async def test_session_creation_persistence_and_tenant_boundaries(client, session):
    task_a = await create_task(client, session)
    task_b = await create_task(client, session, 20)
    created = await create_session(client, task_a)
    assert created["outreach_task_id"] == str(task_a.id)
    assert (
        await client.post(
            "/api/v1/voice-intake/sessions",
            headers=auth_headers(10),
            json={"outreach_task_id": str(task_b.id)},
        )
    ).status_code == 404
    assert (
        await client.get(f"/api/v1/voice-intake/sessions/{created['id']}", headers=auth_headers(20))
    ).status_code == 404
    assert (
        await client.post(
            f"/api/v1/voice-intake/sessions/{created['id']}/turn",
            headers=auth_headers(20),
            json={"patient_message": "hello"},
        )
    ).status_code == 404


async def test_turn_persists_state_and_completion_is_idempotent(client, session):
    task = await create_task(client, session)
    created = await create_session(client, task)
    turned = await client.post(
        f"/api/v1/voice-intake/sessions/{created['id']}/turn",
        headers=auth_headers(10),
        json={"patient_message": "I have a medication concern and chest discomfort"},
    )
    assert turned.status_code == 200, turned.text
    assert turned.json()["current_stage"] == "GENERAL_RECOVERY"
    reloaded = await client.get(
        f"/api/v1/voice-intake/sessions/{created['id']}", headers=auth_headers(10)
    )
    assert reloaded.json()["conversation_state"]["stage"] == "GENERAL_RECOVERY"
    medications_before = list(await session.scalars(select(Medication)))
    completed = await client.post(
        f"/api/v1/voice-intake/sessions/{created['id']}/complete", headers=auth_headers(10)
    )
    assert completed.status_code == 200
    completed_body = completed.json()

    assert completed_body["status"] == "COMPLETED"
    assert completed_body["current_stage"] == "COMPLETION"
    assert completed_body["conversation_state"]["stage"] == "COMPLETION"
    assert completed_body["conversation_state"]["completed"] is True
    assert completed_body["completed_at"] is not None
    repeated = await client.post(
        f"/api/v1/voice-intake/sessions/{created['id']}/complete", headers=auth_headers(10)
    )
    assert repeated.status_code == 200 and repeated.json()["status"] == "COMPLETED"
    notes = list(
        await session.scalars(
            select(StructuredCallNote).where(StructuredCallNote.outreach_task_id == task.id)
        )
    )
    assert len(notes) == 1
    assert list(await session.scalars(select(Medication))) == medications_before


async def test_clinical_reviewer_is_read_only_and_platform_is_denied(client, session):
    task = await create_task(client, session)
    created = await create_session(client, task)
    assert (
        await client.get(f"/api/v1/voice-intake/sessions/{created['id']}", headers=auth_headers(12))
    ).status_code == 200
    assert (
        await client.post(
            f"/api/v1/voice-intake/sessions/{created['id']}/turn",
            headers=auth_headers(12),
            json={"patient_message": "hello"},
        )
    ).status_code == 403
    assert (
        await client.get(f"/api/v1/voice-intake/sessions/{created['id']}", headers=auth_headers(99))
    ).status_code == 403
