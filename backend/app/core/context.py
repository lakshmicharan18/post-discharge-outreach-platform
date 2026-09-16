from collections.abc import Callable
from dataclasses import dataclass
from typing import Annotated
from uuid import UUID

from fastapi import Depends
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_session
from app.core.errors import APIError
from app.models.entities import Role


@dataclass(frozen=True)
class CurrentUserContext:
    user_id: UUID
    hospital_id: UUID | None
    role: Role
    is_active: bool = True

    def require_roles(self, *roles: Role) -> None:
        if not self.is_active or self.role not in roles:
            raise APIError(403, "forbidden", "This operation is not permitted for your role")

    def require_clinical_tenant(self) -> UUID:
        self.require_roles(Role.HOSPITAL_ADMIN, Role.CAMPAIGN_MANAGER, Role.CLINICAL_REVIEWER)
        if self.hospital_id is None:
            raise APIError(403, "clinical_access_denied", "Hospital clinical context is required")
        return self.hospital_id

    def require_platform_admin(self) -> None:
        self.require_roles(Role.PLATFORM_ADMIN)


# Preserve the established service/repository interface.
RequestContext = CurrentUserContext
bearer = HTTPBearer(auto_error=False)


async def get_context(
    session: Annotated[AsyncSession, Depends(get_session)],
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer)],
) -> CurrentUserContext:
    from app.services.auth import AuthService

    if credentials is None:
        raise APIError(401, "authentication_required", "A bearer access token is required")
    return await AuthService(session).resolve_context(credentials.credentials)


def require_any_role(*roles: Role) -> Callable:
    async def guard(
        context: Annotated[CurrentUserContext, Depends(get_context)],
    ) -> CurrentUserContext:
        context.require_roles(*roles)
        return context

    return guard
