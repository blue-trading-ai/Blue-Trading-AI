"""Version 35 security audit logs

Revision ID: v35_security_audit_logs
Revises: v34_login_protection
Create Date: 2026-08-04
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect


revision: str = "v35_security_audit_logs"
down_revision: Union[str, None] = "v34_login_protection"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


TABLE_NAME = "security_audit_logs"

EXPECTED_INDEXES = {
    "ix_security_audit_logs_id": ["id"],
    "ix_security_audit_logs_event_type": ["event_type"],
    "ix_security_audit_logs_outcome": ["outcome"],
    "ix_security_audit_logs_actor_user_id": ["actor_user_id"],
    "ix_security_audit_logs_actor_email": ["actor_email"],
    "ix_security_audit_logs_target_user_id": ["target_user_id"],
    "ix_security_audit_logs_target_email": ["target_email"],
    "ix_security_audit_logs_created_at": ["created_at"],
}


def _table_exists() -> bool:
    bind = op.get_bind()
    inspector = inspect(bind)
    return TABLE_NAME in inspector.get_table_names()


def _existing_index_names() -> set[str]:
    bind = op.get_bind()
    inspector = inspect(bind)

    if TABLE_NAME not in inspector.get_table_names():
        return set()

    return {
        str(index.get("name"))
        for index in inspector.get_indexes(TABLE_NAME)
        if index.get("name")
    }


def upgrade() -> None:
    """
    Create or adopt the Version 35 security audit table safely.

    The table may already exist because older startup code called
    Base.metadata.create_all() before Alembic ran. In that case this
    migration keeps the existing table and creates only missing indexes.
    """

    if not _table_exists():
        op.create_table(
            TABLE_NAME,
            sa.Column(
                "id",
                sa.Integer(),
                nullable=False,
            ),
            sa.Column(
                "event_type",
                sa.String(length=100),
                nullable=False,
            ),
            sa.Column(
                "outcome",
                sa.String(length=20),
                nullable=False,
            ),
            sa.Column(
                "actor_user_id",
                sa.Integer(),
                nullable=True,
            ),
            sa.Column(
                "actor_email",
                sa.String(length=255),
                nullable=True,
            ),
            sa.Column(
                "target_user_id",
                sa.Integer(),
                nullable=True,
            ),
            sa.Column(
                "target_email",
                sa.String(length=255),
                nullable=True,
            ),
            sa.Column(
                "ip_address",
                sa.String(length=64),
                nullable=True,
            ),
            sa.Column(
                "user_agent",
                sa.String(length=500),
                nullable=True,
            ),
            sa.Column(
                "request_path",
                sa.String(length=500),
                nullable=True,
            ),
            sa.Column(
                "request_method",
                sa.String(length=20),
                nullable=True,
            ),
            sa.Column(
                "message",
                sa.String(length=500),
                nullable=True,
            ),
            sa.Column(
                "details",
                sa.Text(),
                nullable=True,
            ),
            sa.Column(
                "is_security_sensitive",
                sa.Boolean(),
                nullable=False,
                server_default=sa.true(),
            ),
            sa.Column(
                "created_at",
                sa.DateTime(timezone=True),
                nullable=False,
                server_default=sa.text("CURRENT_TIMESTAMP"),
            ),
            sa.ForeignKeyConstraint(
                ["actor_user_id"],
                ["users.id"],
                ondelete="SET NULL",
            ),
            sa.ForeignKeyConstraint(
                ["target_user_id"],
                ["users.id"],
                ondelete="SET NULL",
            ),
            sa.PrimaryKeyConstraint("id"),
        )

    existing_indexes = _existing_index_names()

    for index_name, columns in EXPECTED_INDEXES.items():
        if index_name not in existing_indexes:
            op.create_index(
                index_name,
                TABLE_NAME,
                columns,
                unique=False,
            )


def downgrade() -> None:
    """
    Remove the Version 35 security audit table if it exists.
    """

    if not _table_exists():
        return

    existing_indexes = _existing_index_names()

    for index_name in reversed(list(EXPECTED_INDEXES)):
        if index_name in existing_indexes:
            op.drop_index(
                index_name,
                table_name=TABLE_NAME,
            )

    op.drop_table(TABLE_NAME)