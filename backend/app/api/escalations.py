from datetime import datetime, timezone
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.context import RequestContext, get_context
from app.core.database import get_session
from app.schemas.ai import EscalationCaseResolution, EscalationCaseResponse
from app.services.escalations import EscalationCaseService

router = APIRouter(prefix="/api/v1/escalations", tags=["escalations"])
Session = Annotated[AsyncSession, Depends(get_session)]
Context = Annotated[RequestContext, Depends(get_context)]


def response(record) -> EscalationCaseResponse:
    return EscalationCaseResponse(
        id=record.id,
        escalation_decision_id=record.escalation_decision_id,
        intake_session_id=record.intake_session_id,
        status=record.status,
        priority=record.priority,
        assigned_reviewer_id=record.assigned_reviewer_id,
        reviewer_notes=record.reviewer_notes,
        resolution=record.resolution,
        created_at=record.created_at,
        updated_at=record.updated_at,
        resolved_at=record.resolved_at,
    )


@router.get("", response_model=list[EscalationCaseResponse])
async def list_cases(session: Session, context: Context):
    records = await EscalationCaseService(session, context).list_open()
    return [response(record) for record in records]


@router.get("/{case_id}", response_model=EscalationCaseResponse)
async def get_case(case_id: UUID, session: Session, context: Context):
    return response(await EscalationCaseService(session, context).get(case_id))


@router.post("/{case_id}/start-review", response_model=EscalationCaseResponse)
async def start_review(case_id: UUID, session: Session, context: Context):
    return response(await EscalationCaseService(session, context).start_review(case_id))


@router.post("/{case_id}/resolve", response_model=EscalationCaseResponse)
async def resolve_case(
    case_id: UUID,
    payload: EscalationCaseResolution,
    session: Session,
    context: Context,
):
    return response(
        await EscalationCaseService(session, context).resolve(
            case_id,
            payload.reviewer_notes,
            payload.resolution,
            datetime.now(timezone.utc),
        )
    )
