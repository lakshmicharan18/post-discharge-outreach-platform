import asyncio
from datetime import datetime, time, timedelta, timezone
from uuid import uuid4

from conftest import TEST_URL, auth_headers, uid
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.core.context import RequestContext
from app.models.campaigns import Campaign, CampaignStatus, OutreachTask, OutreachTaskState
from app.models.entities import Discharge, Encounter, Hospital, Patient, Role, User
from app.models.healthcare import AuditEvent, HospitalConfiguration
from app.services.scheduler import QueueSchedulerService


def payload(**changes):
    base = {
        "name": "Queue scheduler",
        "clinical_follow_up_hours": 72,
        "calling_window_start": "00:00:00",
        "calling_window_end": "23:59:59",
        "campaign_priority": 50,
        "max_retries": 2,
        "outbound_capacity": 10,
        "eligibility_criteria": {},
    }
    return {**base, **changes}


async def start_campaign(client, session, user_id=10, **changes):
    configuration = await session.scalar(
        select(HospitalConfiguration).where(HospitalConfiguration.hospital_id == uid(user_id // 10))
    )
    configuration.is_ready = True
    configuration.calling_window_start, configuration.calling_window_end = time(0), time(23, 59, 59)
    await session.flush()
    created = await client.post(
        "/api/v1/campaigns", headers=auth_headers(user_id), json=payload(**changes)
    )
    assert created.status_code == 201, created.text
    campaign = created.json()
    assert (
        await client.post(
            f"/api/v1/campaigns/{campaign['id']}/ready", headers=auth_headers(user_id)
        )
    ).status_code == 200
    assert (
        await client.post(
            f"/api/v1/campaigns/{campaign['id']}/start", headers=auth_headers(user_id)
        )
    ).status_code == 200
    task = await session.scalar(
        select(OutreachTask).where(OutreachTask.campaign_id == campaign["id"])
    )
    assert task is not None
    return campaign, task


async def add_pending_task(session, campaign_id, template, *, deadline=None, eligible_at=None):
    now = datetime.now(timezone.utc)
    encounter = Encounter(
        id=uuid4(),
        hospital_id=template.hospital_id,
        patient_id=template.patient_id,
        external_encounter_id=f"queue-{uuid4()}",
        care_setting="INPATIENT",
        admit_at=now - timedelta(days=1),
        discharge_at=now,
        status="DISCHARGED",
    )
    session.add(encounter)
    await session.flush()
    discharge = Discharge(
        id=uuid4(),
        hospital_id=template.hospital_id,
        patient_id=template.patient_id,
        encounter_id=encounter.id,
        discharge_at=now,
        follow_up_deadline=deadline or now + timedelta(days=2),
        discharge_instructions="Synthetic",
    )
    session.add(discharge)
    await session.flush()
    task = OutreachTask(
        hospital_id=template.hospital_id,
        campaign_id=campaign_id,
        patient_id=template.patient_id,
        discharge_id=discharge.id,
        state=OutreachTaskState.PENDING,
        priority_score=0,
        priority_components={},
        attempt_count=0,
        max_attempts=1,
        eligible_at=eligible_at or now,
        next_eligible_at=now,
        clinical_deadline=deadline or now + timedelta(days=2),
    )
    session.add(task)
    await session.flush()
    return task


async def test_reserve_next_is_tenant_scoped_and_refreshes_reservation(client, session):
    _, task_a = await start_campaign(client, session)
    _, task_b = await start_campaign(client, session, user_id=20)
    response = await client.post("/api/v1/queue/reserve-next", headers=auth_headers(10))
    assert response.status_code == 200, response.text
    reserved = response.json()
    assert reserved["id"] == str(task_a.id) and reserved["state"] == "SCHEDULED"
    assert reserved["reservation_token"] and reserved["reservation_expires_at"]
    assert reserved["priority_components"]["total"] == reserved["priority_score"]
    assert task_b.state == OutreachTaskState.PENDING
    other_hospital = await client.post("/api/v1/queue/reserve-next", headers=auth_headers(20))
    assert other_hospital.status_code == 200 and other_hospital.json()["id"] == str(task_b.id)


async def test_capacity_bounds_bulk_reservations(client, session):
    config = await session.scalar(
        select(HospitalConfiguration).where(HospitalConfiguration.hospital_id == uid(1))
    )
    config.max_concurrent_calls = 1
    await session.flush()
    await start_campaign(client, session, name="One")
    await start_campaign(client, session, name="Two")
    response = await client.post(
        "/api/v1/queue/reserve-available?limit=10", headers=auth_headers(10)
    )
    assert response.status_code == 200 and len(response.json()) == 1
    status = await client.get("/api/v1/queue/status", headers=auth_headers(10))
    assert status.status_code == 200 and status.json()["available_capacity"] == 0


async def test_hospital_and_campaign_capacity_are_independent_constraints(client, session):
    config = await session.scalar(
        select(HospitalConfiguration).where(HospitalConfiguration.hospital_id == uid(1))
    )
    config.max_concurrent_calls = 3
    await session.flush()
    campaign_a, task_a = await start_campaign(client, session, name="A", outbound_capacity=1)
    campaign_b, task_b = await start_campaign(client, session, name="B", outbound_capacity=2)
    await add_pending_task(session, campaign_a["id"], task_a)
    await add_pending_task(session, campaign_b["id"], task_b)
    response = await client.post(
        "/api/v1/queue/reserve-available?limit=3", headers=auth_headers(10)
    )
    assert response.status_code == 200 and len(response.json()) == 3
    rows = list(
        await session.scalars(select(OutreachTask).where(OutreachTask.hospital_id == uid(1)))
    )
    assert (
        sum(
            task.state == OutreachTaskState.SCHEDULED
            for task in rows
            if str(task.campaign_id) == campaign_a["id"]
        )
        == 1
    )
    assert (
        sum(
            task.state == OutreachTaskState.SCHEDULED
            for task in rows
            if str(task.campaign_id) == campaign_b["id"]
        )
        == 2
    )


async def test_selection_uses_current_deadline_priority_not_stored_priority(client, session):
    low, low_task = await start_campaign(client, session, name="Low urgent", campaign_priority=1)
    high, high_task = await start_campaign(
        client, session, name="High later", campaign_priority=100
    )
    now = datetime.now(timezone.utc)
    low_task.clinical_deadline, low_task.priority_score = now + timedelta(minutes=30), 0
    high_task.clinical_deadline, high_task.priority_score = now + timedelta(days=10), 999
    await session.flush()
    reserved = await client.post("/api/v1/queue/reserve-next", headers=auth_headers(10))
    assert reserved.status_code == 200
    assert reserved.json()["campaign_id"] == low["id"]
    assert reserved.json()["campaign_id"] != high["id"]


async def test_future_task_paused_campaign_and_expired_lease_are_handled(client, session):
    campaign, task = await start_campaign(client, session)
    task.next_eligible_at = datetime.now(timezone.utc) + timedelta(hours=1)
    await session.flush()
    assert (
        await client.post("/api/v1/queue/reserve-next", headers=auth_headers(10))
    ).json() is None
    task.next_eligible_at = datetime.now(timezone.utc) - timedelta(minutes=1)
    assert (
        await client.post(f"/api/v1/campaigns/{campaign['id']}/pause", headers=auth_headers(10))
    ).status_code == 200
    assert (
        await client.post("/api/v1/queue/reserve-next", headers=auth_headers(10))
    ).json() is None
    assert (
        await client.post(f"/api/v1/campaigns/{campaign['id']}/resume", headers=auth_headers(10))
    ).status_code == 200
    first = (await client.post("/api/v1/queue/reserve-next", headers=auth_headers(10))).json()
    task.reservation_expires_at = datetime.now(timezone.utc) - timedelta(seconds=1)
    old_token = task.reservation_token
    await session.flush()
    renewed = (await client.post("/api/v1/queue/reserve-next", headers=auth_headers(10))).json()
    assert renewed["id"] == first["id"] and renewed["reservation_token"] != str(old_token)


async def test_queue_roles_and_platform_access_are_rejected(client, session):
    await start_campaign(client, session)
    assert (
        await client.post("/api/v1/queue/reserve-next", headers=auth_headers(12))
    ).status_code == 403
    assert (await client.get("/api/v1/queue/status", headers=auth_headers(99))).status_code == 403


async def test_postgres_concurrent_sessions_never_exceed_hospital_capacity():
    """Two independent database sessions contend for one hospital configuration row."""
    engine = create_async_engine(TEST_URL)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    hospital_id, user_id, patient_id, encounter_id, discharge_id, campaign_id = (
        uuid4(),
        uuid4(),
        uuid4(),
        uuid4(),
        uuid4(),
        uuid4(),
    )
    now = datetime.now(timezone.utc)
    async with factory() as setup:
        setup.add(
            Hospital(id=hospital_id, name="Concurrent", code=f"C{hospital_id.hex[:8].upper()}")
        )
        setup.add(
            HospitalConfiguration(
                hospital_id=hospital_id,
                timezone="UTC",
                calling_window_start=time(0),
                calling_window_end=time(23, 59, 59),
                max_concurrent_calls=1,
            )
        )
        setup.add(
            User(
                id=user_id,
                hospital_id=hospital_id,
                email=f"{user_id}@example.test",
                full_name="Scheduler",
                role=Role.HOSPITAL_ADMIN,
                password_hash="test",
            )
        )
        await setup.flush()
        setup.add(
            Patient(
                id=patient_id,
                hospital_id=hospital_id,
                external_patient_id="concurrent",
                first_name="Test",
                last_name="Patient",
                date_of_birth=now.date(),
                phone="+12025550101",
            )
        )
        await setup.flush()
        setup.add(
            Encounter(
                id=encounter_id,
                hospital_id=hospital_id,
                patient_id=patient_id,
                external_encounter_id="concurrent",
                care_setting="INPATIENT",
                admit_at=now - timedelta(days=1),
                discharge_at=now,
                status="DISCHARGED",
            )
        )
        await setup.flush()
        setup.add(
            Discharge(
                id=discharge_id,
                hospital_id=hospital_id,
                patient_id=patient_id,
                encounter_id=encounter_id,
                discharge_at=now,
                follow_up_deadline=now + timedelta(days=1),
                discharge_instructions="Synthetic",
            )
        )
        await setup.flush()
        setup.add(
            Campaign(
                id=campaign_id,
                hospital_id=hospital_id,
                name="Concurrent",
                status=CampaignStatus.RUNNING,
                clinical_follow_up_hours=72,
                calling_window_start=time(0),
                calling_window_end=time(23, 59, 59),
                campaign_priority=50,
                max_retries=0,
                outbound_capacity=1,
                created_by_user_id=user_id,
            )
        )
        await setup.flush()
        setup.add(
            OutreachTask(
                hospital_id=hospital_id,
                campaign_id=campaign_id,
                patient_id=patient_id,
                discharge_id=discharge_id,
                state=OutreachTaskState.PENDING,
                priority_score=0,
                priority_components={},
                attempt_count=0,
                max_attempts=1,
                eligible_at=now,
                next_eligible_at=now,
                clinical_deadline=now + timedelta(days=1),
            )
        )
        await setup.commit()
    context = RequestContext(user_id=user_id, hospital_id=hospital_id, role=Role.HOSPITAL_ADMIN)

    async def reserve_once():
        async with factory() as separate_session:
            return await QueueSchedulerService(separate_session, context).reserve_next(now)

    try:
        results = await asyncio.gather(reserve_once(), reserve_once())
        assert sum(result is not None for result in results) == 1
        async with factory() as check:
            active = await check.scalar(
                select(OutreachTask).where(OutreachTask.campaign_id == campaign_id)
            )
            assert active.state == OutreachTaskState.SCHEDULED
    finally:
        async with factory() as cleanup:
            await cleanup.execute(
                delete(OutreachTask).where(OutreachTask.campaign_id == campaign_id)
            )
            await cleanup.execute(delete(Campaign).where(Campaign.id == campaign_id))
            await cleanup.execute(delete(Discharge).where(Discharge.id == discharge_id))
            await cleanup.execute(delete(Encounter).where(Encounter.id == encounter_id))
            await cleanup.execute(delete(Patient).where(Patient.id == patient_id))
            await cleanup.execute(
                delete(HospitalConfiguration).where(
                    HospitalConfiguration.hospital_id == hospital_id
                )
            )
            await cleanup.execute(delete(AuditEvent).where(AuditEvent.actor_user_id == user_id))
            await cleanup.execute(delete(User).where(User.id == user_id))
            await cleanup.execute(delete(Hospital).where(Hospital.id == hospital_id))
            await cleanup.commit()
        await engine.dispose()
