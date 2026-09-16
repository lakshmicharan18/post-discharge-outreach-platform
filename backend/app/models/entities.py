import enum
from datetime import date, datetime
from uuid import UUID, uuid4

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Date,
    DateTime,
    Enum,
    ForeignKey,
    ForeignKeyConstraint,
    Index,
    MetaData,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    metadata = MetaData(
        naming_convention={
            "ix": "ix_%(table_name)s_%(column_0_name)s",
            "uq": "uq_%(table_name)s_%(column_0_N_name)s",
            "ck": "ck_%(table_name)s_%(constraint_name)s",
            "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
            "pk": "pk_%(table_name)s",
        }
    )


class Role(str, enum.Enum):
    PLATFORM_ADMIN = "PLATFORM_ADMIN"
    HOSPITAL_ADMIN = "HOSPITAL_ADMIN"
    CAMPAIGN_MANAGER = "CAMPAIGN_MANAGER"
    CLINICAL_REVIEWER = "CLINICAL_REVIEWER"


class Identity:
    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)


class Timestamps:
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class Tenant:
    hospital_id: Mapped[UUID] = mapped_column(ForeignKey("hospitals.id"), index=True)


class Hospital(Identity, Timestamps, Base):
    __tablename__ = "hospitals"
    __table_args__ = (CheckConstraint("status IN ('ACTIVE', 'INACTIVE')", name="status"),)
    name: Mapped[str] = mapped_column(String(200))
    code: Mapped[str] = mapped_column(String(50), unique=True)
    timezone: Mapped[str] = mapped_column(String(100), default="UTC")
    status: Mapped[str] = mapped_column(String(20), default="ACTIVE")


class User(Identity, Timestamps, Base):
    __tablename__ = "users"
    __table_args__ = (
        CheckConstraint(
            "(role = 'PLATFORM_ADMIN' AND hospital_id IS NULL) OR "
            "(role <> 'PLATFORM_ADMIN' AND hospital_id IS NOT NULL)",
            name="role_tenant",
        ),
    )
    hospital_id: Mapped[UUID | None] = mapped_column(ForeignKey("hospitals.id"), index=True)
    email: Mapped[str] = mapped_column(String(254), unique=True)
    password_hash: Mapped[str | None] = mapped_column(String(255))
    full_name: Mapped[str] = mapped_column(String(200))
    role: Mapped[Role] = mapped_column(Enum(Role, name="user_role"))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)


class Patient(Identity, Tenant, Timestamps, Base):
    __tablename__ = "patients"
    __table_args__ = (
        UniqueConstraint("hospital_id", "external_patient_id"),
        UniqueConstraint("hospital_id", "id"),
    )
    external_patient_id: Mapped[str] = mapped_column(String(100))
    first_name: Mapped[str] = mapped_column(String(100))
    last_name: Mapped[str] = mapped_column(String(100))
    date_of_birth: Mapped[date] = mapped_column(Date)
    phone: Mapped[str] = mapped_column(String(32))
    preferred_language: Mapped[str] = mapped_column(String(35), default="en")
    communication_preferences: Mapped[dict[str, bool]] = mapped_column(JSONB, default=dict)


class Encounter(Identity, Tenant, Timestamps, Base):
    __tablename__ = "encounters"
    __table_args__ = (
        ForeignKeyConstraint(
            ["hospital_id", "patient_id"], ["patients.hospital_id", "patients.id"]
        ),
        UniqueConstraint("hospital_id", "external_encounter_id"),
        UniqueConstraint("hospital_id", "patient_id", "id"),
        CheckConstraint("discharge_at IS NULL OR discharge_at >= admit_at", name="chronology"),
        CheckConstraint(
            "care_setting IN ('INPATIENT', 'OUTPATIENT', 'EMERGENCY')", name="care_setting"
        ),
        CheckConstraint("status IN ('ADMITTED', 'DISCHARGED', 'CANCELLED')", name="status"),
    )
    patient_id: Mapped[UUID] = mapped_column(index=True)
    external_encounter_id: Mapped[str] = mapped_column(String(100))
    care_setting: Mapped[str] = mapped_column(String(30))
    admit_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    discharge_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    status: Mapped[str] = mapped_column(String(30), default="ADMITTED")


class Discharge(Identity, Tenant, Timestamps, Base):
    __tablename__ = "discharges"
    __table_args__ = (
        ForeignKeyConstraint(
            ["hospital_id", "patient_id"], ["patients.hospital_id", "patients.id"]
        ),
        ForeignKeyConstraint(
            ["hospital_id", "patient_id", "encounter_id"],
            ["encounters.hospital_id", "encounters.patient_id", "encounters.id"],
        ),
        UniqueConstraint("hospital_id", "encounter_id"),
        UniqueConstraint("hospital_id", "source_reference"),
        CheckConstraint("follow_up_deadline >= discharge_at", name="chronology"),
        CheckConstraint("risk_level IN ('LOW', 'MEDIUM', 'HIGH', 'UNKNOWN')", name="risk_level"),
        CheckConstraint("status IN ('PENDING', 'COMPLETED', 'CANCELLED')", name="status"),
    )
    patient_id: Mapped[UUID] = mapped_column(index=True)
    encounter_id: Mapped[UUID] = mapped_column(index=True)
    discharge_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    follow_up_deadline: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    follow_up_window_hours: Mapped[int] = mapped_column(default=72)
    disposition: Mapped[str] = mapped_column(String(50), default="HOME")
    risk_level: Mapped[str] = mapped_column(String(20), default="UNKNOWN", index=True)
    risk_indicators: Mapped[list[str]] = mapped_column(JSONB, default=list)
    discharge_instructions: Mapped[str] = mapped_column(Text)
    communication_eligible: Mapped[bool] = mapped_column(Boolean, default=True)
    source_reference: Mapped[str | None] = mapped_column(String(200))
    status: Mapped[str] = mapped_column(String(30), default="PENDING")


Index("uq_users_email_lower", func.lower(User.email), unique=True)
