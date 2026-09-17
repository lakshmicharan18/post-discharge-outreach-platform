from datetime import datetime, time, timedelta, timezone
from types import SimpleNamespace

from conftest import auth_headers, uid
from sqlalchemy import select

from app.models.campaigns import ManualFollowUp, OutreachAttempt, OutreachTask, OutreachTaskState
from app.models.healthcare import HospitalConfiguration
from app.services.outcomes import OutcomeService


async def prepared_task(client, session, *, max_retries=2):
    config = await session.scalar(
        select(HospitalConfiguration).where(HospitalConfiguration.hospital_id == uid(1))
    )
    config.is_ready, config.calling_window_start, config.calling_window_end = (
        True,
        time(0),
        time(23, 59, 59),
    )
    await session.flush()
    payload = {
        "name": "Outcome",
        "clinical_follow_up_hours": 72,
        "calling_window_start": "00:00:00",
        "calling_window_end": "23:59:59",
        "campaign_priority": 50,
        "max_retries": max_retries,
        "eligibility_criteria": {},
    }
    campaign = (
        await client.post("/api/v1/campaigns", headers=auth_headers(10), json=payload)
    ).json()
    await client.post(f"/api/v1/campaigns/{campaign['id']}/ready", headers=auth_headers(10))
    await client.post(f"/api/v1/campaigns/{campaign['id']}/start", headers=auth_headers(10))
    task = await session.scalar(
        select(OutreachTask).where(OutreachTask.campaign_id == campaign["id"])
    )
    task.state = OutreachTaskState.SCHEDULED
    await session.flush()
    return task


async def start(client, task):
    response = await client.post(
        f"/api/v1/outreach-tasks/{task.id}/start-call", headers=auth_headers(10), json={}
    )
    assert response.status_code == 200, response.text


async def outcome(client, task, kind, key="event-1", **extra):
    return await client.post(
        f"/api/v1/outreach-tasks/{task.id}/outcome",
        headers=auth_headers(10),
        json={"outcome": kind, "idempotency_key": key, **extra},
    )


async def test_completion_retry_callback_and_idempotency(client, session):
    completed = await prepared_task(client, session)
    await start(client, completed)
    assert (await outcome(client, completed, "COMPLETED")).json()["state"] == "COMPLETED"
    retry = await prepared_task(client, session)
    await start(client, retry)
    result = await outcome(client, retry, "NO_ANSWER", "retry")
    assert result.json()["state"] == "RETRY_SCHEDULED" and result.json()["attempt_count"] == 1
    duplicate = await outcome(client, retry, "NO_ANSWER", "retry")
    assert duplicate.status_code == 200 and duplicate.json()["attempt_count"] == 1
    callback = await prepared_task(client, session)
    await start(client, callback)
    when = (datetime.now(timezone.utc) + timedelta(hours=1)).isoformat()
    assert (
        await outcome(client, callback, "CALLBACK_REQUESTED", "callback", callback_at=when)
    ).json()["state"] == "CALLBACK_SCHEDULED"


async def test_dropped_context_and_exhaustion_create_one_manual_follow_up(client, session):
    task = await prepared_task(client, session, max_retries=0)
    await start(client, task)
    response = await outcome(
        client, task, "DROPPED", "drop", partial_context={"completed_questions": ["q1"]}
    )
    assert response.json()["state"] == "MANUAL_FOLLOW_UP"
    attempt = await session.scalar(
        select(OutreachAttempt).where(OutreachAttempt.outreach_task_id == task.id)
    )
    assert attempt.partial_context == {"completed_questions": ["q1"]}
    assert (
        len(
            list(
                await session.scalars(
                    select(ManualFollowUp).where(ManualFollowUp.outreach_task_id == task.id)
                )
            )
        )
        == 1
    )


