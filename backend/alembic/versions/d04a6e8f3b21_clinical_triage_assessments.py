"""clinical triage assessments

Revision ID: d04a6e8f3b21
Revises: c93f5d7e2a10
"""

from typing import Sequence, Union

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "d04a6e8f3b21"
down_revision: Union[str, None] = "c93f5d7e2a10"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "clinical_triage_assessments",
        sa.Column("intake_session_id", sa.Uuid(), nullable=False),
        sa.Column("outreach_task_id", sa.Uuid(), nullable=False),
        sa.Column("classification", sa.String(50), nullable=False),
        sa.Column("requires_human_review", sa.Boolean(), nullable=False),
        sa.Column("assessment", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("execution_metadata", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("hospital_id", sa.Uuid(), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.ForeignKeyConstraint(["hospital_id"], ["hospitals.id"]),
        sa.ForeignKeyConstraint(["intake_session_id"], ["voice_intake_sessions.id"]),
        sa.ForeignKeyConstraint(["outreach_task_id"], ["outreach_tasks.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_clinical_triage_assessments_hospital_id", "clinical_triage_assessments", ["hospital_id"]
    )


def downgrade() -> None:
    op.drop_table("clinical_triage_assessments")
