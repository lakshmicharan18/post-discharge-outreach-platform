from datetime import datetime, timedelta, timezone

import pytest
from conftest import auth_headers, uid


def resource_payload(resource, suffix="1"):
    now = datetime(2026, 1, 2, 12, tzinfo=timezone.utc)
    common = {"external_id": f"EXT-{resource}-{suffix}", "encounter_id": str(uid(1000))}
    values = {
        "conditions": {
            **common,
            "code": "I10",
            "display_name": "Hypertension",
            "clinical_status": "ACTIVE",
            "onset_at": (now - timedelta(days=3)).isoformat(),
        },
        "observations": {
            **common,
            "code": "8867-4",
            "display_name": "Heart rate",
            "value": 72,
            "unit": "beats/min",
            "value_type": "INTEGER",
            "observed_at": now.isoformat(),
        },
        "medications": {
            **common,
            "medication_name": "Synthetic Medication",
            "dose": "5 mg",
            "status": "ACTIVE",
            "started_at": now.isoformat(),
        },
        "care-plans": {
            **common,
            "title": "Follow-up plan",
            "description": "Synthetic",
            "status": "ACTIVE",
            "follow_up_instructions": "Follow up",
            "start_at": now.isoformat(),
        },
        "procedures": {
            **common,
            "code": "PROC",
            "name": "Synthetic procedure",
            "performed_at": now.isoformat(),
            "status": "COMPLETED",
        },
    }
    return values[resource]


@pytest.mark.parametrize(
    "resource", ["conditions", "observations", "medications", "care-plans", "procedures"]
)
async def test_create_and_retrieve_healthcare_resources(client, resource):
    created = await client.post(
        f"/api/v1/patients/{uid(100)}/{resource}",
        headers=auth_headers(10),
        json=resource_payload(resource),
    )
    assert created.status_code == 201, created.text
    result = await client.get(f"/api/v1/patients/{uid(100)}/{resource}", headers=auth_headers(11))
    assert result.status_code == 200
    assert result.json()[0]["hospital_id"] == str(uid(1))
    assert result.json()[0]["patient_id"] == str(uid(100))


@pytest.mark.parametrize(
    "resource", ["conditions", "observations", "medications", "care-plans", "procedures"]
)
async def test_healthcare_resources_are_tenant_isolated(client, resource):
    created = await client.post(
        f"/api/v1/patients/{uid(200)}/{resource}",
        headers=auth_headers(20),
        json={**resource_payload(resource, "B"), "encounter_id": str(uid(2000))},
    )
    assert created.status_code == 201
    hidden = await client.get(f"/api/v1/patients/{uid(200)}/{resource}", headers=auth_headers(10))
    assert hidden.status_code == 404
    direct_path = resource
    resource_id = created.json()["id"]
    assert (
        await client.get(f"/api/v1/{direct_path}/{resource_id}", headers=auth_headers(10))
    ).status_code == 404
    assert (
        await client.get(f"/api/v1/{direct_path}/{resource_id}", headers=auth_headers(20))
    ).status_code == 200


@pytest.mark.parametrize("user_id", [11, 12, 99])
async def test_only_hospital_admin_creates_healthcare_resources(client, user_id):
    response = await client.post(
        f"/api/v1/patients/{uid(100)}/conditions",
        headers=auth_headers(user_id),
        json=resource_payload("conditions"),
    )
    assert response.status_code == 403


async def test_guessed_cross_tenant_encounter_is_not_accepted(client):
    response = await client.post(
        f"/api/v1/patients/{uid(100)}/conditions",
        headers=auth_headers(10),
        json={**resource_payload("conditions"), "encounter_id": str(uid(2000))},
    )
    assert response.status_code == 404


async def test_timeline_is_chronological_and_scoped(client):
    for resource in ("observations", "medications", "care-plans", "procedures"):
        response = await client.post(
            f"/api/v1/patients/{uid(100)}/{resource}",
            headers=auth_headers(10),
            json=resource_payload(resource),
        )
        assert response.status_code == 201
    timeline = await client.get(f"/api/v1/patients/{uid(100)}/timeline", headers=auth_headers(12))
    assert timeline.status_code == 200, timeline.text
    timestamps = [datetime.fromisoformat(item["occurred_at"]) for item in timeline.json()]
    assert timestamps == sorted(timestamps)
    assert {item["event_type"] for item in timeline.json()} >= {
        "ENCOUNTER_ADMISSION",
        "OBSERVATION",
        "PROCEDURE",
        "DISCHARGE",
    }
    assert (
        await client.get(f"/api/v1/patients/{uid(200)}/timeline", headers=auth_headers(10))
    ).status_code == 404


async def test_patient_context_contains_structured_sections(client):
    response = await client.get(f"/api/v1/patients/{uid(100)}/context", headers=auth_headers(10))
    assert response.status_code == 200
    assert set(response.json()) == {
        "patient",
        "encounters",
        "discharges",
        "conditions",
        "observations",
        "medications",
        "care_plans",
        "procedures",
        "timeline",
    }
