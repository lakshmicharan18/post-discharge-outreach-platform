import enum
from datetime import datetime, time
from uuid import UUID

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    Enum,
    ForeignKey,
    ForeignKeyConstraint,
    Index,
    Integer,
    String,
    Text,
    Time,
    UniqueConstraint,
    func,
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


class OutreachTaskState(str, enum.Enum):
    PENDING = "PENDING"
    SCHEDULED = "SCHEDULED"
    CALLING = "CALLING"
    CONNECTED = "CONNECTED"
    COMPLETED = "COMPLETED"
    NO_ANSWER = "NO_ANSWER"
    BUSY = "BUSY"
    VOICEMAIL = "VOICEMAIL"
    DROPPED = "DROPPED"
    RETRY_SCHEDULED = "RETRY_SCHEDULED"
    CALLBACK_SCHEDULED = "CALLBACK_SCHEDULED"
    ESCALATED = "ESCALATED"
    MANUAL_FOLLOW_UP = "MANUAL_FOLLOW_UP"
    FAILED = "FAILED"


class OutreachOutcome(str, enum.Enum):
    COMPLETED = "COMPLETED"
    NO_ANSWER = "NO_ANSWER"
    BUSY = "BUSY"
    VOICEMAIL = "VOICEMAIL"
    DROPPED = "DROPPED"
    INVALID_NUMBER = "INVALID_NUMBER"
    DECLINED = "DECLINED"
    CALLBACK_REQUESTED = "CALLBACK_REQUESTED"
    TECHNICAL_FAILURE = "TECHNICAL_FAILURE"


class ManualFollowUpStatus(str, enum.Enum):
    OPEN = "OPEN"
    RESOLVED = "RESOLVED"


class SimulationRunStatus(str, enum.Enum):
    READY = "READY"
    RUNNING = "RUNNING"
    COMPLETED = "COMPLETED"
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


class OutreachTask(Identity, Tenant, Timestamps, Base):
    __tablename__ = "outreach_tasks"
    __table_args__ = (
        UniqueConstraint("hospital_id", "campaign_id", "discharge_id"),
        CheckConstraint("attempt_count >= 0", name="attempt_count"),
        CheckConstraint("max_attempts > 0", name="max_attempts"),
        Index("ix_outreach_tasks_hospital_state_next", "hospital_id", "state", "next_eligible_at"),
        Index(
            "ix_outreach_tasks_hospital_state_priority", "hospital_id", "state", "priority_score"
        ),
    )
    campaign_id: Mapped[UUID] = mapped_column(ForeignKey("campaigns.id"), index=True)
    patient_id: Mapped[UUID] = mapped_column(ForeignKey("patients.id"), index=True)
    discharge_id: Mapped[UUID] = mapped_column(ForeignKey("discharges.id"), index=True)
    state: Mapped[OutreachTaskState] = mapped_column(
        Enum(OutreachTaskState, name="outreach_task_state"),
        default=OutreachTaskState.PENDING,
        index=True,
    )
    priority_score: Mapped[int] = mapped_column(Integer, index=True)
    priority_components: Mapped[dict] = mapped_column(JSONB, default=dict)
    attempt_count: Mapped[int] = mapped_column(Integer, default=0)
    max_attempts: Mapped[int] = mapped_column(Integer)
    eligible_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    next_eligible_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    clinical_deadline: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    callback_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), index=True)
    scheduled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_outcome: Mapped[str | None] = mapped_column(String(50))
    last_error_code: Mapped[str | None] = mapped_column(String(100))
    manual_follow_up_required: Mapped[bool] = mapped_column(default=False)
    reserved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    reservation_token: Mapped[UUID | None] = mapped_column(index=True)
    reservation_expires_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), index=True
    )


