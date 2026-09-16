from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.context import RequestContext, get_context
from app.core.database import get_session
from app.schemas.outreach import (
    ManualFollowUpResponse,
    OutcomeRequest,
    OutreachAttemptResponse,
    OutreachTaskResponse,
    StartCallRequest,
)
from app.services.outcomes import OutcomeService
from app.services.outreach import OutreachWorkService

router = APIRouter(prefix="/api/v1/outreach-tasks", tags=["outreach-tasks"])
Session = Annotated[AsyncSession, Depends(get_session)]
Context = Annotated[RequestContext, Depends(get_context)]


@router.get("/manual-follow-ups", response_model=list[ManualFollowUpResponse])
async def list_manual_follow_ups(session: Session, context: Context):
    return await OutcomeService(session, context).manual_follow_ups()


@router.get("/{task_id}", response_model=OutreachTaskResponse)
async def get_outreach_task(task_id: UUID, session: Session, context: Context):
    return await OutreachWorkService(session, context).get(task_id)


@router.post("/{task_id}/start-call", response_model=OutreachAttemptResponse)
async def start_call(task_id: UUID, payload: StartCallRequest, session: Session, context: Context):
    from datetime import datetime, timezone

    return await OutcomeService(session, context).start(
        task_id, datetime.now(timezone.utc), payload.provider_call_id
    )


@router.post("/{task_id}/outcome", response_model=OutreachTaskResponse)
async def record_outcome(
    task_id: UUID, payload: OutcomeRequest, session: Session, context: Context
):
    from datetime import datetime, timezone

    return await OutcomeService(session, context).process(
        task_id, payload, datetime.now(timezone.utc)
    )


@router.get("/{task_id}/attempts", response_model=list[OutreachAttemptResponse])
async def list_attempts(task_id: UUID, session: Session, context: Context):
    return await OutcomeService(session, context).attempts(task_id)
