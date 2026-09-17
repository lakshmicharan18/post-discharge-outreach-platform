from datetime import datetime, timezone
from typing import Annotated
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.ai.models import DeterministicFakeModel
from app.core.context import RequestContext, get_context
from app.core.database import get_session
from app.schemas.ai import ClinicalTriageAssessment
from app.services.triage import ClinicalTriageService

router = APIRouter(prefix="/api/v1/triage", tags=["triage"])
Session = Annotated[AsyncSession, Depends(get_session)]
Context = Annotated[RequestContext, Depends(get_context)]


@router.post("/assess", response_model=ClinicalTriageAssessment)
async def assess(intake_session_id: UUID, session: Session, context: Context):
    model = DeterministicFakeModel(
        {
            "assessment_id": str(uuid4()),
            "classification": "INSUFFICIENT_INFORMATION",
            "reasoning_summary": "Deterministic prototype assessment.",
            "recommended_next_action": "HUMAN_REVIEW",
            "confidence": 0.0,
            "requires_human_review": True,
            "execution_metadata": {"provider": "fake"},
        }
    )
    record = await ClinicalTriageService(session, context, model).assess(
        intake_session_id, datetime.now(timezone.utc)
    )
    return ClinicalTriageAssessment.model_validate(record.assessment)


@router.get("/{assessment_id}", response_model=ClinicalTriageAssessment)
async def get_assessment(assessment_id: UUID, session: Session, context: Context):
    model = DeterministicFakeModel({})
    record = await ClinicalTriageService(session, context, model).get(assessment_id)
    return ClinicalTriageAssessment.model_validate(record.assessment)
