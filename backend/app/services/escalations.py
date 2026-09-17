from datetime import datetime
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.context import RequestContext
from app.core.errors import APIError
from app.models.campaigns import VoiceIntakeSession
from app.models.entities import Role
from app.models.triage import EscalationCase, EscalationDecisionRecord
from app.services.audit import add_audit_event
from app.services.mock_ehr import LocalMockEHRClient


class EscalationCaseService:
    def __init__(self, session: AsyncSession, context: RequestContext) -> None:
        self.session = session
        self.context = context
        self.hospital_id = context.require_clinical_tenant()

    async def create_for_decision(self, decision_id: UUID) -> EscalationCase | None:
        decision = await self._decision(decision_id)
        if not decision.requires_human_review:
            return None
        existing = await self.session.scalar(
            select(EscalationCase).where(EscalationCase.escalation_decision_id == decision.id)
        )
        if existing is not None:
            return existing
        case = EscalationCase(
            hospital_id=self.hospital_id,
            escalation_decision_id=decision.id,
            intake_session_id=decision.intake_session_id,
            priority=decision.final_classification,
        )
        self.session.add(case)
        await self.session.flush()
        await add_audit_event(
            self.session,
            self.context,
            self.hospital_id,
            "ESCALATION_CASE_CREATED",
            "EscalationCase",
            case.id,
        )
        await self.session.commit()
        await self.session.refresh(case)
        task_id = await self.session.scalar(
            select(VoiceIntakeSession.outreach_task_id).where(
                VoiceIntakeSession.id == case.intake_session_id
            )
        )
        await LocalMockEHRClient(self.session, self.context).record_escalation_reference(
            task_id,
            case.id,
            {"case_id": str(case.id), "resolution": case.resolution},
        )
        return case

    async def list_open(self) -> list[EscalationCase]:
        self.context.require_roles(
            Role.HOSPITAL_ADMIN, Role.CAMPAIGN_MANAGER, Role.CLINICAL_REVIEWER
        )
        result = await self.session.scalars(
            select(EscalationCase)
            .where(
                EscalationCase.hospital_id == self.hospital_id,
                EscalationCase.status != "RESOLVED",
            )
            .order_by(EscalationCase.created_at, EscalationCase.id)
        )
        return list(result)

    async def get(self, case_id: UUID) -> EscalationCase:
        self.context.require_roles(
            Role.HOSPITAL_ADMIN, Role.CAMPAIGN_MANAGER, Role.CLINICAL_REVIEWER
        )
        case = await self.session.scalar(
            select(EscalationCase).where(
                EscalationCase.id == case_id,
                EscalationCase.hospital_id == self.hospital_id,
            )
        )
        if case is None:
            raise APIError(404, "not_found", "Escalation case not found")
        return case

    async def start_review(self, case_id: UUID) -> EscalationCase:
        self.context.require_roles(Role.CLINICAL_REVIEWER, Role.HOSPITAL_ADMIN)
        case = await self.get(case_id)
        if case.status == "RESOLVED":
            raise APIError(409, "resolved", "Case is already resolved")
        case.status = "IN_REVIEW"
        case.assigned_reviewer_id = self.context.user_id
        await add_audit_event(
            self.session,
            self.context,
            self.hospital_id,
            "ESCALATION_REVIEW_STARTED",
            "EscalationCase",
            case.id,
        )
        await self.session.commit()
        await self.session.refresh(case)
        return case

    async def resolve(
        self,
        case_id: UUID,
        reviewer_notes: str,
        resolution: str,
        now: datetime,
    ) -> EscalationCase:
        self.context.require_roles(Role.CLINICAL_REVIEWER, Role.HOSPITAL_ADMIN)
        case = await self.get(case_id)
        if case.status == "RESOLVED":
            raise APIError(409, "resolved", "Case is already resolved")
        case.status = "RESOLVED"
        case.assigned_reviewer_id = self.context.user_id
        case.reviewer_notes = reviewer_notes
        case.resolution = resolution
        case.resolved_at = now
        await add_audit_event(
            self.session,
            self.context,
            self.hospital_id,
            "ESCALATION_RESOLVED",
            "EscalationCase",
            case.id,
        )
        await self.session.commit()
        await self.session.refresh(case)
        return case

    async def _decision(self, decision_id: UUID) -> EscalationDecisionRecord:
        decision = await self.session.scalar(
            select(EscalationDecisionRecord).where(
                EscalationDecisionRecord.id == decision_id,
                EscalationDecisionRecord.hospital_id == self.hospital_id,
            )
        )
        if decision is None:
            raise APIError(404, "not_found", "Escalation decision not found")
        return decision
