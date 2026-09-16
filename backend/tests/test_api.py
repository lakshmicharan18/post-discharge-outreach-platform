import pytest
from conftest import uid
from sqlalchemy.exc import OperationalError
from test_tenant_isolation import headers

from app.core.config import Settings, get_settings
from app.core.database import get_session
from app.main import app
from app.models.entities import Hospital, User


async def test_health(client):
    response = await client.get("/api/v1/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok", "database": "ok"}


async def test_auth_required_and_unknown_user(client):
    for identity in (None, str(uid(9999))):
        response = await client.get(
            "/api/v1/patients", headers={"X-Dev-User-ID": identity} if identity else {}
        )
        assert response.status_code == 401
        assert response.json()["error"]["request_id"] == response.headers["X-Request-ID"]


async def test_dev_auth_can_be_disabled(client, monkeypatch):
    monkeypatch.setattr(get_settings(), "enable_dev_auth", False)
    assert (await client.get("/api/v1/patients", headers=headers())).status_code == 401


@pytest.mark.parametrize(
    "model,field,value", [(User, "is_active", False), (Hospital, "status", "INACTIVE")]
)
async def test_inactive_identity_or_hospital_denied(client, session, model, field, value):
    record = await session.get(model, uid(10 if model is User else 1))
    setattr(record, field, value)
    await session.flush()
    assert (await client.get("/api/v1/patients", headers=headers())).status_code in (401, 403)


async def test_platform_metadata_is_separate(client):
    assert (await client.get("/api/v1/platform/hospitals", headers=headers())).status_code == 403
    response = await client.get(
        "/api/v1/platform/hospitals", headers={"X-Dev-User-ID": str(uid(99))}
    )
    assert response.status_code == 200
    assert len(response.json()) == 2
    response = await client.post(
        "/api/v1/platform/hospitals",
        headers={"X-Dev-User-ID": str(uid(99))},
        json={"name": "Hospital C", "code": "C", "timezone": "Asia/Kolkata"},
    )
    assert response.status_code == 201


@pytest.mark.parametrize(
    "path",
    ["/api/v1/patients/not-a-uuid", "/api/v1/patients?limit=101", "/api/v1/patients?offset=-1"],
)
async def test_validation_has_safe_error_envelope(client, path):
    response = await client.get(path, headers=headers())
    assert response.status_code == 422
    assert set(response.json()["error"]) == {"code", "message", "request_id"}


async def test_naive_timestamps_rejected(client):
    response = await client.post(
        "/api/v1/encounters",
        headers=headers(),
        json={
            "patient_id": str(uid(100)),
            "external_encounter_id": "BAD",
            "care_setting": "INPATIENT",
            "admit_at": "2026-01-01T00:00:00",
        },
    )
    assert response.status_code == 422


async def test_database_error_is_redacted(client):
    async def broken_session():
        raise OperationalError("sensitive SQL", {"patient": "private"}, Exception("secret"))
        yield

    app.dependency_overrides[get_session] = broken_session
    response = await client.get("/api/v1/health")
    assert response.status_code == 503
    assert "secret" not in response.text and "private" not in response.text


async def test_pagination(client):
    first = await client.get("/api/v1/patients?limit=2", headers=headers())
    second = await client.get("/api/v1/patients?limit=2&offset=2", headers=headers())
    assert len(first.json()) == 2 and len(second.json()) == 1
    assert {row["id"] for row in first.json()}.isdisjoint({row["id"] for row in second.json()})


def test_production_rejects_dev_auth():
    with pytest.raises(ValueError, match="Development authentication"):
        Settings(
            database_url="postgresql+psycopg://localhost/example",
            environment="production",
            enable_dev_auth=True,
        )
