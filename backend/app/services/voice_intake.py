from datetime import datetime
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.context import RequestContext
from app.core.errors import APIError
from app.models.campaigns import VoiceIntakeSession
from app.models.entities import Role
from app.schemas.ai import VoiceIntakeConversation
from app.services.outreach import OutreachWorkService


class VoiceIntakeSessionService:
    def __init__(self, session: AsyncSession, context: RequestContext) -> None:
        self.session, self.context = session, context
        self.hospital_id = context.require_clinical_tenant()

    async def create(self, task_id: UUID) -> VoiceIntakeSession:
        self.context.require_roles(Role.HOSPITAL_ADMIN, Role.CAMPAIGN_MANAGER)
        await OutreachWorkService(self.session, self.context).get(task_id)
        record = VoiceIntakeSession(
            hospital_id=self.hospital_id,
            outreach_task_id=task_id,
            current_stage="START",
            conversation_state={},
            status="ACTIVE",
        )
        self.session.add(record)
        await self.session.commit()
        await self.session.refresh(record)
        return record

    async def get(self, session_id: UUID) -> VoiceIntakeSession:
        record = await self.session.scalar(
            select(VoiceIntakeSession).where(
                VoiceIntakeSession.id == session_id,
                VoiceIntakeSession.hospital_id == self.hospital_id,
            )
        )
        if record is None:
            raise APIError(404, "not_found", "Voice intake session not found")
        return record

    async def save(
        self, record: VoiceIntakeSession, state: dict, stage: str, completed: bool, now: datetime
    ) -> VoiceIntakeSession:
        self.context.require_roles(Role.HOSPITAL_ADMIN, Role.CAMPAIGN_MANAGER)
        record.conversation_state, record.current_stage = state, stage
        if completed and record.status != "COMPLETED":
            record.status, record.completed_at = "COMPLETED", now
        await self.session.commit()
        return record

    async def conversation(self, record: VoiceIntakeSession) -> VoiceIntakeConversation:
        return VoiceIntakeConversation.model_validate(
            {
                "session_id": record.id,
                "outreach_task_id": record.outreach_task_id,
                **record.conversation_state,
            }
        )
