from datetime import datetime
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.context import RequestContext
from app.core.errors import APIError
from app.models.entities import User
from app.models.notifications import Notification, NotificationSeverity, NotificationStatus
from app.models.triage import EscalationCase
from app.models.workflow import WorkflowEvent, WorkflowEventStatus


class NotificationService:
    def __init__(self, session: AsyncSession, context: RequestContext) -> None:
        self.session = session
        self.context = context
        self.hospital_id = context.require_clinical_tenant()

    async def create(
        self,
        notification_type: str,
        title: str,
        message: str,
        severity: NotificationSeverity = NotificationSeverity.INFO,
        recipient_user_id: UUID | None = None,
        related_escalation_id: UUID | None = None,
        related_workflow_event_id: UUID | None = None,
    ) -> Notification:
        if recipient_user_id is not None:
            recipient = await self.session.scalar(
                select(User.id).where(
                    User.id == recipient_user_id,
                    User.hospital_id == self.hospital_id,
                )
            )
            if recipient is None:
                raise APIError(404, "not_found", "Notification recipient not found")
        notification = Notification(
            hospital_id=self.hospital_id,
            notification_type=notification_type,
            title=title,
            message=message,
            severity=severity,
            recipient_user_id=recipient_user_id,
            related_escalation_id=related_escalation_id,
            related_workflow_event_id=related_workflow_event_id,
        )
        self.session.add(notification)
        await self.session.commit()
        await self.session.refresh(notification)
        return notification

    async def list(self, status: NotificationStatus | None = None) -> list[Notification]:
        query = select(Notification).where(Notification.hospital_id == self.hospital_id)
        if status is not None:
            query = query.where(Notification.status == status)
        result = await self.session.scalars(
            query.order_by(Notification.created_at.desc(), Notification.id)
        )
        return list(result)

    async def get(self, notification_id: UUID) -> Notification:
        notification = await self.session.scalar(
            select(Notification).where(
                Notification.id == notification_id,
                Notification.hospital_id == self.hospital_id,
            )
        )
        if notification is None:
            raise APIError(404, "not_found", "Notification not found")
        return notification

    async def mark_read(self, notification_id: UUID, now: datetime) -> Notification:
        notification = await self.get(notification_id)
        if notification.status != NotificationStatus.UNREAD:
            raise APIError(409, "invalid_transition", "Notification is not unread")
        notification.status = NotificationStatus.READ
        notification.read_at = now
        await self.session.commit()
        await self.session.refresh(notification)
        return notification

    async def acknowledge(self, notification_id: UUID, now: datetime) -> Notification:
        notification = await self.get(notification_id)
        if notification.status == NotificationStatus.ACKNOWLEDGED:
            raise APIError(409, "invalid_transition", "Notification is already acknowledged")
        if notification.status == NotificationStatus.UNREAD:
            notification.read_at = now
        notification.status = NotificationStatus.ACKNOWLEDGED
        notification.acknowledged_at = now
        await self.session.commit()
        await self.session.refresh(notification)
        return notification


class SendNotificationHandler:
    def __init__(self, session: AsyncSession, context: RequestContext) -> None:
        self.session = session
        self.context = context
        self.hospital_id = context.require_clinical_tenant()

    async def handle(self, event: WorkflowEvent) -> Notification:
        if event.event_type != "SEND_NOTIFICATION":
            raise APIError(422, "invalid_event_type", "Workflow event is not a notification")
        if event.hospital_id != self.hospital_id:
            raise APIError(404, "not_found", "Workflow event not found")
        if event.status != WorkflowEventStatus.PROCESSING:
            raise APIError(409, "invalid_transition", "Workflow event is not processing")
        escalation_id, recipient_user_id = self._payload_references(event.payload)
        escalation = await self.session.scalar(
            select(EscalationCase).where(
                EscalationCase.id == escalation_id,
                EscalationCase.hospital_id == self.hospital_id,
            )
        )
        if escalation is None or escalation.priority != "URGENT":
            raise APIError(404, "not_found", "Urgent escalation not found")
        existing = await self.session.scalar(
            select(Notification).where(
                Notification.hospital_id == self.hospital_id,
                Notification.related_workflow_event_id == event.id,
            )
        )
        if existing is not None:
            return existing
        return await NotificationService(self.session, self.context).create(
            "URGENT_ESCALATION",
            "Urgent escalation requires review",
            "An urgent escalation case requires review.",
            severity=NotificationSeverity.URGENT,
            recipient_user_id=recipient_user_id,
            related_escalation_id=escalation.id,
            related_workflow_event_id=event.id,
        )

    @staticmethod
    def _payload_references(payload: dict) -> tuple[UUID, UUID | None]:
        if not isinstance(payload, dict) or set(payload) - {"escalation_id", "recipient_user_id"}:
            raise APIError(422, "invalid_payload", "Workflow event payload is invalid")
        try:
            escalation_id = UUID(str(payload["escalation_id"]))
            recipient_user_id = (
                UUID(str(payload["recipient_user_id"]))
                if payload.get("recipient_user_id") is not None
                else None
            )
        except (KeyError, TypeError, ValueError) as exc:
            raise APIError(422, "invalid_payload", "Workflow event payload is invalid") from exc
        return escalation_id, recipient_user_id
