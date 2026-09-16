"""Live Milestone 3 smoke check for seeded backend and frontend."""

import os
from datetime import datetime, timedelta, timezone

import httpx

API = os.environ.get("SMOKE_API_URL", "http://127.0.0.1:8000")
FRONTEND = os.environ.get("SMOKE_FRONTEND_URL", "http://127.0.0.1:3000")
PASSWORD = "DemoOnly-ChangeMe-2026!"


def record(suffix: str, valid: bool = True) -> dict:
    discharge = datetime(2026, 9, 16, 8, tzinfo=timezone.utc)
    return {
        "patient": {
            "external_patient_id": f"SMOKE-M3-{suffix}",
            "first_name": "SyntheticSmoke",
            "last_name": "Patient",
            "date_of_birth": "1980-01-01",
            "phone": "+12025550999" if valid else "invalid-private-phone",
            "preferred_language": "en",
            "communication_preferences": {"voice": True},
        },
        "encounter": {
            "external_encounter_id": f"SMOKE-M3-ENC-{suffix}",
            "care_setting": "INPATIENT",
            "admit_at": (discharge - timedelta(days=1)).isoformat(),
            "discharge_at": discharge.isoformat(),
            "status": "DISCHARGED",
        },
        "discharge": {
            "discharge_at": discharge.isoformat(),
            "follow_up_window_hours": 48,
            "risk_level": "MEDIUM",
            "risk_indicators": ["synthetic_smoke"],
            "discharge_instructions": "Synthetic smoke-test instructions.",
            "source_reference": f"SMOKE-M3-DIS-{suffix}",
        },
        "conditions": [
            {
                "external_id": f"SMOKE-M3-COND-{suffix}",
                "code": "SYN",
                "display_name": "Synthetic condition",
            }
        ],
        "observations": [],
        "medications": [],
        "care_plans": [],
        "procedures": [],
    }


def main() -> None:
    with httpx.Client(base_url=API, timeout=30) as api:
        login = api.post(
            "/api/v1/auth/login",
            json={
                "email": "hospital_admin.1@example.test",
                "password": PASSWORD,
            },
        )
        assert login.status_code == 200
        headers = {"Authorization": "Bearer " + login.json()["access_token"]}
        assert api.get("/api/v1/hospital/configuration", headers=headers).status_code == 200
        payload = {
            "source": "milestone-3-live-smoke",
            "records": [record("VALID"), record("INVALID", False)],
        }
        imported = api.post("/api/v1/discharges/import", headers=headers, json=payload)
        assert imported.status_code == 201, imported.text
        assert imported.json()["successful_records"] == 1
        assert imported.json()["failed_records"] == 1
        assert "invalid-private-phone" not in imported.text
        repeated = api.post("/api/v1/discharges/import", headers=headers, json=payload)
        assert repeated.json()["id"] == imported.json()["id"]
        patients = []
        for offset in (0, 100, 200):
            patients.extend(
                api.get(f"/api/v1/patients?limit=100&offset={offset}", headers=headers).json()
            )
        patient = next(item for item in patients if item["external_patient_id"] == "SMOKE-M3-VALID")
        context = api.get(f"/api/v1/patients/{patient['id']}/context", headers=headers)
        assert context.status_code == 200
        assert len(context.json()["conditions"]) == 1
        assert context.json()["timeline"] == sorted(
            context.json()["timeline"],
            key=lambda event: (event["occurred_at"], event["event_type"], event["resource_id"]),
        )

    with httpx.Client(base_url=FRONTEND, timeout=30) as browser:
        assert browser.get("/patients").status_code == 200
        assert browser.get("/configuration").status_code == 200
        assert browser.get("/import").status_code == 200
        login = browser.post(
            "/api/auth/login",
            headers={"Origin": FRONTEND},
            json={
                "email": "hospital_admin.1@example.test",
                "password": PASSWORD,
            },
        )
        assert login.status_code == 200
        assert browser.get("/api/backend/hospital/configuration").status_code == 200
        assert browser.get("/api/backend/patients?limit=1").status_code == 200
        assert browser.get(f"/api/backend/patients/{patient['id']}/context").status_code == 200
    print(
        "PASS: configuration, partial/idempotent import, timeline, patient pages, authenticated proxy"
    )


if __name__ == "__main__":
    main()
