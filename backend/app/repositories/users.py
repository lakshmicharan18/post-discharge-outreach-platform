from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.context import RequestContext
from app.models.entities import Role, User


class UserRepository:
    def __init__(self, session: AsyncSession, context: RequestContext) -> None:
        context.require_roles(Role.HOSPITAL_ADMIN)
        self.hospital_id = context.require_clinical_tenant()
        self.session = session

    async def list(self, limit: int, offset: int) -> list[User]:
        return list(
            await self.session.scalars(
                select(User)
                .where(User.hospital_id == self.hospital_id)
                .order_by(User.id)
                .limit(limit)
                .offset(offset)
            )
        )

    async def create(self, email: str, full_name: str, role: Role, password_hash: str) -> User:
        if role == Role.PLATFORM_ADMIN:
            from app.core.errors import APIError

            raise APIError(403, "forbidden", "Hospital administrators cannot create platform users")
        user = User(
            hospital_id=self.hospital_id,
            email=email,
            full_name=full_name,
            role=role,
            password_hash=password_hash,
            is_active=True,
        )
        self.session.add(user)
        await self.session.flush()
        await self.session.refresh(user)
        return user
