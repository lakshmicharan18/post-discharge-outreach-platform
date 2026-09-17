from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.api.campaigns import router as campaigns_router
from app.api.healthcare import router as healthcare_router
from app.api.outreach import router as outreach_router
from app.api.queue import router as queue_router
from app.api.routes import router
from app.api.simulation import router as simulation_router
from app.core.database import engine
from app.core.errors import register_error_handlers


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    yield
    await engine.dispose()


app = FastAPI(
    title="Multi-Hospital Post-Discharge Outreach Platform", version="0.1.0", lifespan=lifespan
)
register_error_handlers(app)
app.include_router(router)
app.include_router(healthcare_router)
app.include_router(outreach_router)
app.include_router(queue_router)
app.include_router(simulation_router)
app.include_router(campaigns_router)
