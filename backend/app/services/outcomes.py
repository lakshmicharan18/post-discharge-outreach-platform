from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.context import RequestContext
from app.core.errors import APIError
from app.models.campaigns import (
    Campaign,
    ManualFollowUp,
    OutreachAttempt,
    OutreachOutcome,
    OutreachTask,
    OutreachTaskState,
)
from app.models.entities import Role
from app.models.healthcare import HospitalConfiguration
from app.services.audit import add_audit_event

RETRYABLE = {
    OutreachOutcome.NO_ANSWER,
    OutreachOutcome.BUSY,
    OutreachOutcome.VOICEMAIL,
    OutreachOutcome.DROPPED,
    OutreachOutcome.TECHNICAL_FAILURE,
}
PROCESSING_LEASE = timedelta(minutes=5)
ACTIVE_STATES = (
    OutreachTaskState.SCHEDULED,
    OutreachTaskState.CALLING,
    OutreachTaskState.CONNECTED,
)


class OutcomeService:
    def __init__(self, session: AsyncSession, context: RequestContext) -> None:
        self.session, self.context = session, context
        self.hospital_id = context.require_clinical_tenant()

    async def start(
        self,
        task_id,
        now: datetime,
        provider_call_id: str | None = None,
        worker_id: str | None = None,
    ):
        self.context.require_roles(Role.HOSPITAL_ADMIN, Role.CAMPAIGN_MANAGER)
        task = await self._locked_task(task_id)
        if task.state != OutreachTaskState.SCHEDULED:
            raise APIError(409, "invalid_transition", "Only scheduled work can start an attempt")
        attempt = OutreachAttempt(
            hospital_id=self.hospital_id,
            campaign_id=task.campaign_id,
            outreach_task_id=task.id,
            patient_id=task.patient_id,
            discharge_id=task.discharge_id,
            attempt_number=task.attempt_count + 1,
            started_at=now,
            provider_call_id=provider_call_id,
        )
        self.session.add(attempt)
        task.state, task.started_at = OutreachTaskState.CALLING, now
        task.worker_id = worker_id or provider_call_id or "outreach-worker"
        task.heartbeat_at, task.processing_lease_expires_at = now, now + PROCESSING_LEASE
        task.reserved_at = None
        task.reservation_token = None
        task.reservation_expires_at = None
        await add_audit_event(
            self.session,
            self.context,
            self.hospital_id,
            "OUTREACH_CALL_STARTED",
            "OutreachTask",
            task.id,
        )
        await self.session.commit()
        await self.session.refresh(attempt)
        return attempt

    async def heartbeat(self, task_id, worker_id: str, now: datetime) -> OutreachTask:
        self.context.require_roles(Role.HOSPITAL_ADMIN, Role.CAMPAIGN_MANAGER)
        task = await self._locked_task(task_id)
        if task.state not in ACTIVE_STATES:
            raise APIError(409, "invalid_transition", "Only active work can be heartbeated")
        if task.worker_id is not None and task.worker_id != worker_id:
            raise APIError(409, "lease_not_owned", "Work is owned by another worker")
        if task.state == OutreachTaskState.SCHEDULED and (
            task.reservation_expires_at is None or task.reservation_expires_at <= now
        ):
            raise APIError(409, "lease_expired", "Scheduled reservation has expired")
        task.worker_id = worker_id
        task.heartbeat_at, task.processing_lease_expires_at = now, now + PROCESSING_LEASE
        await self.session.commit()
        await self.session.refresh(task)
        return task

    async def recover_connected(self, task_id, now: datetime) -> OutreachTask | None:
        """Convert a stale connected call to one durable manual follow-up."""
        self.context.require_roles(Role.HOSPITAL_ADMIN, Role.CAMPAIGN_MANAGER)
        task = await self._locked_task(task_id)
        if task.state != OutreachTaskState.CONNECTED:
            return None
        if task.processing_lease_expires_at is None or task.processing_lease_expires_at > now:
            return None
        await self._manual(task, "STALE_CONNECTED_WORKER_RECOVERY")
        self._clear_work_lease(task)
        await add_audit_event(
            self.session,
            self.context,
            self.hospital_id,
            "STALE_CONNECTED_WORKER_RECOVERED",
            "OutreachTask",
            task.id,
        )
        await self.session.commit()
        await self.session.refresh(task)
        return task

    async def process(self, task_id, payload, now: datetime) -> OutreachTask:
        self.context.require_roles(Role.HOSPITAL_ADMIN, Role.CAMPAIGN_MANAGER)
        existing = await self.session.scalar(
            select(OutreachAttempt).where(
                OutreachAttempt.hospital_id == self.hospital_id,
                OutreachAttempt.outcome_event_id == payload.idempotency_key,
            )
        )
        if existing is not None:
            return await self.session.get(OutreachTask, existing.outreach_task_id)
        task = await self._locked_task(task_id)
        if task.state not in (OutreachTaskState.CALLING, OutreachTaskState.CONNECTED):
            raise APIError(409, "invalid_transition", "An outcome requires an active call")
        attempt = await self.session.scalar(
            select(OutreachAttempt)
            .where(OutreachAttempt.outreach_task_id == task.id, OutreachAttempt.ended_at.is_(None))
            .order_by(OutreachAttempt.attempt_number.desc())
            .with_for_update()
        )
        if attempt is None:
            raise APIError(409, "attempt_required", "Start an attempt before recording an outcome")
        attempt.ended_at, attempt.outcome, attempt.outcome_event_id = (
            now,
            payload.outcome,
            payload.idempotency_key,
        )
        attempt.outcome_reason, attempt.technical_error_code = (
            payload.outcome_reason,
            payload.technical_error_code,
        )
        attempt.partial_context = (
            payload.partial_context if payload.outcome == OutreachOutcome.DROPPED else None
        )
        attempt.duration_seconds = max(0, int((now - attempt.started_at).total_seconds()))
        task.attempt_count += 1
        task.last_outcome, task.last_error_code = (
            payload.outcome.value,
            payload.technical_error_code,
        )
        campaign = await self.session.get(Campaign, task.campaign_id)
        configuration = await self.session.scalar(
            select(HospitalConfiguration).where(
                HospitalConfiguration.hospital_id == self.hospital_id
            )
        )
        if campaign is None or configuration is None:
            raise APIError(409, "configuration_required", "Campaign configuration is required")
        if payload.outcome in (OutreachOutcome.COMPLETED, OutreachOutcome.DECLINED):
            task.state, task.completed_at = OutreachTaskState.COMPLETED, now
        elif payload.outcome == OutreachOutcome.CALLBACK_REQUESTED:
            if payload.callback_at is None or payload.callback_at <= now:
                raise APIError(422, "invalid_callback", "Callback time must be in the future")
            callback = self._within_windows(payload.callback_at, configuration, campaign)
            if callback is None or callback > task.clinical_deadline:
                await self._manual(task, "RETRY_WINDOW_UNAVAILABLE")
            else:
                task.state, task.callback_at, task.next_eligible_at = (
                    OutreachTaskState.CALLBACK_SCHEDULED,
                    callback,
                    callback,
                )
                attempt.callback_requested_at = callback
                await add_audit_event(
                    self.session,
                    self.context,
                    self.hospital_id,
                    "OUTREACH_CALLBACK_SCHEDULED",
                    "OutreachTask",
                    task.id,
                )
        elif payload.outcome == OutreachOutcome.INVALID_NUMBER:
            await self._manual(task, "INVALID_NUMBER")
        elif payload.outcome in RETRYABLE:
            if task.attempt_count >= task.max_attempts:
                await self._manual(
                    task,
                    "MAX_RETRIES_EXCEEDED"
                    if payload.outcome != OutreachOutcome.TECHNICAL_FAILURE
                    else "TECHNICAL_FAILURE_EXHAUSTED",
                )
            else:
                delay = configuration.retry_initial_delay_minutes * (
                    configuration.retry_backoff_multiplier ** (task.attempt_count - 1)
                )
                retry_at = self._within_windows(
                    now + timedelta(minutes=float(delay)), configuration, campaign
                )
                if retry_at is None or retry_at > task.clinical_deadline:
                    await self._manual(task, "CLINICAL_WINDOW_EXPIRED")
                else:
                    task.state, task.next_eligible_at = OutreachTaskState.RETRY_SCHEDULED, retry_at
                    await add_audit_event(
                        self.session,
                        self.context,
                        self.hospital_id,
                        "OUTREACH_RETRY_SCHEDULED",
                        "OutreachTask",
                        task.id,
                        {"outcome": payload.outcome.value},
                    )
        await add_audit_event(
            self.session,
            self.context,
            self.hospital_id,
            "OUTREACH_OUTCOME_RECORDED",
            "OutreachTask",
            task.id,
            {"outcome": payload.outcome.value},
        )
        self._clear_work_lease(task)
        await self.session.commit()
        await self.session.refresh(task)
        return task

    async def attempts(self, task_id):
        await self._task(task_id)
        return list(
            await self.session.scalars(
                select(OutreachAttempt)
                .where(
                    OutreachAttempt.hospital_id == self.hospital_id,
                    OutreachAttempt.outreach_task_id == task_id,
                )
                .order_by(OutreachAttempt.attempt_number)
            )
        )

    async def manual_follow_ups(self):
        return list(
            await self.session.scalars(
                select(ManualFollowUp)
                .where(ManualFollowUp.hospital_id == self.hospital_id)
                .order_by(ManualFollowUp.created_at.desc())
            )
        )

    async def _task(self, task_id):
        task = await self.session.scalar(
            select(OutreachTask).where(
                OutreachTask.id == task_id, OutreachTask.hospital_id == self.hospital_id
            )
        )
        if task is None:
            raise APIError(404, "not_found", "Outreach task not found")
        return task

    async def _locked_task(self, task_id):
        task = await self.session.scalar(
            select(OutreachTask)
            .where(OutreachTask.id == task_id, OutreachTask.hospital_id == self.hospital_id)
            .with_for_update()
        )
        if task is None:
            raise APIError(404, "not_found", "Outreach task not found")
        return task

    async def _manual(self, task, reason: str) -> None:
        task.state, task.manual_follow_up_required = OutreachTaskState.MANUAL_FOLLOW_UP, True
        if (
            await self.session.scalar(
                select(ManualFollowUp.id).where(ManualFollowUp.outreach_task_id == task.id)
            )
            is None
        ):
            self.session.add(
                ManualFollowUp(
                    hospital_id=self.hospital_id,
                    patient_id=task.patient_id,
                    campaign_id=task.campaign_id,
                    outreach_task_id=task.id,
                    reason_code=reason,
                )
            )
            await add_audit_event(
                self.session,
                self.context,
                self.hospital_id,
                "MANUAL_FOLLOW_UP_CREATED",
                "OutreachTask",
                task.id,
                {"reason": reason},
            )

    @staticmethod
    def _clear_work_lease(task: OutreachTask) -> None:
        task.worker_id = None
        task.heartbeat_at = None
        task.processing_lease_expires_at = None
        task.reserved_at = None
        task.reservation_token = None
        task.reservation_expires_at = None

    @staticmethod
    def _within_windows(value: datetime, configuration, campaign) -> datetime | None:
        zone = ZoneInfo(configuration.timezone)
        local = value.astimezone(zone)
        for _ in range(8):
            starts = [configuration.calling_window_start, campaign.calling_window_start]
            ends = [configuration.calling_window_end, campaign.calling_window_end]
            start, end = max(starts), min(ends)
            if start >= end:
                return None
            candidate = (
                local.replace(
                    hour=start.hour, minute=start.minute, second=start.second, microsecond=0
                )
                if local.time() < start
                else local
            )
            if candidate.time() >= end:
                local = (local + timedelta(days=1)).replace(
                    hour=start.hour, minute=start.minute, second=start.second, microsecond=0
                )
                continue
            return candidate.astimezone(timezone.utc)
        return None
