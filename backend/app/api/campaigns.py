from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.context import RequestContext, get_context
from app.core.database import get_session
from app.schemas.campaigns import (
    CampaignCreate,
    CampaignEstimateResponse,
    CampaignResponse,
    CampaignScheduleRequest,
    CampaignUpdate,
)
from app.schemas.eligibility import EligibilityPage, PatientEligibilityResponse
from app.schemas.entities import ErrorResponse
from app.services.campaigns import CampaignService
from app.services.eligibility import EligibilityService

router = APIRouter(
    prefix="/api/v1/campaigns",
    tags=["campaigns"],
    responses={code: {"model": ErrorResponse} for code in (401, 403, 404, 409, 422, 500)},
)
Session = Annotated[AsyncSession, Depends(get_session)]
Context = Annotated[RequestContext, Depends(get_context)]
Limit = Annotated[int, Query(ge=1, le=100)]
Offset = Annotated[int, Query(ge=0)]


@router.post("", response_model=CampaignResponse, status_code=201)
async def create_campaign(payload: CampaignCreate, session: Session, context: Context):
    return await CampaignService(session, context).create(payload)


@router.get("", response_model=list[CampaignResponse])
async def list_campaigns(session: Session, context: Context, limit: Limit = 50, offset: Offset = 0):
    return await CampaignService(session, context).list(limit, offset)


@router.get("/{campaign_id}", response_model=CampaignResponse)
async def get_campaign(campaign_id: UUID, session: Session, context: Context):
    return await CampaignService(session, context).get(campaign_id)


@router.patch("/{campaign_id}", response_model=CampaignResponse)
async def update_campaign(
    campaign_id: UUID, payload: CampaignUpdate, session: Session, context: Context
):
    return await CampaignService(session, context).update(campaign_id, payload)


@router.get("/{campaign_id}/estimate", response_model=CampaignEstimateResponse)
async def campaign_estimate(campaign_id: UUID, session: Session, context: Context):
    campaign = await CampaignService(session, context).get(campaign_id)
    return await EligibilityService(session, context).estimate(campaign)


@router.get("/{campaign_id}/eligibility", response_model=EligibilityPage)
async def campaign_eligibility(
    campaign_id: UUID,
    session: Session,
    context: Context,
    eligible: bool | None = None,
    limit: Limit = 50,
    offset: Offset = 0,
):
    campaign = await CampaignService(session, context).get(campaign_id)
    return await EligibilityService(session, context).evaluate(
        campaign, eligible=eligible, limit=limit, offset=offset
    )


@router.get("/{campaign_id}/eligibility/{patient_id}", response_model=PatientEligibilityResponse)
async def patient_campaign_eligibility(
    campaign_id: UUID, patient_id: UUID, session: Session, context: Context
):
    campaign = await CampaignService(session, context).get(campaign_id)
    results = await EligibilityService(session, context).patient_results(campaign, patient_id)
    return PatientEligibilityResponse(patient_id=patient_id, results=results)


@router.post("/{campaign_id}/ready", response_model=CampaignResponse)
async def ready_campaign(campaign_id: UUID, session: Session, context: Context):
    return await CampaignService(session, context).transition(campaign_id, "ready")


@router.post("/{campaign_id}/schedule", response_model=CampaignResponse)
async def schedule_campaign(
    campaign_id: UUID, payload: CampaignScheduleRequest, session: Session, context: Context
):
    return await CampaignService(session, context).transition(campaign_id, "schedule", payload)


@router.post("/{campaign_id}/start", response_model=CampaignResponse)
async def start_campaign(campaign_id: UUID, session: Session, context: Context):
    return await CampaignService(session, context).transition(campaign_id, "start")


@router.post("/{campaign_id}/pause", response_model=CampaignResponse)
async def pause_campaign(campaign_id: UUID, session: Session, context: Context):
    return await CampaignService(session, context).transition(campaign_id, "pause")


@router.post("/{campaign_id}/resume", response_model=CampaignResponse)
async def resume_campaign(campaign_id: UUID, session: Session, context: Context):
    return await CampaignService(session, context).transition(campaign_id, "resume")


@router.post("/{campaign_id}/complete", response_model=CampaignResponse)
async def complete_campaign(campaign_id: UUID, session: Session, context: Context):
    return await CampaignService(session, context).transition(campaign_id, "complete")


@router.post("/{campaign_id}/cancel", response_model=CampaignResponse)
async def cancel_campaign(campaign_id: UUID, session: Session, context: Context):
    return await CampaignService(session, context).transition(campaign_id, "cancel")
