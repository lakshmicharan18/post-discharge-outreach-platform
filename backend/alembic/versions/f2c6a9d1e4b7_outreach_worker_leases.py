"""outreach worker leases

Revision ID: f2c6a9d1e4b7
Revises: 7e4a1c8d9b20
"""

from typing import Sequence, Union

import sqlalchemy as sa

from alembic import op

revision: str = "f2c6a9d1e4b7"
down_revision: Union[str, None] = "7e4a1c8d9b20"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("outreach_tasks", sa.Column("worker_id", sa.String(length=100), nullable=True))
    op.add_column(
        "outreach_tasks", sa.Column("heartbeat_at", sa.DateTime(timezone=True), nullable=True)
    )
    op.add_column(
        "outreach_tasks",
        sa.Column("processing_lease_expires_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index(op.f("ix_outreach_tasks_worker_id"), "outreach_tasks", ["worker_id"])
    op.create_index(op.f("ix_outreach_tasks_heartbeat_at"), "outreach_tasks", ["heartbeat_at"])
    op.create_index(
        op.f("ix_outreach_tasks_processing_lease_expires_at"),
        "outreach_tasks",
        ["processing_lease_expires_at"],
    )
    op.create_index(
        "ix_outreach_tasks_hospital_state_processing_lease",
        "outreach_tasks",
        ["hospital_id", "state", "processing_lease_expires_at"],
    )


def downgrade() -> None:
    op.drop_index("ix_outreach_tasks_hospital_state_processing_lease", table_name="outreach_tasks")
    op.drop_index(
        op.f("ix_outreach_tasks_processing_lease_expires_at"), table_name="outreach_tasks"
    )
    op.drop_index(op.f("ix_outreach_tasks_heartbeat_at"), table_name="outreach_tasks")
    op.drop_index(op.f("ix_outreach_tasks_worker_id"), table_name="outreach_tasks")
    op.drop_column("outreach_tasks", "processing_lease_expires_at")
    op.drop_column("outreach_tasks", "heartbeat_at")
    op.drop_column("outreach_tasks", "worker_id")
