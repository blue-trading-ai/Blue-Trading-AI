"""Version 47 trade-history schema repair

Revision ID: v47_trade_history_schema_repair
Revises: v46_application_event_logs
Create Date: 2026-08-09

Repair three Version-30 TradeHistory columns that may be missing from
PostgreSQL databases created by the earlier baseline migration.

This migration is intentionally idempotent: each column is added only
when it is absent.
"""

from __future__ import annotations

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect


revision: str = "v47_trade_history_schema_repair"
down_revision: Union[str, None] = "v46_application_event_logs"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

TABLE_NAME = "trade_history"


def _table_exists() -> bool:
    inspector = inspect(op.get_bind())
    return TABLE_NAME in inspector.get_table_names()


def _column_names() -> set[str]:
    inspector = inspect(op.get_bind())

    if TABLE_NAME not in inspector.get_table_names():
        return set()

    return {
        str(column.get("name"))
        for column in inspector.get_columns(TABLE_NAME)
        if column.get("name")
    }


def upgrade() -> None:
    if not _table_exists():
        raise RuntimeError(
            "trade_history table does not exist; "
            "the baseline migration must create it before this repair."
        )

    columns = _column_names()

    if "profit_loss_points" not in columns:
        op.add_column(
            TABLE_NAME,
            sa.Column(
                "profit_loss_points",
                sa.Float(),
                nullable=False,
                server_default=sa.text("0.0"),
            ),
        )

    if "risk_reward_achieved" not in columns:
        op.add_column(
            TABLE_NAME,
            sa.Column(
                "risk_reward_achieved",
                sa.Float(),
                nullable=True,
            ),
        )

    if "trade_duration_seconds" not in columns:
        op.add_column(
            TABLE_NAME,
            sa.Column(
                "trade_duration_seconds",
                sa.Integer(),
                nullable=True,
            ),
        )


def downgrade() -> None:
    if not _table_exists():
        return

    columns = _column_names()

    if "trade_duration_seconds" in columns:
        op.drop_column(TABLE_NAME, "trade_duration_seconds")

    if "risk_reward_achieved" in columns:
        op.drop_column(TABLE_NAME, "risk_reward_achieved")

    if "profit_loss_points" in columns:
        op.drop_column(TABLE_NAME, "profit_loss_points")