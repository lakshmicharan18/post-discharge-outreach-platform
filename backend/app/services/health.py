from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.schemas.entities import HealthResponse


async def check_health(session: AsyncSession) -> HealthResponse:
    await session.execute(text("SELECT 1"))
    return HealthResponse()
