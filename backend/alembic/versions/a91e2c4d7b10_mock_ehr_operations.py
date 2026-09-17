"""mock EHR operations

Revision ID: a91e2c4d7b10
Revises: f26c8a1b5d43
"""

from typing import Sequence, Union

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "a91e2c4d7b10"
down_revision: Union[str, None] = "f26c8a1b5d43"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "ehr_operations",
        sa.Column("outreach_task_id", sa.Uuid()),
        sa.Column("reference_id", sa.Uuid(), nullable=False),
        sa.Column("operation_type", sa.String(50), nullable=False),
        sa.Column("idempotency_key", sa.String(150), nullable=False),
        sa.Column("safe_payload", postgresql.JSONB(), nullable=False),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True)),
        sa.Column("error", sa.String(500)),
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
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("hospital_id", "idempotency_key"),
    )
    op.create_index("ix_ehr_operations_hospital_id", "ehr_operations", ["hospital_id"])
    op.create_index("ix_ehr_operations_reference_id", "ehr_operations", ["reference_id"])


def downgrade() -> None:
    op.drop_index("ix_ehr_operations_reference_id", table_name="ehr_operations")
    op.drop_index("ix_ehr_operations_hospital_id", table_name="ehr_operations")
    op.drop_table("ehr_operations")
