"""Generate a deterministic 240-patient synthetic discharge dataset."""

import asyncio
import random
import sys
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

project_root = Path(__file__).resolve().parents[1]
backend_root = project_root / "backend"
sys.path.insert(0, str(backend_root if backend_root.is_dir() else project_root))

from sqlalchemy import select  # noqa: E402

from app.core.config import get_settings  # noqa: E402
from app.core.context import RequestContext  # noqa: E402
from app.core.database import SessionFactory, engine  # noqa: E402
from app.models.entities import Hospital, Role, User  # noqa: E402
from app.schemas.healthcare import DischargeBatchImportRequest  # noqa: E402
from app.services.ingestion import DischargeIngestionService  # noqa: E402

DATASET_SEED = 20260916
PATIENTS_PER_HOSPITAL = 120
ANCHOR = datetime(2026, 9, 15, 12, tzinfo=timezone.utc)


def build_record(tenant: int, index: int, rng: random.Random) -> dict:
    prefix = f"SYN-T{tenant}-{index:03d}"
    discharge_at = ANCHOR - timedelta(hours=rng.randint(1, 24 * 21))
    stay_hours = rng.randint(12, 120)
    follow_up_hours = rng.choice((24, 48, 72, 96, 120, 168))
    risk = rng.choices(("LOW", "MEDIUM", "HIGH"), weights=(55, 30, 15), k=1)[0]
    condition_code, condition_name = rng.choice(
        (
            ("I10", "Hypertension"),
            ("E11", "Type 2 diabetes"),
            ("J18", "Pneumonia"),
            ("I50", "Heart failure"),
            ("S72", "Hip fracture"),
        )
    )
    medication_name = rng.choice(
        ("Synthetic Med Alpha", "Synthetic Med Beta", "Synthetic Med Gamma")
    )
    return {
        "patient": {
            "external_patient_id": prefix,
            "first_name": f"Synthetic{tenant}{index:03d}",
            "last_name": "DemoPatient",
            "date_of_birth": date(
                1940 + (index % 60), 1 + (index % 12), 1 + (index % 27)
            ).isoformat(),
            "phone": f"+1202{tenant}{index:06d}",
            "preferred_language": rng.choice(("en", "en", "en", "hi", "es")),
            "communication_preferences": {
                "voice": index % 7 != 0,
                "sms": index % 3 == 0,
            },
        },
        "encounter": {
            "external_encounter_id": f"{prefix}-ENC",
            "care_setting": rng.choice(("INPATIENT", "INPATIENT", "EMERGENCY", "OUTPATIENT")),
            "admit_at": (discharge_at - timedelta(hours=stay_hours)).isoformat(),
            "discharge_at": discharge_at.isoformat(),
            "status": "DISCHARGED",
        },
        "discharge": {
            "discharge_at": discharge_at.isoformat(),
            "follow_up_window_hours": follow_up_hours,
            "disposition": rng.choice(("HOME", "HOME", "HOME_HEALTH", "SKILLED_NURSING")),
            "risk_level": risk,
            "risk_indicators": [
                indicator
                for indicator, include in (
                    ("recent_emergency_visit", index % 11 == 0),
                    ("multiple_medications", index % 5 == 0),
                    ("limited_support", index % 13 == 0),
                )
                if include
            ],
            "discharge_instructions": "Synthetic follow-up instructions for prototype use only.",
            "communication_eligible": index % 17 != 0,
            "status": "PENDING",
            "source_reference": f"{prefix}-DISCHARGE",
        },
        "conditions": [
            {
                "external_id": f"{prefix}-COND-1",
                "code": condition_code,
                "display_name": condition_name,
                "clinical_status": "ACTIVE",
                "onset_at": (discharge_at - timedelta(days=30 + index)).isoformat(),
            }
        ],
        "observations": [
            {
                "external_id": f"{prefix}-OBS-1",
                "code": "8867-4",
                "display_name": "Heart rate",
                "value": 60 + (index % 45),
                "unit": "beats/min",
                "value_type": "INTEGER",
                "observed_at": (discharge_at - timedelta(hours=2)).isoformat(),
                "source": "SYNTHETIC_IMPORT",
            }
        ],
        "medications": [
            {
                "external_id": f"{prefix}-MED-1",
                "medication_name": medication_name,
                "dose": rng.choice(("5 mg", "10 mg", "20 mg")),
                "route": "oral",
                "frequency": rng.choice(("once daily", "twice daily")),
                "instructions": "Synthetic medication instruction; not for clinical use.",
                "status": "ACTIVE",
                "started_at": discharge_at.isoformat(),
            }
        ],
        "care_plans": [
            {
                "external_id": f"{prefix}-PLAN-1",
                "title": "Synthetic post-discharge plan",
                "description": "Prototype follow-up plan.",
                "status": "ACTIVE",
                "follow_up_instructions": f"Contact within {follow_up_hours} hours.",
                "start_at": discharge_at.isoformat(),
                "end_at": (discharge_at + timedelta(days=30)).isoformat(),
            }
        ],
        "procedures": (
            [
                {
                    "external_id": f"{prefix}-PROC-1",
                    "code": "SYN-PROC",
                    "name": "Synthetic diagnostic procedure",
                    "performed_at": (discharge_at - timedelta(hours=6)).isoformat(),
                    "status": "COMPLETED",
                }
            ]
            if index % 2 == 0
            else []
        ),
    }


async def generate() -> None:
    if get_settings().environment == "production":
        raise RuntimeError("Synthetic generation is disabled in production")
    rng = random.Random(DATASET_SEED)
    async with SessionFactory() as session:
        for tenant in (1, 2):
            hospital = await session.scalar(
                select(Hospital).where(Hospital.code == f"HOSPITAL_{tenant}")
            )
            admin = await session.scalar(
                select(User).where(
                    User.hospital_id == hospital.id if hospital is not None else False,
                    User.role == Role.HOSPITAL_ADMIN,
                )
            )
            if hospital is None or admin is None:
                raise RuntimeError("Run seed/demo.py before generating the synthetic dataset")
            records = [build_record(tenant, index, rng) for index in range(PATIENTS_PER_HOSPITAL)]
            context = RequestContext(admin.id, hospital.id, admin.role, admin.is_active)
            result = await DischargeIngestionService(session, context).import_batch(
                DischargeBatchImportRequest(
                    source=f"deterministic-synthetic-v1-hospital-{tenant}", records=records
                )
            )
            if result.failed_records:
                raise RuntimeError(
                    f"Synthetic generation failed for Hospital {tenant}: {result.errors}"
                )
            print(
                f"Hospital {tenant}: {result.successful_records}/{result.total_records} records; "
                f"import {result.id} ({result.status})"
            )
    await engine.dispose()
    print(f"Synthetic dataset ready: {PATIENTS_PER_HOSPITAL * 2} patients, seed {DATASET_SEED}")


if __name__ == "__main__":
    asyncio.run(generate())
