from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.context import RequestContext
from app.core.errors import APIError
from app.models.campaigns import OutreachTask, OutreachTaskState


class OutreachTaskRepository:
    def __init__(self, session: AsyncSession, context: RequestContext) -> None:
        self.session = session
        self.hospital_id = context.require_clinical_tenant()

    async def get(self, task_id: UUID) -> OutreachTask:
        task = await self.session.scalar(
            select(OutreachTask).where(
                OutreachTask.id == task_id, OutreachTask.hospital_id == self.hospital_id
            )
        )
        if task is None:
            raise APIError(404, "not_found", "Outreach task not found")
        return task

    async def list(
        self,
        campaign_id: UUID,
        state: OutreachTaskState | None,
        patient_id: UUID | None,
        limit: int,
        offset: int,
    ) -> list[OutreachTask]:
        statement = select(OutreachTask).where(
            OutreachTask.hospital_id == self.hospital_id, OutreachTask.campaign_id == campaign_id
        )
        if state is not None:
            statement = statement.where(OutreachTask.state == state)
        if patient_id is not None:
            statement = statement.where(OutreachTask.patient_id == patient_id)
        return list(
            await self.session.scalars(
                statement.order_by(OutreachTask.priority_score.desc(), OutreachTask.id)
                .limit(limit)
                .offset(offset)
            )
        )
