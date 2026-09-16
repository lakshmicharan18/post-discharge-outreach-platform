from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.entities import Hospital, User


class IdentityRepository:
    """Global identity lookup only; never exposes a cross-tenant user list."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def by_email(self, email: str) -> User | None:
        return await self.session.scalar(
            select(User).where(func.lower(User.email) == email.lower())
        )

    async def by_id(self, user_id: UUID) -> User | None:
        return await self.session.get(User, user_id, populate_existing=True)

    async def hospital(self, hospital_id: UUID) -> Hospital | None:
        return await self.session.get(Hospital, hospital_id, populate_existing=True)
