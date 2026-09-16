from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query, Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.context import RequestContext, get_context, require_any_role
from app.core.database import get_session
from app.models.entities import Discharge, Encounter, Hospital, Patient, Role, User
from app.schemas.auth import CurrentUserResponse, LoginRequest, LoginResponse, UserCreate
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
    UserResponse,
)
from app.services.auth import AuthService
from app.services.clinical import ClinicalService
from app.services.health import check_health
from app.services.platform import HospitalService
from app.services.users import UserService

router = APIRouter(
    prefix="/api/v1",
    responses={code: {"model": ErrorResponse} for code in (401, 403, 404, 409, 422, 500, 503)},
)
Session = Annotated[AsyncSession, Depends(get_session)]
Context = Annotated[RequestContext, Depends(get_context)]
HospitalAdmin = Annotated[RequestContext, Depends(require_any_role(Role.HOSPITAL_ADMIN))]
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
async def create_patients(
    payload: PatientCreate, session: Session, context: HospitalAdmin
) -> Patient:
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
    payload: EncounterCreate, session: Session, context: HospitalAdmin
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
    payload: DischargeCreate, session: Session, context: HospitalAdmin
) -> Discharge:
    return await ClinicalService(session, context, Discharge).create(payload)


@router.post("/auth/login", response_model=LoginResponse, tags=["auth"])
async def login(payload: LoginRequest, session: Session, response: Response) -> LoginResponse:
    response.headers["Cache-Control"] = "no-store"
    return await AuthService(session).login(payload)


@router.get("/users/me", response_model=CurrentUserResponse, tags=["users"])
async def current_user(session: Session, context: Context) -> CurrentUserResponse:
    return await AuthService(session).current_user(context)


@router.get("/users", response_model=list[UserResponse], tags=["users"])
async def list_users(
    session: Session, context: HospitalAdmin, limit: Limit = 50, offset: Offset = 0
) -> list[User]:
    return await UserService(session, context).list(limit, offset)


@router.post("/users", response_model=UserResponse, status_code=201, tags=["users"])
async def create_user(payload: UserCreate, session: Session, context: HospitalAdmin) -> User:
    return await UserService(session, context).create(payload)
