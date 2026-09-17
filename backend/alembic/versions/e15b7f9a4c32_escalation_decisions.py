"""escalation decisions

Revision ID: e15b7f9a4c32
Revises: d04a6e8f3b21
"""
from typing import Sequence, Union
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql
from alembic import op

revision: str = "e15b7f9a4c32"
down_revision: Union[str, None] = "d04a6e8f3b21"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table("escalation_decisions", sa.Column("intake_session_id", sa.Uuid(), nullable=False), sa.Column("assessment_ids", postgresql.JSONB(astext_type=sa.Text()), nullable=False), sa.Column("final_classification", sa.String(50), nullable=False), sa.Column("agreement_status", sa.String(30), nullable=False), sa.Column("requires_human_review", sa.Boolean(), nullable=False), sa.Column("disagreement_reason", sa.String(250)), sa.Column("recommended_action", sa.String(100), nullable=False), sa.Column("execution_metadata", postgresql.JSONB(astext_type=sa.Text()), nullable=False), sa.Column("id", sa.Uuid(), nullable=False), sa.Column("hospital_id", sa.Uuid(), nullable=False), sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False), sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False), sa.ForeignKeyConstraint(["hospital_id"], ["hospitals.id"]), sa.ForeignKeyConstraint(["intake_session_id"], ["voice_intake_sessions.id"]), sa.PrimaryKeyConstraint("id"))


def downgrade() -> None:
    op.drop_table("escalation_decisions")
