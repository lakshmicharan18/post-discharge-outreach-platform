from datetime import datetime
from uuid import UUID

from sqlalchemy import DateTime, ForeignKey, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.models.entities import Base, Identity, Tenant, Timestamps


class EHROperationRecord(Identity, Tenant, Timestamps, Base):
    __tablename__ = "ehr_operations"
    __table_args__ = (UniqueConstraint("hospital_id", "idempotency_key"),)

    outreach_task_id: Mapped[UUID | None] = mapped_column(ForeignKey("outreach_tasks.id"))
    reference_id: Mapped[UUID] = mapped_column(index=True)
    operation_type: Mapped[str] = mapped_column(String(50))
    idempotency_key: Mapped[str] = mapped_column(String(150))
    safe_payload: Mapped[dict] = mapped_column(JSONB, default=dict)
    status: Mapped[str] = mapped_column(String(20), default="SUCCEEDED")
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    error: Mapped[str | None] = mapped_column(String(500))
