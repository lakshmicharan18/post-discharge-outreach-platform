from datetime import datetime, timedelta
from uuid import uuid4
from zoneinfo import ZoneInfo

from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.context import RequestContext
from app.core.errors import APIError
from app.models.campaigns import Campaign, CampaignStatus, OutreachTask, OutreachTaskState
from app.models.entities import Discharge, Encounter, Role
from app.models.healthcare import HospitalConfiguration
from app.schemas.eligibility import EligibilityResult
from app.schemas.outreach import QueueStatusResponse
from app.services.audit import add_audit_event
from app.services.priority import score_outreach_task

ACTIVE_STATES = (
    OutreachTaskState.SCHEDULED,
    OutreachTaskState.CALLING,
    OutreachTaskState.CONNECTED,
)
LEASE = timedelta(minutes=5)


class QueueSchedulerService:
    def __init__(self, session: AsyncSession, context: RequestContext) -> None:
        self.session, self.context = session, context
        self.hospital_id = context.require_clinical_tenant()

    async def reserve_available(self, limit: int, now: datetime) -> list[OutreachTask]:
        self.context.require_roles(Role.HOSPITAL_ADMIN, Role.CAMPAIGN_MANAGER)
        try:
            configuration = await self.session.scalar(
                select(HospitalConfiguration)
                .where(HospitalConfiguration.hospital_id == self.hospital_id)
                .with_for_update()
            )
            if configuration is None:
                raise APIError(409, "configuration_required", "Hospital configuration is required")
            await self._release_expired(now)
            active = await self._active_count()
            available = max(0, configuration.max_concurrent_calls - active)
            reserved: list[OutreachTask] = []
            for _ in range(min(limit, available)):
                task = await self._reserve_one(configuration, now)
                if task is None:
                    break
                reserved.append(task)
            if reserved:
                await add_audit_event(
                    self.session,
                    self.context,
                    self.hospital_id,
                    "OUTREACH_TASKS_RESERVED",
                    "Queue",
                    None,
                    {"count": len(reserved)},
                )
            await self.session.commit()
            for task in reserved:
                await self.session.refresh(task)
            return reserved
        except Exception:
            await self.session.rollback()
            raise

    async def reserve_next(self, now: datetime) -> OutreachTask | None:
        tasks = await self.reserve_available(1, now)
        return tasks[0] if tasks else None

    async def status(self, now: datetime) -> QueueStatusResponse:
        configuration = await self.session.scalar(
            select(HospitalConfiguration).where(
                HospitalConfiguration.hospital_id == self.hospital_id
            )
        )
        if configuration is None:
            raise APIError(404, "not_found", "Hospital configuration not found")
        active = await self._active_count()
        pending = (
            await self.session.scalar(
                select(func.count())
                .select_from(OutreachTask)
                .where(
                    OutreachTask.hospital_id == self.hospital_id,
                    OutreachTask.state == OutreachTaskState.PENDING,
                )
            )
            or 0
        )
        oldest = await self.session.scalar(
            select(func.min(OutreachTask.eligible_at)).where(
                OutreachTask.hospital_id == self.hospital_id,
                OutreachTask.state == OutreachTaskState.PENDING,
            )
        )
        approaching = (
            await self.session.scalar(
                select(func.count())
                .select_from(OutreachTask)
                .where(
                    OutreachTask.hospital_id == self.hospital_id,
                    OutreachTask.state == OutreachTaskState.PENDING,
                    OutreachTask.clinical_deadline > now,
                    OutreachTask.clinical_deadline <= now + timedelta(hours=6),
                )
            )
            or 0
        )
        missed = (
            await self.session.scalar(
                select(func.count())
                .select_from(OutreachTask)
                .where(
                    OutreachTask.hospital_id == self.hospital_id,
                    OutreachTask.state == OutreachTaskState.PENDING,
                    OutreachTask.clinical_deadline <= now,
                )
            )
            or 0
        )
        return QueueStatusResponse(
            effective_capacity=configuration.max_concurrent_calls,
            active_reserved_count=active,
            available_capacity=max(0, configuration.max_concurrent_calls - active),
            pending_count=pending,
            oldest_pending_at=oldest,
            approaching_deadline_count=approaching,
            deadline_missed_count=missed,
        )

    async def _release_expired(self, now: datetime) -> None:
        await self.session.execute(
            update(OutreachTask)
            .where(
                OutreachTask.hospital_id == self.hospital_id,
                OutreachTask.state == OutreachTaskState.SCHEDULED,
                OutreachTask.reservation_expires_at <= now,
            )
            .values(
                state=OutreachTaskState.PENDING,
                reserved_at=None,
                reservation_token=None,
                reservation_expires_at=None,
                scheduled_at=None,
            )
        )

    async def _active_count(self) -> int:
        return int(
            await self.session.scalar(
                select(func.count())
                .select_from(OutreachTask)
                .where(
                    OutreachTask.hospital_id == self.hospital_id,
                    OutreachTask.state.in_(ACTIVE_STATES),
                )
            )
            or 0
        )

    async def _reserve_one(
        self, configuration: HospitalConfiguration, now: datetime
    ) -> OutreachTask | None:
        local_time = now.astimezone(ZoneInfo(configuration.timezone)).time()
        if not (
            configuration.calling_window_start <= local_time < configuration.calling_window_end
        ):
            return None
        rows = await self.session.execute(
            select(OutreachTask, Campaign, Discharge, Encounter)
            .join(Campaign, OutreachTask.campaign_id == Campaign.id)
            .join(Discharge, OutreachTask.discharge_id == Discharge.id)
            .join(Encounter, Discharge.encounter_id == Encounter.id)
            .where(
                OutreachTask.hospital_id == self.hospital_id,
                OutreachTask.state.in_(
                    (
                        OutreachTaskState.PENDING,
                        OutreachTaskState.RETRY_SCHEDULED,
                        OutreachTaskState.CALLBACK_SCHEDULED,
                    )
                ),
                OutreachTask.next_eligible_at <= now,
                OutreachTask.clinical_deadline > now,
                OutreachTask.manual_follow_up_required.is_(False),
                Campaign.status == CampaignStatus.RUNNING,
            )
            .with_for_update(skip_locked=True)
        )
        candidates = []
        for task, campaign, discharge, encounter in rows:
            if not (campaign.calling_window_start <= local_time < campaign.calling_window_end):
                continue
            campaign_capacity = campaign.outbound_capacity
            campaign_active = (
                await self.session.scalar(
                    select(func.count())
                    .select_from(OutreachTask)
                    .where(
                        OutreachTask.campaign_id == campaign.id,
                        OutreachTask.state.in_(ACTIVE_STATES),
                    )
                )
                or 0
            )
            if campaign_capacity is not None and campaign_active >= campaign_capacity:
                continue
            result = EligibilityResult(
                patient_id=task.patient_id,
                discharge_id=task.discharge_id,
                campaign_id=campaign.id,
                eligible=True,
                reasons=[],
                evaluated_at=now,
                follow_up_deadline=task.clinical_deadline,
                risk_level=discharge.risk_level,
                care_setting=encounter.care_setting,
            )
            components = score_outreach_task(
                campaign,
                result,
                now=now,
                eligible_at=task.eligible_at,
                attempt_count=task.attempt_count,
                callback_at=task.callback_at,
            )
            candidates.append((components, task, campaign))
        if not candidates:
            return None
        components, task, _ = sorted(
            candidates,
            key=lambda item: (
                -item[0]["total"],
                item[1].clinical_deadline,
                item[1].eligible_at,
                str(item[1].id),
            ),
        )[0]
        task.priority_score, task.priority_components = components["total"], components
        task.state, task.reserved_at = OutreachTaskState.SCHEDULED, now
        task.reservation_token, task.reservation_expires_at = uuid4(), now + LEASE
        task.scheduled_at = now
        await self.session.flush()
        return task
