from datetime import date, datetime
from typing import Annotated, Literal
from uuid import UUID
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from pydantic import (
    AwareDatetime,
    BaseModel,
    ConfigDict,
    EmailStr,
    Field,
    field_validator,
    model_validator,
)

from app.models.entities import Role

Name = Annotated[str, Field(min_length=1, max_length=100)]
ExternalID = Annotated[str, Field(min_length=1, max_length=100)]


class Input(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


class Output(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class HospitalCreate(Input):
    name: str = Field(min_length=1, max_length=200)
    code: str = Field(min_length=1, max_length=50, pattern=r"^[A-Z0-9_-]+$")
    timezone: str = "UTC"
    status: Literal["ACTIVE", "INACTIVE"] = "ACTIVE"

    @field_validator("timezone")
    @classmethod
    def valid_timezone(cls, value: str) -> str:
        try:
            ZoneInfo(value)
        except (ZoneInfoNotFoundError, ValueError) as exc:
            raise ValueError("Unknown IANA timezone") from exc
        return value


class HospitalResponse(HospitalCreate, Output):
    id: UUID
    created_at: datetime
    updated_at: datetime


class UserCreate(Input):
    hospital_id: UUID | None = None
    email: EmailStr = Field(max_length=254)
    full_name: str = Field(min_length=1, max_length=200)
    role: Role
    is_active: bool = True

    @model_validator(mode="after")
    def role_tenant(self) -> "UserCreate":
        if (self.role == Role.PLATFORM_ADMIN) != (self.hospital_id is None):
            raise ValueError("Hospital users require a tenant; platform users have no tenant")
        return self


class UserResponse(UserCreate, Output):
    id: UUID
    created_at: datetime
    updated_at: datetime


class PatientCreate(Input):
    external_patient_id: ExternalID
    first_name: Name
    last_name: Name
    date_of_birth: date
    phone: str = Field(pattern=r"^\+[1-9]\d{7,14}$")
    preferred_language: str = Field(default="en", min_length=2, max_length=35)
    communication_preferences: dict[str, bool] = Field(default_factory=dict)

    @field_validator("date_of_birth")
    @classmethod
    def past_birth_date(cls, value: date) -> date:
        if value > date.today():
            raise ValueError("Birth date cannot be in the future")
        return value


class PatientResponse(PatientCreate, Output):
    id: UUID
    hospital_id: UUID
    created_at: datetime
    updated_at: datetime


class EncounterCreate(Input):
    patient_id: UUID
    external_encounter_id: ExternalID
    care_setting: Literal["INPATIENT", "OUTPATIENT", "EMERGENCY"]
    admit_at: AwareDatetime
    discharge_at: AwareDatetime | None = None
    status: Literal["ADMITTED", "DISCHARGED", "CANCELLED"] = "ADMITTED"

    @model_validator(mode="after")
    def chronology(self) -> "EncounterCreate":
        if self.discharge_at is not None and self.discharge_at < self.admit_at:
            raise ValueError("Discharge must follow admission")
        return self


class EncounterResponse(EncounterCreate, Output):
    id: UUID
    hospital_id: UUID


class DischargeCreate(Input):
    patient_id: UUID
    encounter_id: UUID
    discharge_at: AwareDatetime
    follow_up_deadline: AwareDatetime
    risk_level: Literal["LOW", "MEDIUM", "HIGH", "UNKNOWN"] = "UNKNOWN"
    discharge_instructions: str = Field(min_length=1, max_length=20000)
    status: Literal["PENDING", "COMPLETED", "CANCELLED"] = "PENDING"

    @model_validator(mode="after")
    def chronology(self) -> "DischargeCreate":
        if self.follow_up_deadline < self.discharge_at:
            raise ValueError("Follow-up deadline must follow discharge")
        return self


class DischargeResponse(DischargeCreate, Output):
    id: UUID
    hospital_id: UUID


class ErrorDetail(BaseModel):
    code: str
    message: str
    request_id: UUID


class ErrorResponse(BaseModel):
    error: ErrorDetail


class HealthResponse(BaseModel):
    status: Literal["ok"] = "ok"
    database: Literal["ok"] = "ok"
