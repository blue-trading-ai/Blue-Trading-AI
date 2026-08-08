"""baseline version 31

Revision ID: a0aef49a1c59
Revises:
Create Date: 2026-08-02 22:52:14.101851

This baseline migration safely aligns the existing users table with
Version 31 without deleting users or trade-history records.
"""

from __future__ import annotations

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# Revision identifiers used by Alembic.
revision: str = "a0aef49a1c59"
down_revision: Union[str, Sequence[str], None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """
    Safely align the existing database with Version 31.

    The existing trade_history server defaults are intentionally preserved.
    They are safe and help protect direct database inserts.

    Existing users with NULL values are repaired before NOT NULL constraints
    are applied.
    """

    # Repair any existing NULL account-state values.
    op.execute(
        sa.text(
            """
            UPDATE users
            SET is_active = 1
            WHERE is_active IS NULL
            """
        )
    )

    # Repair any existing NULL account creation timestamps.
    op.execute(
        sa.text(
            """
            UPDATE users
            SET created_at = CURRENT_TIMESTAMP
            WHERE created_at IS NULL
            """
        )
    )

    # SQLite requires batch mode for constraint changes.
    with op.batch_alter_table(
        "users",
        schema=None,
    ) as batch_op:
        batch_op.alter_column(
            "is_active",
            existing_type=sa.Boolean(),
            existing_nullable=True,
            nullable=False,
        )

        batch_op.alter_column(
            "created_at",
            existing_type=sa.DateTime(),
            existing_nullable=True,
            nullable=False,
        )


def downgrade() -> None:
    """
    Restore the previous nullable user-column behavior.

    Data is preserved.
    """

    with op.batch_alter_table(
        "users",
        schema=None,
    ) as batch_op:
        batch_op.alter_column(
            "created_at",
            existing_type=sa.DateTime(),
            existing_nullable=False,
            nullable=True,
        )

        batch_op.alter_column(
            "is_active",
            existing_type=sa.Boolean(),
            existing_nullable=False,
            nullable=True,
        )