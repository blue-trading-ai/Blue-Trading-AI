
"""Version 32 owner-controlled user approval

Revision ID: b32_owner_access
Revises: 826026c92fcc
Create Date: 2026-08-03
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "b32_owner_access"
down_revision: Union[str, None] = "826026c92fcc"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """
    Add Version 32 owner-controlled access fields safely.

    Existing accounts are placed into PENDING status.
    The configured OWNER_EMAIL account will be approved automatically
    on its next successful login by the Version 32 auth bootstrap.
    """

    with op.batch_alter_table("users") as batch_op:
        batch_op.add_column(
            sa.Column(
                "account_status",
                sa.String(length=20),
                nullable=True,
            )
        )
        batch_op.add_column(
            sa.Column(
                "approved_at",
                sa.DateTime(timezone=True),
                nullable=True,
            )
        )
        batch_op.add_column(
            sa.Column(
                "approved_by",
                sa.String(length=255),
                nullable=True,
            )
        )
        batch_op.add_column(
            sa.Column(
                "rejected_at",
                sa.DateTime(timezone=True),
                nullable=True,
            )
        )
        batch_op.add_column(
            sa.Column(
                "suspended_at",
                sa.DateTime(timezone=True),
                nullable=True,
            )
        )
        batch_op.add_column(
            sa.Column(
                "access_status_updated_at",
                sa.DateTime(timezone=True),
                nullable=True,
            )
        )

    op.execute(
        sa.text(
            """
            UPDATE users
            SET
                account_status = 'PENDING',
                access_status_updated_at = CURRENT_TIMESTAMP
            WHERE account_status IS NULL
            """
        )
    )

    with op.batch_alter_table("users") as batch_op:
        batch_op.alter_column(
            "account_status",
            existing_type=sa.String(length=20),
            nullable=False,
        )
        batch_op.alter_column(
            "access_status_updated_at",
            existing_type=sa.DateTime(timezone=True),
            nullable=False,
        )
        batch_op.create_index(
            "ix_users_account_status",
            ["account_status"],
            unique=False,
        )


def downgrade() -> None:
    """
    Remove Version 32 owner-controlled access fields.
    """

    with op.batch_alter_table("users") as batch_op:
        batch_op.drop_index("ix_users_account_status")
        batch_op.drop_column("access_status_updated_at")
        batch_op.drop_column("suspended_at")
        batch_op.drop_column("rejected_at")
        batch_op.drop_column("approved_by")
        batch_op.drop_column("approved_at")
        batch_op.drop_column("account_status")