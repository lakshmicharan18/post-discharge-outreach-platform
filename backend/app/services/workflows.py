from datetime import datetime, timedelta
from typing import Awaitable, Callable
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.context import RequestContext
from app.models.workflow import WorkflowEvent, WorkflowEventStatus

Handler = Callable[[WorkflowEvent], Awaitable[None]]
SAFE_ERROR_TYPES = frozenset(
    {"handler_failure", "provider_failure", "transient_failure", "unknown_failure"}
)


class WorkflowService:
    def __init__(self, session: AsyncSession, handlers: dict[str, Handler] | None = None) -> None:
        self.session, self.handlers = session, handlers or {}

    async def create(
        self,
        context: RequestContext,
        event_type: str,
        payload: dict,
        idempotency_key: str,
        max_attempts: int = 3,
    ) -> WorkflowEvent:
        hospital_id = context.require_clinical_tenant()
        existing = await self.session.scalar(
            select(WorkflowEvent).where(
                WorkflowEvent.hospital_id == hospital_id,
                WorkflowEvent.idempotency_key == idempotency_key,
            )
        )
        if existing is not None:
            return existing
        event = WorkflowEvent(
            hospital_id=hospital_id,
            event_type=event_type,
            payload=payload,
            status=WorkflowEventStatus.PENDING,
            attempt_count=0,
            max_attempts=max_attempts,
            next_attempt_at=datetime.now().astimezone(),
            idempotency_key=idempotency_key,
        )
        self.session.add(event)
        await self.session.commit()
        await self.session.refresh(event)
        return event

    async def claim_for_tenant(
        self, context: RequestContext, now: datetime
    ) -> WorkflowEvent | None:
        hospital_id = context.require_clinical_tenant()
        event = await self.session.scalar(
            select(WorkflowEvent)
            .where(
                WorkflowEvent.hospital_id == hospital_id,
                WorkflowEvent.status.in_(
                    [WorkflowEventStatus.PENDING, WorkflowEventStatus.RETRY_SCHEDULED]
                ),
                WorkflowEvent.next_attempt_at <= now,
            )
            .order_by(WorkflowEvent.next_attempt_at, WorkflowEvent.id)
            .with_for_update(skip_locked=True)
        )
        if event is None:
            return None
        event.status = WorkflowEventStatus.PROCESSING
        event.started_at = now
        event.attempt_count += 1
        await self.session.commit()
        await self.session.refresh(event)
        return event

    async def complete_success(
        self, context: RequestContext, event_id: UUID, now: datetime
    ) -> WorkflowEvent:
        event = await self._get_processing_event(context, event_id)
        event.status = WorkflowEventStatus.SUCCEEDED
        event.processed_at = now
        event.last_error_type = None
        await self.session.commit()
        await self.session.refresh(event)
        return event

    async def complete_failure(
        self, context: RequestContext, event_id: UUID, error_type: str, now: datetime
    ) -> WorkflowEvent:
        event = await self._get_processing_event(context, event_id)
        event.last_error_type = error_type if error_type in SAFE_ERROR_TYPES else "unknown_failure"
        if event.attempt_count >= event.max_attempts:
            event.status = WorkflowEventStatus.FAILED
            event.processed_at = now
        else:
            event.status = WorkflowEventStatus.RETRY_SCHEDULED
            event.next_attempt_at = now + timedelta(minutes=event.attempt_count)
        await self.session.commit()
        await self.session.refresh(event)
        return event

    async def _get_processing_event(self, context: RequestContext, event_id: UUID) -> WorkflowEvent:
        hospital_id = context.require_clinical_tenant()
        event = await self.session.scalar(
            select(WorkflowEvent)
            .where(
                WorkflowEvent.id == event_id,
                WorkflowEvent.hospital_id == hospital_id,
                WorkflowEvent.status == WorkflowEventStatus.PROCESSING,
            )
            .with_for_update()
        )
        if event is None:
            raise ValueError("Workflow event is not processing for this tenant")
        return event

    async def claim(self, now: datetime) -> WorkflowEvent | None:
        event = await self.session.scalar(
            select(WorkflowEvent)
            .where(
                WorkflowEvent.status.in_(
                    [WorkflowEventStatus.PENDING, WorkflowEventStatus.RETRY_SCHEDULED]
                ),
                WorkflowEvent.next_attempt_at <= now,
            )
            .order_by(WorkflowEvent.next_attempt_at)
            .with_for_update(skip_locked=True)
        )
        if event:
            event.status, event.started_at, event.attempt_count = (
                WorkflowEventStatus.PROCESSING,
                now,
                event.attempt_count + 1,
            )
            await self.session.commit()
        return event

    async def process_one(self, now: datetime) -> WorkflowEvent | None:
        event = await self.claim(now)
        if event is None:
            return None
        try:
            await self.handlers.get(event.event_type, _noop)(event)
            event.status, event.processed_at = WorkflowEventStatus.SUCCEEDED, now
        except Exception:
            event.last_error_type = "handler_failure"
            event.status = (
                WorkflowEventStatus.FAILED
                if event.attempt_count >= event.max_attempts
                else WorkflowEventStatus.RETRY_SCHEDULED
            )
            event.next_attempt_at = now + timedelta(minutes=event.attempt_count)
        await self.session.commit()
        return event


async def _noop(event: WorkflowEvent) -> None:
    pass
