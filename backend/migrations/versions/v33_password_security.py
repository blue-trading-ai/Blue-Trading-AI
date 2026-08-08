"""Version 33 password security and token revocation

Revision ID: v33_password_security
Revises: b32_owner_access
Create Date: 2026-08-03
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "v33_password_security"
down_revision: Union[str, None] = "b32_owner_access"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """
    Add password versioning and password-change timestamps safely.

    Existing users start at password_version 1.
    Existing users receive CURRENT_TIMESTAMP as password_changed_at.
    """

    with op.batch_alter_table("users") as batch_op:
        batch_op.add_column(
            sa.Column(
                "password_version",
                sa.Integer(),
                nullable=True,
            )
        )
        batch_op.add_column(
            sa.Column(
                "password_changed_at",
                sa.DateTime(timezone=True),
                nullable=True,
            )
        )

    op.execute(
        sa.text(
            """
            UPDATE users
            SET password_version = 1
            WHERE password_version IS NULL
            """
        )
    )

    op.execute(
        sa.text(
            """
            UPDATE users
            SET password_changed_at = CURRENT_TIMESTAMP
            WHERE password_changed_at IS NULL
            """
        )
    )

    with op.batch_alter_table("users") as batch_op:
        batch_op.alter_column(
            "password_version",
            existing_type=sa.Integer(),
            nullable=False,
        )
        batch_op.alter_column(
            "password_changed_at",
            existing_type=sa.DateTime(timezone=True),
            nullable=False,
        )


def downgrade() -> None:
    """
    Remove Version 33 password-security fields.
    """

    with op.batch_alter_table("users") as batch_op:
        batch_op.drop_column("password_changed_at")
        batch_op.drop_column("password_version")