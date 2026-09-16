import csv
import io
import json
from copy import deepcopy
from datetime import datetime, timedelta, timezone

import pytest
from conftest import auth_headers, uid
from sqlalchemy import func, select

from app.models.entities import Encounter, Patient
from app.models.healthcare import AuditEvent, Condition


def import_record(suffix="1"):
    discharge = datetime(2026, 2, 2, 12, tzinfo=timezone.utc)
    return {
        "patient": {
            "external_patient_id": f"IMPORT-P-{suffix}",
            "first_name": "Synthetic",
            "last_name": "Import",
            "date_of_birth": "1970-01-01",
            "phone": "+12025550199",
            "preferred_language": "en",
            "communication_preferences": {"voice": True},
        },
        "encounter": {
            "external_encounter_id": f"IMPORT-E-{suffix}",
            "care_setting": "INPATIENT",
            "admit_at": (discharge - timedelta(days=2)).isoformat(),
            "discharge_at": discharge.isoformat(),
            "status": "DISCHARGED",
        },
        "discharge": {
            "discharge_at": discharge.isoformat(),
            "follow_up_window_hours": 48,
            "disposition": "HOME",
            "risk_level": "MEDIUM",
            "risk_indicators": ["synthetic_indicator"],
            "discharge_instructions": "Synthetic import instructions.",
            "communication_eligible": True,
            "source_reference": f"IMPORT-D-{suffix}",
        },
        "conditions": [
            {
                "external_id": f"IMPORT-COND-{suffix}",
                "code": "I10",
                "display_name": "Hypertension",
                "clinical_status": "ACTIVE",
            }
        ],
        "observations": [
            {
                "external_id": f"IMPORT-OBS-{suffix}",
                "code": "8867-4",
                "display_name": "Heart rate",
                "value": 75,
                "unit": "beats/min",
                "value_type": "INTEGER",
                "observed_at": discharge.isoformat(),
            }
        ],
        "medications": [
            {
                "external_id": f"IMPORT-MED-{suffix}",
                "medication_name": "Synthetic Medication",
                "status": "ACTIVE",
            }
        ],
        "care_plans": [
            {
                "external_id": f"IMPORT-PLAN-{suffix}",
                "title": "Synthetic plan",
                "description": "Synthetic",
                "status": "ACTIVE",
                "follow_up_instructions": "Follow up",
            }
        ],
        "procedures": [
            {
                "external_id": f"IMPORT-PROC-{suffix}",
                "name": "Synthetic procedure",
                "status": "COMPLETED",
                "performed_at": discharge.isoformat(),
            }
        ],
    }


async def submit(client, records, tenant=1, source="test-json"):
    return await client.post(
        "/api/v1/discharges/import",
        headers=auth_headers(tenant * 10),
        json={"source": source, "records": records},
    )


async def test_valid_batch_imports_full_graph_and_audits(client, session):
    response = await submit(client, [import_record("A"), import_record("B")])
    assert response.status_code == 201, response.text
    assert response.json()["status"] == "COMPLETED"
    assert response.json()["successful_records"] == 2
    assert response.json()["failed_records"] == 0
    patient = await session.scalar(
        select(Patient).where(
            Patient.hospital_id == uid(1), Patient.external_patient_id == "IMPORT-P-A"
        )
    )
    assert patient is not None
    assert (
        await session.scalar(
            select(func.count()).select_from(Condition).where(Condition.patient_id == patient.id)
        )
        == 1
    )
    audit = await session.scalar(
        select(AuditEvent).where(AuditEvent.action == "DISCHARGE_IMPORT_COMPLETED")
    )
    assert audit.details == {"status": "COMPLETED", "successful": 2, "failed": 0}


async def test_partial_batch_keeps_valid_record_and_safe_error(client, session):
    invalid = import_record("INVALID")
    invalid["patient"]["phone"] = "patient-private-bad-phone"
    response = await submit(client, [import_record("VALID"), invalid])
    assert response.status_code == 201
    result = response.json()
    assert result["status"] == "PARTIALLY_COMPLETED"
    assert (result["successful_records"], result["failed_records"]) == (1, 1)
    assert result["errors"][0]["record_index"] == 1
    assert result["errors"][0]["field"] == "patient.phone"
    assert "patient-private-bad-phone" not in response.text
    assert (
        await session.scalar(
            select(func.count())
            .select_from(Patient)
            .where(
                Patient.hospital_id == uid(1),
                Patient.external_patient_id.in_(["IMPORT-P-VALID", "IMPORT-P-INVALID"]),
            )
        )
        == 1
    )


async def test_duplicate_batch_is_idempotent(client, session):
    payload = [import_record("IDEMPOTENT")]
    first = await submit(client, payload)
    second = await submit(client, payload, source="renamed-source.json")
    assert first.status_code == second.status_code == 201
    assert first.json()["id"] == second.json()["id"]
    assert (
        await session.scalar(
            select(func.count())
            .select_from(Patient)
            .where(
                Patient.hospital_id == uid(1), Patient.external_patient_id == "IMPORT-P-IDEMPOTENT"
            )
        )
        == 1
    )
    assert (
        await session.scalar(
            select(func.count())
            .select_from(Encounter)
            .where(
                Encounter.hospital_id == uid(1),
                Encounter.external_encounter_id == "IMPORT-E-IDEMPOTENT",
            )
        )
        == 1
    )


