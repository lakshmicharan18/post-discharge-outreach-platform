from datetime import datetime, timedelta, timezone

import pytest
from conftest import auth_headers, uid
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from app.models.campaigns import OutreachTask, OutreachTaskState
from app.models.entities import Discharge
from app.models.healthcare import HospitalConfiguration
from app.schemas.eligibility import EligibilityResult
from app.services.priority import score_outreach_task


def payload(**changes):
    base = {
        "name": "Queue foundation",
        "clinical_follow_up_hours": 72,
        "calling_window_start": "09:00:00",
        "calling_window_end": "17:00:00",
        "campaign_priority": 50,
        "max_retries": 2,
        "eligibility_criteria": {},
    }
    return {**base, **changes}


async def ready(session):
    config = await session.scalar(
        select(HospitalConfiguration).where(HospitalConfiguration.hospital_id == uid(1))
    )
    config.is_ready = True
    await session.flush()


async def campaign(client, **changes):
    response = await client.post(
        "/api/v1/campaigns", headers=auth_headers(10), json=payload(**changes)
    )
    assert response.status_code == 201, response.text
    return response.json()


async def start(client, session, **changes):
    await ready(session)
    record = await campaign(client, **changes)
    assert (
        await client.post(f"/api/v1/campaigns/{record['id']}/ready", headers=auth_headers(10))
    ).status_code == 200
    assert (
        await client.post(f"/api/v1/campaigns/{record['id']}/start", headers=auth_headers(10))
    ).status_code == 200
    return record


async def task_rows(session, campaign_id):
    return list(
        await session.scalars(select(OutreachTask).where(OutreachTask.campaign_id == campaign_id))
    )


async def test_start_creates_task_for_eligible_patient_and_exposes_it(client, session):
    record = await start(client, session)
    tasks = await task_rows(session, record["id"])
    assert len(tasks) == 1 and tasks[0].state == OutreachTaskState.PENDING
    listed = await client.get(
        f"/api/v1/campaigns/{record['id']}/outreach-tasks", headers=auth_headers(12)
    )
    assert listed.status_code == 200 and listed.json()[0]["patient_id"] == str(uid(100))
    assert (
        await client.get(f"/api/v1/outreach-tasks/{tasks[0].id}", headers=auth_headers(10))
    ).status_code == 200


async def test_ineligible_patient_creates_no_task(client, session):
    discharge = await session.scalar(select(Discharge).where(Discharge.id == uid(10000)))
    discharge.communication_eligible = False
    await session.flush()
    record = await start(client, session)
    assert await task_rows(session, record["id"]) == []


async def test_resume_only_creates_missing_work_and_preserves_terminal_task(client, session):
    record = await start(client, session)
    tasks = await task_rows(session, record["id"])
    tasks[0].state = OutreachTaskState.COMPLETED
    await session.flush()
    assert (
        await client.post(f"/api/v1/campaigns/{record['id']}/pause", headers=auth_headers(10))
    ).status_code == 200
    assert (
        await client.post(f"/api/v1/campaigns/{record['id']}/resume", headers=auth_headers(10))
    ).status_code == 200
    tasks = await task_rows(session, record["id"])
    assert len(tasks) == 1 and tasks[0].state == OutreachTaskState.COMPLETED


async def test_resume_recalculates_and_creates_newly_eligible_missing_work(client, session):
    discharge = await session.scalar(select(Discharge).where(Discharge.id == uid(10000)))
    discharge.communication_eligible = False
    await session.flush()
    record = await start(client, session)
    assert await task_rows(session, record["id"]) == []
    assert (
        await client.post(f"/api/v1/campaigns/{record['id']}/pause", headers=auth_headers(10))
    ).status_code == 200
    discharge.communication_eligible = True
    await session.flush()
    assert (
        await client.post(f"/api/v1/campaigns/{record['id']}/resume", headers=auth_headers(10))
    ).status_code == 200
    assert len(await task_rows(session, record["id"])) == 1


async def test_database_uniqueness_and_tenant_boundaries(client, session):
    record = await start(client, session)
    task = (await task_rows(session, record["id"]))[0]
    duplicate = OutreachTask(
        hospital_id=task.hospital_id,
        campaign_id=task.campaign_id,
        patient_id=task.patient_id,
        discharge_id=task.discharge_id,
        state=OutreachTaskState.PENDING,
        priority_score=0,
        priority_components={},
        attempt_count=0,
        max_attempts=1,
        eligible_at=task.eligible_at,
        next_eligible_at=task.next_eligible_at,
        clinical_deadline=task.clinical_deadline,
    )
    with pytest.raises(IntegrityError):
        async with session.begin_nested():
            session.add(duplicate)
            await session.flush()
    assert (
        await client.get(f"/api/v1/outreach-tasks/{task.id}", headers=auth_headers(20))
    ).status_code == 404
    assert (
        await client.get(f"/api/v1/outreach-tasks/{task.id}", headers=auth_headers(99))
    ).status_code == 403


def result(risk: str, deadline: datetime) -> EligibilityResult:
    return EligibilityResult(
        patient_id=uid(100),
        discharge_id=uid(10000),
        campaign_id=uid(1),
        eligible=True,
        reasons=[],
        evaluated_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
        follow_up_deadline=deadline,
        risk_level=risk,
        care_setting="INPATIENT",
    )


def test_priority_components_are_deterministic_and_explainable():
    now = datetime(2026, 1, 2, 12, tzinfo=timezone.utc)

    class CampaignStub:
        campaign_priority = 50

    base = score_outreach_task(
        CampaignStub(), result("LOW", now + timedelta(days=5)), now=now, eligible_at=now
    )
    high = score_outreach_task(
        CampaignStub(), result("HIGH", now + timedelta(days=5)), now=now, eligible_at=now
    )

    class HigherPriorityCampaignStub:
        campaign_priority = 100

    higher_campaign = score_outreach_task(
        HigherPriorityCampaignStub(),
        result("LOW", now + timedelta(days=5)),
        now=now,
        eligible_at=now,
    )
    urgent = score_outreach_task(
        CampaignStub(), result("LOW", now + timedelta(minutes=30)), now=now, eligible_at=now
    )
    aged = score_outreach_task(
        CampaignStub(),
        result("LOW", now + timedelta(days=5)),
        now=now,
        eligible_at=now - timedelta(days=10),
    )
    callback = score_outreach_task(
        CampaignStub(),
        result("LOW", now + timedelta(days=5)),
        now=now,
        eligible_at=now,
        callback_at=now,
    )
    future_callback = score_outreach_task(
        CampaignStub(),
        result("LOW", now + timedelta(days=5)),
        now=now,
        eligible_at=now,
        callback_at=now + timedelta(hours=1),
    )
    assert (
        high["total"] > base["total"]
        and higher_campaign["total"] > base["total"]
        and urgent["total"] > base["total"]
        and aged["total"] > base["total"]
    )
    assert callback["callback"] == 25 and future_callback["callback"] == 0
    assert base == score_outreach_task(
        CampaignStub(), result("LOW", now + timedelta(days=5)), now=now, eligible_at=now
    )
    assert base["total"] == sum(value for key, value in base.items() if key != "total")
