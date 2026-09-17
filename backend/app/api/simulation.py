from typing import Annotated
from uuid import UUID

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


@router.post("/{run_id}/step")
async def step(run_id: UUID, session: Session, context: Context):
    return await SimulationService(session, context).step(run_id)


@router.post("/{run_id}/advance-next")
async def advance_next(run_id: UUID, session: Session, context: Context):
    return await SimulationService(session, context).advance_to_next(run_id)


@router.post("/{run_id}/run")
async def run(
    run_id: UUID, session: Session, context: Context, max_cycles: int = Query(200, ge=1, le=1000)
):
    return await SimulationService(session, context).run_to_completion(run_id, max_cycles)


@router.get("/{run_id}/summary")
async def summary(run_id: UUID, session: Session, context: Context):
    return await SimulationService(session, context).summary(run_id)


@router.get("/{run_id}/tasks")
async def tasks(run_id: UUID, session: Session, context: Context):
    return await SimulationService(session, context).tasks(run_id)


@router.get("/{run_id}/events")
async def events(
    run_id: UUID, session: Session, context: Context, limit: int = Query(200, ge=1, le=500)
):
    return await SimulationService(session, context).events(run_id, limit)


@router.get("/status")
async def status(session: Session, context: Context):
    return run_response(await SimulationService(session, context).get_run())
