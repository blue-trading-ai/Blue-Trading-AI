"""Version 39 email verification and password reset

Revision ID: v39_account_security_tokens
Revises: v38_refresh_tokens
Create Date: 2026-08-04
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect


revision: str = "v39_account_security_tokens"
down_revision: Union[str, None] = "v38_refresh_tokens"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


TOKEN_TABLE = "account_action_tokens"
USER_TABLE = "users"

EXPECTED_INDEXES = {
    "ix_account_action_tokens_id": ["id"],
    "ix_account_action_tokens_token_id": ["token_id"],
    "ix_account_action_tokens_token_hash": ["token_hash"],
    "ix_account_action_tokens_user_id": ["user_id"],
    "ix_account_action_tokens_email": ["email"],
    "ix_account_action_tokens_purpose": ["purpose"],
    "ix_account_action_tokens_status": ["status"],
    "ix_account_action_tokens_is_active": ["is_active"],
    "ix_account_action_tokens_expires_at": ["expires_at"],
    "ix_account_action_tokens_used_at": ["used_at"],
    "ix_account_action_tokens_revoked_at": ["revoked_at"],
    "ix_account_action_tokens_user_purpose_active": [
        "user_id",
        "purpose",
        "is_active",
    ],
    "ix_account_action_tokens_email_purpose": [
        "email",
        "purpose",
    ],
    "ix_account_action_tokens_status_expiry": [
        "status",
        "expires_at",
    ],
}


def _table_exists(table_name: str) -> bool:
    bind = op.get_bind()
    inspector = inspect(bind)

    return table_name in inspector.get_table_names()


def _column_names(table_name: str) -> set[str]:
    bind = op.get_bind()
    inspector = inspect(bind)

    if table_name not in inspector.get_table_names():
        return set()

    return {
        str(column.get("name"))
        for column in inspector.get_columns(
            table_name
        )
        if column.get("name")
    }


def _existing_index_names(
    table_name: str,
) -> set[str]:
    bind = op.get_bind()
    inspector = inspect(bind)

    if table_name not in inspector.get_table_names():
        return set()

    return {
        str(index.get("name"))
        for index in inspector.get_indexes(
            table_name
        )
        if index.get("name")
    }


def _add_user_columns() -> None:
    existing_columns = _column_names(
        USER_TABLE
    )

    with op.batch_alter_table(
        USER_TABLE
    ) as batch_op:
        if "is_email_verified" not in existing_columns:
            batch_op.add_column(
                sa.Column(
                    "is_email_verified",
                    sa.Boolean(),
                    nullable=False,
                    server_default=sa.false(),
                )
            )

        if "email_verified_at" not in existing_columns:
            batch_op.add_column(
                sa.Column(
                    "email_verified_at",
                    sa.DateTime(timezone=True),
                    nullable=True,
                )
            )

        if (
            "email_verification_requested_at"
            not in existing_columns
        ):
            batch_op.add_column(
                sa.Column(
                    "email_verification_requested_at",
                    sa.DateTime(timezone=True),
                    nullable=True,
                )
            )

    existing_indexes = _existing_index_names(
        USER_TABLE
    )

    if (
        "ix_users_is_email_verified"
        not in existing_indexes
    ):
        op.create_index(
            "ix_users_is_email_verified",
            USER_TABLE,
            ["is_email_verified"],
            unique=False,
        )


def _create_token_table() -> None:
    if not _table_exists(TOKEN_TABLE):
        op.create_table(
            TOKEN_TABLE,
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
                "user_id",
                sa.Integer(),
                nullable=False,
            ),
            sa.Column(
                "email",
                sa.String(length=255),
                nullable=False,
            ),
            sa.Column(
                "purpose",
                sa.String(length=40),
                nullable=False,
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
                server_default=sa.text(
                    "CURRENT_TIMESTAMP"
                ),
            ),
            sa.Column(
                "expires_at",
                sa.DateTime(timezone=True),
                nullable=False,
            ),
            sa.Column(
                "used_at",
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
                "request_ip",
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
                server_default=sa.text(
                    "CURRENT_TIMESTAMP"
                ),
            ),
            sa.Column(
                "updated_at",
                sa.DateTime(timezone=True),
                nullable=False,
                server_default=sa.text(
                    "CURRENT_TIMESTAMP"
                ),
            ),
            sa.ForeignKeyConstraint(
                ["user_id"],
                ["users.id"],
                ondelete="CASCADE",
            ),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint(
                "token_id",
                name=(
                    "uq_account_action_tokens_"
                    "token_id"
                ),
            ),
            sa.UniqueConstraint(
                "token_hash",
                name=(
                    "uq_account_action_tokens_"
                    "token_hash"
                ),
            ),
        )

    existing_indexes = _existing_index_names(
        TOKEN_TABLE
    )

    for index_name, columns in (
        EXPECTED_INDEXES.items()
    ):
        if index_name not in existing_indexes:
            op.create_index(
                index_name,
                TOKEN_TABLE,
                columns,
                unique=False,
            )


def upgrade() -> None:
    """
    Add Version 39 email-verification fields and token storage.

    This migration is safe for SQLite development environments
    where Base.metadata.create_all() may create the new table
    before Alembic runs.
    """

    _add_user_columns()
    _create_token_table()


def downgrade() -> None:
    """
    Remove Version 39 token storage and user verification fields.
    """

    if _table_exists(TOKEN_TABLE):
        existing_indexes = _existing_index_names(
            TOKEN_TABLE
        )

        for index_name in reversed(
            list(EXPECTED_INDEXES)
        ):
            if index_name in existing_indexes:
                op.drop_index(
                    index_name,
                    table_name=TOKEN_TABLE,
                )

        op.drop_table(TOKEN_TABLE)

    user_columns = _column_names(USER_TABLE)
    user_indexes = _existing_index_names(
        USER_TABLE
    )

    if (
        "ix_users_is_email_verified"
        in user_indexes
    ):
        op.drop_index(
            "ix_users_is_email_verified",
            table_name=USER_TABLE,
        )

    with op.batch_alter_table(
        USER_TABLE
    ) as batch_op:
        if (
            "email_verification_requested_at"
            in user_columns
        ):
            batch_op.drop_column(
                "email_verification_requested_at"
            )

        if "email_verified_at" in user_columns:
            batch_op.drop_column(
                "email_verified_at"
            )

        if "is_email_verified" in user_columns:
            batch_op.drop_column(
                "is_email_verified"
            )