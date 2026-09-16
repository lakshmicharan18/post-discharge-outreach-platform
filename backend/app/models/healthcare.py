from datetime import datetime, time
from decimal import Decimal
from uuid import UUID

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    ForeignKeyConstraint,
    Integer,
    Numeric,
    String,
    Text,
    Time,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.models.entities import Base, Identity, Tenant, Timestamps


class HospitalConfiguration(Identity, Timestamps, Base):
    __tablename__ = "hospital_configurations"
    __table_args__ = (
        UniqueConstraint("hospital_id"),
        CheckConstraint("calling_window_end > calling_window_start", name="calling_window"),
        CheckConstraint("default_follow_up_hours > 0", name="follow_up_hours"),
        CheckConstraint("max_concurrent_calls > 0", name="concurrent_calls"),
        CheckConstraint("default_max_retries >= 0", name="max_retries"),
        CheckConstraint("retry_initial_delay_minutes > 0", name="retry_delay"),
        CheckConstraint("retry_backoff_multiplier >= 1", name="retry_backoff"),
    )

    hospital_id: Mapped[UUID] = mapped_column(ForeignKey("hospitals.id"), index=True)
    timezone: Mapped[str] = mapped_column(String(100), default="UTC")
    calling_window_start: Mapped[time] = mapped_column(Time, default=time(9, 0))
    calling_window_end: Mapped[time] = mapped_column(Time, default=time(17, 0))
    default_follow_up_hours: Mapped[int] = mapped_column(Integer, default=72)
    max_concurrent_calls: Mapped[int] = mapped_column(Integer, default=10)
    default_max_retries: Mapped[int] = mapped_column(Integer, default=3)
    retry_initial_delay_minutes: Mapped[int] = mapped_column(Integer, default=60)
    retry_backoff_multiplier: Mapped[Decimal] = mapped_column(Numeric(5, 2), default=2)
    notification_preferences: Mapped[dict] = mapped_column(JSONB, default=dict)
    escalation_contacts: Mapped[list[dict]] = mapped_column(JSONB, default=list)
    ehr_settings: Mapped[dict] = mapped_column(JSONB, default=dict)
    is_ready: Mapped[bool] = mapped_column(Boolean, default=False)


class ClinicalResource:
    hospital_id: Mapped[UUID] = mapped_column(ForeignKey("hospitals.id"), index=True)
    patient_id: Mapped[UUID] = mapped_column(index=True)
    encounter_id: Mapped[UUID | None] = mapped_column(index=True)
    external_id: Mapped[str] = mapped_column(String(150))


def resource_foreign_keys() -> tuple[ForeignKeyConstraint, ForeignKeyConstraint]:
    return (
        ForeignKeyConstraint(
            ["hospital_id", "patient_id"], ["patients.hospital_id", "patients.id"]
        ),
        ForeignKeyConstraint(
            ["hospital_id", "patient_id", "encounter_id"],
            ["encounters.hospital_id", "encounters.patient_id", "encounters.id"],
        ),
    )


class Condition(Identity, ClinicalResource, Timestamps, Base):
    __tablename__ = "conditions"
    __table_args__ = (*resource_foreign_keys(), UniqueConstraint("hospital_id", "external_id"))

    code: Mapped[str] = mapped_column(String(100))
    display_name: Mapped[str] = mapped_column(String(250))
    clinical_status: Mapped[str] = mapped_column(String(30), default="ACTIVE")
    onset_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    notes: Mapped[str | None] = mapped_column(Text)


class Observation(Identity, ClinicalResource, Timestamps, Base):
    __tablename__ = "observations"
    __table_args__ = (*resource_foreign_keys(), UniqueConstraint("hospital_id", "external_id"))

    code: Mapped[str] = mapped_column(String(100))
    display_name: Mapped[str] = mapped_column(String(250))
    value: Mapped[dict] = mapped_column(JSONB)
    unit: Mapped[str | None] = mapped_column(String(50))
    value_type: Mapped[str] = mapped_column(String(30))
    observed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    source: Mapped[str] = mapped_column(String(100), default="IMPORT")


class Medication(Identity, ClinicalResource, Timestamps, Base):
    __tablename__ = "medications"
    __table_args__ = (*resource_foreign_keys(), UniqueConstraint("hospital_id", "external_id"))

    medication_name: Mapped[str] = mapped_column(String(250))
    medication_code: Mapped[str | None] = mapped_column(String(100))
    dose: Mapped[str | None] = mapped_column(String(100))
    route: Mapped[str | None] = mapped_column(String(100))
    frequency: Mapped[str | None] = mapped_column(String(100))
    instructions: Mapped[str | None] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(30), default="ACTIVE")
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    ended_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class CarePlan(Identity, ClinicalResource, Timestamps, Base):
    __tablename__ = "care_plans"
    __table_args__ = (*resource_foreign_keys(), UniqueConstraint("hospital_id", "external_id"))

    title: Mapped[str] = mapped_column(String(250))
    description: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(30), default="ACTIVE")
    follow_up_instructions: Mapped[str] = mapped_column(Text)
    start_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    end_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class Procedure(Identity, ClinicalResource, Timestamps, Base):
    __tablename__ = "procedures"
    __table_args__ = (*resource_foreign_keys(), UniqueConstraint("hospital_id", "external_id"))

    code: Mapped[str | None] = mapped_column(String(100))
    name: Mapped[str] = mapped_column(String(250))
    performed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), index=True)
    status: Mapped[str] = mapped_column(String(30), default="COMPLETED")
    notes: Mapped[str | None] = mapped_column(Text)


class DischargeImport(Identity, Tenant, Timestamps, Base):
    __tablename__ = "discharge_imports"
    __table_args__ = (
        UniqueConstraint("hospital_id", "source_digest"),
        CheckConstraint(
            "status IN ('PENDING', 'PROCESSING', 'COMPLETED', 'PARTIALLY_COMPLETED', 'FAILED')",
            name="status",
        ),
    )

    source: Mapped[str] = mapped_column(String(255))
    source_digest: Mapped[str] = mapped_column(String(64))
    status: Mapped[str] = mapped_column(String(30), default="PENDING", index=True)
    total_records: Mapped[int] = mapped_column(Integer, default=0)
    successful_records: Mapped[int] = mapped_column(Integer, default=0)
    failed_records: Mapped[int] = mapped_column(Integer, default=0)
    errors: Mapped[list[dict]] = mapped_column(JSONB, default=list)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_by_user_id: Mapped[UUID] = mapped_column(ForeignKey("users.id"), index=True)


class AuditEvent(Identity, Tenant, Base):
    __tablename__ = "audit_events"

    actor_user_id: Mapped[UUID] = mapped_column(ForeignKey("users.id"), index=True)
    action: Mapped[str] = mapped_column(String(100), index=True)
    resource_type: Mapped[str] = mapped_column(String(100))
    resource_id: Mapped[UUID | None] = mapped_column()
    details: Mapped[dict] = mapped_column(JSONB, default=dict)
    occurred_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), index=True
    )
