from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.context import RequestContext
from app.models.entities import Hospital


class HospitalRepository:
    """Platform scope includes hospital metadata only, never clinical records."""

    def __init__(self, session: AsyncSession, context: RequestContext):
        context.require_platform_admin()
        self.session = session

    async def list(self, limit: int, offset: int) -> list[Hospital]:
        return list(
            await self.session.scalars(
                select(Hospital).order_by(Hospital.code).limit(limit).offset(offset)
            )
        )

    async def create(self, values: dict) -> Hospital:
        hospital = Hospital(**values)
        self.session.add(hospital)
        await self.session.flush()
        await self.session.refresh(hospital)
        return hospital
