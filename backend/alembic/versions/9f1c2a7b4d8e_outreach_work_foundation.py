"""outreach work foundation

Revision ID: 9f1c2a7b4d8e
Revises: 6b9f5c37d1a2
"""

from typing import Sequence, Union

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "9f1c2a7b4d8e"
down_revision: Union[str, None] = "6b9f5c37d1a2"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

task_state = postgresql.ENUM(
    "PENDING",
    "SCHEDULED",
    "CALLING",
    "CONNECTED",
    "COMPLETED",
    "NO_ANSWER",
    "BUSY",
    "VOICEMAIL",
    "DROPPED",
    "RETRY_SCHEDULED",
    "CALLBACK_SCHEDULED",
    "ESCALATED",
    "MANUAL_FOLLOW_UP",
    "FAILED",
    name="outreach_task_state",
    create_type=False,
)


def upgrade() -> None:
    task_state.create(op.get_bind(), checkfirst=True)
    op.create_table(
        "outreach_tasks",
        sa.Column("campaign_id", sa.Uuid(), nullable=False),
        sa.Column("patient_id", sa.Uuid(), nullable=False),
        sa.Column("discharge_id", sa.Uuid(), nullable=False),
        sa.Column("state", task_state, nullable=False),
        sa.Column("priority_score", sa.Integer(), nullable=False),
        sa.Column("priority_components", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("attempt_count", sa.Integer(), nullable=False),
        sa.Column("max_attempts", sa.Integer(), nullable=False),
        sa.Column("eligible_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("next_eligible_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("clinical_deadline", sa.DateTime(timezone=True), nullable=False),
        sa.Column("callback_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("scheduled_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_outcome", sa.String(length=50), nullable=True),
        sa.Column("last_error_code", sa.String(length=100), nullable=True),
        sa.Column("manual_follow_up_required", sa.Boolean(), nullable=False),
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
        sa.CheckConstraint("attempt_count >= 0", name=op.f("ck_outreach_tasks_attempt_count")),
        sa.CheckConstraint("max_attempts > 0", name=op.f("ck_outreach_tasks_max_attempts")),
        sa.ForeignKeyConstraint(
            ["campaign_id"], ["campaigns.id"], name=op.f("fk_outreach_tasks_campaign_id_campaigns")
        ),
        sa.ForeignKeyConstraint(
            ["patient_id"], ["patients.id"], name=op.f("fk_outreach_tasks_patient_id_patients")
        ),
        sa.ForeignKeyConstraint(
            ["discharge_id"],
            ["discharges.id"],
            name=op.f("fk_outreach_tasks_discharge_id_discharges"),
        ),
        sa.ForeignKeyConstraint(
            ["hospital_id"], ["hospitals.id"], name=op.f("fk_outreach_tasks_hospital_id_hospitals")
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_outreach_tasks")),
        sa.UniqueConstraint(
            "hospital_id",
            "campaign_id",
            "discharge_id",
            name=op.f("uq_outreach_tasks_hospital_id_campaign_id_discharge_id"),
        ),
    )
    for name, columns in (
        ("ix_outreach_tasks_hospital_id", ["hospital_id"]),
        ("ix_outreach_tasks_campaign_id", ["campaign_id"]),
        ("ix_outreach_tasks_patient_id", ["patient_id"]),
        ("ix_outreach_tasks_discharge_id", ["discharge_id"]),
        ("ix_outreach_tasks_state", ["state"]),
        ("ix_outreach_tasks_priority_score", ["priority_score"]),
        ("ix_outreach_tasks_next_eligible_at", ["next_eligible_at"]),
        ("ix_outreach_tasks_clinical_deadline", ["clinical_deadline"]),
        ("ix_outreach_tasks_callback_at", ["callback_at"]),
        ("ix_outreach_tasks_hospital_state_next", ["hospital_id", "state", "next_eligible_at"]),
        ("ix_outreach_tasks_hospital_state_priority", ["hospital_id", "state", "priority_score"]),
    ):
        op.create_index(name, "outreach_tasks", columns, unique=False)


def downgrade() -> None:
    op.drop_table("outreach_tasks")
    task_state.drop(op.get_bind(), checkfirst=True)
