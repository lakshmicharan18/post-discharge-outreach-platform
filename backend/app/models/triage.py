from datetime import datetime
from uuid import UUID

from sqlalchemy import Boolean, DateTime, ForeignKey, String, UniqueConstraint
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


class EscalationDecisionRecord(Identity, Tenant, Timestamps, Base):
    __tablename__ = "escalation_decisions"
    intake_session_id: Mapped[UUID] = mapped_column(
        ForeignKey("voice_intake_sessions.id"), index=True
    )
    assessment_ids: Mapped[list] = mapped_column(JSONB)
    final_classification: Mapped[str] = mapped_column(String(50))
    agreement_status: Mapped[str] = mapped_column(String(30))
    requires_human_review: Mapped[bool] = mapped_column(Boolean)
    disagreement_reason: Mapped[str | None] = mapped_column(String(250))
    recommended_action: Mapped[str] = mapped_column(String(100))
    execution_metadata: Mapped[dict] = mapped_column(JSONB, default=dict)


class EscalationCase(Identity, Tenant, Timestamps, Base):
    __tablename__ = "escalation_cases"
    __table_args__ = (UniqueConstraint("escalation_decision_id"),)
    escalation_decision_id: Mapped[UUID] = mapped_column(ForeignKey("escalation_decisions.id"))
    intake_session_id: Mapped[UUID] = mapped_column(ForeignKey("voice_intake_sessions.id"))
    status: Mapped[str] = mapped_column(String(30), default="OPEN")
    priority: Mapped[str] = mapped_column(String(50))
    assigned_reviewer_id: Mapped[UUID | None] = mapped_column(ForeignKey("users.id"))
    reviewer_notes: Mapped[str | None] = mapped_column(String(2000))
    resolution: Mapped[str | None] = mapped_column(String(100))
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
