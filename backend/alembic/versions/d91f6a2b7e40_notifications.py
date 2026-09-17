"""notifications

Revision ID: d91f6a2b7e40
Revises: c48e2b6d9f31
"""

from typing import Sequence, Union

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "d91f6a2b7e40"
down_revision: Union[str, None] = "c48e2b6d9f31"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    severity = postgresql.ENUM(
        "INFO", "WARNING", "URGENT", name="notification_severity", create_type=False
    )
    status = postgresql.ENUM(
        "UNREAD", "READ", "ACKNOWLEDGED", name="notification_status", create_type=False
    )
    postgresql.ENUM("INFO", "WARNING", "URGENT", name="notification_severity").create(
        op.get_bind(), checkfirst=True
    )
    postgresql.ENUM("UNREAD", "READ", "ACKNOWLEDGED", name="notification_status").create(
        op.get_bind(), checkfirst=True
    )
    op.create_table(
        "notifications",
        sa.Column("notification_type", sa.String(80), nullable=False),
        sa.Column("title", sa.String(200), nullable=False),
        sa.Column("message", sa.String(1000), nullable=False),
        sa.Column("severity", severity, nullable=False),
        sa.Column("status", status, nullable=False),
        sa.Column("recipient_user_id", sa.Uuid(), nullable=True),
        sa.Column("related_escalation_id", sa.Uuid(), nullable=True),
        sa.Column("related_workflow_event_id", sa.Uuid(), nullable=True),
        sa.Column("read_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("acknowledged_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("hospital_id", sa.Uuid(), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.ForeignKeyConstraint(["hospital_id"], ["hospitals.id"]),
        sa.ForeignKeyConstraint(["recipient_user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_notifications_hospital_id", "notifications", ["hospital_id"])
    op.create_index(
        "ix_notifications_hospital_status_created",
        "notifications",
        ["hospital_id", "status", "created_at"],
    )
    op.create_index("ix_notifications_recipient_user_id", "notifications", ["recipient_user_id"])
    op.create_index(
        "ix_notifications_related_escalation_id", "notifications", ["related_escalation_id"]
    )
    op.create_index(
        "ix_notifications_related_workflow_event_id", "notifications", ["related_workflow_event_id"]
    )


def downgrade() -> None:
    op.drop_index("ix_notifications_related_workflow_event_id", table_name="notifications")
    op.drop_index("ix_notifications_related_escalation_id", table_name="notifications")
    op.drop_index("ix_notifications_recipient_user_id", table_name="notifications")
    op.drop_index("ix_notifications_hospital_status_created", table_name="notifications")
    op.drop_index("ix_notifications_hospital_id", table_name="notifications")
    op.drop_table("notifications")
    sa.Enum(name="notification_status").drop(op.get_bind(), checkfirst=True)
    sa.Enum(name="notification_severity").drop(op.get_bind(), checkfirst=True)
