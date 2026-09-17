"""Durable deterministic-scenario setup and controllable simulation clock."""

from datetime import date, datetime, timedelta

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.context import RequestContext
from app.core.errors import APIError
from app.models.campaigns import (
    Campaign,
    CampaignStatus,
    ManualFollowUp,
    OutreachAttempt,
    OutreachTask,
    OutreachTaskState,
    SimulationEvent,
    SimulationRun,
    SimulationRunStatus,
)
from app.models.entities import Discharge, Encounter, Patient, Role
from app.models.healthcare import HospitalConfiguration
from app.schemas.eligibility import EligibilityResult
from app.services.priority import score_outreach_task
from app.services.simulation_scenario import (
    SCENARIO_CAPACITY,
    SCENARIO_NAME,
    SCENARIO_PATIENTS,
    SCENARIO_START_ISO,
    scenario_payload,
)

MUTATION_ROLES = (Role.HOSPITAL_ADMIN, Role.CAMPAIGN_MANAGER)
SCENARIO_PREFIX = "SIM-25-"


class SimulationClock:
    @staticmethod
    def current_time(run: SimulationRun) -> datetime:
        return run.simulated_now

    @staticmethod
    def advance(run: SimulationRun, minutes: int) -> datetime:
        if minutes < 1:
            raise APIError(422, "invalid_clock_advance", "Minutes must be positive")
        run.simulated_now += timedelta(minutes=minutes)
        return run.simulated_now


