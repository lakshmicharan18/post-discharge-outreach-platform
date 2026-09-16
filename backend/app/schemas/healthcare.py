from datetime import datetime, time
from decimal import Decimal
from typing import Any, Literal
from uuid import UUID
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field, field_validator, model_validator

from app.schemas.entities import (
    DischargeResponse,
    EncounterResponse,
    ExternalID,
    Input,
    Output,
    PatientCreate,
    PatientResponse,
)


class HospitalConfigurationBase(Input):
    timezone: str = "UTC"
    calling_window_start: time = time(9, 0)
    calling_window_end: time = time(17, 0)
    default_follow_up_hours: int = Field(default=72, ge=1, le=24 * 30)
    max_concurrent_calls: int = Field(default=10, ge=1, le=1000)
    default_max_retries: int = Field(default=3, ge=0, le=20)
    retry_initial_delay_minutes: int = Field(default=60, ge=1, le=24 * 60)
    retry_backoff_multiplier: Decimal = Field(default=Decimal("2.0"), ge=1, le=10)
    notification_preferences: dict[str, bool] = Field(default_factory=dict)
    escalation_contacts: list[dict[str, str]] = Field(default_factory=list, max_length=50)
    ehr_settings: dict[str, str | bool] = Field(default_factory=dict)
    is_ready: bool = False

    @field_validator("timezone")
    @classmethod
    def valid_timezone(cls, value: str) -> str:
        try:
            ZoneInfo(value)
        except (ZoneInfoNotFoundError, ValueError) as exc:
            raise ValueError("Unknown IANA timezone") from exc
        return value

    @model_validator(mode="after")
    def valid_calling_window(self) -> "HospitalConfigurationBase":
        if self.calling_window_end <= self.calling_window_start:
            raise ValueError("Calling window end must follow start")
        return self


class HospitalConfigurationUpdate(HospitalConfigurationBase):
    pass


class HospitalConfigurationResponse(HospitalConfigurationBase, Output):
    id: UUID
    hospital_id: UUID
    created_at: datetime
    updated_at: datetime


class ResourceInput(Input):
    external_id: ExternalID
    encounter_id: UUID | None = None


class ResourceResponse(Output):
    id: UUID
    hospital_id: UUID
    patient_id: UUID
    encounter_id: UUID | None
    external_id: str
    created_at: datetime
    updated_at: datetime


class ConditionCreate(ResourceInput):
    code: str = Field(min_length=1, max_length=100)
    display_name: str = Field(min_length=1, max_length=250)
    clinical_status: Literal["ACTIVE", "RESOLVED", "INACTIVE"] = "ACTIVE"
    onset_at: AwareDatetime | None = None
    resolved_at: AwareDatetime | None = None
    notes: str | None = Field(default=None, max_length=5000)

    @model_validator(mode="after")
    def chronology(self) -> "ConditionCreate":
        if self.onset_at and self.resolved_at and self.resolved_at < self.onset_at:
            raise ValueError("Resolution must follow onset")
        return self


class ConditionResponse(ConditionCreate, ResourceResponse):
    pass


class ObservationCreate(ResourceInput):
    code: str = Field(min_length=1, max_length=100)
    display_name: str = Field(min_length=1, max_length=250)
    value: str | int | float | bool
    unit: str | None = Field(default=None, max_length=50)
    value_type: Literal["STRING", "INTEGER", "DECIMAL", "BOOLEAN", "CODE"]
    observed_at: AwareDatetime
    source: str = Field(default="IMPORT", min_length=1, max_length=100)


class ObservationResponse(ObservationCreate, ResourceResponse):
    pass


class MedicationCreate(ResourceInput):
    medication_name: str = Field(min_length=1, max_length=250)
    medication_code: str | None = Field(default=None, max_length=100)
    dose: str | None = Field(default=None, max_length=100)
    route: str | None = Field(default=None, max_length=100)
    frequency: str | None = Field(default=None, max_length=100)
    instructions: str | None = Field(default=None, max_length=5000)
    status: Literal["ACTIVE", "COMPLETED", "STOPPED", "ON_HOLD"] = "ACTIVE"
    started_at: AwareDatetime | None = None
    ended_at: AwareDatetime | None = None

    @model_validator(mode="after")
    def chronology(self) -> "MedicationCreate":
        if self.started_at and self.ended_at and self.ended_at < self.started_at:
            raise ValueError("Medication end must follow start")
        return self


class MedicationResponse(MedicationCreate, ResourceResponse):
    pass