class OutreachAttempt(Identity, Tenant, Timestamps, Base):
    __tablename__ = "outreach_attempts"
    __table_args__ = (
        UniqueConstraint("hospital_id", "outcome_event_id"),
        UniqueConstraint("outreach_task_id", "attempt_number"),
        Index(
            "ix_outreach_attempts_hospital_outcome_started", "hospital_id", "outcome", "started_at"
        ),
    )
    campaign_id: Mapped[UUID] = mapped_column(ForeignKey("campaigns.id"), index=True)
    outreach_task_id: Mapped[UUID] = mapped_column(ForeignKey("outreach_tasks.id"), index=True)
    patient_id: Mapped[UUID] = mapped_column(ForeignKey("patients.id"), index=True)
    discharge_id: Mapped[UUID] = mapped_column(ForeignKey("discharges.id"), index=True)
    attempt_number: Mapped[int] = mapped_column(Integer)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    ended_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    duration_seconds: Mapped[int | None] = mapped_column(Integer)
    outcome: Mapped[OutreachOutcome | None] = mapped_column(
        Enum(OutreachOutcome, name="outreach_outcome"), index=True
    )
    outcome_reason: Mapped[str | None] = mapped_column(String(100))
    provider_call_id: Mapped[str | None] = mapped_column(String(150))
    outcome_event_id: Mapped[str | None] = mapped_column(String(150))
    callback_requested_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    technical_error_code: Mapped[str | None] = mapped_column(String(100))
    partial_context: Mapped[dict | None] = mapped_column(JSONB)


class ManualFollowUp(Identity, Tenant, Timestamps, Base):
    __tablename__ = "manual_follow_ups"
    __table_args__ = (
        UniqueConstraint("outreach_task_id"),
        Index(
            "ix_manual_follow_ups_hospital_status_reason", "hospital_id", "status", "reason_code"
        ),
    )
    patient_id: Mapped[UUID] = mapped_column(ForeignKey("patients.id"), index=True)
    campaign_id: Mapped[UUID] = mapped_column(ForeignKey("campaigns.id"), index=True)
    outreach_task_id: Mapped[UUID] = mapped_column(ForeignKey("outreach_tasks.id"), index=True)
    reason_code: Mapped[str] = mapped_column(String(100), index=True)
    status: Mapped[ManualFollowUpStatus] = mapped_column(
        Enum(ManualFollowUpStatus, name="manual_follow_up_status"),
        default=ManualFollowUpStatus.OPEN,
    )
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class SimulationRun(Identity, Tenant, Timestamps, Base):
    __tablename__ = "simulation_runs"
    __table_args__ = (
        UniqueConstraint("hospital_id", "id"),
        CheckConstraint("step_count >= 0", name="step_count"),
        CheckConstraint("configured_capacity > 0", name="configured_capacity"),
    )

    status: Mapped[SimulationRunStatus] = mapped_column(
        Enum(SimulationRunStatus, name="simulation_run_status"),
        default=SimulationRunStatus.READY,
        index=True,
    )
    scenario_name: Mapped[str] = mapped_column(String(100))
    simulated_now: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    step_count: Mapped[int] = mapped_column(Integer, default=0)
    configured_capacity: Mapped[int] = mapped_column(Integer)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_by_user_id: Mapped[UUID] = mapped_column(ForeignKey("users.id"), index=True)


class SimulationEvent(Identity, Tenant, Base):
    __tablename__ = "simulation_events"
    __table_args__ = (
        ForeignKeyConstraint(
            ["hospital_id", "simulation_run_id"],
            ["simulation_runs.hospital_id", "simulation_runs.id"],
        ),
        UniqueConstraint("simulation_run_id", "sequence_number"),
        CheckConstraint("sequence_number >= 1", name="sequence_number"),
        Index("ix_simulation_events_run_sequence", "simulation_run_id", "sequence_number"),
    )

    simulation_run_id: Mapped[UUID] = mapped_column(index=True)
    sequence_number: Mapped[int] = mapped_column(Integer)
    event_type: Mapped[str] = mapped_column(String(100), index=True)
    simulated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    outreach_task_id: Mapped[UUID | None] = mapped_column(ForeignKey("outreach_tasks.id"), index=True)
    campaign_id: Mapped[UUID | None] = mapped_column(ForeignKey("campaigns.id"), index=True)
    safe_payload: Mapped[dict] = mapped_column(JSONB, default=dict)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), index=True
    )
