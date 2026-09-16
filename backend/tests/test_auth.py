from datetime import datetime, timedelta, timezone
from uuid import uuid4

import jwt
import pytest
from conftest import TEST_PASSWORD, auth_headers, uid
from sqlalchemy import select

from app.core.config import get_settings
from app.core.context import RequestContext
from app.core.errors import APIError
from app.core.security import AUDIENCE, ISSUER, create_access_token, verify_password
from app.models.entities import Hospital, Patient, Role, User
from app.repositories.clinical import ClinicalRepository
from app.repositories.users import UserRepository
from app.schemas.entities import PatientCreate
from app.services.clinical import ClinicalService


async def login(client, email="admin1@example.test", password=TEST_PASSWORD):
    return await client.post("/api/v1/auth/login", json={"email": email, "password": password})


def signed_claims(**changes):
    now = datetime.now(timezone.utc)
    claims = {
        "sub": str(uid(10)),
        "iat": int(now.timestamp()),
        "exp": int((now + timedelta(minutes=30)).timestamp()),
        "iss": ISSUER,
        "aud": AUDIENCE,
    }
    claims.update(changes)
    return jwt.encode(claims, get_settings().jwt_secret.get_secret_value(), algorithm="HS256")


async def test_valid_login_and_me(client):
    response = await login(client)
    assert response.status_code == 200, response.text
    result = response.json()
    assert result["token_type"] == "bearer"
    assert result["expires_in"] == get_settings().jwt_access_token_expire_minutes * 60
    assert result["user"]["id"] == str(uid(10))
    assert result["user"]["hospital"]["id"] == str(uid(1))
    assert response.headers["cache-control"] == "no-store"
    response = await client.get(
        "/api/v1/users/me", headers={"Authorization": "Bearer " + result["access_token"]}
    )
    assert response.status_code == 200
    assert response.json() == result["user"]
    claims = jwt.decode(
        result["access_token"],
        get_settings().jwt_secret.get_secret_value(),
        algorithms=["HS256"],
        audience=AUDIENCE,
        issuer=ISSUER,
    )
    assert set(claims) == {"sub", "iat", "exp", "iss", "aud"}
    assert claims["exp"] - claims["iat"] == result["expires_in"]
    assert "password" not in response.text and "password_hash" not in response.text


@pytest.mark.parametrize(
    "email,password",
    [("admin1@example.test", "incorrect"), ("missing@example.test", TEST_PASSWORD)],
)
async def test_credentials_failure_is_generic(client, email, password):
    response = await login(client, email, password)
    assert response.status_code == 401
    assert response.json()["error"]["code"] == "invalid_credentials"
    assert response.json()["error"]["message"] == "Invalid email or password"
    assert response.headers["www-authenticate"] == "Bearer"


@pytest.mark.parametrize("field,value", [("is_active", False), ("password_hash", None)])
async def test_disabled_or_unprovisioned_user_cannot_login_or_use_token(
    client, session, field, value
):
    token = create_access_token(uid(10))
    user = await session.get(User, uid(10))
    setattr(user, field, value)
    await session.flush()
    assert (await login(client)).status_code == 401
    assert (
        await client.get("/api/v1/users/me", headers={"Authorization": f"Bearer {token}"})
    ).status_code == 401


async def test_inactive_hospital_cannot_login(client, session):
    hospital = await session.get(Hospital, uid(1))
    hospital.status = "INACTIVE"
    await session.flush()
    assert (await login(client)).status_code == 403


@pytest.mark.parametrize(
    "authorization", [None, "Bearer broken", "Basic abc", "Bearer", "Bearer null"]
)
async def test_missing_or_malformed_token(client, authorization):
    response = await client.get(
        "/api/v1/users/me", headers={"Authorization": authorization} if authorization else {}
    )
    assert response.status_code == 401


