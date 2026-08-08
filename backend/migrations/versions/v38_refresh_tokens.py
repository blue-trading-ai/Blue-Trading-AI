"""Version 38 secure refresh tokens

Revision ID: v38_refresh_tokens
Revises: v37_auth_sessions
Create Date: 2026-08-04
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect


revision: str = "v38_refresh_tokens"
down_revision: Union[str, None] = "v37_auth_sessions"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


TABLE_NAME = "refresh_tokens"

EXPECTED_INDEXES = {
    "ix_refresh_tokens_id": ["id"],
    "ix_refresh_tokens_token_id": ["token_id"],
    "ix_refresh_tokens_token_hash": ["token_hash"],
    "ix_refresh_tokens_family_id": ["family_id"],
    "ix_refresh_tokens_parent_token_id": ["parent_token_id"],
    "ix_refresh_tokens_replaced_by_token_id": [
        "replaced_by_token_id",
    ],
    "ix_refresh_tokens_session_id": ["session_id"],
    "ix_refresh_tokens_user_id": ["user_id"],
    "ix_refresh_tokens_status": ["status"],
    "ix_refresh_tokens_is_active": ["is_active"],
    "ix_refresh_tokens_expires_at": ["expires_at"],
    "ix_refresh_tokens_revoked_at": ["revoked_at"],
    "ix_refresh_tokens_reuse_detected_at": [
        "reuse_detected_at",
    ],
    "ix_refresh_tokens_user_active": [
        "user_id",
        "is_active",
    ],
    "ix_refresh_tokens_session_active": [
        "session_id",
        "is_active",
    ],
    "ix_refresh_tokens_family_status": [
        "family_id",
        "status",
    ],
    "ix_refresh_tokens_status_expiry": [
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
    Create or adopt the Version 38 refresh-token table.

    This is safe for SQLite development environments where
    Base.metadata.create_all() may create the table before Alembic.
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
                "token_id",
                sa.String(length=64),
                nullable=False,
            ),
            sa.Column(
                "token_hash",
                sa.String(length=64),
                nullable=False,
            ),
            sa.Column(
                "family_id",
                sa.String(length=64),
                nullable=False,
            ),
            sa.Column(
                "parent_token_id",
                sa.String(length=64),
                nullable=True,
            ),
            sa.Column(
                "replaced_by_token_id",
                sa.String(length=64),
                nullable=True,
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
                "last_used_at",
                sa.DateTime(timezone=True),
                nullable=True,
            ),
            sa.Column(
                "rotated_at",
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
                "reuse_detected_at",
                sa.DateTime(timezone=True),
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
                ["session_id"],
                ["auth_sessions.session_id"],
                ondelete="CASCADE",
            ),
            sa.ForeignKeyConstraint(
                ["user_id"],
                ["users.id"],
                ondelete="CASCADE",
            ),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint(
                "token_id",
                name="uq_refresh_tokens_token_id",
            ),
            sa.UniqueConstraint(
                "token_hash",
                name="uq_refresh_tokens_token_hash",
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
    Remove the Version 38 refresh-token table.
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