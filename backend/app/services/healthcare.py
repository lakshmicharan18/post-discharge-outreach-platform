from typing import Generic
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.context import RequestContext
from app.models.entities import Role
from app.models.healthcare import CarePlan, Condition, Medication, Observation, Procedure
from app.repositories.healthcare import (
    HealthcareModel,
    HealthcareRepository,
    PatientContextRepository,
)
from app.schemas.healthcare import (
    CarePlanCreate,
    ConditionCreate,
    MedicationCreate,
    ObservationCreate,
    PatientContextResponse,
    ProcedureCreate,
    TimelineEvent,
)

ResourceCreate = (
    ConditionCreate | ObservationCreate | MedicationCreate | CarePlanCreate | ProcedureCreate
)


class HealthcareService(Generic[HealthcareModel]):
    def __init__(
        self, session: AsyncSession, context: RequestContext, model: type[HealthcareModel]
    ) -> None:
        self.session = session
        self.context = context
        self.repository = HealthcareRepository(session, context, model)

    async def get(self, identifier: UUID) -> HealthcareModel:
        return await self.repository.get(identifier)

    async def list_for_patient(self, patient_id: UUID) -> list[HealthcareModel]:
        return await self.repository.list_for_patient(patient_id)

    async def create(self, patient_id: UUID, payload: ResourceCreate) -> HealthcareModel:
        self.context.require_roles(Role.HOSPITAL_ADMIN)
        try:
            record = await self.repository.create(patient_id, payload.model_dump())
            await self.session.commit()
            return record
        except Exception:
            await self.session.rollback()
            raise


class PatientContextService:
    def __init__(self, session: AsyncSession, context: RequestContext) -> None:
        self.session = session
        self.request_context = context
        self.repository = PatientContextRepository(session, context)

    async def timeline(self, patient_id: UUID) -> list[TimelineEvent]:
        encounters = await self.repository.encounters(patient_id)
        discharges = await self.repository.discharges(patient_id)
        observations = await HealthcareRepository(
            self.session, self.request_context, Observation
        ).list_for_patient(patient_id)
        medications = await HealthcareRepository(
            self.session, self.request_context, Medication
        ).list_for_patient(patient_id)
        care_plans = await HealthcareRepository(
            self.session, self.request_context, CarePlan
        ).list_for_patient(patient_id)
        procedures = await HealthcareRepository(
            self.session, self.request_context, Procedure
        ).list_for_patient(patient_id)
        events: list[TimelineEvent] = []
        for record in encounters:
            events.append(
                TimelineEvent(
                    occurred_at=record.admit_at,
                    event_type="ENCOUNTER_ADMISSION",
                    resource_id=record.id,
                    title=f"{record.care_setting} encounter",
                )
            )
        for record in observations:
            events.append(
                TimelineEvent(
                    occurred_at=record.observed_at,
                    event_type="OBSERVATION",
                    resource_id=record.id,
                    title=record.display_name,
                    summary=f"{record.value} {record.unit or ''}".strip(),
                )
            )
        for record in procedures:
            if record.performed_at:
                events.append(
                    TimelineEvent(
                        occurred_at=record.performed_at,
                        event_type="PROCEDURE",
                        resource_id=record.id,
                        title=record.name,
                    )
                )
        for record in medications:
            if record.started_at:
                events.append(
                    TimelineEvent(
                        occurred_at=record.started_at,
                        event_type="MEDICATION",
                        resource_id=record.id,
                        title=record.medication_name,
                        summary=record.status,
                    )
                )
        for record in care_plans:
            if record.start_at:
                events.append(
                    TimelineEvent(
                        occurred_at=record.start_at,
                        event_type="CARE_PLAN",
                        resource_id=record.id,
                        title=record.title,
                        summary=record.status,
                    )
                )
        for record in discharges:
            events.append(
                TimelineEvent(
                    occurred_at=record.discharge_at,
                    event_type="DISCHARGE",
                    resource_id=record.id,
                    title="Discharged",
                    summary=f"{record.risk_level} risk",
                )
            )
        return sorted(
            events, key=lambda event: (event.occurred_at, event.event_type, str(event.resource_id))
        )

    async def context(self, patient_id: UUID) -> PatientContextResponse:
        patient = await self.repository.patient(patient_id)
        encounters = await self.repository.encounters(patient_id)
        discharges = await self.repository.discharges(patient_id)
        resources = {}
        for name, model in (
            ("conditions", Condition),
            ("observations", Observation),
            ("medications", Medication),
            ("care_plans", CarePlan),
            ("procedures", Procedure),
        ):
            resources[name] = await HealthcareRepository(
                self.session, self.request_context, model
            ).list_for_patient(patient_id)
        return PatientContextResponse(
            patient=patient,
            encounters=encounters,
            discharges=discharges,
            timeline=await self.timeline(patient_id),
            **resources,
        )
