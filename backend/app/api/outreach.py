from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.context import RequestContext, get_context
from app.core.database import get_session
from app.schemas.outreach import OutreachTaskResponse
from app.services.outreach import OutreachWorkService

router = APIRouter(prefix="/api/v1/outreach-tasks", tags=["outreach-tasks"])
Session = Annotated[AsyncSession, Depends(get_session)]
Context = Annotated[RequestContext, Depends(get_context)]


@router.get("/{task_id}", response_model=OutreachTaskResponse)
async def get_outreach_task(task_id: UUID, session: Session, context: Context):
    return await OutreachWorkService(session, context).get(task_id)
