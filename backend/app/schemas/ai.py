import enum
from datetime import datetime
from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class AIContract(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


class VoiceIntakeOutput(AIContract):
    call_disposition: Literal["COMPLETED", "DECLINED", "UNREACHED", "UNKNOWN"]
    identity_status: Literal["VERIFIED", "UNVERIFIED", "NOT_ASKED"]
    consent_status: Literal["CONFIRMED", "DECLINED", "NOT_ASKED"]
    symptoms_reported: list[str] = Field(default_factory=list, max_length=20)
    medication_concerns: list[str] = Field(default_factory=list, max_length=20)
    follow_up_concerns: list[str] = Field(default_factory=list, max_length=20)
    patient_questions: list[str] = Field(default_factory=list, max_length=20)
    callback_requested: bool = False
    red_flag_indicators: list[str] = Field(default_factory=list, max_length=20)
    safe_summary: str | None = Field(default=None, max_length=2000)
    uncertainty_or_missing_information: list[str] = Field(default_factory=list, max_length=20)


class ToolRequest(AIContract):
    name: str = Field(pattern=r"^[a-z][a-z0-9_]{1,80}$")
    request_id: UUID
    arguments: dict[str, Any] = Field(default_factory=dict)


class ToolResult(AIContract):
    name: str
    request_id: UUID
    success: bool
    data: dict[str, Any] | None = None
    error: "SafeToolError | None" = None


class SafeToolError(AIContract):
    code: Literal["not_found", "forbidden", "invalid_input", "tool_not_allowed", "conflict"]
    message: str


class GroundedReference(AIContract):
    source_type: Literal["DISCHARGE_PLAN", "CARE_PLAN", "MEDICATION", "ENCOUNTER"]
    source_id: UUID
    label: str = Field(max_length=250)


class AIExecutionMetadata(AIContract):
    execution_id: UUID
    provider: str
    model: str
    occurred_at: datetime


class PatientToolInput(AIContract):
    patient_id: UUID


class TaskToolInput(AIContract):
    task_id: UUID


class CallbackToolInput(TaskToolInput):
    callback_at: datetime
    idempotency_key: str = Field(min_length=1, max_length=150)


class StructuredCallNoteInput(TaskToolInput):
    note: VoiceIntakeOutput


class KnowledgeSearchToolInput(AIContract):
    query: str = Field(min_length=1, max_length=1000)
    top_k: int = Field(default=5, ge=1, le=10)


class ConversationStage(str, enum.Enum):
    START = "START"
    IDENTITY_CONFIRMATION = "IDENTITY_CONFIRMATION"
    CONSENT = "CONSENT"
    GENERAL_RECOVERY = "GENERAL_RECOVERY"
    SYMPTOMS = "SYMPTOMS"
    MEDICATION_CONCERNS = "MEDICATION_CONCERNS"
    FOLLOW_UP = "FOLLOW_UP"
    PATIENT_QUESTIONS = "PATIENT_QUESTIONS"
    CALLBACK_CONFIRMATION = "CALLBACK_CONFIRMATION"
    COMPLETION = "COMPLETION"
    TERMINATED = "TERMINATED"


class IntakeToolCall(AIContract):
    name: str
    arguments: dict[str, Any] = Field(default_factory=dict)


class VoiceIntakeTurnOutput(AIContract):
    assistant_message: str = Field(min_length=1, max_length=2000)
    next_stage: ConversationStage
    extracted_updates: dict[str, Any] = Field(default_factory=dict)
    requested_tools: list[IntakeToolCall] = Field(default_factory=list, max_length=5)
    uncertainty: list[str] = Field(default_factory=list, max_length=20)
    conversation_complete: bool = False


class VoiceIntakeConversation(AIContract):
    session_id: UUID
    outreach_task_id: UUID
    stage: ConversationStage = ConversationStage.START
    identity_status: Literal["VERIFIED", "UNVERIFIED", "NOT_ASKED"] = "NOT_ASKED"
    consent_status: Literal["CONFIRMED", "DECLINED", "NOT_ASKED"] = "NOT_ASKED"
    preferred_language: str | None = None
    symptoms_reported: list[str] = Field(default_factory=list)
    medication_concerns: list[str] = Field(default_factory=list)
    follow_up_concerns: list[str] = Field(default_factory=list)
    patient_questions: list[str] = Field(default_factory=list)
    callback_requested: bool = False
    red_flag_indicators: list[str] = Field(default_factory=list)
    uncertainty: list[str] = Field(default_factory=list)
    grounded_references: list[dict[str, Any]] = Field(default_factory=list)
    completed: bool = False


class VoiceIntakeSessionCreate(AIContract):
    outreach_task_id: UUID


class VoiceIntakeTurnRequest(AIContract):
    patient_message: str = Field(min_length=1, max_length=4000)


class VoiceIntakeSessionResponse(AIContract):
    id: UUID
    outreach_task_id: UUID
    current_stage: ConversationStage
    status: str
    conversation_state: dict[str, Any]
    completed_at: datetime | None


class TriageClassification(str, enum.Enum):
    ROUTINE = "ROUTINE"
    CONCERNING = "CONCERNING"
    URGENT = "URGENT"
    INSUFFICIENT_INFORMATION = "INSUFFICIENT_INFORMATION"


class ClinicalTriageAssessment(AIContract):
    assessment_id: UUID
    classification: TriageClassification
    patient_reported_findings: list[str] = Field(default_factory=list)
    clinical_context_facts: list[str] = Field(default_factory=list)
    protocol_references: list[dict[str, Any]] = Field(default_factory=list)
    reasoning_summary: str = Field(max_length=1000)
    uncertainty: list[str] = Field(default_factory=list)
    missing_information: list[str] = Field(default_factory=list)
    recommended_next_action: str = Field(max_length=100)
    confidence: float = Field(ge=0, le=1)
    requires_human_review: bool
    execution_metadata: dict[str, Any] = Field(default_factory=dict)


class AgreementStatus(str, enum.Enum):
    CONSENSUS = "CONSENSUS"
    MAJORITY = "MAJORITY"
    DISAGREEMENT = "DISAGREEMENT"


class EscalationDecision(AIContract):
    decision_id: UUID
    intake_session_id: UUID
    assessment_ids: list[UUID] = Field(min_length=3, max_length=3)
    final_classification: TriageClassification
    agreement_status: AgreementStatus
    requires_human_review: bool
    disagreement_reason: str | None = None
    recommended_action: str
    execution_metadata: dict[str, Any] = Field(default_factory=dict)


class EscalationCaseResolution(AIContract):
    reviewer_notes: str = Field(min_length=1, max_length=2000)
    resolution: str = Field(min_length=1, max_length=100)


class EscalationCaseResponse(AIContract):
    id: UUID
    escalation_decision_id: UUID
    intake_session_id: UUID
    status: str
    priority: str
    assigned_reviewer_id: UUID | None
    reviewer_notes: str | None
    resolution: str | None
    created_at: datetime
    updated_at: datetime
    resolved_at: datetime | None
