"""workflow events

Revision ID: c48e2b6d9f31
Revises: b37d9e1a4c20
"""

from typing import Sequence, Union

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "c48e2b6d9f31"
down_revision: Union[str, None] = "b37d9e1a4c20"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    status = postgresql.ENUM(
        "PENDING",
        "PROCESSING",
        "RETRY_SCHEDULED",
        "SUCCEEDED",
        "FAILED",
        name="workflow_event_status",
        create_type=False,
    )
    postgresql.ENUM(
        "PENDING",
        "PROCESSING",
        "RETRY_SCHEDULED",
        "SUCCEEDED",
        "FAILED",
        name="workflow_event_status",
    ).create(op.get_bind(), checkfirst=True)
    op.create_table(
        "workflow_events",
        sa.Column("event_type", sa.String(80), nullable=False),
        sa.Column("payload", postgresql.JSONB(), nullable=False),
        sa.Column("status", status, nullable=False),
        sa.Column("attempt_count", sa.Integer(), nullable=False),
        sa.Column("max_attempts", sa.Integer(), nullable=False),
        sa.Column("next_attempt_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("idempotency_key", sa.String(150), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True)),
        sa.Column("processed_at", sa.DateTime(timezone=True)),
        sa.Column("last_error_type", sa.String(100)),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("hospital_id", sa.Uuid(), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.CheckConstraint("attempt_count >= 0", name="attempt_count"),
        sa.CheckConstraint("max_attempts > 0", name="max_attempts"),
        sa.ForeignKeyConstraint(["hospital_id"], ["hospitals.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("hospital_id", "idempotency_key"),
    )
    op.create_index(
        "ix_workflow_events_hospital_status_next",
        "workflow_events",
        ["hospital_id", "status", "next_attempt_at"],
    )


def downgrade() -> None:
    op.drop_index("ix_workflow_events_hospital_status_next", table_name="workflow_events")
    op.drop_table("workflow_events")
    sa.Enum(name="workflow_event_status").drop(op.get_bind(), checkfirst=True)