@pytest.mark.parametrize(
    "kind",
    [
        "expired",
        "wrong_signature",
        "none_algorithm",
        "wrong_algorithm",
        "missing_exp",
        "missing_iat",
        "bad_sub",
        "future_iat",
        "wrong_issuer",
        "wrong_audience",
        "unknown_user",
    ],
)
async def test_invalid_signed_tokens(client, kind):
    now = int(datetime.now(timezone.utc).timestamp())
    claims = {"sub": str(uid(10)), "iat": now, "exp": now + 120, "iss": ISSUER, "aud": AUDIENCE}
    key = get_settings().jwt_secret.get_secret_value()
    algorithm = "HS256"
    if kind == "expired":
        claims.update(iat=now - 120, exp=now - 60)
    if kind == "wrong_signature":
        key = "incorrect-test-key-only-" * 3
    if kind == "none_algorithm":
        algorithm, key = "none", ""
    if kind == "wrong_algorithm":
        algorithm = "HS512"
    if kind == "missing_exp":
        del claims["exp"]
    if kind == "missing_iat":
        del claims["iat"]
    if kind == "bad_sub":
        claims["sub"] = "invalid-uuid"
    if kind == "future_iat":
        claims["iat"] = now + 60
    if kind == "wrong_issuer":
        claims["iss"] = "another-service"
    if kind == "wrong_audience":
        claims["aud"] = "another-api"
    if kind == "unknown_user":
        claims["sub"] = str(uuid4())
    token = jwt.encode(claims, key, algorithm=algorithm)
    assert (
        await client.get("/api/v1/users/me", headers={"Authorization": f"Bearer {token}"})
    ).status_code == 401


async def test_identity_ignores_extra_claims_and_headers(client):
    token = signed_claims(role="PLATFORM_ADMIN", hospital_id=str(uid(2)))
    response = await client.get(
        "/api/v1/users/me",
        headers={
            "Authorization": f"Bearer {token}",
            "X-Role": "PLATFORM_ADMIN",
            "X-Hospital-ID": str(uid(2)),
            "X-Dev-User-ID": str(uid(99)),
        },
    )
    assert response.status_code == 200
    assert response.json()["role"] == "HOSPITAL_ADMIN"
    assert response.json()["hospital_id"] == str(uid(1))


async def test_current_database_role_overrides_previously_issued_token(client, session):
    response = await login(client)
    headers = {"Authorization": "Bearer " + response.json()["access_token"]}
    user = await session.get(User, uid(10))
    user.role = Role.CAMPAIGN_MANAGER
    await session.flush()
    assert (await client.get("/api/v1/users/me", headers=headers)).json()[
        "role"
    ] == "CAMPAIGN_MANAGER"
    assert (await client.get("/api/v1/users", headers=headers)).status_code == 403


@pytest.mark.parametrize("tenant", [1, 2])
async def test_user_list_is_hospital_scoped(client, tenant):
    response = await client.get("/api/v1/users", headers=auth_headers(tenant * 10))
    assert response.status_code == 200
    assert len(response.json()) == 3
    assert {row["hospital_id"] for row in response.json()} == {str(uid(tenant))}
    assert "password_hash" not in response.text


@pytest.mark.parametrize("user_id", [11, 12, 21, 22, 99])
@pytest.mark.parametrize("method", ["get", "post"])
async def test_other_roles_cannot_manage_users(client, user_id, method):
    response = await client.request(
        method,
        "/api/v1/users",
        headers=auth_headers(user_id),
        json={
            "email": "new@example.test",
            "full_name": "New",
            "role": "CLINICAL_REVIEWER",
            "password": TEST_PASSWORD,
        }
        if method == "post"
        else None,
    )
    assert response.status_code == 403


async def test_create_user_hashed_and_login_works(client, session):
    response = await client.post(
        "/api/v1/users",
        headers=auth_headers(10),
        json={
            "email": "NEW@EXAMPLE.TEST",
            "full_name": "New Reviewer",
            "role": "CLINICAL_REVIEWER",
            "password": TEST_PASSWORD,
        },
    )
    assert response.status_code == 201, response.text
    assert response.json()["hospital_id"] == str(uid(1))
    assert response.json()["email"] == "new@example.test"
    assert "password" not in response.text
    user = await session.scalar(select(User).where(User.email == "new@example.test"))
    assert user.password_hash != TEST_PASSWORD
    assert user.password_hash.startswith("$argon2id$")
    assert verify_password(TEST_PASSWORD, user.password_hash)
    authenticated = await login(client, "NEW@example.test")
    assert authenticated.status_code == 200
    assert authenticated.json()["user"]["role"] == "CLINICAL_REVIEWER"


@pytest.mark.parametrize(
    "extra,status",
    [
        ({"role": "PLATFORM_ADMIN"}, 403),
        ({"hospital_id": str(uid(2))}, 422),
        ({"password_hash": "forged"}, 422),
        ({"is_active": True}, 422),
    ],
)
async def test_user_creation_cannot_escalate_or_select_tenant(client, extra, status):
    response = await client.post(
        "/api/v1/users",
        headers=auth_headers(10),
        json={
            "email": "new@example.test",
            "full_name": "New",
            "role": "CLINICAL_REVIEWER",
            "password": TEST_PASSWORD,
            **extra,
        },
    )
    assert response.status_code == status


