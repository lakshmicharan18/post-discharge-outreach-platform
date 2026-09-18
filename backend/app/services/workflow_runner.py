import asyncio
from collections.abc import Callable
from contextlib import AbstractAsyncContextManager
from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.context import CurrentUserContext
from app.models.entities import Role
from app.models.workflow import WorkflowEvent, WorkflowEventStatus
from app.services.notifications import SendNotificationHandler
from app.services.workflows import WorkflowService

SessionProvider = Callable[[], AbstractAsyncContextManager[AsyncSession]]
SYSTEM_WORKER_USER_ID = UUID(int=0)


class WorkflowEventRunner:
    def __init__(
        self, session_provider: SessionProvider, poll_interval_seconds: float = 2.0
    ) -> None:
        self.session_provider = session_provider
        self.poll_interval_seconds = poll_interval_seconds

    async def run_forever(self) -> None:
        while True:
            await self.run_once()
            await asyncio.sleep(self.poll_interval_seconds)

    async def run_once(self) -> bool:
        now = datetime.now(timezone.utc)
        async with self.session_provider() as session:
            hospital_id = await session.scalar(
                select(WorkflowEvent.hospital_id)
                .where(
                    WorkflowEvent.status.in_(
                        [WorkflowEventStatus.PENDING, WorkflowEventStatus.RETRY_SCHEDULED]
                    ),
                    WorkflowEvent.next_attempt_at <= now,
                )
                .order_by(WorkflowEvent.next_attempt_at, WorkflowEvent.id)
                .limit(1)
            )
            if hospital_id is None:
                return False
            context = CurrentUserContext(SYSTEM_WORKER_USER_ID, hospital_id, Role.HOSPITAL_ADMIN)
            workflows = WorkflowService(session)
            event = await workflows.claim_for_tenant(context, now)
            if event is None:
                return False
            if event.event_type != "SEND_NOTIFICATION":
                await workflows.complete_failure(context, event.id, "unknown_failure", now)
                return True
            try:
                await SendNotificationHandler(session, context).handle(event)
            except Exception:
                await workflows.complete_failure(context, event.id, "handler_failure", now)
            else:
                await workflows.complete_success(context, event.id, now)
            return True
