from contextlib import asynccontextmanager
from datetime import datetime, timezone
from uuid import UUID, uuid4

from sqlalchemy import func, select
from test_escalation_notification_delivery import context, urgent_case_and_event

from app.models.notifications import Notification
from app.models.workflow import WorkflowEventStatus
from app.services.workflow_runner import WorkflowEventRunner
from app.services.workflows import WorkflowService


def runner_for(session) -> WorkflowEventRunner:
    @asynccontextmanager
    async def session_provider():
        yield session

    return WorkflowEventRunner(session_provider)


async def test_runner_automatically_delivers_notification_and_completes_event(client, session):
    case, event = await urgent_case_and_event(client, session)

    assert await runner_for(session).run_once()

    await session.refresh(event)
    notification = await session.scalar(
        select(Notification).where(Notification.related_workflow_event_id == event.id)
    )
    assert event.status == WorkflowEventStatus.SUCCEEDED
    assert event.processed_at is not None
    assert notification is not None
    assert notification.hospital_id == UUID(int=1)
    assert notification.related_escalation_id == case.id


async def test_runner_handler_failure_retries_then_fails_at_max_attempts(session):
    workflows = WorkflowService(session)
    event = await workflows.create(
        context(1),
        "SEND_NOTIFICATION",
        {"escalation_id": str(uuid4())},
        f"missing-escalation:{uuid4()}",
        max_attempts=2,
    )
    event.next_attempt_at = datetime.now(timezone.utc)
    await session.commit()
    runner = runner_for(session)

    assert await runner.run_once()
    await session.refresh(event)
    assert event.status == WorkflowEventStatus.RETRY_SCHEDULED
    assert event.attempt_count == 1
    assert event.last_error_type == "handler_failure"
    assert event.next_attempt_at > event.started_at

    event.next_attempt_at = datetime.now(timezone.utc)
    await session.commit()
    assert await runner.run_once()
    await session.refresh(event)
    assert event.status == WorkflowEventStatus.FAILED
    assert event.attempt_count == 2
    assert event.processed_at is not None


async def test_runner_fails_closed_for_foreign_escalation_reference(client, session):
    case, existing_event = await urgent_case_and_event(client, session)
    existing_event.status = WorkflowEventStatus.SUCCEEDED
    event = await WorkflowService(session).create(
        context(2),
        "SEND_NOTIFICATION",
        {"escalation_id": str(case.id)},
        f"foreign-escalation:{uuid4()}",
    )
    event.next_attempt_at = datetime.now(timezone.utc)
    await session.commit()

    assert await runner_for(session).run_once()

    await session.refresh(event)
    assert event.hospital_id == UUID(int=2)
    assert event.status == WorkflowEventStatus.RETRY_SCHEDULED
    assert await session.scalar(select(func.count()).select_from(Notification)) == 0


async def test_runner_marks_unknown_event_type_as_failed(session):
    event = await WorkflowService(session).create(
        context(1), "UNSUPPORTED_EVENT", {}, f"unknown-event:{uuid4()}", max_attempts=1
    )
    event.next_attempt_at = datetime.now(timezone.utc)
    await session.commit()

    assert await runner_for(session).run_once()

    await session.refresh(event)
    assert event.status == WorkflowEventStatus.FAILED
    assert event.last_error_type == "unknown_failure"
    assert event.processed_at is not None
