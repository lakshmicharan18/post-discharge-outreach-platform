import enum
from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class EligibilityReason(str, enum.Enum):
    CAMPAIGN_NOT_CONFIGURED = "CAMPAIGN_NOT_CONFIGURED"
    CAMPAIGN_NOT_ACTIVE = "CAMPAIGN_NOT_ACTIVE"
    DISCHARGE_STATUS_NOT_PENDING = "DISCHARGE_STATUS_NOT_PENDING"
    DISCHARGE_OUTSIDE_CAMPAIGN_DATES = "DISCHARGE_OUTSIDE_CAMPAIGN_DATES"
    FOLLOW_UP_WINDOW_EXPIRED = "FOLLOW_UP_WINDOW_EXPIRED"
    FOLLOW_UP_DEADLINE_EXPIRED = "FOLLOW_UP_DEADLINE_EXPIRED"
    COMMUNICATION_NOT_ELIGIBLE = "COMMUNICATION_NOT_ELIGIBLE"
    COMMUNICATION_PREFERENCE_MISMATCH = "COMMUNICATION_PREFERENCE_MISMATCH"
    RISK_LEVEL_NOT_INCLUDED = "RISK_LEVEL_NOT_INCLUDED"
    CARE_SETTING_NOT_INCLUDED = "CARE_SETTING_NOT_INCLUDED"
    DISCHARGE_BEFORE_CRITERION = "DISCHARGE_BEFORE_CRITERION"
    DISCHARGE_AFTER_CRITERION = "DISCHARGE_AFTER_CRITERION"
    CONDITION_CODE_NOT_INCLUDED = "CONDITION_CODE_NOT_INCLUDED"


class EligibilityResult(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    patient_id: UUID
    discharge_id: UUID
    campaign_id: UUID
    eligible: bool
    reasons: list[EligibilityReason]
    evaluated_at: datetime
    follow_up_deadline: datetime
    risk_level: str
    care_setting: str


class EligibilityPage(BaseModel):
    total: int
    limit: int
    offset: int
    items: list[EligibilityResult]


class PatientEligibilityResponse(BaseModel):
    patient_id: UUID
    results: list[EligibilityResult]
