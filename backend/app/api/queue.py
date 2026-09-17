from datetime import datetime, timezone
from typing import Annotated

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.context import RequestContext, get_context
from app.core.database import get_session
from app.schemas.entities import ErrorResponse
from app.schemas.outreach import OutreachTaskResponse, QueueStatusResponse, StaleRecoveryResponse
from app.services.scheduler import QueueSchedulerService

router = APIRouter(
    prefix="/api/v1/queue",
    tags=["queue"],
    responses={code: {"model": ErrorResponse} for code in (401, 403, 404, 409, 422, 500)},
)
Session = Annotated[AsyncSession, Depends(get_session)]
Context = Annotated[RequestContext, Depends(get_context)]


@router.post("/reserve-next", response_model=OutreachTaskResponse | None)
async def reserve_next(session: Session, context: Context):
    return await QueueSchedulerService(session, context).reserve_next(datetime.now(timezone.utc))


@router.post("/reserve-available", response_model=list[OutreachTaskResponse])
async def reserve_available(
    session: Session,
    context: Context,
    limit: Annotated[int, Query(ge=1, le=100)] = 1,
):
    return await QueueSchedulerService(session, context).reserve_available(
        limit, datetime.now(timezone.utc)
    )


@router.post("/recover-stale", response_model=StaleRecoveryResponse)
async def recover_stale(
    session: Session,
    context: Context,
    limit: Annotated[int, Query(ge=1, le=100)] = 100,
):
    return await QueueSchedulerService(session, context).recover_stale(
        datetime.now(timezone.utc), limit
    )


@router.get("/status", response_model=QueueStatusResponse)
async def queue_status(session: Session, context: Context):
    return await QueueSchedulerService(session, context).status(datetime.now(timezone.utc))
