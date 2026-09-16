from sqlalchemy.ext.asyncio import AsyncSession
from starlette.concurrency import run_in_threadpool

from app.core.context import RequestContext
from app.core.errors import APIError
from app.core.security import hash_password
from app.models.entities import Role, User
from app.repositories.users import UserRepository
from app.schemas.auth import UserCreate


class UserService:
    def __init__(self, session: AsyncSession, context: RequestContext) -> None:
        self.repository = UserRepository(session, context)
        self.session = session

    async def list(self, limit: int, offset: int) -> list[User]:
        return await self.repository.list(limit, offset)

    async def create(self, payload: UserCreate) -> User:
        if payload.role == Role.PLATFORM_ADMIN:
            raise APIError(403, "forbidden", "Hospital administrators cannot create platform users")
        encoded = await run_in_threadpool(hash_password, payload.password.get_secret_value())
        try:
            user = await self.repository.create(
                payload.email, payload.full_name, payload.role, encoded
            )
            await self.session.commit()
            return user
        except Exception:
            await self.session.rollback()
            raise
