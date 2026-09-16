"""campaign domain and lifecycle

Revision ID: 6b9f5c37d1a2
Revises: 10c82d1fbab4
"""

from typing import Sequence, Union

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "6b9f5c37d1a2"
down_revision: Union[str, None] = "10c82d1fbab4"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


campaign_status = postgresql.ENUM(
    "DRAFT",
    "READY",
    "SCHEDULED",
    "RUNNING",
    "PAUSED",
    "COMPLETED",
    "CANCELLED",
    "FAILED",
    name="campaign_status",
    create_type=False,
)


def upgrade() -> None:
    campaign_status.create(op.get_bind(), checkfirst=True)
    op.create_table(
        "campaigns",
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("status", campaign_status, nullable=False),
        sa.Column("start_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("end_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("clinical_follow_up_hours", sa.Integer(), nullable=True),
        sa.Column("calling_window_start", sa.Time(), nullable=True),
        sa.Column("calling_window_end", sa.Time(), nullable=True),
        sa.Column("campaign_priority", sa.Integer(), nullable=True),
        sa.Column("max_retries", sa.Integer(), nullable=True),
        sa.Column("outbound_capacity", sa.Integer(), nullable=True),
        sa.Column(
            "escalation_configuration", postgresql.JSONB(astext_type=sa.Text()), nullable=False
        ),
        sa.Column("eligibility_criteria", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("created_by_user_id", sa.Uuid(), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("paused_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
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
        sa.CheckConstraint(
            "calling_window_start IS NULL OR calling_window_end IS NULL OR "
            "calling_window_end > calling_window_start",
            name=op.f("ck_campaigns_calling_window"),
        ),
        sa.CheckConstraint(
            "clinical_follow_up_hours IS NULL OR clinical_follow_up_hours > 0",
            name=op.f("ck_campaigns_follow_up_hours"),
        ),
        sa.CheckConstraint(
            "campaign_priority IS NULL OR campaign_priority BETWEEN 1 AND 100",
            name=op.f("ck_campaigns_priority"),
        ),
        sa.CheckConstraint(
            "max_retries IS NULL OR max_retries >= 0",
            name=op.f("ck_campaigns_max_retries"),
        ),
        sa.CheckConstraint(
            "outbound_capacity IS NULL OR outbound_capacity > 0",
            name=op.f("ck_campaigns_outbound_capacity"),
        ),
        sa.CheckConstraint(
            "end_at IS NULL OR start_at IS NULL OR end_at >= start_at",
            name=op.f("ck_campaigns_dates"),
        ),
        sa.ForeignKeyConstraint(
            ["created_by_user_id"], ["users.id"], name=op.f("fk_campaigns_created_by_user_id_users")
        ),
        sa.ForeignKeyConstraint(
            ["hospital_id"], ["hospitals.id"], name=op.f("fk_campaigns_hospital_id_hospitals")
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_campaigns")),
    )
    op.create_index(op.f("ix_campaigns_hospital_id"), "campaigns", ["hospital_id"], unique=False)
    op.create_index(op.f("ix_campaigns_status"), "campaigns", ["status"], unique=False)
    op.create_index(op.f("ix_campaigns_start_at"), "campaigns", ["start_at"], unique=False)
    op.create_index(
        op.f("ix_campaigns_campaign_priority"), "campaigns", ["campaign_priority"], unique=False
    )
    op.create_index(
        "ix_campaigns_hospital_status", "campaigns", ["hospital_id", "status"], unique=False
    )
    op.create_index(
        "ix_campaigns_hospital_priority",
        "campaigns",
        ["hospital_id", "campaign_priority"],
        unique=False,
    )
    op.create_index(
        op.f("ix_campaigns_created_by_user_id"), "campaigns", ["created_by_user_id"], unique=False
    )


def downgrade() -> None:
    op.drop_table("campaigns")
    campaign_status.drop(op.get_bind(), checkfirst=True)
