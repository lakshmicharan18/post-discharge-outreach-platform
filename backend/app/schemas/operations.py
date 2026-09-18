from datetime import datetime
from uuid import UUID

from pydantic import BaseModel


class QueueOperationsSummary(BaseModel):
    effective_capacity: int
    active_reserved_count: int
    available_capacity: int
    pending_count: int
    approaching_deadline_count: int
    deadline_missed_count: int


class WorkflowOperationsSummary(BaseModel):
    pending: int
    processing: int
    retry_scheduled: int
    succeeded: int
    failed: int


class WorkflowEventOperationsItem(BaseModel):
    id: UUID
    event_type: str
    status: str
    attempt_count: int
    max_attempts: int
    next_attempt_at: datetime
    processed_at: datetime | None
    last_error_type: str | None
    created_at: datetime


class EscalationOperationsSummary(BaseModel):
    open: int
    in_review: int
    resolved: int
    urgent_open: int


class EscalationOperationsItem(BaseModel):
    id: UUID
    status: str
    priority: str
    assigned_reviewer_id: UUID | None
    created_at: datetime
    resolved_at: datetime | None


class NotificationOperationsSummary(BaseModel):
    unread: int
    urgent_unread: int


class NotificationOperationsItem(BaseModel):
    id: UUID
    notification_type: str
    title: str
    severity: str
    status: str
    related_escalation_id: UUID | None
    created_at: datetime


class AIExecutionOperationsSummary(BaseModel):
    total: int
    successful: int
    failed: int
    average_latency_ms: float | None


class AIExecutionOperationsItem(BaseModel):
    id: UUID
    purpose: str
    provider: str
    model: str
    prompt_version: str
    latency_ms: int
    success: bool
    input_tokens: int | None
    output_tokens: int | None
    error_type: str | None
    created_at: datetime


class OperationsSummaryResponse(BaseModel):
    queue: QueueOperationsSummary
    workflows: WorkflowOperationsSummary
    recent_workflows: list[WorkflowEventOperationsItem]
    escalations: EscalationOperationsSummary
    recent_escalations: list[EscalationOperationsItem]
    notifications: NotificationOperationsSummary
    recent_notifications: list[NotificationOperationsItem]
    ai_executions: AIExecutionOperationsSummary
    recent_ai_executions: list[AIExecutionOperationsItem]
