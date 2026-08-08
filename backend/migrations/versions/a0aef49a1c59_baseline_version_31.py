"""baseline version 31

Revision ID: a0aef49a1c59
Revises:
Create Date: 2026-08-02 22:52:14.101851

Initial database foundation for Blue-Trading-AI.

Creates:
- users (Version 31 foundation)
- trade_history (Version 30 trading foundation)

Later migrations add:
- owner approval
- password security
- login protection
- email verification
- roles
- trading signals
- background services
"""

from __future__ import annotations

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "a0aef49a1c59"
down_revision: Union[str, Sequence[str], None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:

    # ============================
    # USERS TABLE - VERSION 31
    # ============================

    op.create_table(
        "users",

        sa.Column(
            "id",
            sa.Integer(),
            nullable=False,
        ),

        sa.Column(
            "username",
            sa.String(length=100),
            nullable=False,
        ),

        sa.Column(
            "email",
            sa.String(length=255),
            nullable=False,
        ),

        sa.Column(
            "hashed_password",
            sa.String(length=255),
            nullable=False,
        ),

        sa.Column(
            "is_active",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("1"),
        ),

        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
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


    # ============================
    # TRADE HISTORY TABLE
    # ============================

    op.create_table(
        "trade_history",

        sa.Column(
            "id",
            sa.Integer(),
            nullable=False,
        ),

        sa.Column(
            "signal_id",
            sa.String(length=100),
            nullable=False,
        ),

        sa.Column(
            "symbol",
            sa.String(length=50),
            nullable=False,
        ),

        sa.Column(
            "interval",
            sa.String(length=20),
            nullable=False,
        ),

        sa.Column(
            "direction",
            sa.String(length=10),
            nullable=False,
        ),

        sa.Column(
            "market_session",
            sa.String(length=20),
            nullable=True,
        ),

        sa.Column(
            "market_condition",
            sa.String(length=80),
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
            sa.String(length=30),
            nullable=True,
        ),

        sa.Column(
            "status",
            sa.String(length=30),
            nullable=False,
            server_default=sa.text("'ACTIVE'"),
        ),

        sa.Column(
            "result",
            sa.String(length=30),
            nullable=False,
            server_default=sa.text("'PENDING'"),
        ),
                sa.Column(
            "trade_allowed",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("1"),
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
            server_default=sa.text("0"),
        ),

        sa.Column(
            "tp2_hit",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("0"),
        ),

        sa.Column(
            "stop_loss_hit",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("0"),
        ),

        sa.Column(
            "profit_loss_points",
            sa.Float(),
            nullable=False,
            server_default=sa.text("0.0"),
        ),

        sa.Column(
            "risk_reward_achieved",
            sa.Float(),
            nullable=True,
        ),

        sa.Column(
            "trade_duration_seconds",
            sa.Integer(),
            nullable=True,
        ),

        sa.Column(
            "learning_registered",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("0"),
        ),

        sa.Column(
            "learning_registered_at",
            sa.DateTime(timezone=True),
            nullable=True,
        ),

        sa.Column(
            "learning_result",
            sa.String(length=20),
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
            sa.String(length=100),
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


    # Trade history indexes

    op.create_index(
        "ix_trade_history_id",
        "trade_history",
        ["id"],
        unique=False,
    )

    op.create_index(
        "ix_trade_history_signal_id",
        "trade_history",
        ["signal_id"],
        unique=False,
    )

    op.create_index(
        "ix_trade_history_symbol",
        "trade_history",
        ["symbol"],
        unique=False,
    )

    op.create_index(
        "ix_trade_history_interval",
        "trade_history",
        ["interval"],
        unique=False,
    )

    op.create_index(
        "ix_trade_history_direction",
        "trade_history",
        ["direction"],
        unique=False,
    )

    op.create_index(
        "ix_trade_history_status",
        "trade_history",
        ["status"],
        unique=False,
    )

    op.create_index(
        "ix_trade_history_result",
        "trade_history",
        ["result"],
        unique=False,
    )

    op.create_index(
        "ix_trade_history_learning_registered",
        "trade_history",
        ["learning_registered"],
        unique=False,
    )

    op.create_index(
        "ix_trade_history_created_at",
        "trade_history",
        ["created_at"],
        unique=False,
    )


def downgrade() -> None:

    op.drop_table(
        "trade_history"
    )

    op.drop_table(
        "users"
    )