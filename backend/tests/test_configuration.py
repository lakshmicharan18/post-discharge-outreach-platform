import pytest
from conftest import auth_headers, uid
from sqlalchemy import select

from app.models.healthcare import AuditEvent


def configuration_payload(**changes):
    payload = {
        "timezone": "Asia/Kolkata",
        "calling_window_start": "08:30:00",
        "calling_window_end": "18:00:00",
        "default_follow_up_hours": 48,
        "max_concurrent_calls": 12,
        "default_max_retries": 4,
        "retry_initial_delay_minutes": 45,
        "retry_backoff_multiplier": "1.5",
        "notification_preferences": {"import_failures": True},
        "escalation_contacts": [{"name": "Review Desk", "channel": "internal"}],
        "ehr_settings": {"provider": "mock", "enabled": False},
        "is_ready": True,
    }
    return {**payload, **changes}


@pytest.mark.parametrize("user_id", [10, 11, 12])
async def test_hospital_roles_read_own_configuration(client, user_id):
    response = await client.get("/api/v1/hospital/configuration", headers=auth_headers(user_id))
    assert response.status_code == 200
    assert response.json()["hospital_id"] == str(uid(1))


async def test_hospital_admin_updates_own_configuration_and_audits(client, session):
    response = await client.put(
        "/api/v1/hospital/configuration",
        headers=auth_headers(10),
        json=configuration_payload(),
    )
    assert response.status_code == 200, response.text
    assert response.json()["max_concurrent_calls"] == 12
    assert response.json()["hospital_id"] == str(uid(1))
    audit = await session.scalar(
        select(AuditEvent).where(AuditEvent.action == "HOSPITAL_CONFIGURATION_UPDATED")
    )
    assert audit.hospital_id == uid(1)
    assert audit.details == {"is_ready": True}


@pytest.mark.parametrize("user_id", [11, 12])
async def test_read_roles_cannot_update_configuration(client, user_id):
    response = await client.put(
        "/api/v1/hospital/configuration",
        headers=auth_headers(user_id),
        json=configuration_payload(),
    )
    assert response.status_code == 403


async def test_hospital_admin_cannot_select_another_configuration(client):
    assert (
        await client.get(
            f"/api/v1/platform/hospitals/{uid(2)}/configuration", headers=auth_headers(10)
        )
    ).status_code == 403
    response = await client.put(
        "/api/v1/hospital/configuration",
        headers=auth_headers(10),
        json={**configuration_payload(), "hospital_id": str(uid(2))},
    )
    assert response.status_code == 422


async def test_platform_admin_can_configure_hospital_without_clinical_access(client):
    response = await client.put(
        f"/api/v1/platform/hospitals/{uid(2)}/configuration",
        headers=auth_headers(99),
        json=configuration_payload(timezone="America/New_York"),
    )
    assert response.status_code == 200
    assert response.json()["hospital_id"] == str(uid(2))
    assert (await client.get("/api/v1/patients", headers=auth_headers(99))).status_code == 403


@pytest.mark.parametrize(
    "changes",
    [
        {"calling_window_start": "18:00:00", "calling_window_end": "08:00:00"},
        {"timezone": "Not/A_Timezone"},
        {"max_concurrent_calls": 0},
    ],
)
async def test_configuration_validation(client, changes):
    response = await client.put(
        "/api/v1/hospital/configuration",
        headers=auth_headers(10),
        json=configuration_payload(**changes),
    )
    assert response.status_code == 422
