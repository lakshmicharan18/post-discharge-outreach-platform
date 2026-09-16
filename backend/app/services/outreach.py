from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.context import RequestContext
from app.models.campaigns import Campaign, OutreachTask, OutreachTaskState
from app.repositories.outreach import OutreachTaskRepository
from app.schemas.outreach import OutreachWorkCreationSummary
from app.services.audit import add_audit_event
from app.services.eligibility import EligibilityService
from app.services.priority import score_outreach_task


class OutreachWorkService:
    """Creates durable work from current eligibility; scheduling is deliberately deferred."""

    def __init__(self, session: AsyncSession, context: RequestContext) -> None:
        self.session = session
        self.context = context
        self.hospital_id = context.require_clinical_tenant()
        self.repository = OutreachTaskRepository(session, context)

    async def create_missing(
        self, campaign: Campaign, *, now: datetime | None = None
    ) -> OutreachWorkCreationSummary:
        evaluated_at = now or datetime.now(timezone.utc)
        results = await EligibilityService(self.session, self.context).all_results(
            campaign, now=evaluated_at
        )
        eligible = [result for result in results if result.eligible]
        created = 0
        for result in eligible:
            components = score_outreach_task(
                campaign, result, now=evaluated_at, eligible_at=evaluated_at
            )
            statement = (
                insert(OutreachTask)
                .values(
                    hospital_id=self.hospital_id,
                    campaign_id=campaign.id,
                    patient_id=result.patient_id,
                    discharge_id=result.discharge_id,
                    state=OutreachTaskState.PENDING,
                    priority_score=components["total"],
                    priority_components=components,
                    attempt_count=0,
                    max_attempts=(campaign.max_retries or 0) + 1,
                    eligible_at=evaluated_at,
                    next_eligible_at=evaluated_at,
                    clinical_deadline=result.follow_up_deadline,
                    manual_follow_up_required=False,
                )
                .on_conflict_do_nothing(
                    index_elements=["hospital_id", "campaign_id", "discharge_id"]
                )
                .returning(OutreachTask.id)
            )
            if (await self.session.scalar(statement)) is not None:
                created += 1
        summary = OutreachWorkCreationSummary(
            campaign_id=campaign.id,
            evaluated=len(results),
            eligible=len(eligible),
            created=created,
            already_existing=len(eligible) - created,
            ineligible=len(results) - len(eligible),
        )
        await add_audit_event(
            self.session,
            self.context,
            self.hospital_id,
            "OUTREACH_WORK_GENERATED",
            "Campaign",
            campaign.id,
            summary.model_dump(mode="json", exclude={"campaign_id"}),
        )
        return summary

    async def get(self, task_id: UUID) -> OutreachTask:
        return await self.repository.get(task_id)

    async def list(
        self, campaign_id: UUID, state, patient_id: UUID | None, limit: int, offset: int
    ):
        return await self.repository.list(campaign_id, state, patient_id, limit, offset)
