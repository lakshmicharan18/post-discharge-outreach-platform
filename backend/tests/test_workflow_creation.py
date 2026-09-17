from uuid import UUID

from sqlalchemy import func, select

from app.core.context import CurrentUserContext
from app.models.entities import Role
from app.models.workflow import WorkflowEvent, WorkflowEventStatus
from app.services.workflows import WorkflowService


def context(tenant: int):
    return CurrentUserContext(UUID(int=tenant * 10), UUID(int=tenant), Role.HOSPITAL_ADMIN)


async def test_tenant_scoped_event_creation_and_idempotency(session):
    service = WorkflowService(session)
    event = await service.create(context(1), "RETRY_OUTREACH", {"task_id": "safe-id"}, "event-1", 4)
    assert event.hospital_id == UUID(int=1)
    assert event.status == WorkflowEventStatus.PENDING
    assert event.attempt_count == 0 and event.max_attempts == 4
    assert event.event_type == "RETRY_OUTREACH" and event.payload == {"task_id": "safe-id"}
    duplicate = await service.create(context(1), "RETRY_OUTREACH", {}, "event-1")
    assert duplicate.id == event.id
    other = await service.create(context(2), "RETRY_OUTREACH", {}, "event-1")
    assert other.id != event.id
    assert await session.scalar(select(func.count()).select_from(WorkflowEvent)) == 2
