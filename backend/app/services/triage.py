from datetime import datetime
from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.ai.models import StructuredModel
from app.ai.tools import ControlledAITools
from app.core.context import RequestContext
from app.core.errors import APIError
from app.models.entities import Role
from app.models.triage import ClinicalTriageRecord
from app.schemas.ai import ClinicalTriageAssessment, ToolRequest
from app.services.voice_intake import VoiceIntakeSessionService


class ClinicalTriageService:
    def __init__(
        self, session: AsyncSession, context: RequestContext, model: StructuredModel
    ) -> None:
        self.session, self.context, self.model = session, context, model
        self.hospital_id = context.require_clinical_tenant()

    async def assess(self, intake_session_id, now: datetime) -> ClinicalTriageRecord:
        self.context.require_roles(
            Role.HOSPITAL_ADMIN, Role.CLINICAL_REVIEWER, Role.CAMPAIGN_MANAGER
        )
        intake = await VoiceIntakeSessionService(self.session, self.context).get(intake_session_id)
        if intake.status != "COMPLETED":
            raise APIError(409, "intake_incomplete", "Voice intake session must be completed")
        tools = ControlledAITools(self.session, self.context)
        task = await tools.invoke(
            ToolRequest(
                name="get_current_outreach_task",
                request_id=uuid4(),
                arguments={"task_id": intake.outreach_task_id},
            )
        )
        patient = await tools.invoke(
            ToolRequest(
                name="get_patient_context",
                request_id=uuid4(),
                arguments={"patient_id": task.data["patient_id"]},
            )
        )
        discharge = await tools.invoke(
            ToolRequest(
                name="get_discharge_plan",
                request_id=uuid4(),
                arguments={"patient_id": task.data["patient_id"]},
            )
        )
        prompt = str(
            {
                "intake": intake.conversation_state,
                "patient": patient.data,
                "discharge": discharge.data,
            }
        )
        output = await self.model.generate(prompt, ClinicalTriageAssessment)
        record = ClinicalTriageRecord(
            hospital_id=self.hospital_id,
            intake_session_id=intake.id,
            outreach_task_id=intake.outreach_task_id,
            classification=output.classification.value,
            requires_human_review=output.requires_human_review,
            assessment=output.model_dump(mode="json"),
            execution_metadata=output.execution_metadata,
        )
        self.session.add(record)
        await self.session.commit()
        await self.session.refresh(record)
        return record

    async def get(self, assessment_id) -> ClinicalTriageRecord:
        record = await self.session.scalar(
            select(ClinicalTriageRecord).where(
                ClinicalTriageRecord.id == assessment_id,
                ClinicalTriageRecord.hospital_id == self.hospital_id,
            )
        )
        if record is None:
            raise APIError(404, "not_found", "Triage assessment not found")
        return record
