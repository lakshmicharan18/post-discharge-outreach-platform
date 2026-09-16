"""Add password hashes and case-insensitive email uniqueness.

Revision ID: 2a0000000001
Revises: e18e73d6e369
"""

import sqlalchemy as sa

from alembic import op

revision = "2a0000000001"
down_revision = "e18e73d6e369"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Existing users remain uncredentialed until explicitly provisioned. No shared default.
    op.add_column("users", sa.Column("password_hash", sa.String(255), nullable=True))
    op.create_index("uq_users_email_lower", "users", [sa.text("lower(email)")], unique=True)


def downgrade() -> None:
    op.drop_index("uq_users_email_lower", table_name="users")
    op.drop_column("users", "password_hash")
