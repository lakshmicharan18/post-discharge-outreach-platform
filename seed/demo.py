"""Idempotent synthetic seed. Run from backend: uv run python ../seed/demo.py."""

import asyncio
import sys
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from uuid import UUID

project_root = Path(__file__).resolve().parents[1]
backend_root = project_root / "backend"
sys.path.insert(0, str(backend_root if backend_root.is_dir() else project_root))

from sqlalchemy import select  # noqa: E402

from app.core.config import get_settings  # noqa: E402
from app.core.database import SessionFactory, engine  # noqa: E402
from app.models.entities import Discharge, Encounter, Hospital, Patient, Role, User  # noqa: E402


def seed_id(number: int) -> UUID:
    return UUID(int=number)


async def seed() -> None:
    if get_settings().environment == "production":
        raise RuntimeError("Demo seed is disabled in production")
    async with SessionFactory.begin() as session:
        for tenant in (1, 2):
            hospital = await session.scalar(
                select(Hospital).where(Hospital.code == f"HOSPITAL_{tenant}")
            )
            if hospital is None:
                hospital = Hospital(
                    id=seed_id(tenant),
                    name=f"Hospital {'A' if tenant == 1 else 'B'}",
                    code=f"HOSPITAL_{tenant}",
                    timezone="Asia/Kolkata",
                )
                session.add(hospital)
                await session.flush()
            for index, role in enumerate(
                (Role.HOSPITAL_ADMIN, Role.CAMPAIGN_MANAGER, Role.CLINICAL_REVIEWER)
            ):
                email = f"{role.value.lower()}.{tenant}@example.test"
                if await session.scalar(select(User).where(User.email == email)) is None:
                    session.add(
                        User(
                            id=seed_id(tenant * 100 + index),
                            hospital_id=hospital.id,
                            email=email,
                            full_name=f"Demo {role.value}",
                            role=role,
                        )
                    )
            for index in range(3):
                external_id = f"DEMO-{index + 1}"
                patient = await session.scalar(
                    select(Patient).where(
                        Patient.hospital_id == hospital.id,
                        Patient.external_patient_id == external_id,
                    )
                )
                if patient is not None:
                    continue
                patient = Patient(
                    id=seed_id(tenant * 1000 + index),
                    hospital_id=hospital.id,
                    external_patient_id=external_id,
                    first_name=f"Synthetic{index + 1}",
                    last_name=f"Hospital{tenant}",
                    date_of_birth=date(1980 + index, 1, 1),
                    phone=f"+1202555010{index}",
                    preferred_language="en",
                    communication_preferences={"voice": True, "sms": False},
                )
                session.add(patient)
                await session.flush()
                discharge_at = datetime(2026, 1, 10, 12, tzinfo=timezone.utc)
                encounter = Encounter(
                    id=seed_id(tenant * 10000 + index),
                    hospital_id=hospital.id,
                    patient_id=patient.id,
                    external_encounter_id=external_id,
                    care_setting="INPATIENT",
                    admit_at=discharge_at - timedelta(days=2),
                    discharge_at=discharge_at,
                    status="DISCHARGED",
                )
                session.add(encounter)
                await session.flush()
                session.add(
                    Discharge(
                        id=seed_id(tenant * 100000 + index),
                        hospital_id=hospital.id,
                        patient_id=patient.id,
                        encounter_id=encounter.id,
                        discharge_at=discharge_at,
                        follow_up_deadline=discharge_at + timedelta(days=3),
                        risk_level="UNKNOWN",
                        discharge_instructions="Synthetic demo instructions.",
                    )
                )
        if await session.get(User, seed_id(999)) is None:
            session.add(
                User(
                    id=seed_id(999),
                    email="platform.admin@example.test",
                    full_name="Demo Platform Admin",
                    role=Role.PLATFORM_ADMIN,
                )
            )
    await engine.dispose()
    print("Synthetic seed ready. Hospital A admin:", seed_id(100))
    print("Hospital B admin:", seed_id(200), "Platform admin:", seed_id(999))


if __name__ == "__main__":
    asyncio.run(seed())
