from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import APIError
from app.models.healthcare import HospitalConfiguration


class HospitalConfigurationRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get(self, hospital_id: UUID) -> HospitalConfiguration:
        configuration = await self.session.scalar(
            select(HospitalConfiguration).where(HospitalConfiguration.hospital_id == hospital_id)
        )
        if configuration is None:
            raise APIError(404, "not_found", "Hospital configuration not found")
        return configuration

    async def update(self, hospital_id: UUID, values: dict) -> HospitalConfiguration:
        configuration = await self.get(hospital_id)
        for field, value in values.items():
            setattr(configuration, field, value)
        await self.session.flush()
        await self.session.refresh(configuration)
        return configuration
