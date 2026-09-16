from datetime import datetime, timedelta, timezone

from conftest import auth_headers, uid
from sqlalchemy import select

from app.models.healthcare import AuditEvent, HospitalConfiguration


def campaign_payload(**changes):
    payload = {
        "name": "Post-discharge follow-up",
        "description": "Synthetic operational campaign",
        "clinical_follow_up_hours": 72,
        "calling_window_start": "09:00:00",
        "calling_window_end": "17:00:00",
        "campaign_priority": 50,
        "max_retries": 3,
        "outbound_capacity": 10,
        "escalation_configuration": {"reviewer_group": "care-team"},
        "eligibility_criteria": {"discharge_status": "PENDING"},
    }
    return {**payload, **changes}


async def ready_hospital(session, hospital_id=1):
    configuration = await session.scalar(
        select(HospitalConfiguration).where(HospitalConfiguration.hospital_id == uid(hospital_id))
    )
    configuration.is_ready = True
    await session.flush()


async def create_campaign(client, user_id=10, **changes):
    response = await client.post(
        "/api/v1/campaigns", headers=auth_headers(user_id), json=campaign_payload(**changes)
    )
    assert response.status_code == 201, response.text
    return response.json()


async def test_hospital_admin_and_campaign_manager_create_campaigns(client):
    admin = await create_campaign(client, 10, name="Admin campaign")
    manager = await create_campaign(client, 11, name="Manager campaign")
    assert admin["hospital_id"] == str(uid(1))
    assert manager["created_by_user_id"] == str(uid(11))
    assert admin["status"] == "DRAFT"


async def test_clinical_reviewer_cannot_create_campaign(client):
    response = await client.post(
        "/api/v1/campaigns", headers=auth_headers(12), json=campaign_payload()
    )
    assert response.status_code == 403


async def test_campaign_list_and_records_are_tenant_scoped(client):
    campaign = await create_campaign(client, 20, name="Hospital B campaign")
    assert (await client.get("/api/v1/campaigns", headers=auth_headers(10))).json() == []
    assert (
        await client.get(f"/api/v1/campaigns/{campaign['id']}", headers=auth_headers(10))
    ).status_code == 404
    assert (
        await client.patch(
            f"/api/v1/campaigns/{campaign['id']}",
            headers=auth_headers(10),
            json={"name": "Guessed update"},
        )
    ).status_code == 404
    assert (
        await client.post(f"/api/v1/campaigns/{campaign['id']}/cancel", headers=auth_headers(10))
    ).status_code == 404
    assert (await client.get("/api/v1/campaigns", headers=auth_headers(20))).json()[0][
        "id"
    ] == campaign["id"]
    assert (await client.get("/api/v1/campaigns", headers=auth_headers(22))).status_code == 200


async def test_platform_admin_has_no_campaign_access(client):
    campaign = await create_campaign(client)
    assert (await client.get("/api/v1/campaigns", headers=auth_headers(99))).status_code == 403
    assert (
        await client.get(f"/api/v1/campaigns/{campaign['id']}", headers=auth_headers(99))
    ).status_code == 403


async def test_campaign_can_be_updated_only_while_draft(client, session):
    campaign = await create_campaign(client)
    updated = await client.patch(
        f"/api/v1/campaigns/{campaign['id']}",
        headers=auth_headers(11),
        json={"name": "Updated campaign", "campaign_priority": 80},
    )
    assert updated.status_code == 200
    assert updated.json()["campaign_priority"] == 80
    await ready_hospital(session)
    assert (
        await client.post(f"/api/v1/campaigns/{campaign['id']}/ready", headers=auth_headers(10))
    ).status_code == 200
    assert (
        await client.patch(
            f"/api/v1/campaigns/{campaign['id']}",
            headers=auth_headers(10),
            json={"name": "Late update"},
        )
    ).status_code == 409


