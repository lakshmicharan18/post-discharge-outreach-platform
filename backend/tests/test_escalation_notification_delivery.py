from datetime import datetime, timezone
from uuid import UUID

import pytest
from sqlalchemy import func, select
from test_triage import completed_session

from app.core.context import CurrentUserContext
from app.core.errors import APIError
from app.models.entities import Role
from app.models.notifications import Notification, NotificationSeverity, NotificationStatus
from app.models.triage import EscalationDecisionRecord
from app.models.workflow import WorkflowEvent, WorkflowEventStatus
from app.services.escalations import EscalationCaseService
from app.services.notifications import SendNotificationHandler
from app.services.workflows import WorkflowService


def context(tenant: int) -> CurrentUserContext:
    return CurrentUserContext(UUID(int=tenant * 10), UUID(int=tenant), Role.HOSPITAL_ADMIN)


async def urgent_case_and_event(client, session):
    intake_session_id = await completed_session(client, session)
    decision = EscalationDecisionRecord(
        hospital_id=UUID(int=1),
        intake_session_id=UUID(intake_session_id),
        assessment_ids=[],
        final_classification="URGENT",
        agreement_status="DISAGREEMENT",
        requires_human_review=True,
        recommended_action="HUMAN_REVIEW",
        execution_metadata={},
    )
    session.add(decision)
    await session.commit()
    case = await EscalationCaseService(session, context(1)).create_for_decision(decision.id)
    event = await session.scalar(
        select(WorkflowEvent).where(
            WorkflowEvent.hospital_id == UUID(int=1),
            WorkflowEvent.idempotency_key == f"send-notification:{case.id}",
        )
    )
    assert event is not None
    return case, event


async def test_urgent_escalation_enqueues_safe_tenant_scoped_notification_event(client, session):
    case, event = await urgent_case_and_event(client, session)

    assert event.hospital_id == UUID(int=1)
    assert event.event_type == "SEND_NOTIFICATION"
    assert event.status == WorkflowEventStatus.PENDING
    assert event.payload == {"escalation_id": str(case.id)}


async def test_notification_handler_delivers_one_urgent_notification(client, session):
    case, event = await urgent_case_and_event(client, session)
    now = datetime.now(timezone.utc)
    claimed = await WorkflowService(session).claim_for_tenant(context(1), now)
    assert claimed is not None and claimed.id == event.id

    handler = SendNotificationHandler(session, context(1))
    notification = await handler.handle(claimed)
    repeated = await handler.handle(claimed)

    assert notification.id == repeated.id
    assert notification.status == NotificationStatus.UNREAD
    assert notification.severity == NotificationSeverity.URGENT
    assert notification.related_escalation_id == case.id
    assert notification.related_workflow_event_id == claimed.id
    assert await session.scalar(select(func.count()).select_from(Notification)) == 1


async def test_cross_tenant_notification_processing_is_rejected(client, session):
    _, event = await urgent_case_and_event(client, session)
    claimed = await WorkflowService(session).claim_for_tenant(
        context(1), datetime.now(timezone.utc)
    )
    assert claimed is not None and claimed.id == event.id

    with pytest.raises(APIError) as error:
        await SendNotificationHandler(session, context(2)).handle(claimed)
    assert error.value.status == 404
    assert await session.scalar(select(func.count()).select_from(Notification)) == 0
