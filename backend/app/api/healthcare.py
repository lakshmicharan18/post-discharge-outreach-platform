from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, File, UploadFile
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.context import RequestContext, get_context, require_any_role
from app.core.database import get_session
from app.core.errors import APIError
from app.models.entities import Role
from app.models.healthcare import CarePlan, Condition, Medication, Observation, Procedure
from app.schemas.healthcare import (
    CarePlanCreate,
    CarePlanResponse,
    ConditionCreate,
    ConditionResponse,
    DischargeBatchImportRequest,
    DischargeImportResponse,
    HospitalConfigurationResponse,
    HospitalConfigurationUpdate,
    MedicationCreate,
    MedicationResponse,
    ObservationCreate,
    ObservationResponse,
    PatientContextResponse,
    ProcedureCreate,
    ProcedureResponse,
    TimelineEvent,
)
from app.services.configuration import HospitalConfigurationService
from app.services.healthcare import HealthcareService, PatientContextService
from app.services.ingestion import DischargeIngestionService, parse_csv_import

router = APIRouter(prefix="/api/v1")
Session = Annotated[AsyncSession, Depends(get_session)]
Context = Annotated[RequestContext, Depends(get_context)]
HospitalAdmin = Annotated[RequestContext, Depends(require_any_role(Role.HOSPITAL_ADMIN))]


@router.get(
    "/hospital/configuration",
    response_model=HospitalConfigurationResponse,
    tags=["hospital-configuration"],
)
async def get_hospital_configuration(
    session: Session, context: Context
) -> HospitalConfigurationResponse:
    return await HospitalConfigurationService(session, context).get_own()


@router.put(
    "/hospital/configuration",
    response_model=HospitalConfigurationResponse,
    tags=["hospital-configuration"],
)
async def update_hospital_configuration(
    payload: HospitalConfigurationUpdate, session: Session, context: HospitalAdmin
) -> HospitalConfigurationResponse:
    return await HospitalConfigurationService(session, context).update_own(payload)


@router.get(
    "/platform/hospitals/{hospital_id}/configuration",
    response_model=HospitalConfigurationResponse,
    tags=["platform"],
)
async def get_platform_hospital_configuration(
    hospital_id: UUID, session: Session, context: Context
) -> HospitalConfigurationResponse:
    return await HospitalConfigurationService(session, context).get_platform(hospital_id)


@router.put(
    "/platform/hospitals/{hospital_id}/configuration",
    response_model=HospitalConfigurationResponse,
    tags=["platform"],
)
async def update_platform_hospital_configuration(
    hospital_id: UUID,
    payload: HospitalConfigurationUpdate,
    session: Session,
    context: Context,
) -> HospitalConfigurationResponse:
    return await HospitalConfigurationService(session, context).update_platform(
        hospital_id, payload
    )


@router.get(
    "/patients/{patient_id}/conditions", response_model=list[ConditionResponse], tags=["clinical"]
)
async def list_conditions(patient_id: UUID, session: Session, context: Context):
    return await HealthcareService(session, context, Condition).list_for_patient(patient_id)


@router.post(
    "/patients/{patient_id}/conditions",
    response_model=ConditionResponse,
    status_code=201,
    tags=["clinical"],
)
async def create_condition(
    patient_id: UUID, payload: ConditionCreate, session: Session, context: HospitalAdmin
):
    return await HealthcareService(session, context, Condition).create(patient_id, payload)


@router.get("/conditions/{identifier}", response_model=ConditionResponse, tags=["clinical"])
async def get_condition(identifier: UUID, session: Session, context: Context):
    return await HealthcareService(session, context, Condition).get(identifier)


@router.get(
    "/patients/{patient_id}/observations",
    response_model=list[ObservationResponse],
    tags=["clinical"],
)
async def list_observations(patient_id: UUID, session: Session, context: Context):
    return await HealthcareService(session, context, Observation).list_for_patient(patient_id)


@router.post(
    "/patients/{patient_id}/observations",
    response_model=ObservationResponse,
    status_code=201,
    tags=["clinical"],
)
async def create_observation(
    patient_id: UUID, payload: ObservationCreate, session: Session, context: HospitalAdmin
):
    return await HealthcareService(session, context, Observation).create(patient_id, payload)


@router.get("/observations/{identifier}", response_model=ObservationResponse, tags=["clinical"])
async def get_observation(identifier: UUID, session: Session, context: Context):
    return await HealthcareService(session, context, Observation).get(identifier)