@pytest.mark.parametrize(
    "email", ["admin1@example.test", "ADMIN1@EXAMPLE.TEST", "admin2@example.test"]
)
async def test_email_uniqueness_is_global_case_insensitive_and_safe(client, email):
    response = await client.post(
        "/api/v1/users",
        headers=auth_headers(10),
        json={
            "email": email,
            "full_name": "New",
            "role": "CLINICAL_REVIEWER",
            "password": TEST_PASSWORD,
        },
    )
    assert response.status_code == 409
    assert email not in response.text
    assert "password" not in response.text


@pytest.mark.parametrize("user_id,tenant", [(11, 1), (12, 1), (21, 2), (22, 2)])
@pytest.mark.parametrize(
    "resource,multiplier", [("patients", 100), ("encounters", 1000), ("discharges", 10000)]
)
async def test_read_roles_tenant_boundary(client, user_id, tenant, resource, multiplier):
    headers = auth_headers(user_id)
    assert (
        await client.get(f"/api/v1/{resource}/{uid(tenant * multiplier)}", headers=headers)
    ).status_code == 200
    assert (
        await client.get(f"/api/v1/{resource}/{uid((3 - tenant) * multiplier)}", headers=headers)
    ).status_code == 404
    rows = await client.get(f"/api/v1/{resource}", headers=headers)
    assert {row["hospital_id"] for row in rows.json()} == {str(uid(tenant))}


@pytest.mark.parametrize("user_id", [11, 12, 99])
@pytest.mark.parametrize("resource", ["patients", "encounters", "discharges"])
async def test_clinical_writes_require_hospital_admin(client, user_id, resource):
    assert (
        await client.post(f"/api/v1/{resource}", headers=auth_headers(user_id), json={})
    ).status_code == 403


@pytest.mark.parametrize(
    "resource,multiplier", [("patients", 100), ("encounters", 1000), ("discharges", 10000)]
)
@pytest.mark.parametrize("tenant", [1, 2])
async def test_platform_cannot_get_arbitrary_clinical_record(client, tenant, resource, multiplier):
    assert (
        await client.get(f"/api/v1/{resource}/{uid(tenant * multiplier)}", headers=auth_headers(99))
    ).status_code == 403


async def test_service_repository_write_guards_cannot_be_bypassed(session):
    context = RequestContext(uid(11), uid(1), Role.CAMPAIGN_MANAGER)
    payload = PatientCreate(
        external_patient_id="DENIED",
        first_name="Test",
        last_name="Test",
        date_of_birth="1990-01-01",
        phone="+12025550111",
    )
    with pytest.raises(APIError) as error:
        await ClinicalService(session, context, Patient).create(payload)
    assert error.value.status == 403
    with pytest.raises(APIError):
        await ClinicalRepository(session, context, Patient).create(payload.model_dump())
    with pytest.raises(APIError):
        UserRepository(session, context)


async def test_secrets_are_not_logged_or_echoed(client, caplog):
    response = await login(client, password="Sensitive-Submitted-Password")
    assert response.status_code == 401
    invalid = await client.post(
        "/api/v1/auth/login", json={"email": "invalid", "password": "Sensitive-Submitted-Password"}
    )
    assert invalid.status_code == 422
    success = await login(client)
    token = success.json()["access_token"]
    assert "Sensitive-Submitted-Password" not in response.text + invalid.text + caplog.text
    assert token not in caplog.text
    assert "$argon2" not in caplog.text + success.text


async def test_password_whitespace_is_not_silently_stripped(client):
    password = "  Significant whitespace  "
    response = await client.post(
        "/api/v1/users",
        headers=auth_headers(10),
        json={
            "email": "spaces@example.test",
            "full_name": "Space",
            "role": "CLINICAL_REVIEWER",
            "password": password,
        },
    )
    assert response.status_code == 201
    assert (await login(client, "spaces@example.test", password)).status_code == 200
    assert (await login(client, "spaces@example.test", password.strip())).status_code == 401


async def test_token_expiration_is_configurable(client, monkeypatch):
    monkeypatch.setattr(get_settings(), "jwt_access_token_expire_minutes", 7)
    response = await login(client)
    assert response.json()["expires_in"] == 420
