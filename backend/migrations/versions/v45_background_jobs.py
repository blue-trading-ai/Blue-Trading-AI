"""Version 45 background jobs

Revision ID: v45_background_jobs
Revises: v43_trading_signals
Create Date: 2026-08-04
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect


revision: str = "v45_background_jobs"
down_revision: Union[str, None] = "v43_trading_signals"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


TABLE_NAME = "background_jobs"


EXPECTED_INDEXES = {
    "ix_background_jobs_id": ["id"],
    "ix_background_jobs_job_uid": ["job_uid"],
    "ix_background_jobs_job_type": ["job_type"],
    "ix_background_jobs_status": ["status"],
    "ix_background_jobs_symbol": ["symbol"],
    "ix_background_jobs_timeframe": ["timeframe"],
    "ix_background_jobs_attempt_count": ["attempt_count"],
    "ix_background_jobs_priority": ["priority"],
    "ix_background_jobs_is_recurring": ["is_recurring"],
    "ix_background_jobs_scheduled_at": ["scheduled_at"],
    "ix_background_jobs_started_at": ["started_at"],
    "ix_background_jobs_finished_at": ["finished_at"],
    "ix_background_jobs_retry_at": ["retry_at"],
    "ix_background_jobs_heartbeat_at": ["heartbeat_at"],
    "ix_background_jobs_worker_name": ["worker_name"],
    "ix_background_jobs_status_schedule": [
        "status",
        "scheduled_at",
    ],
    "ix_background_jobs_type_status": [
        "job_type",
        "status",
    ],
    "ix_background_jobs_symbol_timeframe": [
        "symbol",
        "timeframe",
    ],
    "ix_background_jobs_priority_schedule": [
        "priority",
        "scheduled_at",
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
                "job_uid",
                sa.String(length=64),
                nullable=False,
            ),
            sa.Column(
                "job_type",
                sa.String(length=40),
                nullable=False,
            ),
            sa.Column(
                "status",
                sa.String(length=30),
                nullable=False,
                server_default=sa.text("'PENDING'"),
            ),
            sa.Column(
                "symbol",
                sa.String(length=40),
                nullable=True,
            ),
            sa.Column(
                "timeframe",
                sa.String(length=20),
                nullable=True,
            ),
            sa.Column(
                "payload",
                sa.JSON(),
                nullable=True,
            ),
            sa.Column(
                "result_payload",
                sa.JSON(),
                nullable=True,
            ),
            sa.Column(
                "error_message",
                sa.Text(),
                nullable=True,
            ),
            sa.Column(
                "attempt_count",
                sa.Integer(),
                nullable=False,
                server_default=sa.text("0"),
            ),
            sa.Column(
                "max_attempts",
                sa.Integer(),
                nullable=False,
                server_default=sa.text("3"),
            ),
            sa.Column(
                "priority",
                sa.Integer(),
                nullable=False,
                server_default=sa.text("100"),
            ),
            sa.Column(
                "is_recurring",
                sa.Boolean(),
                nullable=False,
                server_default=sa.false(),
            ),
            sa.Column(
                "scheduled_at",
                sa.DateTime(timezone=True),
                nullable=False,
                server_default=sa.text(
                    "CURRENT_TIMESTAMP"
                ),
            ),
            sa.Column(
                "started_at",
                sa.DateTime(timezone=True),
                nullable=True,
            ),
            sa.Column(
                "finished_at",
                sa.DateTime(timezone=True),
                nullable=True,
            ),
            sa.Column(
                "retry_at",
                sa.DateTime(timezone=True),
                nullable=True,
            ),
            sa.Column(
                "heartbeat_at",
                sa.DateTime(timezone=True),
                nullable=True,
            ),
            sa.Column(
                "duration_ms",
                sa.Integer(),
                nullable=True,
            ),
            sa.Column(
                "worker_name",
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
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint(
                "job_uid",
                name="uq_background_jobs_job_uid",
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
    Create Version 45 persistent background-job storage.

    This migration is safe for local SQLite environments
    where SQLAlchemy metadata may create the table first.
    """

    _create_table()


def downgrade() -> None:
    """
    Remove Version 45 background-job storage.
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