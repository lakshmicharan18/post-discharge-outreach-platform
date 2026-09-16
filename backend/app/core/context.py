from dataclasses import dataclass
from typing import Annotated
from uuid import UUID

from fastapi import Depends, Header
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.database import get_session
from app.core.errors import APIError
from app.models.entities import Hospital, Role, User


@dataclass(frozen=True)
class RequestContext:
    user_id: UUID
    hospital_id: UUID | None
    role: Role

    def require_clinical_tenant(self) -> UUID:
        if (
            self.role not in (Role.HOSPITAL_ADMIN, Role.CAMPAIGN_MANAGER, Role.CLINICAL_REVIEWER)
            or self.hospital_id is None
        ):
            raise APIError(403, "clinical_access_denied", "Hospital clinical context is required")
        return self.hospital_id

    def require_platform_admin(self) -> None:
        if self.role != Role.PLATFORM_ADMIN:
            raise APIError(403, "forbidden", "Platform administrator role is required")


async def get_context(
    session: Annotated[AsyncSession, Depends(get_session)],
    x_dev_user_id: Annotated[UUID | None, Header()] = None,
) -> RequestContext:
    """Replace this dependency with verified authentication in a later milestone.

    The opt-in local adapter resolves role/tenant from the database, never headers.
    A user UUID is not a credential; do not expose this adapter on public networks.
    """
    if not get_settings().enable_dev_auth or x_dev_user_id is None:
        raise APIError(401, "authentication_required", "A verified identity is required")
    user = await session.get(User, x_dev_user_id)
    if user is None or not user.is_active:
        raise APIError(401, "invalid_identity", "Identity is unavailable")
    if user.hospital_id is not None:
        hospital = await session.get(Hospital, user.hospital_id)
        if hospital is None or hospital.status != "ACTIVE":
            raise APIError(403, "inactive_hospital", "Hospital is unavailable")
    return RequestContext(user.id, user.hospital_id, user.role)
