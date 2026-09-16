"""outreach outcomes and manual follow ups

Revision ID: d6a1e4f9b203
Revises: c5b8d4e1a9f0
"""

from typing import Sequence, Union

import sqlalchemy as sa

from alembic import op

revision: str = "d6a1e4f9b203"
down_revision: Union[str, None] = "c5b8d4e1a9f0"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    outcome = sa.Enum(
        "COMPLETED",
        "NO_ANSWER",
        "BUSY",
        "VOICEMAIL",
        "DROPPED",
        "INVALID_NUMBER",
        "DECLINED",
        "CALLBACK_REQUESTED",
        "TECHNICAL_FAILURE",
        name="outreach_outcome",
    )
    status = sa.Enum("OPEN", "RESOLVED", name="manual_follow_up_status")
    op.create_table(
        "outreach_attempts",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("hospital_id", sa.Uuid(), nullable=False),
        sa.Column("campaign_id", sa.Uuid(), nullable=False),
        sa.Column("outreach_task_id", sa.Uuid(), nullable=False),
        sa.Column("patient_id", sa.Uuid(), nullable=False),
        sa.Column("discharge_id", sa.Uuid(), nullable=False),
        sa.Column("attempt_number", sa.Integer(), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("ended_at", sa.DateTime(timezone=True)),
        sa.Column("duration_seconds", sa.Integer()),
        sa.Column("outcome", outcome),
        sa.Column("outcome_reason", sa.String(100)),
        sa.Column("provider_call_id", sa.String(150)),
        sa.Column("outcome_event_id", sa.String(150)),
        sa.Column("callback_requested_at", sa.DateTime(timezone=True)),
        sa.Column("technical_error_code", sa.String(100)),
        sa.Column("partial_context", sa.dialects.postgresql.JSONB()),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.ForeignKeyConstraint(["campaign_id"], ["campaigns.id"]),
        sa.ForeignKeyConstraint(["outreach_task_id"], ["outreach_tasks.id"]),
        sa.ForeignKeyConstraint(["patient_id"], ["patients.id"]),
        sa.ForeignKeyConstraint(["discharge_id"], ["discharges.id"]),
        sa.ForeignKeyConstraint(["hospital_id"], ["hospitals.id"]),
        sa.UniqueConstraint("hospital_id", "outcome_event_id"),
        sa.UniqueConstraint("outreach_task_id", "attempt_number"),
    )
    op.create_index(
        "ix_outreach_attempts_hospital_outcome_started",
        "outreach_attempts",
        ["hospital_id", "outcome", "started_at"],
    )
    op.create_table(
        "manual_follow_ups",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("hospital_id", sa.Uuid(), nullable=False),
        sa.Column("patient_id", sa.Uuid(), nullable=False),
        sa.Column("campaign_id", sa.Uuid(), nullable=False),
        sa.Column("outreach_task_id", sa.Uuid(), nullable=False),
        sa.Column("reason_code", sa.String(100), nullable=False),
        sa.Column("status", status, nullable=False, server_default="OPEN"),
        sa.Column("resolved_at", sa.DateTime(timezone=True)),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.ForeignKeyConstraint(["hospital_id"], ["hospitals.id"]),
        sa.ForeignKeyConstraint(["patient_id"], ["patients.id"]),
        sa.ForeignKeyConstraint(["campaign_id"], ["campaigns.id"]),
        sa.ForeignKeyConstraint(["outreach_task_id"], ["outreach_tasks.id"]),
        sa.UniqueConstraint("outreach_task_id"),
    )
    op.create_index(
        "ix_manual_follow_ups_hospital_status_reason",
        "manual_follow_ups",
        ["hospital_id", "status", "reason_code"],
    )


def downgrade() -> None:
    op.drop_table("manual_follow_ups")
    op.drop_table("outreach_attempts")
    sa.Enum(name="manual_follow_up_status").drop(op.get_bind(), checkfirst=True)
    sa.Enum(name="outreach_outcome").drop(op.get_bind(), checkfirst=True)
