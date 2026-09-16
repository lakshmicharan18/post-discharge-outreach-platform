from sqlalchemy.ext.asyncio import AsyncSession
from starlette.concurrency import run_in_threadpool

from app.core.config import get_settings
from app.core.context import CurrentUserContext
from app.core.errors import APIError
from app.core.security import create_access_token, decode_access_token, verify_password
from app.models.entities import Hospital, User
from app.repositories.identity import IdentityRepository
from app.schemas.auth import CurrentUserResponse, LoginRequest, LoginResponse


class AuthService:
    def __init__(self, session: AsyncSession) -> None:
        self.repository = IdentityRepository(session)

    async def active_hospital(self, user: User) -> Hospital | None:
        if user.hospital_id is None:
            return None
        hospital = await self.repository.hospital(user.hospital_id)
        if hospital is None or hospital.status != "ACTIVE":
            raise APIError(403, "inactive_hospital", "Hospital is unavailable")
        return hospital

    async def login(self, payload: LoginRequest) -> LoginResponse:
        user = await self.repository.by_email(payload.email)
        valid = await run_in_threadpool(
            verify_password,
            payload.password.get_secret_value(),
            user.password_hash if user else None,
        )
        if not valid or user is None or not user.is_active:
            raise APIError(401, "invalid_credentials", "Invalid email or password")
        hospital = await self.active_hospital(user)
        return LoginResponse(
            access_token=create_access_token(user.id),
            expires_in=get_settings().jwt_access_token_expire_minutes * 60,
            user=self.user_response(user, hospital),
        )

    async def resolve_context(self, token: str) -> CurrentUserContext:
        user = await self.repository.by_id(decode_access_token(token))
        if user is None or not user.is_active or user.password_hash is None:
            raise APIError(401, "invalid_identity", "Identity is unavailable")
        await self.active_hospital(user)
        # Re-read role and tenant on every request; token/header claims cannot override them.
        return CurrentUserContext(user.id, user.hospital_id, user.role, user.is_active)

    async def current_user(self, context: CurrentUserContext) -> CurrentUserResponse:
        user = await self.repository.by_id(context.user_id)
        if user is None or not user.is_active:
            raise APIError(401, "invalid_identity", "Identity is unavailable")
        return self.user_response(user, await self.active_hospital(user))

    @staticmethod
    def user_response(user: User, hospital: Hospital | None) -> CurrentUserResponse:
        result = CurrentUserResponse.model_validate(user)
        if hospital is not None:
            from app.schemas.entities import HospitalResponse

            result.hospital = HospitalResponse.model_validate(hospital)
        return result
