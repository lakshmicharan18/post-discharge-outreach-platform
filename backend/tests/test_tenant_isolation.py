from datetime import datetime, timedelta, timezone
from uuid import uuid4

import pytest
from conftest import auth_headers, uid
from sqlalchemy.exc import IntegrityError

from app.core.context import RequestContext
from app.core.errors import APIError
from app.models.entities import Discharge, Encounter, Patient, Role
from app.repositories.clinical import ClinicalRepository


def headers(tenant=1):
    return auth_headers(tenant * 10)


def patient_payload():
    return {
        "external_patient_id": "NEW",
        "first_name": "Synthetic",
        "last_name": "New",
        "date_of_birth": "1990-01-01",
        "phone": "+12025550109",
    }


@pytest.mark.parametrize(
    "resource,multiplier", [("patients", 100), ("encounters", 1000), ("discharges", 10000)]
)
@pytest.mark.parametrize("tenant", [1, 2])
async def test_own_record_allowed_other_tenant_not_found(client, resource, multiplier, tenant):
    own = await client.get(
        f"/api/v1/{resource}/{uid(tenant * multiplier)}", headers=headers(tenant)
    )
    assert own.status_code == 200
    assert own.json()["hospital_id"] == str(uid(tenant))
    other = await client.get(
        f"/api/v1/{resource}/{uid((3 - tenant) * multiplier)}", headers=headers(tenant)
    )
    missing = await client.get(f"/api/v1/{resource}/{uuid4()}", headers=headers(tenant))
    assert other.status_code == missing.status_code == 404
    assert other.json()["error"]["code"] == missing.json()["error"]["code"] == "not_found"


@pytest.mark.parametrize("resource,count", [("patients", 3), ("encounters", 1), ("discharges", 1)])
@pytest.mark.parametrize("tenant", [1, 2])
async def test_lists_are_tenant_scoped(client, resource, count, tenant):
    response = await client.get(f"/api/v1/{resource}", headers=headers(tenant))
    assert response.status_code == 200
    assert len(response.json()) == count
    assert {row["hospital_id"] for row in response.json()} == {str(uid(tenant))}


@pytest.mark.parametrize("resource", ["patients", "encounters", "discharges"])
async def test_platform_admin_has_no_clinical_access(client, resource):
    response = await client.get(
        f"/api/v1/{resource}", headers={**auth_headers(99), "X-Hospital-ID": str(uid(1))}
    )
    assert response.status_code == 403


async def test_repository_also_enforces_context(session):
    context = RequestContext(uid(10), uid(1), Role.HOSPITAL_ADMIN)
    repo = ClinicalRepository(session, context, Patient)
    with pytest.raises(APIError) as error:
        await repo.get(uid(200))
    assert error.value.status == 404
    for hospital_id in (None, uid(1)):
        with pytest.raises(APIError):
            ClinicalRepository(
                session, RequestContext(uid(99), hospital_id, Role.PLATFORM_ADMIN), Patient
            )


async def test_create_assigns_tenant_and_rejects_tenant_in_payload(client):
    payload = patient_payload()
    rejected = await client.post(
        "/api/v1/patients", headers=headers(), json={**payload, "hospital_id": str(uid(2))}
    )
    assert rejected.status_code == 422
    created = await client.post(
        "/api/v1/patients",
        headers={**headers(), "X-Hospital-ID": str(uid(2)), "X-Role": "PLATFORM_ADMIN"},
        json=payload,
    )
    assert created.status_code == 201
    assert created.json()["hospital_id"] == str(uid(1))
    assert datetime.fromisoformat(created.json()["created_at"]).tzinfo is not None
    duplicate = await client.post("/api/v1/patients", headers=headers(), json=payload)
    assert duplicate.status_code == 409
    other = await client.post("/api/v1/patients", headers=headers(2), json=payload)
    assert other.status_code == 201  # external IDs are unique within a hospital only


async def test_cross_tenant_encounter_write_denied(client):
    response = await client.post(
        "/api/v1/encounters",
        headers=headers(),
        json={
            "patient_id": str(uid(200)),
            "external_encounter_id": "NEW",
            "care_setting": "INPATIENT",
            "admit_at": "2026-01-01T00:00:00Z",
        },
    )
    assert response.status_code == 404


@pytest.mark.parametrize(
    "patient,encounter,status", [(200, 2000, 404), (100, 2000, 404), (101, 1000, 422)]
)
async def test_invalid_discharge_relationships_denied(client, patient, encounter, status):
    response = await client.post(
        "/api/v1/discharges",
        headers=headers(),
        json={
            "patient_id": str(uid(patient)),
            "encounter_id": str(uid(encounter)),
            "discharge_at": "2026-01-01T00:00:00Z",
            "follow_up_deadline": "2026-01-02T00:00:00Z",
            "discharge_instructions": "Synthetic",
        },
    )
    assert response.status_code == status


@pytest.mark.parametrize("model", [Encounter, Discharge])
async def test_database_rejects_cross_tenant_links(session, model):
    now = datetime.now(timezone.utc)
    values = {"hospital_id": uid(1), "patient_id": uid(200)}
    if model is Encounter:
        values.update(external_encounter_id="INVALID", care_setting="INPATIENT", admit_at=now)
    else:
        values.update(
            encounter_id=uid(2000),
            discharge_at=now,
            follow_up_deadline=now + timedelta(days=1),
            discharge_instructions="Synthetic",
        )
    with pytest.raises(IntegrityError):
        async with session.begin_nested():
            session.add(model(**values))
            await session.flush()


async def test_database_rejects_wrong_patient_for_encounter(session):
    now = datetime.now(timezone.utc)
    with pytest.raises(IntegrityError):
        async with session.begin_nested():
            session.add(
                Discharge(
                    hospital_id=uid(1),
                    patient_id=uid(101),
                    encounter_id=uid(1000),
                    discharge_at=now,
                    follow_up_deadline=now,
                    discharge_instructions="Synthetic",
                )
            )
            await session.flush()


async def test_valid_encounter_and_discharge_creation(client):
    response = await client.post(
        "/api/v1/encounters",
        headers=headers(),
        json={
            "patient_id": str(uid(101)),
            "external_encounter_id": "NEW",
            "care_setting": "INPATIENT",
            "admit_at": "2026-01-01T00:00:00Z",
            "discharge_at": "2026-01-02T00:00:00Z",
            "status": "DISCHARGED",
        },
    )
    assert response.status_code == 201
    response = await client.post(
        "/api/v1/discharges",
        headers=headers(),
        json={
            "patient_id": str(uid(101)),
            "encounter_id": response.json()["id"],
            "discharge_at": "2026-01-02T00:00:00Z",
            "follow_up_deadline": "2026-01-03T00:00:00Z",
            "discharge_instructions": "Synthetic",
        },
    )
    assert response.status_code == 201
    assert response.json()["hospital_id"] == str(uid(1))
    assert response.json()["follow_up_window_hours"] == 24
    mismatch = await client.post(
        "/api/v1/discharges",
        headers=headers(),
        json={
            "patient_id": str(uid(102)),
            "encounter_id": response.json()["encounter_id"],
            "discharge_at": "2026-01-02T00:00:00Z",
            "follow_up_deadline": "2026-01-03T00:00:00Z",
            "follow_up_window_hours": 72,
            "discharge_instructions": "Synthetic",
        },
    )
    assert mismatch.status_code == 422
