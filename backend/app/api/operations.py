from datetime import datetime, timezone
from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.context import RequestContext, get_context
from app.core.database import get_session
from app.schemas.operations import OperationsSummaryResponse
from app.services.operations import OperationsService

router = APIRouter(prefix="/api/v1/operations", tags=["operations"])
Session = Annotated[AsyncSession, Depends(get_session)]
Context = Annotated[RequestContext, Depends(get_context)]


@router.get("/summary", response_model=OperationsSummaryResponse)
async def summary(session: Session, context: Context) -> OperationsSummaryResponse:
    return await OperationsService(session, context).summary(datetime.now(timezone.utc))
