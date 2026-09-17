"""simulation run persistence

Revision ID: 7e4a1c8d9b20
Revises: d6a1e4f9b203
"""

from typing import Sequence, Union

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "7e4a1c8d9b20"
down_revision: Union[str, None] = "d6a1e4f9b203"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


simulation_run_status = postgresql.ENUM(
    "READY",
    "RUNNING",
    "COMPLETED",
    "FAILED",
    name="simulation_run_status",
    create_type=False,
)


def upgrade() -> None:
    simulation_run_status.create(op.get_bind(), checkfirst=True)
    op.create_table(
        "simulation_runs",
        sa.Column("status", simulation_run_status, nullable=False),
        sa.Column("scenario_name", sa.String(length=100), nullable=False),
        sa.Column("simulated_now", sa.DateTime(timezone=True), nullable=False),
        sa.Column("step_count", sa.Integer(), nullable=False),
        sa.Column("configured_capacity", sa.Integer(), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_by_user_id", sa.Uuid(), nullable=False),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("hospital_id", sa.Uuid(), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.CheckConstraint("step_count >= 0", name=op.f("ck_simulation_runs_step_count")),
        sa.CheckConstraint(
            "configured_capacity > 0", name=op.f("ck_simulation_runs_configured_capacity")
        ),
        sa.ForeignKeyConstraint(["created_by_user_id"], ["users.id"]),
        sa.ForeignKeyConstraint(["hospital_id"], ["hospitals.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("hospital_id", "id"),
    )
    op.create_index("ix_simulation_runs_hospital_id", "simulation_runs", ["hospital_id"])
    op.create_index("ix_simulation_runs_status", "simulation_runs", ["status"])
    op.create_index(
        "ix_simulation_runs_created_by_user_id", "simulation_runs", ["created_by_user_id"]
    )

    op.create_table(
        "simulation_events",
        sa.Column("simulation_run_id", sa.Uuid(), nullable=False),
        sa.Column("sequence_number", sa.Integer(), nullable=False),
        sa.Column("event_type", sa.String(length=100), nullable=False),
        sa.Column("simulated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("outreach_task_id", sa.Uuid(), nullable=True),
        sa.Column("campaign_id", sa.Uuid(), nullable=True),
        sa.Column("safe_payload", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("hospital_id", sa.Uuid(), nullable=False),
        sa.CheckConstraint(
            "sequence_number >= 1", name=op.f("ck_simulation_events_sequence_number")
        ),
        sa.ForeignKeyConstraint(["campaign_id"], ["campaigns.id"]),
        sa.ForeignKeyConstraint(["outreach_task_id"], ["outreach_tasks.id"]),
        sa.ForeignKeyConstraint(
            ["hospital_id", "simulation_run_id"],
            ["simulation_runs.hospital_id", "simulation_runs.id"],
        ),
        sa.ForeignKeyConstraint(["hospital_id"], ["hospitals.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("simulation_run_id", "sequence_number"),
    )
    op.create_index("ix_simulation_events_hospital_id", "simulation_events", ["hospital_id"])
    op.create_index("ix_simulation_events_simulation_run_id", "simulation_events", ["simulation_run_id"])
    op.create_index("ix_simulation_events_event_type", "simulation_events", ["event_type"])
    op.create_index("ix_simulation_events_simulated_at", "simulation_events", ["simulated_at"])
    op.create_index("ix_simulation_events_outreach_task_id", "simulation_events", ["outreach_task_id"])
    op.create_index("ix_simulation_events_campaign_id", "simulation_events", ["campaign_id"])
    op.create_index("ix_simulation_events_created_at", "simulation_events", ["created_at"])
    op.create_index(
        "ix_simulation_events_run_sequence", "simulation_events", ["simulation_run_id", "sequence_number"]
    )


def downgrade() -> None:
    op.drop_table("simulation_events")
    op.drop_table("simulation_runs")
    simulation_run_status.drop(op.get_bind(), checkfirst=True)
