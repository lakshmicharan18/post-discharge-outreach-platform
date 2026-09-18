from datetime import datetime

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.context import RequestContext
from app.models.ai import AIExecution
from app.models.notifications import Notification, NotificationSeverity, NotificationStatus
from app.models.triage import EscalationCase
from app.models.workflow import WorkflowEvent, WorkflowEventStatus
from app.schemas.operations import (
    AIExecutionOperationsItem,
    AIExecutionOperationsSummary,
    EscalationOperationsItem,
    EscalationOperationsSummary,
    NotificationOperationsItem,
    NotificationOperationsSummary,
    OperationsSummaryResponse,
    QueueOperationsSummary,
    WorkflowEventOperationsItem,
    WorkflowOperationsSummary,
)
from app.services.scheduler import QueueSchedulerService


class OperationsService:
    def __init__(self, session: AsyncSession, context: RequestContext) -> None:
        self.session = session
        self.context = context
        self.hospital_id = context.require_clinical_tenant()

    async def summary(self, now: datetime) -> OperationsSummaryResponse:
        queue = await QueueSchedulerService(self.session, self.context).status(now)
        workflows, recent_workflows = await self._workflows()
        escalations, recent_escalations = await self._escalations()
        notifications, recent_notifications = await self._notifications()
        ai_executions, recent_ai_executions = await self._ai_executions()
        return OperationsSummaryResponse(
            queue=QueueOperationsSummary(
                effective_capacity=queue.effective_capacity,
                active_reserved_count=queue.active_reserved_count,
                available_capacity=queue.available_capacity,
                pending_count=queue.pending_count,
                approaching_deadline_count=queue.approaching_deadline_count,
                deadline_missed_count=queue.deadline_missed_count,
            ),
            workflows=workflows,
            recent_workflows=recent_workflows,
            escalations=escalations,
            recent_escalations=recent_escalations,
            notifications=notifications,
            recent_notifications=recent_notifications,
            ai_executions=ai_executions,
            recent_ai_executions=recent_ai_executions,
        )

    async def _workflows(
        self,
    ) -> tuple[WorkflowOperationsSummary, list[WorkflowEventOperationsItem]]:
        counts = await self._counts_by_status(WorkflowEvent, WorkflowEvent.status)
        records = list(
            await self.session.scalars(
                select(WorkflowEvent)
                .where(WorkflowEvent.hospital_id == self.hospital_id)
                .order_by(WorkflowEvent.created_at.desc(), WorkflowEvent.id.desc())
                .limit(10)
            )
        )
        return (
            WorkflowOperationsSummary(
                pending=counts.get(WorkflowEventStatus.PENDING.value, 0),
                processing=counts.get(WorkflowEventStatus.PROCESSING.value, 0),
                retry_scheduled=counts.get(WorkflowEventStatus.RETRY_SCHEDULED.value, 0),
                succeeded=counts.get(WorkflowEventStatus.SUCCEEDED.value, 0),
                failed=counts.get(WorkflowEventStatus.FAILED.value, 0),
            ),
            [
                WorkflowEventOperationsItem(
                    id=record.id,
                    event_type=record.event_type,
                    status=record.status.value,
                    attempt_count=record.attempt_count,
                    max_attempts=record.max_attempts,
                    next_attempt_at=record.next_attempt_at,
                    processed_at=record.processed_at,
                    last_error_type=record.last_error_type,
                    created_at=record.created_at,
                )
                for record in records
            ],
        )

    async def _escalations(
        self,
    ) -> tuple[EscalationOperationsSummary, list[EscalationOperationsItem]]:
        result = await self.session.execute(
            select(
                func.count().filter(EscalationCase.status == "OPEN"),
                func.count().filter(EscalationCase.status == "IN_REVIEW"),
                func.count().filter(EscalationCase.status == "RESOLVED"),
                func.count().filter(
                    EscalationCase.status != "RESOLVED", EscalationCase.priority == "URGENT"
                ),
            ).where(EscalationCase.hospital_id == self.hospital_id)
        )
        open_count, in_review, resolved, urgent_open = result.one()
        records = list(
            await self.session.scalars(
                select(EscalationCase)
                .where(EscalationCase.hospital_id == self.hospital_id)
                .order_by(EscalationCase.created_at.desc(), EscalationCase.id.desc())
                .limit(10)
            )
        )
        return (
            EscalationOperationsSummary(
                open=int(open_count),
                in_review=int(in_review),
                resolved=int(resolved),
                urgent_open=int(urgent_open),
            ),
            [
                EscalationOperationsItem(
                    id=record.id,
                    status=record.status,
                    priority=record.priority,
                    assigned_reviewer_id=record.assigned_reviewer_id,
                    created_at=record.created_at,
                    resolved_at=record.resolved_at,
                )
                for record in records
            ],
        )

    async def _notifications(
        self,
    ) -> tuple[NotificationOperationsSummary, list[NotificationOperationsItem]]:
        result = await self.session.execute(
            select(
                func.count().filter(Notification.status == NotificationStatus.UNREAD),
                func.count().filter(
                    Notification.status == NotificationStatus.UNREAD,
                    Notification.severity == NotificationSeverity.URGENT,
                ),
            ).where(Notification.hospital_id == self.hospital_id)
        )
        unread, urgent_unread = result.one()
        records = list(
            await self.session.scalars(
                select(Notification)
                .where(Notification.hospital_id == self.hospital_id)
                .order_by(Notification.created_at.desc(), Notification.id.desc())
                .limit(10)
            )
        )
        return (
            NotificationOperationsSummary(unread=int(unread), urgent_unread=int(urgent_unread)),
            [
                NotificationOperationsItem(
                    id=record.id,
                    notification_type=record.notification_type,
                    title=record.title,
                    severity=record.severity.value,
                    status=record.status.value,
                    related_escalation_id=record.related_escalation_id,
                    created_at=record.created_at,
                )
                for record in records
            ],
        )

    async def _ai_executions(
        self,
    ) -> tuple[AIExecutionOperationsSummary, list[AIExecutionOperationsItem]]:
        result = await self.session.execute(
            select(
                func.count(),
                func.count().filter(AIExecution.success.is_(True)),
                func.count().filter(AIExecution.success.is_(False)),
                func.avg(AIExecution.latency_ms),
            ).where(AIExecution.hospital_id == self.hospital_id)
        )
        total, successful, failed, average_latency = result.one()
        records = list(
            await self.session.scalars(
                select(AIExecution)
                .where(AIExecution.hospital_id == self.hospital_id)
                .order_by(AIExecution.created_at.desc(), AIExecution.id.desc())
                .limit(10)
            )
        )
        return (
            AIExecutionOperationsSummary(
                total=int(total),
                successful=int(successful),
                failed=int(failed),
                average_latency_ms=float(average_latency) if average_latency is not None else None,
            ),
            [
                AIExecutionOperationsItem(
                    id=record.id,
                    purpose=record.purpose,
                    provider=record.provider,
                    model=record.model,
                    prompt_version=record.prompt_version,
                    latency_ms=record.latency_ms,
                    success=record.success,
                    input_tokens=record.input_tokens,
                    output_tokens=record.output_tokens,
                    error_type=record.error_type,
                    created_at=record.created_at,
                )
                for record in records
            ],
        )

    async def _counts_by_status(self, model, status_column) -> dict[str, int]:
        rows = await self.session.execute(
            select(status_column, func.count())
            .where(model.hospital_id == self.hospital_id)
            .group_by(status_column)
        )
        return {
            status.value if hasattr(status, "value") else str(status): int(count)
            for status, count in rows.all()
        }
