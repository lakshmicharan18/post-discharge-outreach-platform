from datetime import datetime, timedelta, timezone
from uuid import UUID, uuid4

import pytest

from app.core.context import CurrentUserContext
from app.models.entities import Role
from app.models.workflow import WorkflowEventStatus
from app.services.workflows import WorkflowService


def context(tenant: int) -> CurrentUserContext:
    return CurrentUserContext(UUID(int=tenant * 10), UUID(int=tenant), Role.HOSPITAL_ADMIN)


async def claimed_event(session, *, tenant: int = 1, max_attempts: int = 3):
    service = WorkflowService(session)
    claimed_at = datetime.now(timezone.utc)
    event = await service.create(
        context(tenant), "RETRY_OUTREACH", {}, f"processing-{uuid4().hex}", max_attempts
    )
    event.next_attempt_at = claimed_at
    await session.commit()
    claimed = await service.claim_for_tenant(context(tenant), claimed_at)
    assert claimed is not None
    return service, claimed, claimed_at


async def test_processing_event_completes_successfully(session):
    service, event, claimed_at = await claimed_event(session)
    completed_at = claimed_at + timedelta(seconds=1)

    completed = await service.complete_success(context(1), event.id, completed_at)

    assert completed.status == WorkflowEventStatus.SUCCEEDED
    assert completed.processed_at == completed_at
    assert completed.last_error_type is None
    assert completed.hospital_id == UUID(int=1)


async def test_processing_failure_schedules_deterministic_retry(session):
    service, event, claimed_at = await claimed_event(session)
    failed_at = claimed_at + timedelta(seconds=1)

    scheduled = await service.complete_failure(
        context(1), event.id, "exception message containing secrets", failed_at
    )

    assert scheduled.status == WorkflowEventStatus.RETRY_SCHEDULED
    assert scheduled.last_error_type == "unknown_failure"
    assert scheduled.next_attempt_at == failed_at + timedelta(minutes=1)
    assert scheduled.next_attempt_at > failed_at
    assert scheduled.hospital_id == UUID(int=1)


async def test_failure_at_max_attempts_is_terminal(session):
    service, event, claimed_at = await claimed_event(session, max_attempts=1)
    scheduled_at = event.next_attempt_at
    failed_at = claimed_at + timedelta(seconds=1)

    failed = await service.complete_failure(context(1), event.id, "provider_failure", failed_at)

    assert failed.status == WorkflowEventStatus.FAILED
    assert failed.processed_at == failed_at
    assert failed.last_error_type == "provider_failure"
    assert failed.next_attempt_at == scheduled_at


async def test_only_processing_events_in_the_same_tenant_can_complete(session):
    service = WorkflowService(session)
    pending = await service.create(context(1), "RETRY_OUTREACH", {}, f"pending-{uuid4().hex}")
    with pytest.raises(ValueError, match="not processing"):
        await service.complete_success(context(1), pending.id, datetime.now(timezone.utc))

    _, processing, claimed_at = await claimed_event(session)
    with pytest.raises(ValueError, match="not processing"):
        await service.complete_failure(
            context(2), processing.id, "error message containing secrets", claimed_at
        )
    assert processing.status == WorkflowEventStatus.PROCESSING

    await service.complete_success(context(1), processing.id, claimed_at + timedelta(seconds=1))
    with pytest.raises(ValueError, match="not processing"):
        await service.complete_failure(context(1), processing.id, "handler_failure", claimed_at)
