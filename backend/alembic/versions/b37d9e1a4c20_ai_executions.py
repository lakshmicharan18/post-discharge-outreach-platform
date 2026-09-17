"""AI execution metadata

Revision ID: b37d9e1a4c20
Revises: a91e2c4d7b10
"""

from typing import Sequence, Union

import sqlalchemy as sa

from alembic import op

revision: str = "b37d9e1a4c20"
down_revision: Union[str, None] = "a91e2c4d7b10"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "ai_executions",
        sa.Column("purpose", sa.String(80), nullable=False),
        sa.Column("provider", sa.String(80), nullable=False),
        sa.Column("model", sa.String(160), nullable=False),
        sa.Column("prompt_version", sa.String(80), nullable=False),
        sa.Column("latency_ms", sa.Integer(), nullable=False),
        sa.Column("success", sa.Boolean(), nullable=False),
        sa.Column("input_tokens", sa.Integer()),
        sa.Column("output_tokens", sa.Integer()),
        sa.Column("estimated_cost", sa.Float()),
        sa.Column("error_type", sa.String(100)),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("hospital_id", sa.Uuid(), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.ForeignKeyConstraint(["hospital_id"], ["hospitals.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_ai_executions_hospital_id", "ai_executions", ["hospital_id"])


def downgrade() -> None:
    op.drop_index("ix_ai_executions_hospital_id", table_name="ai_executions")
    op.drop_table("ai_executions")
