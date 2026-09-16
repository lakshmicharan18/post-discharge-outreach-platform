"""Run against the local seeded backend and frontend: uv run python ../scripts/smoke_auth.py."""

import os

import httpx

API = os.environ.get("SMOKE_API_URL", "http://127.0.0.1:8000")
FRONTEND = os.environ.get("SMOKE_FRONTEND_URL", "http://127.0.0.1:3000")
PASSWORD = "DemoOnly-ChangeMe-2026!"  # Public synthetic-data demo credential only.


def verify() -> None:
    with httpx.Client(base_url=API, timeout=15) as api:
        assert api.get("/api/v1/health").status_code == 200
        assert api.get("/api/v1/patients").status_code == 401
        tokens = {}
        emails = ["platform.admin@example.test"] + [
            f"{role}.{tenant}@example.test"
            for tenant in (1, 2)
            for role in ("hospital_admin", "campaign_manager", "clinical_reviewer")
        ]
        for email in emails:
            response = api.post("/api/v1/auth/login", json={"email": email, "password": PASSWORD})
            assert response.status_code == 200, f"Demo login failed: {email}"
            assert "password" not in response.text
            tokens[email] = {"Authorization": "Bearer " + response.json()["access_token"]}
            assert api.get("/api/v1/users/me", headers=tokens[email]).status_code == 200
        a, b, platform = [
            tokens[email]
            for email in (
                "hospital_admin.1@example.test",
                "hospital_admin.2@example.test",
                "platform.admin@example.test",
            )
        ]
        patients_a = api.get("/api/v1/patients", headers=a).json()
        patients_b = api.get("/api/v1/patients", headers=b).json()
        assert len(patients_a) == len(patients_b) == 3
        assert api.get("/api/v1/patients/" + patients_b[0]["id"], headers=a).status_code == 404
        assert api.get("/api/v1/patients/" + patients_a[0]["id"], headers=b).status_code == 404
        assert api.get("/api/v1/patients", headers=platform).status_code == 403
        assert api.get("/api/v1/platform/hospitals", headers=platform).status_code == 200
    with httpx.Client(base_url=FRONTEND, timeout=15) as browser:
        assert browser.get("/login").status_code == 200
        assert browser.get("/api/auth/me").status_code == 401
        payload = {"email": "hospital_admin.1@example.test", "password": PASSWORD}
        assert (
            browser.post(
                "/api/auth/login", json=payload, headers={"Origin": "https://untrusted.example"}
            ).status_code
            == 403
        )
        response = browser.post("/api/auth/login", json=payload, headers={"Origin": FRONTEND})
        assert response.status_code == 200
        assert "access_token" not in response.json()
        cookie = response.headers["set-cookie"].lower()
        assert "httponly" in cookie and "samesite=strict" in cookie and "max-age=" in cookie
        assert response.headers["cache-control"] == "no-store"
        me = browser.get("/api/auth/me")
        assert me.status_code == 200
        assert me.json()["role"] == "HOSPITAL_ADMIN"
        assert me.json()["hospital"]["name"] == "Hospital A"
        assert (
            browser.post(
                "/api/auth/logout", headers={"Origin": "https://untrusted.example"}
            ).status_code
            == 403
        )
        assert browser.get("/api/auth/me").status_code == 200
        assert browser.post("/api/auth/logout", headers={"Origin": FRONTEND}).status_code == 200
        assert browser.get("/api/auth/me").status_code == 401
    print(
        "PASS: seven demo logins, tenant isolation, platform boundary, browser login/cookie/logout, origin checks"
    )


if __name__ == "__main__":
    verify()