async def test_invalid_number_and_roles_are_tenant_scoped(client, session):
    task = await prepared_task(client, session)
    await start(client, task)
    assert (await outcome(client, task, "INVALID_NUMBER", "invalid")).json()[
        "state"
    ] == "MANUAL_FOLLOW_UP"
    other = await prepared_task(client, session)
    assert (
        await client.post(
            f"/api/v1/outreach-tasks/{other.id}/start-call", headers=auth_headers(20), json={}
        )
    ).status_code == 404
    assert (
        await client.get(f"/api/v1/outreach-tasks/{task.id}/attempts", headers=auth_headers(99))
    ).status_code == 403
    assert (
        await client.post(
            f"/api/v1/outreach-tasks/{other.id}/start-call", headers=auth_headers(12), json={}
        )
    ).status_code == 403


async def test_stale_scheduled_recovery_releases_capacity_without_creating_attempt(client, session):
    task = await prepared_task(client, session)
    task.reservation_expires_at = datetime.now(timezone.utc) - timedelta(seconds=1)
    await session.flush()

    recovered = await client.post("/api/v1/queue/recover-stale", headers=auth_headers(10))
    assert recovered.status_code == 200, recovered.text
    assert recovered.json()["scheduled_released"] == 1
    await session.refresh(task)
    assert task.state == OutreachTaskState.PENDING
    assert task.reservation_token is None
    assert (
        await session.scalar(
            select(OutreachAttempt.id).where(OutreachAttempt.outreach_task_id == task.id)
        )
        is None
    )


async def test_stale_call_recovery_is_idempotent_and_records_technical_failure(client, session):
    task = await prepared_task(client, session)
    await start(client, task)
    task.processing_lease_expires_at = datetime.now(timezone.utc) - timedelta(seconds=1)
    await session.flush()

    recovered = await client.post("/api/v1/queue/recover-stale", headers=auth_headers(10))
    assert recovered.status_code == 200, recovered.text
    assert recovered.json()["calling_recovered"] == 1
    await session.refresh(task)
    assert task.state == OutreachTaskState.RETRY_SCHEDULED
    attempts = list(
        await session.scalars(
            select(OutreachAttempt).where(OutreachAttempt.outreach_task_id == task.id)
        )
    )
    assert len(attempts) == 1
    assert attempts[0].outcome.value == "TECHNICAL_FAILURE"
    assert attempts[0].technical_error_code == "STALE_CALLING_WORKER_RECOVERY"

    repeated = await client.post("/api/v1/queue/recover-stale", headers=auth_headers(10))
    assert repeated.status_code == 200 and repeated.json()["calling_recovered"] == 0
    assert (
        await session.scalar(
            select(OutreachAttempt).where(OutreachAttempt.outreach_task_id == task.id)
        )
    ).attempt_number == 1


async def test_stale_connected_recovery_creates_one_manual_follow_up(client, session):
    task = await prepared_task(client, session)
    await start(client, task)
    task.state = OutreachTaskState.CONNECTED
    task.processing_lease_expires_at = datetime.now(timezone.utc) - timedelta(seconds=1)
    await session.flush()

    recovered = await client.post("/api/v1/queue/recover-stale", headers=auth_headers(10))
    assert recovered.status_code == 200, recovered.text
    assert recovered.json()["connected_recovered"] == 1
    await session.refresh(task)
    assert task.state == OutreachTaskState.MANUAL_FOLLOW_UP
    follow_ups = list(
        await session.scalars(
            select(ManualFollowUp).where(ManualFollowUp.outreach_task_id == task.id)
        )
    )
    assert len(follow_ups) == 1
    assert follow_ups[0].reason_code == "STALE_CONNECTED_WORKER_RECOVERY"

    repeated = await client.post("/api/v1/queue/recover-stale", headers=auth_headers(10))
    assert repeated.status_code == 200 and repeated.json()["connected_recovered"] == 0


def test_retry_window_moves_to_next_valid_hospital_and_campaign_window():
    configuration = SimpleNamespace(
        timezone="UTC", calling_window_start=time(8), calling_window_end=time(20)
    )
    campaign = SimpleNamespace(calling_window_start=time(9), calling_window_end=time(18))
    retry = OutcomeService._within_windows(
        datetime(2026, 1, 1, 21, tzinfo=timezone.utc), configuration, campaign
    )
    assert retry == datetime(2026, 1, 2, 9, tzinfo=timezone.utc)
