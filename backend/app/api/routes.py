from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.context import RequestContext, get_context
from app.core.database import get_session
from app.models.entities import Discharge, Encounter, Hospital, Patient
from app.schemas.entities import (
    DischargeCreate,
    DischargeResponse,
    EncounterCreate,
    EncounterResponse,
    ErrorResponse,
    HealthResponse,
    HospitalCreate,
    HospitalResponse,
    PatientCreate,
    PatientResponse,
)
from app.services.clinical import ClinicalService
from app.services.health import check_health
from app.services.platform import HospitalService

router = APIRouter(
    prefix="/api/v1",
    responses={code: {"model": ErrorResponse} for code in (401, 403, 404, 409, 422, 500, 503)},
)
Session = Annotated[AsyncSession, Depends(get_session)]
Context = Annotated[RequestContext, Depends(get_context)]
Limit = Annotated[int, Query(ge=1, le=100)]
Offset = Annotated[int, Query(ge=0)]


@router.get("/health", response_model=HealthResponse, tags=["health"])
async def health(session: Session) -> HealthResponse:
    return await check_health(session)


@router.get("/platform/hospitals", response_model=list[HospitalResponse], tags=["platform"])
async def list_hospitals(
    session: Session, context: Context, limit: Limit = 50, offset: Offset = 0
) -> list[Hospital]:
    return await HospitalService(session, context).list(limit, offset)


@router.post(
    "/platform/hospitals", response_model=HospitalResponse, status_code=201, tags=["platform"]
)
async def create_hospital(payload: HospitalCreate, session: Session, context: Context) -> Hospital:
    return await HospitalService(session, context).create(payload)


@router.get("/patients", response_model=list[PatientResponse], tags=["patients"])
async def list_patients(
    session: Session, context: Context, limit: Limit = 50, offset: Offset = 0
) -> list[Patient]:
    return await ClinicalService(session, context, Patient).list(limit, offset)


@router.get("/patients/{identifier}", response_model=PatientResponse, tags=["patients"])
async def get_patients(identifier: UUID, session: Session, context: Context) -> Patient:
    return await ClinicalService(session, context, Patient).get(identifier)


@router.post("/patients", response_model=PatientResponse, status_code=201, tags=["patients"])
async def create_patients(payload: PatientCreate, session: Session, context: Context) -> Patient:
    return await ClinicalService(session, context, Patient).create(payload)


@router.get("/encounters", response_model=list[EncounterResponse], tags=["encounters"])
async def list_encounters(
    session: Session, context: Context, limit: Limit = 50, offset: Offset = 0
):
    return await ClinicalService(session, context, Encounter).list(limit, offset)


@router.get("/encounters/{identifier}", response_model=EncounterResponse, tags=["encounters"])
async def get_encounters(identifier: UUID, session: Session, context: Context) -> Encounter:
    return await ClinicalService(session, context, Encounter).get(identifier)


@router.post("/encounters", response_model=EncounterResponse, status_code=201, tags=["encounters"])
async def create_encounters(
    payload: EncounterCreate, session: Session, context: Context
) -> Encounter:
    return await ClinicalService(session, context, Encounter).create(payload)


@router.get("/discharges", response_model=list[DischargeResponse], tags=["discharges"])
async def list_discharges(
    session: Session, context: Context, limit: Limit = 50, offset: Offset = 0
):
    return await ClinicalService(session, context, Discharge).list(limit, offset)


@router.get("/discharges/{identifier}", response_model=DischargeResponse, tags=["discharges"])
async def get_discharges(identifier: UUID, session: Session, context: Context) -> Discharge:
    return await ClinicalService(session, context, Discharge).get(identifier)


@router.post("/discharges", response_model=DischargeResponse, status_code=201, tags=["discharges"])
async def create_discharges(
    payload: DischargeCreate, session: Session, context: Context
) -> Discharge:
    return await ClinicalService(session, context, Discharge).create(payload)