async def test_changed_duplicate_external_ids_update_without_duplication(client, session):
    original = import_record("UPDATE")
    assert (await submit(client, [original])).status_code == 201
    changed = deepcopy(original)
    changed["patient"]["first_name"] = "UpdatedSynthetic"
    changed["conditions"][0]["display_name"] = "Updated condition"
    response = await submit(client, [changed], source="updated.json")
    assert response.status_code == 201
    patient = await session.scalar(
        select(Patient).where(
            Patient.hospital_id == uid(1), Patient.external_patient_id == "IMPORT-P-UPDATE"
        )
    )
    await session.refresh(patient)
    assert patient.first_name == "UpdatedSynthetic"
    assert (
        await session.scalar(
            select(func.count())
            .select_from(Condition)
            .where(Condition.hospital_id == uid(1), Condition.external_id == "IMPORT-COND-UPDATE")
        )
        == 1
    )


@pytest.mark.parametrize(
    "mutation,field",
    [
        (
            lambda row: row["discharge"].update(follow_up_deadline="2026-01-01T00:00:00Z"),
            "discharge",
        ),
        (lambda row: row["encounter"].update(discharge_at="2025-01-01T00:00:00Z"), "encounter"),
        (lambda row: row["discharge"].update(risk_level="EXTREME"), "discharge.risk_level"),
    ],
)
async def test_import_validation_failures_are_explicit(client, mutation, field):
    record = import_record("BAD")
    mutation(record)
    response = await submit(client, [record])
    assert response.status_code == 201
    assert response.json()["status"] == "FAILED"
    assert response.json()["failed_records"] == 1
    assert response.json()["errors"][0]["field"].startswith(field)


async def test_client_hospital_id_cannot_override_context(client, session):
    record = import_record("TENANT")
    record["patient"]["hospital_id"] = str(uid(2))
    response = await submit(client, [record])
    assert response.status_code == 201
    assert response.json()["status"] == "FAILED"
    assert (
        await session.scalar(
            select(func.count())
            .select_from(Patient)
            .where(Patient.external_patient_id == "IMPORT-P-TENANT")
        )
        == 0
    )


async def test_nested_cross_tenant_encounter_guess_fails_without_update(client, session):
    record = import_record("GUESS")
    record["conditions"][0]["encounter_id"] = str(uid(2000))
    response = await submit(client, [record])
    assert response.json()["status"] == "FAILED"
    assert response.json()["errors"][0]["code"] == "not_found"
    assert (
        await session.scalar(
            select(func.count())
            .select_from(Patient)
            .where(Patient.external_patient_id == "IMPORT-P-GUESS")
        )
        == 0
    )


async def test_import_job_is_tenant_scoped(client):
    created = await submit(client, [import_record("JOB")])
    import_id = created.json()["id"]
    assert (
        await client.get(f"/api/v1/discharges/imports/{import_id}", headers=auth_headers(20))
    ).status_code == 404
    assert (
        await client.get(f"/api/v1/discharges/imports/{import_id}", headers=auth_headers(10))
    ).status_code == 200


@pytest.mark.parametrize("headers", [{}, auth_headers(11), auth_headers(12), auth_headers(99)])
async def test_import_requires_hospital_admin(client, headers):
    response = await client.post(
        "/api/v1/discharges/import", headers=headers, json={"records": [import_record()]}
    )
    assert response.status_code in (401, 403)


async def test_csv_import(client):
    row = import_record("CSV")
    output = io.StringIO()
    columns = [
        "external_patient_id",
        "first_name",
        "last_name",
        "date_of_birth",
        "phone",
        "preferred_language",
        "communication_preferences",
        "external_encounter_id",
        "care_setting",
        "admit_at",
        "discharge_at",
        "encounter_status",
        "follow_up_window_hours",
        "disposition",
        "risk_level",
        "risk_indicators",
        "discharge_instructions",
        "communication_eligible",
        "discharge_status",
        "source_reference",
        "conditions",
        "observations",
        "medications",
        "care_plans",
        "procedures",
    ]
    writer = csv.DictWriter(output, fieldnames=columns, extrasaction="ignore")
    writer.writeheader()
    writer.writerow(
        {
            **row["patient"],
            **row["encounter"],
            "encounter_status": row["encounter"]["status"],
            **row["discharge"],
            "discharge_status": row["discharge"].get("status", "PENDING"),
            "communication_preferences": json.dumps(row["patient"]["communication_preferences"]),
            "risk_indicators": json.dumps(row["discharge"]["risk_indicators"]),
            **{
                key: json.dumps(row[key])
                for key in ("conditions", "observations", "medications", "care_plans", "procedures")
            },
        }
    )
    response = await client.post(
        "/api/v1/discharges/import/csv",
        headers=auth_headers(10),
        files={"file": ("synthetic.csv", output.getvalue(), "text/csv")},
    )
    assert response.status_code == 201, response.text
    assert response.json()["status"] == "COMPLETED"


async def test_import_errors_do_not_contain_submitted_patient_data(client):
    record = import_record("PRIVATE")
    record["patient"]["first_name"] = "SensitivePatientName"
    record["patient"]["phone"] = "bad"
    response = await submit(client, [record])
    assert "SensitivePatientName" not in response.text
    assert "IMPORT-P-PRIVATE" not in response.text
    job = await client.get(
        f"/api/v1/discharges/imports/{response.json()['id']}", headers=auth_headers(10)
    )
    assert "SensitivePatientName" not in job.text
    assert "IMPORT-P-PRIVATE" not in job.text