@router.get(
    "/patients/{patient_id}/medications",
    response_model=list[MedicationResponse],
    tags=["clinical"],
)
async def list_medications(patient_id: UUID, session: Session, context: Context):
    return await HealthcareService(session, context, Medication).list_for_patient(patient_id)


@router.post(
    "/patients/{patient_id}/medications",
    response_model=MedicationResponse,
    status_code=201,
    tags=["clinical"],
)
async def create_medication(
    patient_id: UUID, payload: MedicationCreate, session: Session, context: HospitalAdmin
):
    return await HealthcareService(session, context, Medication).create(patient_id, payload)


@router.get("/medications/{identifier}", response_model=MedicationResponse, tags=["clinical"])
async def get_medication(identifier: UUID, session: Session, context: Context):
    return await HealthcareService(session, context, Medication).get(identifier)


@router.get(
    "/patients/{patient_id}/care-plans",
    response_model=list[CarePlanResponse],
    tags=["clinical"],
)
async def list_care_plans(patient_id: UUID, session: Session, context: Context):
    return await HealthcareService(session, context, CarePlan).list_for_patient(patient_id)


@router.post(
    "/patients/{patient_id}/care-plans",
    response_model=CarePlanResponse,
    status_code=201,
    tags=["clinical"],
)
async def create_care_plan(
    patient_id: UUID, payload: CarePlanCreate, session: Session, context: HospitalAdmin
):
    return await HealthcareService(session, context, CarePlan).create(patient_id, payload)


@router.get("/care-plans/{identifier}", response_model=CarePlanResponse, tags=["clinical"])
async def get_care_plan(identifier: UUID, session: Session, context: Context):
    return await HealthcareService(session, context, CarePlan).get(identifier)


@router.get(
    "/patients/{patient_id}/procedures",
    response_model=list[ProcedureResponse],
    tags=["clinical"],
)
async def list_procedures(patient_id: UUID, session: Session, context: Context):
    return await HealthcareService(session, context, Procedure).list_for_patient(patient_id)


@router.post(
    "/patients/{patient_id}/procedures",
    response_model=ProcedureResponse,
    status_code=201,
    tags=["clinical"],
)
async def create_procedure(
    patient_id: UUID, payload: ProcedureCreate, session: Session, context: HospitalAdmin
):
    return await HealthcareService(session, context, Procedure).create(patient_id, payload)


@router.get("/procedures/{identifier}", response_model=ProcedureResponse, tags=["clinical"])
async def get_procedure(identifier: UUID, session: Session, context: Context):
    return await HealthcareService(session, context, Procedure).get(identifier)


@router.get(
    "/patients/{patient_id}/timeline", response_model=list[TimelineEvent], tags=["clinical"]
)
async def patient_timeline(patient_id: UUID, session: Session, context: Context):
    return await PatientContextService(session, context).timeline(patient_id)


@router.get(
    "/patients/{patient_id}/context", response_model=PatientContextResponse, tags=["clinical"]
)
async def patient_context(patient_id: UUID, session: Session, context: Context):
    return await PatientContextService(session, context).context(patient_id)


@router.post(
    "/discharges/import",
    response_model=DischargeImportResponse,
    status_code=201,
    tags=["imports"],
)
async def import_discharges(
    payload: DischargeBatchImportRequest, session: Session, context: HospitalAdmin
):
    return await DischargeIngestionService(session, context).import_batch(payload)


@router.post(
    "/discharges/import/csv",
    response_model=DischargeImportResponse,
    status_code=201,
    tags=["imports"],
)
async def import_discharges_csv(
    session: Session,
    context: HospitalAdmin,
    file: Annotated[UploadFile, File(description="UTF-8 CSV, maximum 5 MiB")],
):
    if file.content_type not in ("text/csv", "application/csv", "application/vnd.ms-excel"):
        raise APIError(415, "unsupported_media_type", "Upload must be a CSV file")
    content = await file.read(5 * 1024 * 1024 + 1)
    if len(content) > 5 * 1024 * 1024:
        raise APIError(413, "file_too_large", "CSV exceeds the 5 MiB limit")
    payload = parse_csv_import(content, file.filename)
    return await DischargeIngestionService(session, context).import_batch(payload)


@router.get(
    "/discharges/imports/{import_id}",
    response_model=DischargeImportResponse,
    tags=["imports"],
)
async def get_discharge_import(import_id: UUID, session: Session, context: HospitalAdmin):
    return await DischargeIngestionService(session, context).get(import_id)
