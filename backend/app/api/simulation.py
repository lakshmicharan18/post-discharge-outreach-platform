from datetime import datetime, timezone
from typing import Annotated

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.context import RequestContext, get_context
from app.core.database import get_session
from app.schemas.outreach import OutreachTaskResponse
from app.services.simulation import SimulationService

router = APIRouter(prefix="/api/v1/simulation", tags=["simulation"])
Session = Annotated[AsyncSession, Depends(get_session)]
Context = Annotated[RequestContext, Depends(get_context)]


@router.post("/step", response_model=OutreachTaskResponse | None)
async def step(session: Session, context: Context):
    return await SimulationService(session, context).step()

@router.post("/setup")
async def setup(session: Session, context: Context): return await SimulationService(session, context).setup()
@router.post("/advance-time")
async def advance_time(session: Session, context: Context, minutes: int = Query(ge=1, le=1440)): return await SimulationService(session, context).advance(minutes)
@router.get("/status")
async def status(session: Session, context: Context): return await SimulationService(session, context).status()
@router.get("/events")
async def events(session: Session, context: Context): return (await SimulationService(session, context).status())["events"]
