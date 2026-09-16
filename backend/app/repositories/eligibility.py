from collections import defaultdict
from dataclasses import dataclass
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.context import RequestContext
from app.core.errors import APIError
from app.models.entities import Discharge, Encounter, Patient
from app.models.healthcare import Condition


@dataclass(frozen=True)
class EligibilityCandidate:
    patient: Patient
    discharge: Discharge
    encounter: Encounter
    condition_codes: frozenset[str]


class EligibilityRepository:
    """Reads the current tenant's discharge graph for dynamic eligibility evaluation."""

    def __init__(self, session: AsyncSession, context: RequestContext) -> None:
        self.session = session
        self.hospital_id = context.require_clinical_tenant()

    async def candidates(self, patient_id: UUID | None = None) -> list[EligibilityCandidate]:
        if patient_id is not None:
            patient = await self.session.scalar(
                select(Patient).where(
                    Patient.id == patient_id, Patient.hospital_id == self.hospital_id
                )
            )
            if patient is None:
                raise APIError(404, "not_found", "Patient not found")
        statement = (
            select(Discharge, Patient, Encounter)
            .join(
                Patient,
                (Patient.id == Discharge.patient_id)
                & (Patient.hospital_id == Discharge.hospital_id),
            )
            .join(
                Encounter,
                (Encounter.id == Discharge.encounter_id)
                & (Encounter.patient_id == Discharge.patient_id)
                & (Encounter.hospital_id == Discharge.hospital_id),
            )
            .where(Discharge.hospital_id == self.hospital_id)
            .order_by(Discharge.discharge_at.desc(), Discharge.id)
        )
        if patient_id is not None:
            statement = statement.where(Discharge.patient_id == patient_id)
        records = list((await self.session.execute(statement)).all())
        patient_ids = [patient.id for _, patient, _ in records]
        codes: dict[UUID, set[str]] = defaultdict(set)
        if patient_ids:
            condition_rows = await self.session.execute(
                select(Condition.patient_id, Condition.code).where(
                    Condition.hospital_id == self.hospital_id,
                    Condition.patient_id.in_(patient_ids),
                )
            )
            for condition_patient_id, code in condition_rows:
                codes[condition_patient_id].add(code)
        return [
            EligibilityCandidate(patient, discharge, encounter, frozenset(codes[patient.id]))
            for discharge, patient, encounter in records
        ]
