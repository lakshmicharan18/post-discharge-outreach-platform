from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict

from app.models.campaigns import ManualFollowUpStatus, OutreachOutcome, OutreachTaskState


class OutreachTaskResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    hospital_id: UUID
    campaign_id: UUID
    patient_id: UUID
    discharge_id: UUID
    state: OutreachTaskState
    priority_score: int
    priority_components: dict[str, int]
    attempt_count: int
    max_attempts: int
    eligible_at: datetime
    next_eligible_at: datetime
    clinical_deadline: datetime
    callback_at: datetime | None
    scheduled_at: datetime | None
    started_at: datetime | None
    completed_at: datetime | None
    last_outcome: str | None
    last_error_code: str | None
    manual_follow_up_required: bool
    reserved_at: datetime | None
    reservation_token: UUID | None
    reservation_expires_at: datetime | None
    created_at: datetime
    updated_at: datetime


class OutreachWorkCreationSummary(BaseModel):
    campaign_id: UUID
    evaluated: int
    eligible: int
    created: int
    already_existing: int
    ineligible: int


class QueueStatusResponse(BaseModel):
    effective_capacity: int
    active_reserved_count: int
    available_capacity: int
    pending_count: int
    oldest_pending_at: datetime | None
    approaching_deadline_count: int
    deadline_missed_count: int


class StartCallRequest(BaseModel):
    provider_call_id: str | None = None


class OutcomeRequest(BaseModel):
    outcome: OutreachOutcome
    idempotency_key: str
    callback_at: datetime | None = None
    outcome_reason: str | None = None
    technical_error_code: str | None = None
    partial_context: dict | None = None


class OutreachAttemptResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    outreach_task_id: UUID
    attempt_number: int
    started_at: datetime
    ended_at: datetime | None
    duration_seconds: int | None
    outcome: OutreachOutcome | None
    outcome_reason: str | None
    callback_requested_at: datetime | None
    technical_error_code: str | None
    partial_context: dict | None


class ManualFollowUpResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    outreach_task_id: UUID
    patient_id: UUID
    campaign_id: UUID
    reason_code: str
    status: ManualFollowUpStatus
    created_at: datetime
    resolved_at: datetime | None
