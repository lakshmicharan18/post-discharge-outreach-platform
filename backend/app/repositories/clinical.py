from typing import Generic, TypeVar
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.context import RequestContext
from app.core.errors import APIError
from app.models.entities import Discharge, Encounter, Patient, Role

ClinicalModel = TypeVar("ClinicalModel", Patient, Encounter, Discharge)


class ClinicalRepository(Generic[ClinicalModel]):
    """All clinical access requires a tenant. There is no unscoped/admin mode."""

    def __init__(self, session: AsyncSession, context: RequestContext, model: type[ClinicalModel]):
        self.hospital_id = context.require_clinical_tenant()
        self.context = context
        self.session = session
        self.model = model

    async def get(self, identifier: UUID) -> ClinicalModel:
        result = await self.session.scalar(
            select(self.model).where(
                self.model.hospital_id == self.hospital_id, self.model.id == identifier
            )
        )
        if result is None:
            raise APIError(404, "not_found", "Record not found")
        return result

    async def list(self, limit: int = 50, offset: int = 0) -> list[ClinicalModel]:
        result = await self.session.scalars(
            select(self.model)
            .where(self.model.hospital_id == self.hospital_id)
            .order_by(self.model.id)
            .limit(limit)
            .offset(offset)
        )
        return list(result)

    async def create(self, values: dict) -> ClinicalModel:
        self.context.require_roles(Role.HOSPITAL_ADMIN)
        # Assign the tenant here even if a future caller supplies one incorrectly.
        record = self.model(**{**values, "hospital_id": self.hospital_id})
        self.session.add(record)
        await self.session.flush()
        await self.session.refresh(record)
        return record
