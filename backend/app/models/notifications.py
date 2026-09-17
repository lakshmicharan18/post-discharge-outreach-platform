import enum
from datetime import datetime
from uuid import UUID

from sqlalchemy import DateTime, Enum, ForeignKey, Index, String
from sqlalchemy.orm import Mapped, mapped_column

from app.models.entities import Base, Identity, Tenant, Timestamps


class NotificationSeverity(str, enum.Enum):
    INFO = "INFO"
    WARNING = "WARNING"
    URGENT = "URGENT"


class NotificationStatus(str, enum.Enum):
    UNREAD = "UNREAD"
    READ = "READ"
    ACKNOWLEDGED = "ACKNOWLEDGED"


class Notification(Identity, Tenant, Timestamps, Base):
    __tablename__ = "notifications"
    __table_args__ = (
        Index("ix_notifications_hospital_status_created", "hospital_id", "status", "created_at"),
    )

    notification_type: Mapped[str] = mapped_column(String(80))
    title: Mapped[str] = mapped_column(String(200))
    message: Mapped[str] = mapped_column(String(1000))
    severity: Mapped[NotificationSeverity] = mapped_column(
        Enum(NotificationSeverity, name="notification_severity"),
        default=NotificationSeverity.INFO,
    )
    status: Mapped[NotificationStatus] = mapped_column(
        Enum(NotificationStatus, name="notification_status"),
        default=NotificationStatus.UNREAD,
    )
    recipient_user_id: Mapped[UUID | None] = mapped_column(ForeignKey("users.id"), index=True)
    related_escalation_id: Mapped[UUID | None] = mapped_column(index=True)
    related_workflow_event_id: Mapped[UUID | None] = mapped_column(index=True)
    read_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    acknowledged_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
