from uuid import UUID, uuid4

from sqlalchemy import select

from app.models.notifications import Notification, NotificationSeverity, NotificationStatus


async def test_tenant_owned_notification_persists_with_optional_references(session):
    escalation_id = uuid4()
    workflow_event_id = uuid4()
    notification = Notification(
        hospital_id=UUID(int=1),
        notification_type="ESCALATION_REQUIRES_REVIEW",
        title="Review required",
        message="A review case requires attention.",
        severity=NotificationSeverity.URGENT,
        recipient_user_id=UUID(int=10),
        related_escalation_id=escalation_id,
        related_workflow_event_id=workflow_event_id,
    )
    session.add(notification)
    await session.commit()
    await session.refresh(notification)

    assert notification.hospital_id == UUID(int=1)
    assert notification.status == NotificationStatus.UNREAD
    assert notification.severity == NotificationSeverity.URGENT
    assert notification.related_escalation_id == escalation_id
    assert notification.related_workflow_event_id == workflow_event_id

    foreign_tenant_result = await session.scalar(
        select(Notification).where(
            Notification.id == notification.id,
            Notification.hospital_id == UUID(int=2),
        )
    )
    assert foreign_tenant_result is None
