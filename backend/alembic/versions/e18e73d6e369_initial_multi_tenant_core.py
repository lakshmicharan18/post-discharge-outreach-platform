"""initial multi-tenant core

Revision ID: e18e73d6e369
Revises:
"""

from typing import Sequence, Union

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "e18e73d6e369"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "hospitals",
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("code", sa.String(length=50), nullable=False),
        sa.Column("timezone", sa.String(length=100), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint("status IN ('ACTIVE', 'INACTIVE')", name=op.f("ck_hospitals_status")),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_hospitals")),
        sa.UniqueConstraint("code", name=op.f("uq_hospitals_code")),
    )
    op.create_table(
        "patients",
        sa.Column("external_patient_id", sa.String(length=100), nullable=False),
        sa.Column("first_name", sa.String(length=100), nullable=False),
        sa.Column("last_name", sa.String(length=100), nullable=False),
        sa.Column("date_of_birth", sa.Date(), nullable=False),
        sa.Column("phone", sa.String(length=32), nullable=False),
        sa.Column("preferred_language", sa.String(length=35), nullable=False),
        sa.Column(
            "communication_preferences", postgresql.JSONB(astext_type=sa.Text()), nullable=False
        ),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("hospital_id", sa.Uuid(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["hospital_id"], ["hospitals.id"], name=op.f("fk_patients_hospital_id_hospitals")
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_patients")),
        sa.UniqueConstraint(
            "hospital_id",
            "external_patient_id",
            name=op.f("uq_patients_hospital_id_external_patient_id"),
        ),
        sa.UniqueConstraint("hospital_id", "id", name=op.f("uq_patients_hospital_id_id")),
    )
    op.create_index(op.f("ix_patients_hospital_id"), "patients", ["hospital_id"], unique=False)
    op.create_table(
        "users",
        sa.Column("hospital_id", sa.Uuid(), nullable=True),
        sa.Column("email", sa.String(length=254), nullable=False),
        sa.Column("full_name", sa.String(length=200), nullable=False),
        sa.Column(
            "role",
            sa.Enum(
                "PLATFORM_ADMIN",
                "HOSPITAL_ADMIN",
                "CAMPAIGN_MANAGER",
                "CLINICAL_REVIEWER",
                name="user_role",
            ),
            nullable=False,
        ),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "(role = 'PLATFORM_ADMIN' AND hospital_id IS NULL) OR (role <> 'PLATFORM_ADMIN' AND hospital_id IS NOT NULL)",
            name=op.f("ck_users_role_tenant"),
        ),
        sa.ForeignKeyConstraint(
            ["hospital_id"], ["hospitals.id"], name=op.f("fk_users_hospital_id_hospitals")
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_users")),
        sa.UniqueConstraint("email", name=op.f("uq_users_email")),
    )
    op.create_index(op.f("ix_users_hospital_id"), "users", ["hospital_id"], unique=False)
    op.create_table(
        "encounters",
        sa.Column("patient_id", sa.Uuid(), nullable=False),
        sa.Column("external_encounter_id", sa.String(length=100), nullable=False),
        sa.Column("care_setting", sa.String(length=30), nullable=False),
        sa.Column("admit_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("discharge_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("status", sa.String(length=30), nullable=False),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("hospital_id", sa.Uuid(), nullable=False),
        sa.CheckConstraint(
            "care_setting IN ('INPATIENT', 'OUTPATIENT', 'EMERGENCY')",
            name=op.f("ck_encounters_care_setting"),
        ),
        sa.CheckConstraint(
            "status IN ('ADMITTED', 'DISCHARGED', 'CANCELLED')", name=op.f("ck_encounters_status")
        ),
        sa.CheckConstraint(
            "discharge_at IS NULL OR discharge_at >= admit_at",
            name=op.f("ck_encounters_chronology"),
        ),
        sa.ForeignKeyConstraint(
            ["hospital_id", "patient_id"],
            ["patients.hospital_id", "patients.id"],
            name=op.f("fk_encounters_hospital_id_patients"),
        ),
        sa.ForeignKeyConstraint(
            ["hospital_id"], ["hospitals.id"], name=op.f("fk_encounters_hospital_id_hospitals")
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_encounters")),
        sa.UniqueConstraint(
            "hospital_id",
            "external_encounter_id",
            name=op.f("uq_encounters_hospital_id_external_encounter_id"),
        ),
        sa.UniqueConstraint(
            "hospital_id", "patient_id", "id", name=op.f("uq_encounters_hospital_id_patient_id_id")
        ),
    )
    op.create_index(op.f("ix_encounters_hospital_id"), "encounters", ["hospital_id"], unique=False)
    op.create_index(op.f("ix_encounters_patient_id"), "encounters", ["patient_id"], unique=False)
    op.create_table(
        "discharges",
        sa.Column("patient_id", sa.Uuid(), nullable=False),
        sa.Column("encounter_id", sa.Uuid(), nullable=False),
        sa.Column("discharge_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("follow_up_deadline", sa.DateTime(timezone=True), nullable=False),
        sa.Column("risk_level", sa.String(length=20), nullable=False),
        sa.Column("discharge_instructions", sa.Text(), nullable=False),
        sa.Column("status", sa.String(length=30), nullable=False),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("hospital_id", sa.Uuid(), nullable=False),
        sa.CheckConstraint(
            "risk_level IN ('LOW', 'MEDIUM', 'HIGH', 'UNKNOWN')",
            name=op.f("ck_discharges_risk_level"),
        ),
        sa.CheckConstraint(
            "status IN ('PENDING', 'COMPLETED', 'CANCELLED')", name=op.f("ck_discharges_status")
        ),
        sa.CheckConstraint(
            "follow_up_deadline >= discharge_at", name=op.f("ck_discharges_chronology")
        ),
        sa.ForeignKeyConstraint(
            ["hospital_id", "patient_id", "encounter_id"],
            ["encounters.hospital_id", "encounters.patient_id", "encounters.id"],
            name=op.f("fk_discharges_hospital_id_encounters"),
        ),
        sa.ForeignKeyConstraint(
            ["hospital_id", "patient_id"],
            ["patients.hospital_id", "patients.id"],
            name=op.f("fk_discharges_hospital_id_patients"),
        ),
        sa.ForeignKeyConstraint(
            ["hospital_id"], ["hospitals.id"], name=op.f("fk_discharges_hospital_id_hospitals")
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_discharges")),
        sa.UniqueConstraint(
            "hospital_id", "encounter_id", name=op.f("uq_discharges_hospital_id_encounter_id")
        ),
    )
    op.create_index(
        op.f("ix_discharges_encounter_id"), "discharges", ["encounter_id"], unique=False
    )
    op.create_index(op.f("ix_discharges_hospital_id"), "discharges", ["hospital_id"], unique=False)
    op.create_index(op.f("ix_discharges_patient_id"), "discharges", ["patient_id"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_discharges_patient_id"), table_name="discharges")
    op.drop_index(op.f("ix_discharges_hospital_id"), table_name="discharges")
    op.drop_index(op.f("ix_discharges_encounter_id"), table_name="discharges")
    op.drop_table("discharges")
    op.drop_index(op.f("ix_encounters_patient_id"), table_name="encounters")
    op.drop_index(op.f("ix_encounters_hospital_id"), table_name="encounters")
    op.drop_table("encounters")
    op.drop_index(op.f("ix_users_hospital_id"), table_name="users")
    op.drop_table("users")
    op.drop_index(op.f("ix_patients_hospital_id"), table_name="patients")
    op.drop_table("patients")
    op.drop_table("hospitals")
    sa.Enum(name="user_role").drop(op.get_bind(), checkfirst=True)
