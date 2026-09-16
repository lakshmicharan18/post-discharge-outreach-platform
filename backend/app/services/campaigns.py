from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.context import RequestContext
from app.core.errors import APIError
from app.models.campaigns import Campaign, CampaignStatus
from app.models.entities import Role
from app.models.healthcare import HospitalConfiguration
from app.repositories.campaigns import CampaignRepository
from app.schemas.campaigns import (
    CampaignCreate,
    CampaignEstimateResponse,
    CampaignScheduleRequest,
    CampaignUpdate,
)
from app.services.audit import add_audit_event
from app.services.eligibility import EligibilityService
from app.services.outreach import OutreachWorkService

MUTATION_ROLES = (Role.HOSPITAL_ADMIN, Role.CAMPAIGN_MANAGER)
TRANSITIONS = {
    "ready": ({CampaignStatus.DRAFT}, CampaignStatus.READY, "CAMPAIGN_READY"),
    "schedule": ({CampaignStatus.READY}, CampaignStatus.SCHEDULED, "CAMPAIGN_SCHEDULED"),
    "start": (
        {CampaignStatus.READY, CampaignStatus.SCHEDULED},
        CampaignStatus.RUNNING,
        "CAMPAIGN_STARTED",
    ),
    "pause": ({CampaignStatus.RUNNING}, CampaignStatus.PAUSED, "CAMPAIGN_PAUSED"),
    "resume": ({CampaignStatus.PAUSED}, CampaignStatus.RUNNING, "CAMPAIGN_RESUMED"),
    "complete": ({CampaignStatus.RUNNING}, CampaignStatus.COMPLETED, "CAMPAIGN_COMPLETED"),
    "cancel": (
        {
            CampaignStatus.DRAFT,
            CampaignStatus.READY,
            CampaignStatus.SCHEDULED,
            CampaignStatus.RUNNING,
            CampaignStatus.PAUSED,
        },
        CampaignStatus.CANCELLED,
        "CAMPAIGN_CANCELLED",
    ),
}


class CampaignService:
    def __init__(self, session: AsyncSession, context: RequestContext) -> None:
        self.session = session
        self.context = context
        self.hospital_id = context.require_clinical_tenant()
        self.repository = CampaignRepository(session, context)

    async def create(self, payload: CampaignCreate) -> Campaign:
        self.context.require_roles(*MUTATION_ROLES)
        try:
            values = payload.model_dump()
            values["eligibility_criteria"] = payload.eligibility_criteria.model_dump(mode="json")
            campaign = await self.repository.create(
                {**values, "created_by_user_id": self.context.user_id}
            )
            await add_audit_event(
                self.session,
                self.context,
                self.hospital_id,
                "CAMPAIGN_CREATED",
                "Campaign",
                campaign.id,
                {"status": campaign.status.value},
            )
            await self.session.commit()
            await self.session.refresh(campaign)
            return campaign
        except Exception:
            await self.session.rollback()
            raise

    async def list(self, limit: int, offset: int) -> list[Campaign]:
        return await self.repository.list(limit, offset)

    async def get(self, campaign_id: UUID) -> Campaign:
        return await self.repository.get(campaign_id)

    async def update(self, campaign_id: UUID, payload: CampaignUpdate) -> Campaign:
        self.context.require_roles(*MUTATION_ROLES)
        campaign = await self.repository.get(campaign_id)
        if campaign.status is not CampaignStatus.DRAFT:
            raise APIError(409, "campaign_not_editable", "Only draft campaigns can be updated")
        values = payload.model_dump(exclude_unset=True)
        if "eligibility_criteria" in values:
            values["eligibility_criteria"] = payload.eligibility_criteria.model_dump(mode="json")
        try:
            for field, value in values.items():
                setattr(campaign, field, value)
            await self.session.flush()
            await add_audit_event(
                self.session,
                self.context,
                self.hospital_id,
                "CAMPAIGN_UPDATED",
                "Campaign",
                campaign.id,
                {"updated_fields": sorted(values)},
            )
            await self.session.commit()
            await self.session.refresh(campaign)
            return campaign
        except Exception:
            await self.session.rollback()
            raise

    async def transition(
        self, campaign_id: UUID, action: str, schedule: CampaignScheduleRequest | None = None
    ) -> Campaign:
        self.context.require_roles(*MUTATION_ROLES)
        allowed, target, audit_action = TRANSITIONS[action]
        campaign = await self.repository.get(campaign_id)
        if campaign.status not in allowed:
            raise APIError(
                409,
                "invalid_campaign_transition",
                f"Cannot {action} a campaign in {campaign.status.value} state",
            )
        if action in {"ready", "start"}:
            await self._validate_activation(campaign)
        if action == "schedule":
            if schedule is None:
                raise APIError(422, "schedule_required", "A scheduled start time is required")
            if campaign.end_at and schedule.start_at > campaign.end_at:
                raise APIError(
                    422, "invalid_campaign_dates", "Scheduled start exceeds campaign end"
                )
            campaign.start_at = schedule.start_at
        now = datetime.now(timezone.utc)
        previous_status = campaign.status
        campaign.status = target
        if action == "start":
            campaign.started_at = now
        elif action == "pause":
            campaign.paused_at = now
        elif action == "complete":
            campaign.completed_at = now
        try:
            work_summary = None
            if action in {"start", "resume"}:
                work_summary = await OutreachWorkService(self.session, self.context).create_missing(
                    campaign, now=now
                )
            await self.session.flush()
            await add_audit_event(
                self.session,
                self.context,
                self.hospital_id,
                audit_action,
                "Campaign",
                campaign.id,
                {
                    "from_status": previous_status.value,
                    "to_status": target.value,
                    **({"work_created": work_summary.created} if work_summary else {}),
                },
            )
            await self.session.commit()
            await self.session.refresh(campaign)
            return campaign
        except Exception:
            await self.session.rollback()
            raise

    async def estimate(self, campaign_id: UUID) -> CampaignEstimateResponse:
        campaign = await self.repository.get(campaign_id)
        return await EligibilityService(self.session, self.context).estimate(campaign)

    async def _validate_activation(self, campaign: Campaign) -> None:
        EligibilityService._criteria(campaign)
        required = (
            campaign.clinical_follow_up_hours,
            campaign.calling_window_start,
            campaign.calling_window_end,
            campaign.campaign_priority,
            campaign.max_retries,
        )
        if any(value is None for value in required):
            raise APIError(
                409, "campaign_not_configured", "Campaign operational configuration is incomplete"
            )
        configuration = await self.session.scalar(
            select(HospitalConfiguration).where(
                HospitalConfiguration.hospital_id == self.hospital_id
            )
        )
        if configuration is None or not configuration.is_ready:
            raise APIError(409, "hospital_not_ready", "Hospital configuration must be ready")
