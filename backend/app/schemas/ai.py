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
