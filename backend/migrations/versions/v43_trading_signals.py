"""Version 43 trading signal database

Revision ID: v43_trading_signals
Revises: v41_roles_permissions
Create Date: 2026-08-04
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect


revision: str = "v43_trading_signals"
down_revision: Union[str, None] = "v41_roles_permissions"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


TABLE_NAME = "trading_signals"


EXPECTED_INDEXES = {
    "ix_trading_signals_id": ["id"],
    "ix_trading_signals_signal_uid": ["signal_uid"],
    "ix_trading_signals_created_by_user_id": [
        "created_by_user_id"
    ],
    "ix_trading_signals_symbol": ["symbol"],
    "ix_trading_signals_timeframe": ["timeframe"],
    "ix_trading_signals_direction": ["direction"],
    "ix_trading_signals_status": ["status"],
    "ix_trading_signals_result": ["result"],
    "ix_trading_signals_risk_reward_ratio": [
        "risk_reward_ratio"
    ],
    "ix_trading_signals_confidence": ["confidence"],
    "ix_trading_signals_confirmations_count": [
        "confirmations_count"
    ],
    "ix_trading_signals_strategy_version": [
        "strategy_version"
    ],
    "ix_trading_signals_source": ["source"],
    "ix_trading_signals_is_trade_allowed": [
        "is_trade_allowed"
    ],
    "ix_trading_signals_generated_at": [
        "generated_at"
    ],
    "ix_trading_signals_activated_at": [
        "activated_at"
    ],
    "ix_trading_signals_completed_at": [
        "completed_at"
    ],
    "ix_trading_signals_symbol_timeframe": [
        "symbol",
        "timeframe",
    ],
    "ix_trading_signals_status_result": [
        "status",
        "result",
    ],
    "ix_trading_signals_generated_status": [
        "generated_at",
        "status",
    ],
    "ix_trading_signals_trade_quality": [
        "confidence",
        "confirmations_count",
        "risk_reward_ratio",
    ],
}


def _table_exists(table_name: str) -> bool:
    inspector = inspect(op.get_bind())

    return table_name in inspector.get_table_names()


def _index_names(table_name: str) -> set[str]:
    inspector = inspect(op.get_bind())

    if table_name not in inspector.get_table_names():
        return set()

    return {
        str(index.get("name"))
        for index in inspector.get_indexes(
            table_name
        )
        if index.get("name")
    }


def _create_table() -> None:
    if not _table_exists(TABLE_NAME):
        op.create_table(
            TABLE_NAME,
            sa.Column(
                "id",
                sa.Integer(),
                nullable=False,
            ),
            sa.Column(
                "signal_uid",
                sa.String(length=64),
                nullable=False,
            ),
            sa.Column(
                "created_by_user_id",
                sa.Integer(),
                nullable=True,
            ),
            sa.Column(
                "symbol",
                sa.String(length=40),
                nullable=False,
            ),
            sa.Column(
                "timeframe",
                sa.String(length=20),
                nullable=False,
            ),
            sa.Column(
                "direction",
                sa.String(length=20),
                nullable=False,
            ),
            sa.Column(
                "status",
                sa.String(length=20),
                nullable=False,
                server_default=sa.text("'PENDING'"),
            ),
            sa.Column(
                "result",
                sa.String(length=20),
                nullable=False,
                server_default=sa.text("'NONE'"),
            ),
            sa.Column(
                "entry_price",
                sa.Numeric(24, 10),
                nullable=True,
            ),
            sa.Column(
                "stop_loss",
                sa.Numeric(24, 10),
                nullable=True,
            ),
            sa.Column(
                "take_profit_1",
                sa.Numeric(24, 10),
                nullable=True,
            ),
            sa.Column(
                "take_profit_2",
                sa.Numeric(24, 10),
                nullable=True,
            ),
            sa.Column(
                "take_profit_3",
                sa.Numeric(24, 10),
                nullable=True,
            ),
            sa.Column(
                "risk_reward_ratio",
                sa.Numeric(12, 4),
                nullable=True,
            ),
            sa.Column(
                "confidence",
                sa.Numeric(6, 2),
                nullable=False,
                server_default=sa.text("0.00"),
            ),
            sa.Column(
                "confirmations_count",
                sa.Integer(),
                nullable=False,
                server_default=sa.text("0"),
            ),
            sa.Column(
                "strategy_version",
                sa.String(length=50),
                nullable=True,
            ),
            sa.Column(
                "market_structure",
                sa.JSON(),
                nullable=True,
            ),
            sa.Column(
                "confirmations",
                sa.JSON(),
                nullable=True,
            ),
            sa.Column(
                "analysis_details",
                sa.JSON(),
                nullable=True,
            ),
            sa.Column(
                "reasoning",
                sa.Text(),
                nullable=True,
            ),
            sa.Column(
                "rejection_reason",
                sa.Text(),
                nullable=True,
            ),
            sa.Column(
                "source",
                sa.String(length=50),
                nullable=False,
                server_default=sa.text(
                    "'MARKETMIND_AI'"
                ),
            ),
            sa.Column(
                "is_trade_allowed",
                sa.Boolean(),
                nullable=False,
                server_default=sa.false(),
            ),
            sa.Column(
                "minimum_confidence_required",
                sa.Numeric(6, 2),
                nullable=False,
                server_default=sa.text("80.00"),
            ),
            sa.Column(
                "minimum_confirmations_required",
                sa.Integer(),
                nullable=False,
                server_default=sa.text("3"),
            ),
            sa.Column(
                "minimum_risk_reward_required",
                sa.Numeric(12, 4),
                nullable=False,
                server_default=sa.text("1.5000"),
            ),
            sa.Column(
                "generated_at",
                sa.DateTime(timezone=True),
                nullable=False,
                server_default=sa.text(
                    "CURRENT_TIMESTAMP"
                ),
            ),
            sa.Column(
                "activated_at",
                sa.DateTime(timezone=True),
                nullable=True,
            ),
            sa.Column(
                "completed_at",
                sa.DateTime(timezone=True),
                nullable=True,
            ),
            sa.Column(
                "cancelled_at",
                sa.DateTime(timezone=True),
                nullable=True,
            ),
            sa.Column(
                "expired_at",
                sa.DateTime(timezone=True),
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
                ["created_by_user_id"],
                ["users.id"],
                ondelete="SET NULL",
            ),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint(
                "signal_uid",
                name=(
                    "uq_trading_signals_"
                    "signal_uid"
                ),
            ),
        )

    existing_indexes = _index_names(
        TABLE_NAME
    )

    for index_name, columns in (
        EXPECTED_INDEXES.items()
    ):
        if index_name not in existing_indexes:
            op.create_index(
                index_name,
                TABLE_NAME,
                columns,
                unique=False,
            )


def upgrade() -> None:
    """
    Create Version 43 persistent trading-signal storage.

    This is idempotent for local SQLite environments where
    SQLAlchemy metadata may create the table before Alembic.
    """

    _create_table()


def downgrade() -> None:
    """
    Remove Version 43 trading-signal storage.
    """

    if not _table_exists(TABLE_NAME):
        return

    existing_indexes = _index_names(
        TABLE_NAME
    )

    for index_name in reversed(
        list(EXPECTED_INDEXES)
    ):
        if index_name in existing_indexes:
            op.drop_index(
                index_name,
                table_name=TABLE_NAME,
            )

    op.drop_table(TABLE_NAME)