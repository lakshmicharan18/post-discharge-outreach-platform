from uuid import UUID

from sqlalchemy import Boolean, ForeignKey, String
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.models.entities import Base, Identity, Tenant, Timestamps


class ClinicalTriageRecord(Identity, Tenant, Timestamps, Base):
    __tablename__ = "clinical_triage_assessments"
    intake_session_id: Mapped[UUID] = mapped_column(
        ForeignKey("voice_intake_sessions.id"), index=True
    )
    outreach_task_id: Mapped[UUID] = mapped_column(ForeignKey("outreach_tasks.id"), index=True)
    classification: Mapped[str] = mapped_column(String(50), index=True)
    requires_human_review: Mapped[bool] = mapped_column(Boolean)
    assessment: Mapped[dict] = mapped_column(JSONB)
    execution_metadata: Mapped[dict] = mapped_column(JSONB, default=dict)
