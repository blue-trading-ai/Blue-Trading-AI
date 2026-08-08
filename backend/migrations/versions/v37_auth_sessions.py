"""Version 37 secure authentication sessions

Revision ID: v37_auth_sessions
Revises: v35_security_audit_logs
Create Date: 2026-08-04
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect


revision: str = "v37_auth_sessions"
down_revision: Union[str, None] = "v35_security_audit_logs"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


TABLE_NAME = "auth_sessions"

EXPECTED_INDEXES = {
    "ix_auth_sessions_id": ["id"],
    "ix_auth_sessions_session_id": ["session_id"],
    "ix_auth_sessions_user_id": ["user_id"],
    "ix_auth_sessions_token_jti_hash": ["token_jti_hash"],
    "ix_auth_sessions_status": ["status"],
    "ix_auth_sessions_is_active": ["is_active"],
    "ix_auth_sessions_expires_at": ["expires_at"],
    "ix_auth_sessions_revoked_at": ["revoked_at"],
    "ix_auth_sessions_user_active": [
        "user_id",
        "is_active",
    ],
    "ix_auth_sessions_status_expiry": [
        "status",
        "expires_at",
    ],
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
    Create or adopt the Version 37 authentication-session table.

    This migration is idempotent for SQLite development environments
    where Base.metadata.create_all() may have created the table before
    Alembic runs.
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
                "session_id",
                sa.String(length=64),
                nullable=False,
            ),
            sa.Column(
                "user_id",
                sa.Integer(),
                nullable=False,
            ),
            sa.Column(
                "token_jti_hash",
                sa.String(length=64),
                nullable=False,
            ),
            sa.Column(
                "password_version",
                sa.Integer(),
                nullable=False,
                server_default=sa.text("1"),
            ),
            sa.Column(
                "status",
                sa.String(length=20),
                nullable=False,
                server_default=sa.text("'ACTIVE'"),
            ),
            sa.Column(
                "is_active",
                sa.Boolean(),
                nullable=False,
                server_default=sa.true(),
            ),
            sa.Column(
                "issued_at",
                sa.DateTime(timezone=True),
                nullable=False,
                server_default=sa.text("CURRENT_TIMESTAMP"),
            ),
            sa.Column(
                "expires_at",
                sa.DateTime(timezone=True),
                nullable=False,
            ),
            sa.Column(
                "last_seen_at",
                sa.DateTime(timezone=True),
                nullable=True,
            ),
            sa.Column(
                "revoked_at",
                sa.DateTime(timezone=True),
                nullable=True,
            ),
            sa.Column(
                "revoke_reason",
                sa.String(length=100),
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
                "created_at",
                sa.DateTime(timezone=True),
                nullable=False,
                server_default=sa.text("CURRENT_TIMESTAMP"),
            ),
            sa.Column(
                "updated_at",
                sa.DateTime(timezone=True),
                nullable=False,
                server_default=sa.text("CURRENT_TIMESTAMP"),
            ),
            sa.ForeignKeyConstraint(
                ["user_id"],
                ["users.id"],
                ondelete="CASCADE",
            ),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint(
                "session_id",
                name="uq_auth_sessions_session_id",
            ),
            sa.UniqueConstraint(
                "token_jti_hash",
                name="uq_auth_sessions_token_jti_hash",
            ),
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
    Remove the Version 37 authentication-session table.
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