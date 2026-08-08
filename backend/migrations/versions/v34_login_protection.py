"""Version 34 login protection

Revision ID: v34_login_protection
Revises: v33_password_security
Create Date: 2026-08-03
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "v34_login_protection"
down_revision: Union[str, None] = "v33_password_security"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """
    Add failed-login tracking and temporary lockout fields safely.

    Existing users start with:
    - failed_login_attempts = 0
    - no failed-login timestamp
    - no lockout
    - no recorded last-login timestamp
    """

    with op.batch_alter_table("users") as batch_op:
        batch_op.add_column(
            sa.Column(
                "failed_login_attempts",
                sa.Integer(),
                nullable=True,
            )
        )
        batch_op.add_column(
            sa.Column(
                "last_failed_login_at",
                sa.DateTime(timezone=True),
                nullable=True,
            )
        )
        batch_op.add_column(
            sa.Column(
                "locked_until",
                sa.DateTime(timezone=True),
                nullable=True,
            )
        )
        batch_op.add_column(
            sa.Column(
                "last_login_at",
                sa.DateTime(timezone=True),
                nullable=True,
            )
        )

    op.execute(
        sa.text(
            """
            UPDATE users
            SET failed_login_attempts = 0
            WHERE failed_login_attempts IS NULL
            """
        )
    )

    with op.batch_alter_table("users") as batch_op:
        batch_op.alter_column(
            "failed_login_attempts",
            existing_type=sa.Integer(),
            nullable=False,
        )


def downgrade() -> None:
    """
    Remove Version 34 login-protection fields.
    """

    with op.batch_alter_table("users") as batch_op:
        batch_op.drop_column("last_login_at")
        batch_op.drop_column("locked_until")
        batch_op.drop_column("last_failed_login_at")
        batch_op.drop_column("failed_login_attempts")