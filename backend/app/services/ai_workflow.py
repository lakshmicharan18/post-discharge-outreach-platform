from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.context import RequestContext
from app.core.errors import APIError
from app.models.campaigns import OutreachTask, VoiceIntakeSession
from app.models.ehr import EHROperationRecord
from app.models.entities import Discharge, Encounter, Patient
from app.models.notifications import Notification
from app.models.triage import ClinicalTriageRecord, EscalationCase, EscalationDecisionRecord
from app.schemas.ai_workflow import (
    AIWorkflowAssessment,
    AIWorkflowConsensus,
    AIWorkflowDischarge,
    AIWorkflowEHROperation,
    AIWorkflowEncounter,
    AIWorkflowEscalation,
    AIWorkflowNotification,
    AIWorkflowPatient,
    AIWorkflowVoiceIntake,
    PatientAIWorkflowResponse,
)


class PatientAIWorkflowService:
    def __init__(self, session: AsyncSession, context: RequestContext) -> None:
        self.session = session
        self.hospital_id = context.require_clinical_tenant()

    async def get(self, patient_id: UUID) -> PatientAIWorkflowResponse:
        patient = await self.session.scalar(
            select(Patient).where(Patient.id == patient_id, Patient.hospital_id == self.hospital_id)
        )
        if patient is None:
            raise APIError(404, "not_found", "Patient not found")
        encounter = await self.session.scalar(
            select(Encounter)
            .where(Encounter.patient_id == patient.id, Encounter.hospital_id == self.hospital_id)
            .order_by(Encounter.admit_at.desc(), Encounter.id.desc())
        )
        discharge = await self.session.scalar(
            select(Discharge)
            .where(Discharge.patient_id == patient.id, Discharge.hospital_id == self.hospital_id)
            .order_by(Discharge.discharge_at.desc(), Discharge.id.desc())
        )
        intake = await self.session.scalar(
            select(VoiceIntakeSession)
            .join(OutreachTask, OutreachTask.id == VoiceIntakeSession.outreach_task_id)
            .where(
                VoiceIntakeSession.hospital_id == self.hospital_id,
                OutreachTask.hospital_id == self.hospital_id,
                OutreachTask.patient_id == patient.id,
            )
            .order_by(VoiceIntakeSession.created_at.desc(), VoiceIntakeSession.id.desc())
        )
        triage_records: list[ClinicalTriageRecord] = []
        decision: EscalationDecisionRecord | None = None
        if intake is not None:
            triage_records = list(
                await self.session.scalars(
                    select(ClinicalTriageRecord)
                    .where(
                        ClinicalTriageRecord.hospital_id == self.hospital_id,
                        ClinicalTriageRecord.intake_session_id == intake.id,
                    )
                    .order_by(
                        ClinicalTriageRecord.created_at.desc(), ClinicalTriageRecord.id.desc()
                    )
                )
            )
            decision = await self.session.scalar(
                select(EscalationDecisionRecord)
                .where(
                    EscalationDecisionRecord.hospital_id == self.hospital_id,
                    EscalationDecisionRecord.intake_session_id == intake.id,
                )
                .order_by(
                    EscalationDecisionRecord.created_at.desc(), EscalationDecisionRecord.id.desc()
                )
            )
        assessment_ids = self._assessment_ids(decision)
        assessments = self._independent_assessments(triage_records, assessment_ids)
        escalation = await self._escalation(decision)
        notification = await self._notification(escalation)
        ehr_operation = await self._ehr_operation(intake)
        return PatientAIWorkflowResponse(
            patient=AIWorkflowPatient(
                id=patient.id,
                external_patient_id=patient.external_patient_id,
                first_name=patient.first_name,
                last_name=patient.last_name,
                preferred_language=patient.preferred_language,
            ),
            latest_encounter=(
                AIWorkflowEncounter(
                    id=encounter.id,
                    care_setting=encounter.care_setting,
                    admit_at=encounter.admit_at,
                    discharge_at=encounter.discharge_at,
                    status=encounter.status,
                )
                if encounter
                else None
            ),
            latest_discharge=(
                AIWorkflowDischarge(
                    id=discharge.id,
                    discharge_at=discharge.discharge_at,
                    follow_up_deadline=discharge.follow_up_deadline,
                    risk_level=discharge.risk_level,
                    disposition=discharge.disposition,
                    status=discharge.status,
                )
                if discharge
                else None
            ),
            voice_intake=self._voice_intake(intake),
            triage_assessment=self._assessment(triage_records[0]) if triage_records else None,
            independent_assessments=assessments,
            consensus=self._consensus(decision, assessment_ids),
            escalation=self._escalation_response(escalation),
            notification=self._notification_response(notification),
            mock_ehr_operation=self._ehr_response(ehr_operation),
        )

    async def _escalation(self, decision: EscalationDecisionRecord | None) -> EscalationCase | None:
        if decision is None:
            return None
        return await self.session.scalar(
            select(EscalationCase).where(
                EscalationCase.hospital_id == self.hospital_id,
                EscalationCase.escalation_decision_id == decision.id,
            )
        )

    async def _notification(self, escalation: EscalationCase | None) -> Notification | None:
        if escalation is None:
            return None
        return await self.session.scalar(
            select(Notification)
            .where(
                Notification.hospital_id == self.hospital_id,
                Notification.related_escalation_id == escalation.id,
            )
            .order_by(Notification.created_at.desc(), Notification.id.desc())
        )

    async def _ehr_operation(self, intake: VoiceIntakeSession | None) -> EHROperationRecord | None:
        if intake is None:
            return None
        return await self.session.scalar(
            select(EHROperationRecord)
            .where(
                EHROperationRecord.hospital_id == self.hospital_id,
                EHROperationRecord.outreach_task_id == intake.outreach_task_id,
            )
            .order_by(EHROperationRecord.created_at.desc(), EHROperationRecord.id.desc())
        )

    @staticmethod
    def _assessment_ids(decision: EscalationDecisionRecord | None) -> list[UUID]:
        if decision is None:
            return []
        ids: list[UUID] = []
        for value in decision.assessment_ids:
            try:
                ids.append(UUID(str(value)))
            except (TypeError, ValueError):
                continue
        return ids

    def _independent_assessments(
        self, records: list[ClinicalTriageRecord], ids: list[UUID]
    ) -> list[AIWorkflowAssessment]:
        records_by_id = {record.id: record for record in records}
        return [
            self._assessment(records_by_id[identifier])
            for identifier in ids
            if identifier in records_by_id
        ]

    @staticmethod
    def _voice_intake(record: VoiceIntakeSession | None) -> AIWorkflowVoiceIntake | None:
        if record is None:
            return None
        safe_keys = {
            "identity_status",
            "consent_status",
            "preferred_language",
            "symptoms_reported",
            "medication_concerns",
            "follow_up_concerns",
            "patient_questions",
            "callback_requested",
            "red_flag_indicators",
            "uncertainty",
            "grounded_references",
            "completed",
        }
        captured = {
            key: value for key, value in record.conversation_state.items() if key in safe_keys
        }
        return AIWorkflowVoiceIntake(
            id=record.id,
            outreach_task_id=record.outreach_task_id,
            current_stage=record.current_stage,
            status=record.status,
            captured_information=captured,
            completed_at=record.completed_at,
        )

    @staticmethod
    def _assessment(record: ClinicalTriageRecord) -> AIWorkflowAssessment:
        safe_keys = {
            "assessment_id",
            "classification",
            "patient_reported_findings",
            "clinical_context_facts",
            "protocol_references",
            "uncertainty",
            "missing_information",
            "recommended_next_action",
            "confidence",
            "requires_human_review",
        }
        assessment = {key: value for key, value in record.assessment.items() if key in safe_keys}
        return AIWorkflowAssessment(
            id=record.id,
            classification=record.classification,
            requires_human_review=record.requires_human_review,
            assessment=assessment,
            created_at=record.created_at,
        )

    @staticmethod
    def _consensus(
        record: EscalationDecisionRecord | None, assessment_ids: list[UUID]
    ) -> AIWorkflowConsensus | None:
        if record is None:
            return None
        return AIWorkflowConsensus(
            id=record.id,
            assessment_ids=assessment_ids,
            final_classification=record.final_classification,
            agreement_status=record.agreement_status,
            requires_human_review=record.requires_human_review,
            disagreement_reason=record.disagreement_reason,
            recommended_action=record.recommended_action,
            created_at=record.created_at,
        )

    @staticmethod
    def _escalation_response(record: EscalationCase | None) -> AIWorkflowEscalation | None:
        if record is None:
            return None
        return AIWorkflowEscalation(
            id=record.id,
            status=record.status,
            priority=record.priority,
            assigned_reviewer_id=record.assigned_reviewer_id,
            resolution=record.resolution,
            created_at=record.created_at,
            updated_at=record.updated_at,
            resolved_at=record.resolved_at,
        )

    @staticmethod
    def _notification_response(record: Notification | None) -> AIWorkflowNotification | None:
        if record is None:
            return None
        return AIWorkflowNotification(
            id=record.id,
            notification_type=record.notification_type,
            title=record.title,
            message=record.message,
            severity=record.severity.value,
            status=record.status.value,
            recipient_user_id=record.recipient_user_id,
            created_at=record.created_at,
            read_at=record.read_at,
            acknowledged_at=record.acknowledged_at,
        )

    @staticmethod
    def _ehr_response(record: EHROperationRecord | None) -> AIWorkflowEHROperation | None:
        if record is None:
            return None
        return AIWorkflowEHROperation(
            id=record.id,
            operation_type=record.operation_type,
            status=record.status,
            completed_at=record.completed_at,
            created_at=record.created_at,
        )
