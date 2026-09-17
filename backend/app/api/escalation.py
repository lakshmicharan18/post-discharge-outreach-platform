from datetime import datetime, timezone
from typing import Annotated
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.ai.models import DeterministicFakeModel
from app.core.context import RequestContext, get_context
from app.core.database import get_session
from app.schemas.ai import EscalationDecision
from app.services.consensus import ConsensusTriageService

router = APIRouter(prefix="/api/v1/escalation", tags=["escalation"])
Session = Annotated[AsyncSession, Depends(get_session)]
Context = Annotated[RequestContext, Depends(get_context)]


def fake_model():
    return DeterministicFakeModel(
        {
            "assessment_id": str(uuid4()),
            "classification": "INSUFFICIENT_INFORMATION",
            "reasoning_summary": "Deterministic conservative assessment.",
            "recommended_next_action": "HUMAN_REVIEW",
            "confidence": 0.0,
            "requires_human_review": True,
        }
    )


def response(record) -> EscalationDecision:
    return EscalationDecision(
        decision_id=record.id,
        intake_session_id=record.intake_session_id,
        assessment_ids=[UUID(value) for value in record.assessment_ids],
        final_classification=record.final_classification,
        agreement_status=record.agreement_status,
        requires_human_review=record.requires_human_review,
        disagreement_reason=record.disagreement_reason,
        recommended_action=record.recommended_action,
        execution_metadata=record.execution_metadata,
    )


@router.post("/assess-consensus", response_model=EscalationDecision)
async def assess_consensus(intake_session_id: UUID, session: Session, context: Context):
    record = await ConsensusTriageService(session, context).assess_consensus(
        intake_session_id, [fake_model(), fake_model(), fake_model()], datetime.now(timezone.utc)
    )
    return response(record)


@router.get("/{decision_id}", response_model=EscalationDecision)
async def get_decision(decision_id: UUID, session: Session, context: Context):
    return response(await ConsensusTriageService(session, context).get(decision_id))
