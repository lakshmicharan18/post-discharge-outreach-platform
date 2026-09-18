import asyncio
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager, suppress

from fastapi import FastAPI

from app.api.campaigns import router as campaigns_router
from app.api.escalation import router as escalation_router
from app.api.escalations import router as escalations_router
from app.api.healthcare import router as healthcare_router
from app.api.knowledge import router as knowledge_router
from app.api.outreach import router as outreach_router
from app.api.queue import router as queue_router
from app.api.routes import router
from app.api.simulation import router as simulation_router
from app.api.triage import router as triage_router
from app.api.voice_intake import router as voice_intake_router
from app.core.database import SessionFactory, engine
from app.core.errors import register_error_handlers
from app.services.workflow_runner import WorkflowEventRunner


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    worker_task = asyncio.create_task(
        WorkflowEventRunner(SessionFactory).run_forever(), name="workflow-event-runner"
    )
    try:
        yield
    finally:
        worker_task.cancel()
        with suppress(asyncio.CancelledError):
            await worker_task
        await engine.dispose()


app = FastAPI(
    title="Multi-Hospital Post-Discharge Outreach Platform", version="0.1.0", lifespan=lifespan
)
register_error_handlers(app)
app.include_router(router)
app.include_router(healthcare_router)
app.include_router(knowledge_router)
app.include_router(outreach_router)
app.include_router(queue_router)
app.include_router(simulation_router)
app.include_router(triage_router)
app.include_router(voice_intake_router)
app.include_router(campaigns_router)
app.include_router(escalation_router)
app.include_router(escalations_router)
