import csv
import hashlib
import io
import json
from datetime import datetime, timedelta, timezone
from typing import Any

from pydantic import ValidationError
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.context import RequestContext
from app.core.errors import APIError
from app.models.entities import Discharge, Encounter, Patient, Role
from app.models.healthcare import (
    CarePlan,
    Condition,
    DischargeImport,
    HospitalConfiguration,
    Medication,
    Observation,
    Procedure,
)
from app.schemas.healthcare import DischargeBatchImportRequest, DischargeImportRecord
from app.services.audit import add_audit_event

RESOURCE_MODELS = (
    ("conditions", Condition),
    ("observations", Observation),
    ("medications", Medication),
    ("care_plans", CarePlan),
    ("procedures", Procedure),
)


class DischargeIngestionService:
    def __init__(self, session: AsyncSession, context: RequestContext) -> None:
        context.require_roles(Role.HOSPITAL_ADMIN)
        self.session = session
        self.context = context
        self.hospital_id = context.require_clinical_tenant()

    async def get(self, import_id) -> DischargeImport:
        result = await self.session.scalar(
            select(DischargeImport).where(
                DischargeImport.hospital_id == self.hospital_id,
                DischargeImport.id == import_id,
            )
        )
        if result is None:
            raise APIError(404, "not_found", "Import not found")
        return result

    async def import_batch(self, payload: DischargeBatchImportRequest) -> DischargeImport:
        digest = hashlib.sha256(
            json.dumps(payload.records, sort_keys=True, separators=(",", ":"), default=str).encode()
        ).hexdigest()
        existing = await self.session.scalar(
            select(DischargeImport).where(
                DischargeImport.hospital_id == self.hospital_id,
                DischargeImport.source_digest == digest,
            )
        )
        if existing is not None:
            return existing

        job = DischargeImport(
            hospital_id=self.hospital_id,
            source=payload.source,
            source_digest=digest,
            status="PROCESSING",
            total_records=len(payload.records),
            started_at=datetime.now(timezone.utc),
            created_by_user_id=self.context.user_id,
        )
        self.session.add(job)
        await self.session.flush()

        errors: list[dict[str, Any]] = []
        successes = 0
        for index, raw_record in enumerate(payload.records):
            try:
                record = DischargeImportRecord.model_validate(raw_record)
            except ValidationError as exc:
                first = exc.errors(include_input=False)[0]
                errors.append(
                    {
                        "record_index": index,
                        "code": "validation_error",
                        "field": ".".join(str(item) for item in first["loc"]),
                        "message": first["msg"][:250],
                    }
                )
                continue
            try:
                async with self.session.begin_nested():
                    await self._upsert_record(record)
                successes += 1
            except APIError as exc:
                errors.append(
                    {
                        "record_index": index,
                        "code": exc.code,
                        "field": None,
                        "message": exc.message,
                    }
                )
            except IntegrityError:
                errors.append(
                    {
                        "record_index": index,
                        "code": "data_conflict",
                        "field": None,
                        "message": "Record conflicts with existing tenant data",
                    }
                )
            except SQLAlchemyError:
                errors.append(
                    {
                        "record_index": index,
                        "code": "database_error",
                        "field": None,
                        "message": "Record could not be stored",
                    }
                )

        job.successful_records = successes
        job.failed_records = len(errors)
        job.errors = errors
        job.completed_at = datetime.now(timezone.utc)
        if successes and errors:
            job.status = "PARTIALLY_COMPLETED"
        elif successes:
            job.status = "COMPLETED"
        else:
            job.status = "FAILED"
        await add_audit_event(
            self.session,
            self.context,
            self.hospital_id,
            "DISCHARGE_IMPORT_COMPLETED",
            "DischargeImport",
            job.id,
            {"status": job.status, "successful": successes, "failed": len(errors)},
        )
        try:
            await self.session.commit()
            await self.session.refresh(job)
            return job
        except Exception:
            await self.session.rollback()
            raise

    async def _upsert_record(self, record: DischargeImportRecord) -> None:
        patient = await self.session.scalar(
            select(Patient).where(
                Patient.hospital_id == self.hospital_id,
                Patient.external_patient_id == record.patient.external_patient_id,
            )
        )
        patient_values = record.patient.model_dump()
        if patient is None:
            patient = Patient(hospital_id=self.hospital_id, **patient_values)
            self.session.add(patient)
            await self.session.flush()
        else:
            for field, value in patient_values.items():
                setattr(patient, field, value)

        encounter = await self.session.scalar(
            select(Encounter).where(
                Encounter.hospital_id == self.hospital_id,
                Encounter.external_encounter_id == record.encounter.external_encounter_id,
            )
        )
        encounter_values = record.encounter.model_dump()
        if encounter is None:
            encounter = Encounter(
                hospital_id=self.hospital_id, patient_id=patient.id, **encounter_values
            )
            self.session.add(encounter)
            await self.session.flush()
        elif encounter.patient_id != patient.id:
            raise APIError(
                409, "external_id_conflict", "External encounter belongs to another patient"
            )
        else:
            for field, value in encounter_values.items():
                setattr(encounter, field, value)

        configuration = await self.session.scalar(
            select(HospitalConfiguration).where(
                HospitalConfiguration.hospital_id == self.hospital_id
            )
        )
        if configuration is None:
            raise APIError(409, "configuration_required", "Hospital configuration is required")
        discharge_values = record.discharge.model_dump()
        deadline = discharge_values.pop("follow_up_deadline")
        window = discharge_values.pop("follow_up_window_hours")
        if deadline is None:
            window = window or configuration.default_follow_up_hours
            deadline = record.discharge.discharge_at + timedelta(hours=window)
        else:
            calculated = max(
                1, int((deadline - record.discharge.discharge_at).total_seconds() // 3600)
            )
            if window is not None and window != calculated:
                raise APIError(
                    422,
                    "follow_up_window_mismatch",
                    "Follow-up deadline and window are inconsistent",
                )
            window = calculated
        source_reference = discharge_values.pop("source_reference") or (
            f"encounter:{record.encounter.external_encounter_id}"
        )
        discharge = await self.session.scalar(
            select(Discharge).where(
                Discharge.hospital_id == self.hospital_id,
                Discharge.encounter_id == encounter.id,
            )
        )
        values = {
            **discharge_values,
            "follow_up_deadline": deadline,
            "follow_up_window_hours": window,
            "source_reference": source_reference,
        }
        if discharge is None:
            discharge = Discharge(
                hospital_id=self.hospital_id,
                patient_id=patient.id,
                encounter_id=encounter.id,
                **values,
            )
            self.session.add(discharge)
            await self.session.flush()
        elif discharge.patient_id != patient.id:
            raise APIError(409, "relationship_conflict", "Discharge belongs to another patient")
        else:
            for field, value in values.items():
                setattr(discharge, field, value)

        for field_name, model in RESOURCE_MODELS:
            for resource_data in getattr(record, field_name):
                if resource_data.encounter_id not in (None, encounter.id):
                    raise APIError(
                        404, "not_found", "Nested resource encounter was not found in this import"
                    )
                resource = await self.session.scalar(
                    select(model).where(
                        model.hospital_id == self.hospital_id,
                        model.external_id == resource_data.external_id,
                    )
                )
                values = resource_data.model_dump(exclude={"encounter_id"})
                if resource is None:
                    self.session.add(
                        model(
                            hospital_id=self.hospital_id,
                            patient_id=patient.id,
                            encounter_id=encounter.id,
                            **values,
                        )
                    )
                elif resource.patient_id != patient.id:
                    raise APIError(
                        409, "external_id_conflict", "Clinical resource belongs to another patient"
                    )
                else:
                    resource.encounter_id = encounter.id
                    for field, value in values.items():
                        setattr(resource, field, value)
        await self.session.flush()


def parse_csv_import(content: bytes, filename: str | None) -> DischargeBatchImportRequest:
    try:
        text = content.decode("utf-8-sig")
    except UnicodeDecodeError as exc:
        raise APIError(422, "invalid_csv", "CSV must use UTF-8 encoding") from exc
    try:
        reader = csv.DictReader(io.StringIO(text))
        if reader.fieldnames is None:
            raise ValueError("Missing header")
        records: list[dict[str, Any]] = []
        for row in reader:
            nested = {}
            for key in ("conditions", "observations", "medications", "care_plans", "procedures"):
                nested[key] = json.loads(row.get(key) or "[]")
            preferences = json.loads(row.get("communication_preferences") or "{}")
            records.append(
                {
                    "patient": {
                        "external_patient_id": row.get("external_patient_id"),
                        "first_name": row.get("first_name"),
                        "last_name": row.get("last_name"),
                        "date_of_birth": row.get("date_of_birth"),
                        "phone": row.get("phone"),
                        "preferred_language": row.get("preferred_language") or "en",
                        "communication_preferences": preferences,
                    },
                    "encounter": {
                        "external_encounter_id": row.get("external_encounter_id"),
                        "care_setting": row.get("care_setting"),
                        "admit_at": row.get("admit_at"),
                        "discharge_at": row.get("discharge_at"),
                        "status": row.get("encounter_status") or "DISCHARGED",
                    },
                    "discharge": {
                        "discharge_at": row.get("discharge_at"),
                        "follow_up_deadline": row.get("follow_up_deadline") or None,
                        "follow_up_window_hours": row.get("follow_up_window_hours") or None,
                        "disposition": row.get("disposition") or "HOME",
                        "risk_level": row.get("risk_level") or "UNKNOWN",
                        "risk_indicators": json.loads(row.get("risk_indicators") or "[]"),
                        "discharge_instructions": row.get("discharge_instructions"),
                        "communication_eligible": (
                            row.get("communication_eligible") or "true"
                        ).lower()
                        in ("true", "1", "yes"),
                        "status": row.get("discharge_status") or "PENDING",
                        "source_reference": row.get("source_reference") or None,
                    },
                    **nested,
                }
            )
        return DischargeBatchImportRequest(source=(filename or "csv-upload")[:255], records=records)
    except (ValueError, TypeError, json.JSONDecodeError) as exc:
        raise APIError(422, "invalid_csv", "CSV structure or JSON columns are invalid") from exc
