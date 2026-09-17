import asyncio
import os
from datetime import datetime, timedelta, timezone
from uuid import UUID, uuid4

from sqlalchemy import delete
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.core.context import CurrentUserContext
from app.models.entities import Hospital, Role
from app.models.workflow import WorkflowEvent, WorkflowEventStatus
from app.services.workflows import WorkflowService


def context(tenant: int):
    return CurrentUserContext(UUID(int=tenant * 10), UUID(int=tenant), Role.HOSPITAL_ADMIN)


async def test_claims_only_due_tenant_eligible_events(session):
    service, now = WorkflowService(session), datetime.now(timezone.utc)
    due = await service.create(context(1), "RETRY_OUTREACH", {}, "due")
    future = await service.create(context(1), "RETRY_OUTREACH", {}, "future")
    foreign = await service.create(context(2), "RETRY_OUTREACH", {}, "foreign")
    due.next_attempt_at = now
    future.next_attempt_at = now + timedelta(minutes=1)
    foreign.next_attempt_at = now
    await session.commit()
    claimed = await service.claim_for_tenant(context(1), now)
    assert claimed.id == due.id
    assert claimed.status == WorkflowEventStatus.PROCESSING
    assert claimed.started_at == now and claimed.attempt_count == 1
    assert await service.claim_for_tenant(context(1), now) is None


async def test_terminal_and_processing_events_are_not_claimed(session):
    service, now = WorkflowService(session), datetime.now(timezone.utc)
    for key, status in (
        ("s", WorkflowEventStatus.SUCCEEDED),
        ("f", WorkflowEventStatus.FAILED),
        ("p", WorkflowEventStatus.PROCESSING),
    ):
        event = await service.create(context(1), "RETRY_OUTREACH", {}, key)
        event.status = status
    await session.commit()
    assert await service.claim_for_tenant(context(1), now) is None


async def test_competing_workers_claim_distinct_events_once():
    """Independent PostgreSQL sessions use SKIP LOCKED rather than duplicate a claim."""
    engine = create_async_engine(os.environ["TEST_DATABASE_URL"])
    sessions = async_sessionmaker(engine, expire_on_commit=False)
    hospital_id = uuid4()
    worker_context = CurrentUserContext(uuid4(), hospital_id, Role.HOSPITAL_ADMIN)
    now = datetime.now(timezone.utc)

    try:
        async with sessions() as setup_session:
            setup_session.add(
                Hospital(id=hospital_id, name="Concurrent", code=f"C{hospital_id.hex}")
            )
            await setup_session.commit()

            setup_service = WorkflowService(setup_session)
            events = [
                await setup_service.create(
                    worker_context, "RETRY_OUTREACH", {}, f"concurrent-{index}"
                )
                for index in range(2)
            ]
            for event in events:
                event.next_attempt_at = now
            await setup_session.commit()

        async with sessions() as worker_one, sessions() as worker_two:
            claimed_one, claimed_two = await asyncio.gather(
                WorkflowService(worker_one).claim_for_tenant(worker_context, now),
                WorkflowService(worker_two).claim_for_tenant(worker_context, now),
            )

        claimed = [event for event in (claimed_one, claimed_two) if event is not None]
        assert len(claimed) == 2
        assert {event.id for event in claimed} == {event.id for event in events}
        assert all(event.status == WorkflowEventStatus.PROCESSING for event in claimed)
        assert all(event.attempt_count == 1 for event in claimed)

        async with sessions() as verify_session:
            persisted = [await verify_session.get(WorkflowEvent, event.id) for event in events]
        assert all(event is not None for event in persisted)
        assert all(event.status == WorkflowEventStatus.PROCESSING for event in persisted)
        assert all(event.attempt_count == 1 for event in persisted)
    finally:
        async with sessions() as cleanup_session:
            await cleanup_session.execute(
                delete(WorkflowEvent).where(WorkflowEvent.hospital_id == hospital_id)
            )
            await cleanup_session.execute(delete(Hospital).where(Hospital.id == hospital_id))
            await cleanup_session.commit()
        await engine.dispose()
