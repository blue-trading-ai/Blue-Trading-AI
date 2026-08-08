"""baseline version 31

Revision ID: a0aef49a1c59
Revises:
Create Date: 2026-08-02

Safe initial database foundation.

Works with:
- Fresh PostgreSQL database
- Existing partially created database
"""

from __future__ import annotations

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect


revision: str = "a0aef49a1c59"

down_revision: Union[str, Sequence[str], None] = None

branch_labels: Union[str, Sequence[str], None] = None

depends_on: Union[str, Sequence[str], None] = None



# ============================
# HELPERS
# ============================


def table_exists(table_name: str) -> bool:

    inspector = inspect(
        op.get_bind()
    )

    return (
        table_name
        in inspector.get_table_names()
    )



def existing_columns(table_name: str) -> set[str]:

    inspector = inspect(
        op.get_bind()
    )

    if not table_exists(table_name):
        return set()

    return {
        column["name"]
        for column in inspector.get_columns(
            table_name
        )
    }



# ============================
# USERS TABLE
# ============================


def create_users_table():

    if table_exists("users"):
        return


    op.create_table(

        "users",


        sa.Column(
            "id",
            sa.Integer(),
            nullable=False,
        ),


        sa.Column(
            "username",
            sa.String(100),
            nullable=False,
        ),


        sa.Column(
            "email",
            sa.String(255),
            nullable=False,
        ),


        sa.Column(
            "hashed_password",
            sa.String(255),
            nullable=False,
        ),


        sa.Column(
            "is_active",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text(
                "true"
            ),
        ),


        sa.Column(
            "created_at",
            sa.DateTime(
                timezone=True
            ),
            nullable=False,
            server_default=sa.text(
                "CURRENT_TIMESTAMP"
            ),
        ),


        sa.PrimaryKeyConstraint(
            "id"
        ),


        sa.UniqueConstraint(
            "username",
            name="uq_users_username",
        ),


        sa.UniqueConstraint(
            "email",
            name="uq_users_email",
        ),
    )


    op.create_index(
        "ix_users_id",
        "users",
        ["id"],
        unique=False,
    )


    op.create_index(
        "ix_users_username",
        "users",
        ["username"],
        unique=False,
    )


    op.create_index(
        "ix_users_email",
        "users",
        ["email"],
        unique=False,
    )



def upgrade():

    create_users_table()
    # ============================
# TRADE HISTORY TABLE
# ============================


