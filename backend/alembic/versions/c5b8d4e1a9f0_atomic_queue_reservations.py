"""atomic queue reservations

Revision ID: c5b8d4e1a9f0
Revises: 9f1c2a7b4d8e
"""

from typing import Sequence, Union

import sqlalchemy as sa

from alembic import op

revision: str = "c5b8d4e1a9f0"
down_revision: Union[str, None] = "9f1c2a7b4d8e"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "outreach_tasks", sa.Column("reserved_at", sa.DateTime(timezone=True), nullable=True)
    )
    op.add_column("outreach_tasks", sa.Column("reservation_token", sa.Uuid(), nullable=True))
    op.add_column(
        "outreach_tasks",
        sa.Column("reservation_expires_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index(
        op.f("ix_outreach_tasks_reservation_token"),
        "outreach_tasks",
        ["reservation_token"],
        unique=False,
    )
    op.create_index(
        op.f("ix_outreach_tasks_reservation_expires_at"),
        "outreach_tasks",
        ["reservation_expires_at"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_outreach_tasks_reservation_expires_at"), table_name="outreach_tasks")
    op.drop_index(op.f("ix_outreach_tasks_reservation_token"), table_name="outreach_tasks")
    op.drop_column("outreach_tasks", "reservation_expires_at")
    op.drop_column("outreach_tasks", "reservation_token")
    op.drop_column("outreach_tasks", "reserved_at")