async def test_invalid_campaign_configuration_cannot_become_ready(client, session):
    await ready_hospital(session)
    response = await client.post(
        "/api/v1/campaigns", headers=auth_headers(10), json={"name": "Incomplete"}
    )
    assert response.status_code == 201
    assert (
        await client.post(
            f"/api/v1/campaigns/{response.json()['id']}/ready", headers=auth_headers(10)
        )
    ).status_code == 409


async def test_campaign_lifecycle_and_audit_events(client, session):
    await ready_hospital(session)
    campaign = await create_campaign(client)
    campaign_id = campaign["id"]
    assert (
        await client.post(f"/api/v1/campaigns/{campaign_id}/ready", headers=auth_headers(11))
    ).json()["status"] == "READY"
    scheduled = datetime.now(timezone.utc) + timedelta(hours=1)
    assert (
        await client.post(
            f"/api/v1/campaigns/{campaign_id}/schedule",
            headers=auth_headers(10),
            json={"start_at": scheduled.isoformat()},
        )
    ).json()["status"] == "SCHEDULED"
    assert (
        await client.post(f"/api/v1/campaigns/{campaign_id}/start", headers=auth_headers(11))
    ).json()["status"] == "RUNNING"
    assert (
        await client.post(f"/api/v1/campaigns/{campaign_id}/pause", headers=auth_headers(10))
    ).json()["status"] == "PAUSED"
    assert (
        await client.post(f"/api/v1/campaigns/{campaign_id}/resume", headers=auth_headers(11))
    ).json()["status"] == "RUNNING"
    assert (
        await client.post(f"/api/v1/campaigns/{campaign_id}/complete", headers=auth_headers(10))
    ).json()["status"] == "COMPLETED"
    assert (
        await client.post(f"/api/v1/campaigns/{campaign_id}/start", headers=auth_headers(10))
    ).status_code == 409
    actions = set(
        await session.scalars(
            select(AuditEvent.action).where(AuditEvent.resource_id == campaign_id)
        )
    )
    assert {
        "CAMPAIGN_CREATED",
        "CAMPAIGN_READY",
        "CAMPAIGN_SCHEDULED",
        "CAMPAIGN_STARTED",
        "CAMPAIGN_PAUSED",
        "CAMPAIGN_RESUMED",
        "CAMPAIGN_COMPLETED",
    } <= actions


async def test_ready_campaign_can_start_without_scheduling(client, session):
    await ready_hospital(session)
    campaign = await create_campaign(client)
    campaign_id = campaign["id"]
    assert (
        await client.post(f"/api/v1/campaigns/{campaign_id}/ready", headers=auth_headers(10))
    ).json()["status"] == "READY"
    assert (
        await client.post(f"/api/v1/campaigns/{campaign_id}/start", headers=auth_headers(11))
    ).json()["status"] == "RUNNING"


async def test_campaign_cancellation_from_valid_state_and_terminal_rejection(client, session):
    await ready_hospital(session)
    campaign = await create_campaign(client)
    campaign_id = campaign["id"]
    assert (
        await client.post(f"/api/v1/campaigns/{campaign_id}/cancel", headers=auth_headers(11))
    ).json()["status"] == "CANCELLED"
    assert (
        await client.post(f"/api/v1/campaigns/{campaign_id}/ready", headers=auth_headers(11))
    ).status_code == 409
    audit = await session.scalar(
        select(AuditEvent).where(
            AuditEvent.resource_id == campaign_id, AuditEvent.action == "CAMPAIGN_CANCELLED"
        )
    )
    assert audit.details == {"from_status": "DRAFT", "to_status": "CANCELLED"}


async def test_preliminary_estimate_uses_scoped_pending_discharges(client):
    campaign = await create_campaign(client, max_retries=2)
    response = await client.get(
        f"/api/v1/campaigns/{campaign['id']}/estimate", headers=auth_headers(12)
    )
    assert response.status_code == 200
    assert response.json()["preliminary_candidate_count"] == 1
    assert response.json()["estimated_outreach_attempts"] == 3
    assert response.json()["eligibility_evaluation"] == "PENDING_MILESTONE_4B"
