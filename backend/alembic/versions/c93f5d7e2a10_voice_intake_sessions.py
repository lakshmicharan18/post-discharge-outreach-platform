"""voice intake sessions

Revision ID: c93f5d7e2a10
Revises: b82e4a6c3d10
"""

from typing import Sequence, Union

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "c93f5d7e2a10"
down_revision: Union[str, None] = "b82e4a6c3d10"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "voice_intake_sessions",
        sa.Column("outreach_task_id", sa.Uuid(), nullable=False),
        sa.Column("outreach_attempt_id", sa.Uuid(), nullable=True),
        sa.Column("current_stage", sa.String(50), nullable=False),
        sa.Column("conversation_state", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("status", sa.String(30), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("hospital_id", sa.Uuid(), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.ForeignKeyConstraint(["hospital_id"], ["hospitals.id"]),
        sa.ForeignKeyConstraint(["outreach_task_id"], ["outreach_tasks.id"]),
        sa.ForeignKeyConstraint(["outreach_attempt_id"], ["outreach_attempts.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_voice_intake_sessions_hospital_id", "voice_intake_sessions", ["hospital_id"]
    )
    op.create_index(
        "ix_voice_intake_sessions_hospital_task",
        "voice_intake_sessions",
        ["hospital_id", "outreach_task_id"],
    )


def downgrade() -> None:
    op.drop_table("voice_intake_sessions")