class SimulationService:
    def __init__(self, session: AsyncSession, context: RequestContext) -> None:
        self.session, self.context = session, context
        self.hospital_id = context.require_clinical_tenant()

    async def initialize(self) -> SimulationRun:
        self.context.require_roles(*MUTATION_ROLES)
        try:
            await self._reset_scenario_data()
            start = datetime.fromisoformat(SCENARIO_START_ISO)
            configuration = await self.session.scalar(
                select(HospitalConfiguration).where(
                    HospitalConfiguration.hospital_id == self.hospital_id
                )
            )
            if configuration is None:
                raise APIError(409, "configuration_required", "Hospital configuration is required")
            configuration.max_concurrent_calls = SCENARIO_CAPACITY
            campaign = Campaign(
                hospital_id=self.hospital_id,
                name="Deterministic simulation campaign",
                description="Synthetic fixed 25-patient demonstration.",
                status=CampaignStatus.READY,
                start_at=start,
                clinical_follow_up_hours=72,
                calling_window_start=configuration.calling_window_start,
                calling_window_end=configuration.calling_window_end,
                campaign_priority=50,
                max_retries=2,
                outbound_capacity=SCENARIO_CAPACITY,
                escalation_configuration={},
                eligibility_criteria={
                    "discharge_status": "PENDING",
                    "communication_eligible": True,
                },
                created_by_user_id=self.context.user_id,
            )
            self.session.add(campaign)
            await self.session.flush()
            for index, definition in enumerate(SCENARIO_PATIENTS, 1):
                await self._create_scenario_task(campaign, definition, index, start)
            run = SimulationRun(
                hospital_id=self.hospital_id,
                status=SimulationRunStatus.READY,
                scenario_name=SCENARIO_NAME,
                simulated_now=start,
                step_count=0,
                configured_capacity=SCENARIO_CAPACITY,
                started_at=start,
                created_by_user_id=self.context.user_id,
            )
            self.session.add(run)
            await self.session.flush()
            self.session.add(
                SimulationEvent(
                    hospital_id=self.hospital_id,
                    simulation_run_id=run.id,
                    sequence_number=1,
                    event_type="SCENARIO_INITIALIZED",
                    simulated_at=start,
                    campaign_id=campaign.id,
                    safe_payload={
                        "scenario_name": SCENARIO_NAME,
                        "patient_count": len(SCENARIO_PATIENTS),
                        "configured_capacity": SCENARIO_CAPACITY,
                        "patients": scenario_payload(),
                    },
                )
            )
            await self.session.commit()
            await self.session.refresh(run)
            return run
        except Exception:
            await self.session.rollback()
            raise

    async def reset(self) -> SimulationRun:
        return await self.initialize()

    async def get_run(self) -> SimulationRun:
        run = await self.session.scalar(
            select(SimulationRun)
            .where(
                SimulationRun.hospital_id == self.hospital_id,
                SimulationRun.scenario_name == SCENARIO_NAME,
            )
            .order_by(SimulationRun.created_at.desc())
        )
        if run is None:
            raise APIError(404, "not_found", "Simulation has not been initialized")
        return run

    async def advance_clock(self, minutes: int) -> SimulationRun:
        self.context.require_roles(*MUTATION_ROLES)
        try:
            run = await self.get_run()
            now = SimulationClock.advance(run, minutes)
            sequence = (
                await self.session.scalar(
                    select(SimulationEvent.sequence_number)
                    .where(SimulationEvent.simulation_run_id == run.id)
                    .order_by(SimulationEvent.sequence_number.desc())
                    .limit(1)
                )
                or 0
            ) + 1
            self.session.add(
                SimulationEvent(
                    hospital_id=self.hospital_id,
                    simulation_run_id=run.id,
                    sequence_number=sequence,
                    event_type="TIME_ADVANCED",
                    simulated_at=now,
                    safe_payload={"minutes": minutes},
                )
            )
            await self.session.commit()
            await self.session.refresh(run)
            return run
        except Exception:
            await self.session.rollback()
            raise

    async def _create_scenario_task(
        self, campaign, definition, index: int, start: datetime
    ) -> None:
        patient = Patient(
            hospital_id=self.hospital_id,
            external_patient_id=f"{SCENARIO_PREFIX}{definition.scenario_key}",
            first_name="Synthetic",
            last_name=f"Patient {index:02d}",
            date_of_birth=date(1980, 1, 1),
            phone=f"+1555000{index:04d}",
            communication_preferences={"phone": True},
        )
        self.session.add(patient)
        await self.session.flush()
        discharge_at = start + timedelta(hours=definition.discharge_offset_hours)
        encounter = Encounter(
            hospital_id=self.hospital_id,
            patient_id=patient.id,
            external_encounter_id=f"{SCENARIO_PREFIX}E-{definition.scenario_key}",
            care_setting="INPATIENT",
            admit_at=discharge_at - timedelta(days=2),
            discharge_at=discharge_at,
            status="DISCHARGED",
        )
        self.session.add(encounter)
        await self.session.flush()
        deadline = start + timedelta(minutes=definition.deadline_offset_minutes)
        discharge = Discharge(
            hospital_id=self.hospital_id,
            patient_id=patient.id,
            encounter_id=encounter.id,
            discharge_at=discharge_at,
            follow_up_deadline=deadline,
            discharge_instructions="Synthetic simulation data only.",
            risk_level=definition.risk,
            source_reference=f"{SCENARIO_PREFIX}D-{definition.scenario_key}",
        )
        self.session.add(discharge)
        await self.session.flush()
        result = EligibilityResult(
            patient_id=patient.id,
            discharge_id=discharge.id,
            campaign_id=campaign.id,
            eligible=True,
            reasons=[],
            evaluated_at=start,
            follow_up_deadline=deadline,
            risk_level=definition.risk,
            care_setting=encounter.care_setting,
        )
        components = score_outreach_task(campaign, result, now=start, eligible_at=start)
        self.session.add(
            OutreachTask(
                hospital_id=self.hospital_id,
                campaign_id=campaign.id,
                patient_id=patient.id,
                discharge_id=discharge.id,
                state=OutreachTaskState.PENDING,
                priority_score=components["total"],
                priority_components=components,
                attempt_count=0,
                max_attempts=len(definition.outcomes),
                eligible_at=start,
                next_eligible_at=start,
                clinical_deadline=deadline,
                manual_follow_up_required=False,
            )
        )

    async def _reset_scenario_data(self) -> None:
        patient_ids = select(Patient.id).where(
            Patient.hospital_id == self.hospital_id,
            Patient.external_patient_id.like(f"{SCENARIO_PREFIX}%"),
        )
        task_ids = select(OutreachTask.id).where(OutreachTask.patient_id.in_(patient_ids))
        await self.session.execute(
            delete(ManualFollowUp).where(ManualFollowUp.outreach_task_id.in_(task_ids))
        )
        await self.session.execute(
            delete(OutreachAttempt).where(OutreachAttempt.outreach_task_id.in_(task_ids))
        )
        await self.session.execute(
            delete(OutreachTask).where(OutreachTask.patient_id.in_(patient_ids))
        )
        run_ids = select(SimulationRun.id).where(
            SimulationRun.hospital_id == self.hospital_id,
            SimulationRun.scenario_name == SCENARIO_NAME,
        )
        await self.session.execute(
            delete(SimulationEvent).where(SimulationEvent.simulation_run_id.in_(run_ids))
        )
        await self.session.execute(delete(SimulationRun).where(SimulationRun.id.in_(run_ids)))
        await self.session.execute(
            delete(Campaign).where(
                Campaign.hospital_id == self.hospital_id,
                Campaign.name == "Deterministic simulation campaign",
            )
        )
        await self.session.execute(delete(Discharge).where(Discharge.patient_id.in_(patient_ids)))
        await self.session.execute(delete(Encounter).where(Encounter.patient_id.in_(patient_ids)))
        await self.session.execute(delete(Patient).where(Patient.id.in_(patient_ids)))
