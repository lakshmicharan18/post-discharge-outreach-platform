from datetime import datetime, time
from typing import Annotated
from uuid import UUID

from pydantic import AwareDatetime, Field, model_validator

from app.models.campaigns import CampaignStatus
from app.schemas.entities import Input, Output

CampaignName = Annotated[str, Field(min_length=1, max_length=200)]


class CampaignFields(Input):
    description: str | None = Field(default=None, max_length=10000)
    start_at: AwareDatetime | None = None
    end_at: AwareDatetime | None = None
    clinical_follow_up_hours: int | None = Field(default=None, ge=1, le=24 * 30)
    calling_window_start: time | None = None
    calling_window_end: time | None = None
    campaign_priority: int | None = Field(default=None, ge=1, le=100)
    max_retries: int | None = Field(default=None, ge=0, le=20)
    outbound_capacity: int | None = Field(default=None, ge=1, le=1000)
    escalation_configuration: dict = Field(default_factory=dict)
    eligibility_criteria: dict = Field(default_factory=dict)

    @model_validator(mode="after")
    def valid_dates_and_window(self) -> "CampaignFields":
        if self.start_at and self.end_at and self.end_at < self.start_at:
            raise ValueError("Campaign end must follow start")
        if (self.calling_window_start is None) != (self.calling_window_end is None):
            raise ValueError("Both calling window times are required together")
        if self.calling_window_start and self.calling_window_end:
            if self.calling_window_end <= self.calling_window_start:
                raise ValueError("Calling window end must follow start")
        return self


class CampaignCreate(CampaignFields):
    name: CampaignName


class CampaignUpdate(CampaignFields):
    name: CampaignName | None = None


class CampaignResponse(CampaignFields, Output):
    id: UUID
    hospital_id: UUID
    name: str
    status: CampaignStatus
    created_by_user_id: UUID
    started_at: datetime | None
    paused_at: datetime | None
    completed_at: datetime | None
    created_at: datetime
    updated_at: datetime


class CampaignScheduleRequest(Input):
    start_at: AwareDatetime


class CampaignEstimateResponse(Output):
    campaign_id: UUID
    preliminary_candidate_count: int
    estimated_outreach_attempts: int
    eligibility_evaluation: str = "PENDING_MILESTONE_4B"
