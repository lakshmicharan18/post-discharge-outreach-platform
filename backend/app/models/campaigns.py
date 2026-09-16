import enum
from datetime import datetime, time
from uuid import UUID

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    Enum,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    Time,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.models.entities import Base, Identity, Tenant, Timestamps


class CampaignStatus(str, enum.Enum):
    DRAFT = "DRAFT"
    READY = "READY"
    SCHEDULED = "SCHEDULED"
    RUNNING = "RUNNING"
    PAUSED = "PAUSED"
    COMPLETED = "COMPLETED"
    CANCELLED = "CANCELLED"
    FAILED = "FAILED"


class Campaign(Identity, Tenant, Timestamps, Base):
    __tablename__ = "campaigns"
    __table_args__ = (
        CheckConstraint(
            "calling_window_start IS NULL OR calling_window_end IS NULL OR "
            "calling_window_end > calling_window_start",
            name="calling_window",
        ),
        CheckConstraint(
            "clinical_follow_up_hours IS NULL OR clinical_follow_up_hours > 0",
            name="follow_up_hours",
        ),
        CheckConstraint(
            "campaign_priority IS NULL OR campaign_priority BETWEEN 1 AND 100", name="priority"
        ),
        CheckConstraint("max_retries IS NULL OR max_retries >= 0", name="max_retries"),
        CheckConstraint(
            "outbound_capacity IS NULL OR outbound_capacity > 0", name="outbound_capacity"
        ),
        CheckConstraint("end_at IS NULL OR start_at IS NULL OR end_at >= start_at", name="dates"),
        Index("ix_campaigns_hospital_status", "hospital_id", "status"),
        Index("ix_campaigns_hospital_priority", "hospital_id", "campaign_priority"),
    )

    name: Mapped[str] = mapped_column(String(200))
    description: Mapped[str | None] = mapped_column(Text)
    status: Mapped[CampaignStatus] = mapped_column(
        Enum(CampaignStatus, name="campaign_status"), default=CampaignStatus.DRAFT, index=True
    )
    start_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), index=True)
    end_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    clinical_follow_up_hours: Mapped[int | None] = mapped_column(Integer)
    calling_window_start: Mapped[time | None] = mapped_column(Time)
    calling_window_end: Mapped[time | None] = mapped_column(Time)
    campaign_priority: Mapped[int | None] = mapped_column(Integer, index=True)
    max_retries: Mapped[int | None] = mapped_column(Integer)
    outbound_capacity: Mapped[int | None] = mapped_column(Integer)
    escalation_configuration: Mapped[dict] = mapped_column(JSONB, default=dict)
    eligibility_criteria: Mapped[dict] = mapped_column(JSONB, default=dict)
    created_by_user_id: Mapped[UUID] = mapped_column(ForeignKey("users.id"), index=True)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    paused_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
