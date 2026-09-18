from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class AIWorkflowSchema(BaseModel):
    model_config = ConfigDict(extra="forbid")


class AIWorkflowPatient(AIWorkflowSchema):
    id: UUID
    external_patient_id: str
    first_name: str
    last_name: str
    preferred_language: str


class AIWorkflowEncounter(AIWorkflowSchema):
    id: UUID
    care_setting: str
    admit_at: datetime
    discharge_at: datetime | None
    status: str


class AIWorkflowDischarge(AIWorkflowSchema):
    id: UUID
    discharge_at: datetime
    follow_up_deadline: datetime
    risk_level: str
    disposition: str
    status: str


class AIWorkflowVoiceIntake(AIWorkflowSchema):
    id: UUID
    outreach_task_id: UUID
    current_stage: str
    status: str
    captured_information: dict[str, Any]
    completed_at: datetime | None


class AIWorkflowAssessment(AIWorkflowSchema):
    id: UUID
    classification: str
    requires_human_review: bool
    assessment: dict[str, Any]
    created_at: datetime


class AIWorkflowConsensus(AIWorkflowSchema):
    id: UUID
    assessment_ids: list[UUID]
    final_classification: str
    agreement_status: str
    requires_human_review: bool
    disagreement_reason: str | None
    recommended_action: str
    created_at: datetime


class AIWorkflowEscalation(AIWorkflowSchema):
    id: UUID
    status: str
    priority: str
    assigned_reviewer_id: UUID | None
    resolution: str | None
    created_at: datetime
    updated_at: datetime
    resolved_at: datetime | None


class AIWorkflowNotification(AIWorkflowSchema):
    id: UUID
    notification_type: str
    title: str
    message: str
    severity: str
    status: str
    recipient_user_id: UUID | None
    created_at: datetime
    read_at: datetime | None
    acknowledged_at: datetime | None


class AIWorkflowEHROperation(AIWorkflowSchema):
    id: UUID
    operation_type: str
    status: str
    completed_at: datetime | None
    created_at: datetime


class PatientAIWorkflowResponse(AIWorkflowSchema):
    patient: AIWorkflowPatient
    latest_encounter: AIWorkflowEncounter | None
    latest_discharge: AIWorkflowDischarge | None
    voice_intake: AIWorkflowVoiceIntake | None
    triage_assessment: AIWorkflowAssessment | None
    independent_assessments: list[AIWorkflowAssessment]
    consensus: AIWorkflowConsensus | None
    escalation: AIWorkflowEscalation | None
    notification: AIWorkflowNotification | None
    mock_ehr_operation: AIWorkflowEHROperation | None
