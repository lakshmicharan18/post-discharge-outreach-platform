import os
from collections.abc import AsyncIterator
from datetime import date, datetime, timedelta, timezone
from uuid import UUID

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.engine import make_url
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine

# Require an explicitly selected disposable PostgreSQL database before importing app.
TEST_URL = os.environ.get("TEST_DATABASE_URL")
if not TEST_URL or not (make_url(TEST_URL).database or "").endswith("_test"):
    raise RuntimeError("Set TEST_DATABASE_URL to a migrated PostgreSQL database ending in _test")
os.environ["DATABASE_URL"] = TEST_URL
os.environ["ENVIRONMENT"] = "test"
os.environ["ENABLE_DEV_AUTH"] = "true"

from app.core.database import get_session  # noqa: E402
from app.main import app  # noqa: E402
from app.models.entities import Discharge, Encounter, Hospital, Patient, Role, User  # noqa: E402


def uid(number: int) -> UUID:
    return UUID(int=number)


@pytest.fixture
async def session() -> AsyncIterator[AsyncSession]:
    engine = create_async_engine(TEST_URL)
    async with engine.connect() as connection:
        transaction = await connection.begin()
        async with AsyncSession(
            bind=connection, expire_on_commit=False, join_transaction_mode="create_savepoint"
        ) as session:
            for tenant in (1, 2):
                session.add(Hospital(id=uid(tenant), name=f"Hospital {tenant}", code=f"H{tenant}"))
            await session.flush()
            for tenant in (1, 2):
                session.add(
                    User(
                        id=uid(tenant * 10),
                        hospital_id=uid(tenant),
                        email=f"admin{tenant}@example.test",
                        full_name="Test Admin",
                        role=Role.HOSPITAL_ADMIN,
                    )
                )
                for i in range(3):
                    session.add(
                        Patient(
                            id=uid(tenant * 100 + i),
                            hospital_id=uid(tenant),
                            external_patient_id=f"P{i}",
                            first_name="Synthetic",
                            last_name="Patient",
                            date_of_birth=date(1980, 1, 1),
                            phone="+12025550101",
                        )
                    )
            session.add(
                User(
                    id=uid(99),
                    email="platform@example.test",
                    full_name="Platform",
                    role=Role.PLATFORM_ADMIN,
                )
            )
            await session.flush()
            now = datetime.now(timezone.utc)
            for tenant in (1, 2):
                session.add(
                    Encounter(
                        id=uid(tenant * 1000),
                        hospital_id=uid(tenant),
                        patient_id=uid(tenant * 100),
                        external_encounter_id="E1",
                        care_setting="INPATIENT",
                        admit_at=now - timedelta(days=1),
                        discharge_at=now,
                        status="DISCHARGED",
                    )
                )
            await session.flush()
            for tenant in (1, 2):
                session.add(
                    Discharge(
                        id=uid(tenant * 10000),
                        hospital_id=uid(tenant),
                        patient_id=uid(tenant * 100),
                        encounter_id=uid(tenant * 1000),
                        discharge_at=now,
                        follow_up_deadline=now + timedelta(days=2),
                        discharge_instructions="Synthetic",
                    )
                )
            await session.flush()
            yield session
        await transaction.rollback()
    await engine.dispose()


@pytest.fixture
async def client(session: AsyncSession) -> AsyncIterator[AsyncClient]:
    async def override_session():
        yield session

    app.dependency_overrides[get_session] = override_session
    async with AsyncClient(
        transport=ASGITransport(app=app, raise_app_exceptions=False), base_url="http://test"
    ) as client:
        yield client
    app.dependency_overrides.clear()
