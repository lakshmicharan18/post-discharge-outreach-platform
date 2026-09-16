from collections import Counter
from datetime import datetime, timedelta, timezone
from uuid import UUID

from pydantic import ValidationError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.context import RequestContext
from app.core.errors import APIError
from app.models.campaigns import Campaign, CampaignStatus
from app.repositories.eligibility import EligibilityCandidate, EligibilityRepository
from app.schemas.campaigns import CampaignEstimateResponse, EligibilityCriteria
from app.schemas.eligibility import EligibilityPage, EligibilityReason, EligibilityResult


class EligibilityService:
    """Deterministic, dynamic evaluation shared by eligibility APIs and workload estimates."""

    def __init__(self, session: AsyncSession, context: RequestContext) -> None:
        self.session = session
        self.context = context
        self.context.require_clinical_tenant()
        self.repository = EligibilityRepository(session, context)

    async def evaluate(
        self,
        campaign: Campaign,
        *,
        patient_id: UUID | None = None,
        eligible: bool | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> EligibilityPage:
        results = await self._all_results(campaign, patient_id)
        if eligible is not None:
            results = [result for result in results if result.eligible is eligible]
        return EligibilityPage(
            total=len(results), limit=limit, offset=offset, items=results[offset : offset + limit]
        )

    async def patient_results(
        self, campaign: Campaign, patient_id: UUID
    ) -> list[EligibilityResult]:
        return (await self.evaluate(campaign, patient_id=patient_id, limit=100, offset=0)).items

    async def estimate(self, campaign: Campaign) -> CampaignEstimateResponse:
        results = await self.all_results(campaign)
        eligible_results = [result for result in results if result.eligible]
        reason_counts = Counter(
            reason.value for result in results if not result.eligible for reason in result.reasons
        )
        risk_counts = Counter(result.risk_level for result in eligible_results)
        retries = campaign.max_retries or 0
        return CampaignEstimateResponse(
            campaign_id=campaign.id,
            total_evaluated=len(results),
            eligible_patients=len(eligible_results),
            ineligible_patients=len(results) - len(eligible_results),
            estimated_outreach_attempts=len(eligible_results) * (retries + 1),
            by_risk_level=dict(sorted(risk_counts.items())),
            by_ineligibility_reason=dict(sorted(reason_counts.items())),
        )

    async def all_results(
        self, campaign: Campaign, *, now: datetime | None = None
    ) -> list[EligibilityResult]:
        return await self._all_results(campaign, evaluated_at=now)

    async def _all_results(
        self,
        campaign: Campaign,
        patient_id: UUID | None = None,
        evaluated_at: datetime | None = None,
    ) -> list[EligibilityResult]:
        criteria = self._criteria(campaign)
        evaluated_at = evaluated_at or datetime.now(timezone.utc)
        candidates = await self.repository.candidates(patient_id)
        return [
            self._evaluate_candidate(campaign, criteria, candidate, evaluated_at)
            for candidate in candidates
        ]

    @staticmethod
    def _criteria(campaign: Campaign) -> EligibilityCriteria:
        try:
            return EligibilityCriteria.model_validate(campaign.eligibility_criteria)
        except ValidationError as exc:
            raise APIError(
                409, "campaign_criteria_invalid", "Campaign eligibility criteria are invalid"
            ) from exc

    @staticmethod
    def _evaluate_candidate(
        campaign: Campaign,
        criteria: EligibilityCriteria,
        candidate: EligibilityCandidate,
        evaluated_at: datetime,
    ) -> EligibilityResult:
        discharge = candidate.discharge
        reasons: list[EligibilityReason] = []
        required_configuration = (
            campaign.clinical_follow_up_hours,
            campaign.calling_window_start,
            campaign.calling_window_end,
            campaign.campaign_priority,
            campaign.max_retries,
        )
        if any(value is None for value in required_configuration):
            reasons.append(EligibilityReason.CAMPAIGN_NOT_CONFIGURED)
        if campaign.status in {
            CampaignStatus.COMPLETED,
            CampaignStatus.CANCELLED,
            CampaignStatus.FAILED,
        }:
            reasons.append(EligibilityReason.CAMPAIGN_NOT_ACTIVE)
        if discharge.status != "PENDING":
            reasons.append(EligibilityReason.DISCHARGE_STATUS_NOT_PENDING)
        if (campaign.start_at and discharge.discharge_at < campaign.start_at) or (
            campaign.end_at and discharge.discharge_at > campaign.end_at
        ):
            reasons.append(EligibilityReason.DISCHARGE_OUTSIDE_CAMPAIGN_DATES)
        if campaign.clinical_follow_up_hours is not None:
            if evaluated_at > discharge.discharge_at + timedelta(
                hours=campaign.clinical_follow_up_hours
            ):
                reasons.append(EligibilityReason.FOLLOW_UP_WINDOW_EXPIRED)
        if evaluated_at > discharge.follow_up_deadline:
            reasons.append(EligibilityReason.FOLLOW_UP_DEADLINE_EXPIRED)
        if not discharge.communication_eligible:
            reasons.append(EligibilityReason.COMMUNICATION_NOT_ELIGIBLE)
        if criteria.risk_levels and discharge.risk_level not in criteria.risk_levels:
            reasons.append(EligibilityReason.RISK_LEVEL_NOT_INCLUDED)
        if (
            criteria.care_settings
            and candidate.encounter.care_setting not in criteria.care_settings
        ):
            reasons.append(EligibilityReason.CARE_SETTING_NOT_INCLUDED)
        if criteria.discharge_after and discharge.discharge_at < criteria.discharge_after:
            reasons.append(EligibilityReason.DISCHARGE_BEFORE_CRITERION)
        if criteria.discharge_before and discharge.discharge_at > criteria.discharge_before:
            reasons.append(EligibilityReason.DISCHARGE_AFTER_CRITERION)
        if criteria.condition_codes and not candidate.condition_codes.intersection(
            criteria.condition_codes
        ):
            reasons.append(EligibilityReason.CONDITION_CODE_NOT_INCLUDED)
        if any(
            candidate.patient.communication_preferences.get(key) != expected
            for key, expected in criteria.required_communication_preferences.items()
        ):
            reasons.append(EligibilityReason.COMMUNICATION_PREFERENCE_MISMATCH)
        return EligibilityResult(
            patient_id=candidate.patient.id,
            discharge_id=discharge.id,
            campaign_id=campaign.id,
            eligible=not reasons,
            reasons=reasons,
            evaluated_at=evaluated_at,
            follow_up_deadline=discharge.follow_up_deadline,
            risk_level=discharge.risk_level,
            care_setting=candidate.encounter.care_setting,
        )
