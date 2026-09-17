from datetime import datetime, timedelta, timezone
from uuid import UUID

import pytest

from app.core.context import CurrentUserContext
from app.core.errors import APIError
from app.models.entities import Role
from app.models.notifications import NotificationSeverity, NotificationStatus
from app.services.notifications import NotificationService


def context(tenant: int) -> CurrentUserContext:
    return CurrentUserContext(UUID(int=tenant * 10), UUID(int=tenant), Role.HOSPITAL_ADMIN)


async def test_notification_creation_retrieval_and_status_filtering(session):
    hospital_one = NotificationService(session, context(1))
    hospital_two = NotificationService(session, context(2))
    unread = await hospital_one.create("WORKFLOW_UPDATE", "Queue updated", "Work is available.")
    warning = await hospital_one.create(
        "REVIEW_REQUIRED",
        "Review required",
        "A review case requires attention.",
        severity=NotificationSeverity.WARNING,
    )
    foreign = await hospital_two.create("WORKFLOW_UPDATE", "Queue updated", "Work is available.")

    assert unread.hospital_id == UUID(int=1)
    assert unread.status == NotificationStatus.UNREAD
    assert await hospital_one.get(unread.id) == unread
    assert {notification.id for notification in await hospital_one.list()} == {
        unread.id,
        warning.id,
    }
    assert len(await hospital_one.list(NotificationStatus.UNREAD)) == 2
    with pytest.raises(APIError) as error:
        await hospital_two.get(unread.id)
    assert error.value.status == 404
    assert (await hospital_two.get(foreign.id)).hospital_id == UUID(int=2)


async def test_notification_read_and_acknowledgement_lifecycle(session):
    service = NotificationService(session, context(1))
    now = datetime.now(timezone.utc)
    notification = await service.create("WORKFLOW_UPDATE", "Queue updated", "Work is available.")

    read = await service.mark_read(notification.id, now)
    assert read.status == NotificationStatus.READ
    assert read.read_at == now

    acknowledged = await service.acknowledge(notification.id, now + timedelta(seconds=1))
    assert acknowledged.status == NotificationStatus.ACKNOWLEDGED
    assert acknowledged.read_at == now
    assert acknowledged.acknowledged_at == now + timedelta(seconds=1)
    with pytest.raises(APIError) as error:
        await service.acknowledge(notification.id, now + timedelta(seconds=2))
    assert error.value.status == 409


async def test_cross_tenant_update_is_blocked_and_unread_acknowledgement_is_timestamped(session):
    hospital_one = NotificationService(session, context(1))
    hospital_two = NotificationService(session, context(2))
    now = datetime.now(timezone.utc)
    foreign = await hospital_one.create("WORKFLOW_UPDATE", "Queue updated", "Work is available.")

    with pytest.raises(APIError) as error:
        await hospital_two.mark_read(foreign.id, now)
    assert error.value.status == 404
    assert foreign.status == NotificationStatus.UNREAD

    acknowledged = await hospital_one.acknowledge(foreign.id, now)
    assert acknowledged.status == NotificationStatus.ACKNOWLEDGED
    assert acknowledged.read_at == now
    assert acknowledged.acknowledged_at == now