class CarePlanCreate(ResourceInput):
    title: str = Field(min_length=1, max_length=250)
    description: str = Field(min_length=1, max_length=10000)
    status: Literal["DRAFT", "ACTIVE", "COMPLETED", "CANCELLED"] = "ACTIVE"
    follow_up_instructions: str = Field(min_length=1, max_length=10000)
    start_at: AwareDatetime | None = None
    end_at: AwareDatetime | None = None

    @model_validator(mode="after")
    def chronology(self) -> "CarePlanCreate":
        if self.start_at and self.end_at and self.end_at < self.start_at:
            raise ValueError("Care plan end must follow start")
        return self


class CarePlanResponse(CarePlanCreate, ResourceResponse):
    pass


class ProcedureCreate(ResourceInput):
    code: str | None = Field(default=None, max_length=100)
    name: str = Field(min_length=1, max_length=250)
    performed_at: AwareDatetime | None = None
    status: Literal["PLANNED", "IN_PROGRESS", "COMPLETED", "CANCELLED"] = "COMPLETED"
    notes: str | None = Field(default=None, max_length=5000)


class ProcedureResponse(ProcedureCreate, ResourceResponse):
    pass


class EncounterImport(Input):
    external_encounter_id: ExternalID
    care_setting: Literal["INPATIENT", "OUTPATIENT", "EMERGENCY"]
    admit_at: AwareDatetime
    discharge_at: AwareDatetime
    status: Literal["DISCHARGED", "CANCELLED"] = "DISCHARGED"

    @model_validator(mode="after")
    def chronology(self) -> "EncounterImport":
        if self.discharge_at < self.admit_at:
            raise ValueError("Discharge must follow admission")
        return self


class DischargeImportData(Input):
    discharge_at: AwareDatetime
    follow_up_deadline: AwareDatetime | None = None
    follow_up_window_hours: int | None = Field(default=None, ge=1, le=24 * 30)
    disposition: str = Field(default="HOME", min_length=1, max_length=50)
    risk_level: Literal["LOW", "MEDIUM", "HIGH", "UNKNOWN"] = "UNKNOWN"
    risk_indicators: list[str] = Field(default_factory=list, max_length=50)
    discharge_instructions: str = Field(min_length=1, max_length=20000)
    communication_eligible: bool = True
    status: Literal["PENDING", "COMPLETED", "CANCELLED"] = "PENDING"
    source_reference: str | None = Field(default=None, min_length=1, max_length=200)

    @model_validator(mode="after")
    def chronology(self) -> "DischargeImportData":
        if self.follow_up_deadline and self.follow_up_deadline < self.discharge_at:
            raise ValueError("Follow-up deadline must follow discharge")
        return self


class DischargeImportRecord(Input):
    patient: PatientCreate
    encounter: EncounterImport
    discharge: DischargeImportData
    conditions: list[ConditionCreate] = Field(default_factory=list, max_length=100)
    observations: list[ObservationCreate] = Field(default_factory=list, max_length=100)
    medications: list[MedicationCreate] = Field(default_factory=list, max_length=100)
    care_plans: list[CarePlanCreate] = Field(default_factory=list, max_length=100)
    procedures: list[ProcedureCreate] = Field(default_factory=list, max_length=100)

    @model_validator(mode="after")
    def consistent_discharge(self) -> "DischargeImportRecord":
        if self.discharge.discharge_at != self.encounter.discharge_at:
            raise ValueError("Encounter and discharge timestamps must match")
        return self


class DischargeBatchImportRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    source: str = Field(default="json-upload", min_length=1, max_length=255)
    # Raw records allow record-level validation and partial success.
    records: list[dict[str, Any]] = Field(min_length=1, max_length=1000)


class ImportError(BaseModel):
    record_index: int
    code: str
    field: str | None = None
    message: str


class DischargeImportResponse(Output):
    id: UUID
    hospital_id: UUID
    source: str
    status: Literal["PENDING", "PROCESSING", "COMPLETED", "PARTIALLY_COMPLETED", "FAILED"]
    total_records: int
    successful_records: int
    failed_records: int
    errors: list[ImportError]
    started_at: datetime | None
    completed_at: datetime | None
    created_by_user_id: UUID
    created_at: datetime
    updated_at: datetime


class TimelineEvent(BaseModel):
    occurred_at: datetime
    event_type: Literal[
        "ENCOUNTER_ADMISSION", "OBSERVATION", "PROCEDURE", "MEDICATION", "CARE_PLAN", "DISCHARGE"
    ]
    resource_id: UUID
    title: str
    summary: str | None = None


class PatientContextResponse(BaseModel):
    patient: PatientResponse
    encounters: list[EncounterResponse]
    discharges: list[DischargeResponse]
    conditions: list[ConditionResponse]
    observations: list[ObservationResponse]
    medications: list[MedicationResponse]
    care_plans: list[CarePlanResponse]
    procedures: list[ProcedureResponse]
    timeline: list[TimelineEvent]
