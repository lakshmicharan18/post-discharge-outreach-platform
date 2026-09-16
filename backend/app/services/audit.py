from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.context import RequestContext
from app.models.healthcare import AuditEvent


async def add_audit_event(
    session: AsyncSession,
    context: RequestContext,
    hospital_id: UUID,
    action: str,
    resource_type: str,
    resource_id: UUID | None,
    details: dict | None = None,
) -> AuditEvent:
    event = AuditEvent(
        hospital_id=hospital_id,
        actor_user_id=context.user_id,
        action=action,
        resource_type=resource_type,
        resource_id=resource_id,
        details=details or {},
    )
    session.add(event)
    await session.flush()
    return event
