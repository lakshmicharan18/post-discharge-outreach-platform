from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.context import RequestContext
from app.core.errors import APIError
from app.models.entities import Hospital, Role
from app.models.healthcare import HospitalConfiguration
from app.repositories.configuration import HospitalConfigurationRepository
from app.schemas.healthcare import HospitalConfigurationUpdate
from app.services.audit import add_audit_event


class HospitalConfigurationService:
    def __init__(self, session: AsyncSession, context: RequestContext) -> None:
        self.session = session
        self.context = context
        self.repository = HospitalConfigurationRepository(session)

    def own_hospital_id(self) -> UUID:
        return self.context.require_clinical_tenant()

    async def get_own(self) -> HospitalConfiguration:
        return await self.repository.get(self.own_hospital_id())

    async def update_own(self, payload: HospitalConfigurationUpdate) -> HospitalConfiguration:
        self.context.require_roles(Role.HOSPITAL_ADMIN)
        return await self._update(self.own_hospital_id(), payload)

    async def get_platform(self, hospital_id: UUID) -> HospitalConfiguration:
        self.context.require_platform_admin()
        return await self.repository.get(hospital_id)

    async def update_platform(
        self, hospital_id: UUID, payload: HospitalConfigurationUpdate
    ) -> HospitalConfiguration:
        self.context.require_platform_admin()
        return await self._update(hospital_id, payload)

    async def _update(
        self, hospital_id: UUID, payload: HospitalConfigurationUpdate
    ) -> HospitalConfiguration:
        hospital = await self.session.get(Hospital, hospital_id)
        if hospital is None:
            raise APIError(404, "not_found", "Hospital not found")
        try:
            configuration = await self.repository.update(hospital_id, payload.model_dump())
            hospital.timezone = payload.timezone
            await add_audit_event(
                self.session,
                self.context,
                hospital_id,
                "HOSPITAL_CONFIGURATION_UPDATED",
                "HospitalConfiguration",
                configuration.id,
                {"is_ready": configuration.is_ready},
            )
            await self.session.commit()
            return configuration
        except Exception:
            await self.session.rollback()
            raise
