"""Live Milestone 4 campaign and eligibility smoke check for seeded local services."""

import os
from datetime import datetime, timezone

import httpx

API = os.environ.get("SMOKE_API_URL", "http://127.0.0.1:8000")
FRONTEND = os.environ.get("SMOKE_FRONTEND_URL", "http://127.0.0.1:3000")
PASSWORD = "DemoOnly-ChangeMe-2026!"


def login(client: httpx.Client, email: str) -> dict[str, str]:
    response = client.post("/api/v1/auth/login", json={"email": email, "password": PASSWORD})
    assert response.status_code == 200, response.text
    return {"Authorization": "Bearer " + response.json()["access_token"]}


def main() -> None:
    suffix = datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S")
    with httpx.Client(base_url=API, timeout=30) as api:
        admin = login(api, "hospital_admin.1@example.test")
        reviewer = login(api, "clinical_reviewer.1@example.test")
        hospital_b = login(api, "hospital_admin.2@example.test")
        ready = api.put("/api/v1/hospital/configuration", headers=admin, json={"is_ready": True})
        assert ready.status_code == 200, ready.text
        created = api.post(
            "/api/v1/campaigns",
            headers=admin,
            json={
                "name": f"M4 smoke {suffix}",
                "clinical_follow_up_hours": 72,
                "calling_window_start": "09:00:00",
                "calling_window_end": "17:00:00",
                "campaign_priority": 50,
                "max_retries": 2,
                "eligibility_criteria": {"communication_eligible": True},
            },
        )
        assert created.status_code == 201, created.text
        campaign_id = created.json()["id"]
        estimate = api.get(f"/api/v1/campaigns/{campaign_id}/estimate", headers=admin)
        assert estimate.status_code == 200, estimate.text
        assert {"total_evaluated", "eligible_patients", "estimated_outreach_attempts"} <= set(
            estimate.json()
        )
        ready_campaign = api.post(f"/api/v1/campaigns/{campaign_id}/ready", headers=admin)
        assert ready_campaign.status_code == 200 and ready_campaign.json()["status"] == "READY"
        eligibility = api.get(
            f"/api/v1/campaigns/{campaign_id}/eligibility?limit=25", headers=admin
        )
        assert eligibility.status_code == 200 and "items" in eligibility.json()
        started = api.post(f"/api/v1/campaigns/{campaign_id}/start", headers=admin)
        assert started.status_code == 200 and started.json()["status"] == "RUNNING"
        paused = api.post(f"/api/v1/campaigns/{campaign_id}/pause", headers=admin)
        assert paused.status_code == 200 and paused.json()["status"] == "PAUSED"
        resumed = api.post(f"/api/v1/campaigns/{campaign_id}/resume", headers=admin)
        assert resumed.status_code == 200 and resumed.json()["status"] == "RUNNING"
        assert (
            api.get(f"/api/v1/campaigns/{campaign_id}/eligibility", headers=reviewer).status_code
            == 200
        )
        assert (
            api.post(f"/api/v1/campaigns/{campaign_id}/pause", headers=reviewer).status_code == 403
        )
        assert api.get(f"/api/v1/campaigns/{campaign_id}", headers=hospital_b).status_code == 404

    with httpx.Client(base_url=FRONTEND, timeout=30) as browser:
        assert browser.get("/campaigns").status_code == 200
        assert browser.get(f"/campaigns/{campaign_id}").status_code == 200
        response = browser.post(
            "/api/auth/login",
            headers={"Origin": FRONTEND},
            json={"email": "hospital_admin.1@example.test", "password": PASSWORD},
        )
        assert response.status_code == 200, response.text
        assert browser.get("/api/backend/campaigns?limit=25").status_code == 200
        assert browser.get(f"/api/backend/campaigns/{campaign_id}/estimate").status_code == 200
        assert (
            browser.get(f"/api/backend/campaigns/{campaign_id}/eligibility?limit=25").status_code
            == 200
        )
    print(
        "PASS: campaign lifecycle, estimate, eligibility, reviewer boundary, tenant boundary, frontend proxy/pages"
    )


if __name__ == "__main__":
    main()