def create_trade_history_table():

    if table_exists("trade_history"):
        return


    op.create_table(

        "trade_history",


        sa.Column(
            "id",
            sa.Integer(),
            nullable=False,
        ),


        sa.Column(
            "signal_id",
            sa.String(100),
            nullable=False,
        ),


        sa.Column(
            "symbol",
            sa.String(50),
            nullable=False,
        ),


        sa.Column(
            "interval",
            sa.String(20),
            nullable=False,
        ),


        sa.Column(
            "direction",
            sa.String(10),
            nullable=False,
        ),


        sa.Column(
            "market_session",
            sa.String(20),
            nullable=True,
        ),


        sa.Column(
            "market_condition",
            sa.String(80),
            nullable=True,
        ),


        sa.Column(
            "entry_price",
            sa.Float(),
            nullable=False,
        ),


        sa.Column(
            "stop_loss",
            sa.Float(),
            nullable=False,
        ),


        sa.Column(
            "take_profit_1",
            sa.Float(),
            nullable=False,
        ),


        sa.Column(
            "take_profit_2",
            sa.Float(),
            nullable=False,
        ),


        sa.Column(
            "confidence",
            sa.Float(),
            nullable=False,
        ),


        sa.Column(
            "directional_confidence",
            sa.Float(),
            nullable=True,
        ),


        sa.Column(
            "confirmation_count",
            sa.Integer(),
            nullable=False,
            server_default=sa.text("0"),
        ),


        sa.Column(
            "trade_quality_score",
            sa.Float(),
            nullable=True,
        ),


        sa.Column(
            "trade_quality_grade",
            sa.String(30),
            nullable=True,
        ),


        sa.Column(
            "status",
            sa.String(30),
            nullable=False,
            server_default=sa.text("'ACTIVE'"),
        ),


        sa.Column(
            "result",
            sa.String(30),
            nullable=False,
            server_default=sa.text("'PENDING'"),
        ),


        sa.Column(
            "trade_allowed",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("true"),
        ),


        sa.Column(
            "current_price",
            sa.Float(),
            nullable=True,
        ),


        sa.Column(
            "exit_price",
            sa.Float(),
            nullable=True,
        ),


        sa.Column(
            "tp1_hit",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
        ),


        sa.Column(
            "tp2_hit",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
        ),


        sa.Column(
            "stop_loss_hit",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
        ),

        sa.Column(
            "learning_registered",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
        ),


        sa.Column(
            "learning_registered_at",
            sa.DateTime(timezone=True),
            nullable=True,
        ),

        sa.Column(
            "learning_result",
            sa.String(20),
            nullable=True,
        ),


        sa.Column(
            "learning_confidence_adjustment",
            sa.Float(),
            nullable=False,
            server_default=sa.text("0.0"),
        ),


        sa.Column(
            "reason",
            sa.Text(),
            nullable=True,
        ),


        sa.Column(
            "confirmation_details",
            sa.Text(),
            nullable=True,
        ),


        sa.Column(
            "engine_version",
            sa.String(100),
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


        sa.Column(
            "closed_at",
            sa.DateTime(timezone=True),
            nullable=True,
        ),


        sa.PrimaryKeyConstraint(
            "id"
        ),


        sa.UniqueConstraint(
            "signal_id",
            name="uq_trade_history_signal_id",
        ),
    )
    # ============================
# REPAIR EXISTING TABLES
# ============================


def add_missing_trade_columns():

    if not table_exists("trade_history"):
        return


    columns = existing_columns(
        "trade_history"
    )


    with op.batch_alter_table(
        "trade_history"
    ) as batch_op:


        if "trade_allowed" not in columns:
            batch_op.add_column(
                sa.Column(
                    "trade_allowed",
                    sa.Boolean(),
                    nullable=False,
                    server_default=sa.text(
                        "true"
                    ),
                )
            )


        if "current_price" not in columns:
            batch_op.add_column(
                sa.Column(
                    "current_price",
                    sa.Float(),
                    nullable=True,
                )
            )


        if "exit_price" not in columns:
            batch_op.add_column(
                sa.Column(
                    "exit_price",
                    sa.Float(),
                    nullable=True,
                )
            )


        if "tp1_hit" not in columns:
            batch_op.add_column(
                sa.Column(
                    "tp1_hit",
                    sa.Boolean(),
                    nullable=False,
                    server_default=sa.text(
                        "false"
                    ),
                )
            )


        if "tp2_hit" not in columns:
            batch_op.add_column(
                sa.Column(
                    "tp2_hit",
                    sa.Boolean(),
                    nullable=False,
                    server_default=sa.text(
                        "false"
                    ),
                )
            )


        if "stop_loss_hit" not in columns:
            batch_op.add_column(
                sa.Column(
                    "stop_loss_hit",
                    sa.Boolean(),
                    nullable=False,
                    server_default=sa.text(
                        "false"
                    ),
                )
            )


        if "learning_registered" not in columns:
            batch_op.add_column(
                sa.Column(
                    "learning_registered",
                    sa.Boolean(),
                    nullable=False,
                    server_default=sa.text(
                        "false"
                    ),
                )
            )



# ============================
# UPGRADE
# ============================


def upgrade():

    create_users_table()

    create_trade_history_table()

    add_missing_trade_columns()



# ============================
# DOWNGRADE
# ============================


def downgrade():

    if table_exists(
        "trade_history"
    ):
        op.drop_table(
            "trade_history"
        )


    if table_exists(
        "users"
    ):
        op.drop_table(
            "users"
        )
        