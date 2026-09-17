import enum
from datetime import datetime

from sqlalchemy import CheckConstraint, DateTime, Enum, Index, Integer, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.models.entities import Base, Identity, Tenant, Timestamps


class WorkflowEventStatus(str, enum.Enum):
    PENDING = "PENDING"
    PROCESSING = "PROCESSING"
    RETRY_SCHEDULED = "RETRY_SCHEDULED"
    SUCCEEDED = "SUCCEEDED"
    FAILED = "FAILED"


class WorkflowEvent(Identity, Tenant, Timestamps, Base):
    __tablename__ = "workflow_events"
    __table_args__ = (
        UniqueConstraint("hospital_id", "idempotency_key"),
        CheckConstraint("attempt_count >= 0", name="attempt_count"),
        CheckConstraint("max_attempts > 0", name="max_attempts"),
        Index(
            "ix_workflow_events_hospital_status_next", "hospital_id", "status", "next_attempt_at"
        ),
    )
    event_type: Mapped[str] = mapped_column(String(80))
    payload: Mapped[dict] = mapped_column(JSONB, default=dict)
    status: Mapped[WorkflowEventStatus] = mapped_column(
        Enum(WorkflowEventStatus, name="workflow_event_status"),
        default=WorkflowEventStatus.PENDING,
        index=True,
    )
    attempt_count: Mapped[int] = mapped_column(Integer, default=0)
    max_attempts: Mapped[int] = mapped_column(Integer, default=3)
    next_attempt_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    idempotency_key: Mapped[str] = mapped_column(String(150))
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    processed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_error_type: Mapped[str | None] = mapped_column(String(100))
