from datetime import datetime, timedelta, timezone

from conftest import auth_headers, uid
from sqlalchemy import select

from app.models.entities import Discharge, Encounter


def campaign_payload(**changes):
    payload = {
        "name": "Eligibility campaign",
        "clinical_follow_up_hours": 72,
        "calling_window_start": "09:00:00",
        "calling_window_end": "17:00:00",
        "campaign_priority": 50,
        "max_retries": 2,
        "eligibility_criteria": {},
    }
    return {**payload, **changes}


async def create_campaign(client, user_id=10, **changes):
    response = await client.post(
        "/api/v1/campaigns", headers=auth_headers(user_id), json=campaign_payload(**changes)
    )
    assert response.status_code == 201, response.text
    return response.json()


async def discharge(session, hospital_id=1):
    return await session.scalar(
        select(Discharge).where(
            Discharge.hospital_id == uid(hospital_id),
            Discharge.patient_id == uid(hospital_id * 100),
        )
    )


async def test_eligible_patient_has_explainable_empty_reason_list(client):
    campaign = await create_campaign(client)
    response = await client.get(
        f"/api/v1/campaigns/{campaign['id']}/eligibility", headers=auth_headers(12)
    )
    assert response.status_code == 200
    item = response.json()["items"][0]
    assert item["patient_id"] == str(uid(100))
    assert item["eligible"] is True
    assert item["reasons"] == []
    assert item["risk_level"] == "UNKNOWN"


async def test_expired_follow_up_window_has_stable_reasons(client, session):
    record = await discharge(session)
    now = datetime.now(timezone.utc)
    record.discharge_at = now - timedelta(days=5)
    record.follow_up_deadline = now - timedelta(days=1)
    await session.flush()
    campaign = await create_campaign(client)
    result = (
        await client.get(
            f"/api/v1/campaigns/{campaign['id']}/eligibility/{uid(100)}", headers=auth_headers(10)
        )
    ).json()["results"][0]
    assert result["eligible"] is False
    assert result["reasons"] == ["FOLLOW_UP_WINDOW_EXPIRED", "FOLLOW_UP_DEADLINE_EXPIRED"]


async def test_communication_ineligible_patient_is_excluded(client, session):
    record = await discharge(session)
    record.communication_eligible = False
    await session.flush()
    campaign = await create_campaign(client)
    result = (
        await client.get(
            f"/api/v1/campaigns/{campaign['id']}/eligibility", headers=auth_headers(11)
        )
    ).json()["items"][0]
    assert result["reasons"] == ["COMMUNICATION_NOT_ELIGIBLE"]


async def test_unsupported_criteria_are_rejected(client):
    response = await client.post(
        "/api/v1/campaigns",
        headers=auth_headers(10),
        json=campaign_payload(eligibility_criteria={"unsupported_rule": "value"}),
    )
    assert response.status_code == 422


async def test_risk_level_criterion_is_applied(client, session):
    record = await discharge(session)
    record.risk_level = "HIGH"
    await session.flush()
    campaign = await create_campaign(client, eligibility_criteria={"risk_levels": ["LOW"]})
    result = (
        await client.get(
            f"/api/v1/campaigns/{campaign['id']}/eligibility", headers=auth_headers(10)
        )
    ).json()["items"][0]
    assert result["reasons"] == ["RISK_LEVEL_NOT_INCLUDED"]


async def test_care_setting_and_discharge_time_criteria_are_applied(client, session):
    encounter = await session.scalar(select(Encounter).where(Encounter.id == uid(1000)))
    record = await discharge(session)
    encounter.care_setting = "EMERGENCY"
    record.discharge_at = datetime.now(timezone.utc) - timedelta(days=2)
    await session.flush()
    campaign = await create_campaign(
        client,
        eligibility_criteria={
            "care_settings": ["INPATIENT"],
            "discharge_after": (datetime.now(timezone.utc) - timedelta(days=1)).isoformat(),
        },
    )
    result = (
        await client.get(
            f"/api/v1/campaigns/{campaign['id']}/eligibility", headers=auth_headers(10)
        )
    ).json()["items"][0]
    assert result["reasons"] == ["CARE_SETTING_NOT_INCLUDED", "DISCHARGE_BEFORE_CRITERION"]


async def test_estimate_uses_same_eligibility_results_and_attempt_formula(client, session):
    record = await discharge(session)
    record.communication_eligible = False
    await session.flush()
    campaign = await create_campaign(client, max_retries=4)
    eligibility = await client.get(
        f"/api/v1/campaigns/{campaign['id']}/eligibility", headers=auth_headers(11)
    )
    estimate = await client.get(
        f"/api/v1/campaigns/{campaign['id']}/estimate", headers=auth_headers(11)
    )
    assert eligibility.status_code == estimate.status_code == 200
    assert estimate.json()["total_evaluated"] == eligibility.json()["total"] == 1
    assert estimate.json()["eligible_patients"] == 0
    assert estimate.json()["estimated_outreach_attempts"] == 0
    assert estimate.json()["by_ineligibility_reason"] == {"COMMUNICATION_NOT_ELIGIBLE": 1}


async def test_eligibility_is_tenant_scoped_and_platform_is_denied(client):
    campaign = await create_campaign(client, 20, name="Hospital B eligibility")
    assert (
        await client.get(
            f"/api/v1/campaigns/{campaign['id']}/eligibility/{uid(200)}", headers=auth_headers(10)
        )
    ).status_code == 404
    assert (
        await client.get(
            f"/api/v1/campaigns/{campaign['id']}/eligibility", headers=auth_headers(99)
        )
    ).status_code == 403
    assert (
        await client.get(
            f"/api/v1/campaigns/{campaign['id']}/eligibility", headers=auth_headers(21)
        )
    ).status_code == 200
