from typing import Generic
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.context import RequestContext
from app.core.errors import APIError
from app.models.entities import Discharge, Encounter, Patient, Role
from app.repositories.clinical import ClinicalModel, ClinicalRepository
from app.schemas.entities import DischargeCreate, EncounterCreate, PatientCreate


class ClinicalService(Generic[ClinicalModel]):
    def __init__(self, session: AsyncSession, context: RequestContext, model: type[ClinicalModel]):
        self.repository = ClinicalRepository(session, context, model)
        self.session, self.context, self.model = session, context, model

    async def get(self, identifier: UUID) -> ClinicalModel:
        return await self.repository.get(identifier)

    async def list(self, limit: int, offset: int) -> list[ClinicalModel]:
        return await self.repository.list(limit, offset)

    async def create(
        self, payload: PatientCreate | EncounterCreate | DischargeCreate
    ) -> ClinicalModel:
        self.context.require_roles(Role.HOSPITAL_ADMIN)
        if self.model in (Encounter, Discharge):
            await ClinicalRepository(self.session, self.context, Patient).get(payload.patient_id)
        if self.model is Discharge:
            encounter = await ClinicalRepository(self.session, self.context, Encounter).get(
                payload.encounter_id
            )
            if encounter.patient_id != payload.patient_id:
                raise APIError(
                    422, "invalid_relationship", "Encounter does not belong to the patient"
                )
        try:
            record = await self.repository.create(payload.model_dump())
            await self.session.commit()
            return record
        except Exception:
            await self.session.rollback()
            raise
