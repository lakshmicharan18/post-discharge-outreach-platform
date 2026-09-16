from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.api.routes import router
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
