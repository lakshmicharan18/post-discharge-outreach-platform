"""escalation cases

Revision ID: f26c8a1b5d43
Revises: e15b7f9a4c32
"""

from typing import Sequence, Union

import sqlalchemy as sa

from alembic import op

revision: str = "f26c8a1b5d43"
down_revision: Union[str, None] = "e15b7f9a4c32"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "escalation_cases",
        sa.Column("escalation_decision_id", sa.Uuid(), nullable=False),
        sa.Column("intake_session_id", sa.Uuid(), nullable=False),
        sa.Column("status", sa.String(30), nullable=False, server_default="OPEN"),
        sa.Column("priority", sa.String(50), nullable=False),
        sa.Column("assigned_reviewer_id", sa.Uuid(), nullable=True),
        sa.Column("reviewer_notes", sa.String(2000), nullable=True),
        sa.Column("resolution", sa.String(100), nullable=True),
        sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("hospital_id", sa.Uuid(), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.ForeignKeyConstraint(["assigned_reviewer_id"], ["users.id"]),
        sa.ForeignKeyConstraint(["escalation_decision_id"], ["escalation_decisions.id"]),
        sa.ForeignKeyConstraint(["hospital_id"], ["hospitals.id"]),
        sa.ForeignKeyConstraint(["intake_session_id"], ["voice_intake_sessions.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("escalation_decision_id"),
    )
    op.create_index("ix_escalation_cases_hospital_id", "escalation_cases", ["hospital_id"])


def downgrade() -> None:
    op.drop_index("ix_escalation_cases_hospital_id", table_name="escalation_cases")
    op.drop_table("escalation_cases")
