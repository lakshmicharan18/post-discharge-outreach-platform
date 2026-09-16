from sqlalchemy.ext.asyncio import AsyncSession

from app.core.context import RequestContext
from app.models.entities import Hospital
from app.repositories.platform import HospitalRepository
from app.schemas.entities import HospitalCreate


class HospitalService:
    def __init__(self, session: AsyncSession, context: RequestContext):
        self.repository = HospitalRepository(session, context)
        self.session = session

    async def list(self, limit: int, offset: int) -> list[Hospital]:
        return await self.repository.list(limit, offset)

    async def create(self, payload: HospitalCreate) -> Hospital:
        try:
            hospital = await self.repository.create(payload.model_dump())
            await self.session.commit()
            return hospital
        except Exception:
            await self.session.rollback()
            raise
