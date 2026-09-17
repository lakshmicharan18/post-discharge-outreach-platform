"""AI structured call notes.

Revision ID: a71d3e9b4c20
Revises: f2c6a9d1e4b7
"""

from typing import Sequence, Union

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "a71d3e9b4c20"
down_revision: Union[str, None] = "f2c6a9d1e4b7"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "structured_call_notes",
        sa.Column("outreach_task_id", sa.Uuid(), nullable=False),
        sa.Column("patient_id", sa.Uuid(), nullable=False),
        sa.Column("note", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
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
        sa.ForeignKeyConstraint(["patient_id"], ["patients.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_structured_call_notes_hospital_id", "structured_call_notes", ["hospital_id"]
    )
    op.create_index(
        "ix_structured_call_notes_outreach_task_id", "structured_call_notes", ["outreach_task_id"]
    )
    op.create_index("ix_structured_call_notes_patient_id", "structured_call_notes", ["patient_id"])
    op.create_index(
        "ix_structured_call_notes_task_created",
        "structured_call_notes",
        ["outreach_task_id", "created_at"],
    )


def downgrade() -> None:
    op.drop_table("structured_call_notes")
