from typing import Annotated

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.context import RequestContext, get_context
from app.core.database import get_session
from app.services.simulation import SimulationService

router = APIRouter(prefix="/api/v1/simulation", tags=["simulation"])
Session = Annotated[AsyncSession, Depends(get_session)]
Context = Annotated[RequestContext, Depends(get_context)]


def run_response(run):
    return {
        "id": run.id,
        "scenario_name": run.scenario_name,
        "simulated_now": run.simulated_now,
        "configured_capacity": run.configured_capacity,
    }


@router.post("/initialize")
async def initialize(session: Session, context: Context):
    return run_response(await SimulationService(session, context).initialize())


@router.post("/reset")
async def reset(session: Session, context: Context):
    return run_response(await SimulationService(session, context).reset())


@router.post("/advance-time")
async def advance_time(session: Session, context: Context, minutes: int = Query(ge=1, le=1440)):
    return run_response(await SimulationService(session, context).advance_clock(minutes))


@router.get("/status")
async def status(session: Session, context: Context):
    return run_response(await SimulationService(session, context).get_run())
