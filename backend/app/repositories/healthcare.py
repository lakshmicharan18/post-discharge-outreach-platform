from typing import Generic, TypeVar
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.context import RequestContext
from app.core.errors import APIError
from app.models.entities import Discharge, Encounter, Patient, Role
from app.models.healthcare import CarePlan, Condition, Medication, Observation, Procedure

HealthcareModel = TypeVar(
    "HealthcareModel", Condition, Observation, Medication, CarePlan, Procedure
)


class HealthcareRepository(Generic[HealthcareModel]):
    """Tenant-scoped access to simplified healthcare resources."""

    def __init__(
        self, session: AsyncSession, context: RequestContext, model: type[HealthcareModel]
    ) -> None:
        self.session = session
        self.context = context
        self.hospital_id = context.require_clinical_tenant()
        self.model = model

    async def get(self, identifier: UUID) -> HealthcareModel:
        record = await self.session.scalar(
            select(self.model).where(
                self.model.hospital_id == self.hospital_id, self.model.id == identifier
            )
        )
        if record is None:
            raise APIError(404, "not_found", "Record not found")
        return record

    async def list_for_patient(self, patient_id: UUID) -> list[HealthcareModel]:
        await self.require_patient(patient_id)
        return list(
            await self.session.scalars(
                select(self.model)
                .where(
                    self.model.hospital_id == self.hospital_id,
                    self.model.patient_id == patient_id,
                )
                .order_by(self.model.created_at, self.model.id)
            )
        )

    async def create(self, patient_id: UUID, values: dict) -> HealthcareModel:
        self.context.require_roles(Role.HOSPITAL_ADMIN)
        await self.require_patient(patient_id)
        encounter_id = values.get("encounter_id")
        if encounter_id is not None:
            await self.require_encounter(patient_id, encounter_id)
        record = self.model(**{**values, "hospital_id": self.hospital_id, "patient_id": patient_id})
        self.session.add(record)
        await self.session.flush()
        await self.session.refresh(record)
        return record

    async def require_patient(self, patient_id: UUID) -> Patient:
        patient = await self.session.scalar(
            select(Patient).where(Patient.hospital_id == self.hospital_id, Patient.id == patient_id)
        )
        if patient is None:
            raise APIError(404, "not_found", "Patient not found")
        return patient

    async def require_encounter(self, patient_id: UUID, encounter_id: UUID) -> Encounter:
        encounter = await self.session.scalar(
            select(Encounter).where(
                Encounter.hospital_id == self.hospital_id,
                Encounter.patient_id == patient_id,
                Encounter.id == encounter_id,
            )
        )
        if encounter is None:
            raise APIError(404, "not_found", "Encounter not found")
        return encounter


class PatientContextRepository:
    def __init__(self, session: AsyncSession, context: RequestContext) -> None:
        self.session = session
        self.context = context
        self.hospital_id = context.require_clinical_tenant()

    async def patient(self, patient_id: UUID) -> Patient:
        return await HealthcareRepository(self.session, self.context, Condition).require_patient(
            patient_id
        )

    async def encounters(self, patient_id: UUID) -> list[Encounter]:
        await self.patient(patient_id)
        return list(
            await self.session.scalars(
                select(Encounter)
                .where(
                    Encounter.hospital_id == self.hospital_id,
                    Encounter.patient_id == patient_id,
                )
                .order_by(Encounter.admit_at, Encounter.id)
            )
        )

    async def discharges(self, patient_id: UUID) -> list[Discharge]:
        await self.patient(patient_id)
        return list(
            await self.session.scalars(
                select(Discharge)
                .where(
                    Discharge.hospital_id == self.hospital_id,
                    Discharge.patient_id == patient_id,
                )
                .order_by(Discharge.discharge_at, Discharge.id)
            )
        )
