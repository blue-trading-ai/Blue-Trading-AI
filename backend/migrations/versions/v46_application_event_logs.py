"""Version 46 application event logs

Revision ID: v46_application_event_logs
Revises: v45_background_jobs
Create Date: 2026-08-04
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect


revision: str = "v46_application_event_logs"
down_revision: Union[str, None] = "v45_background_jobs"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


TABLE_NAME = "application_event_logs"


EXPECTED_INDEXES = {
    "ix_application_event_logs_id": ["id"],
    "ix_application_event_logs_event_uid": [
        "event_uid"
    ],
    "ix_application_event_logs_level": ["level"],
    "ix_application_event_logs_event_type": [
        "event_type"
    ],
    "ix_application_event_logs_event_name": [
        "event_name"
    ],
    "ix_application_event_logs_source": [
        "source"
    ],
    "ix_application_event_logs_request_id": [
        "request_id"
    ],
    "ix_application_event_logs_user_id": [
        "user_id"
    ],
    "ix_application_event_logs_job_uid": [
        "job_uid"
    ],
    "ix_application_event_logs_method": [
        "method"
    ],
    "ix_application_event_logs_path": ["path"],
    "ix_application_event_logs_status_code": [
        "status_code"
    ],
    "ix_application_event_logs_duration_ms": [
        "duration_ms"
    ],
    "ix_application_event_logs_client_ip_hash": [
        "client_ip_hash"
    ],
    "ix_application_event_logs_exception_type": [
        "exception_type"
    ],
    "ix_application_event_logs_created_at": [
        "created_at"
    ],
    "ix_application_event_logs_level_created": [
        "level",
        "created_at",
    ],
    "ix_application_event_logs_type_created": [
        "event_type",
        "created_at",
    ],
    "ix_application_event_logs_request_path": [
        "request_id",
        "path",
    ],
    "ix_application_event_logs_status_duration": [
        "status_code",
        "duration_ms",
    ],
    "ix_application_event_logs_job_created": [
        "job_uid",
        "created_at",
    ],
}


def _table_exists(
    table_name: str,
) -> bool:
    inspector = inspect(op.get_bind())

    return table_name in inspector.get_table_names()


def _index_names(
    table_name: str,
) -> set[str]:
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
                "event_uid",
                sa.String(length=64),
                nullable=False,
            ),
            sa.Column(
                "level",
                sa.String(length=20),
                nullable=False,
                server_default=sa.text("'INFO'"),
            ),
            sa.Column(
                "event_type",
                sa.String(length=40),
                nullable=False,
                server_default=sa.text(
                    "'APPLICATION'"
                ),
            ),
            sa.Column(
                "event_name",
                sa.String(length=120),
                nullable=False,
            ),
            sa.Column(
                "message",
                sa.Text(),
                nullable=False,
            ),
            sa.Column(
                "source",
                sa.String(length=120),
                nullable=True,
            ),
            sa.Column(
                "request_id",
                sa.String(length=80),
                nullable=True,
            ),
            sa.Column(
                "user_id",
                sa.Integer(),
                nullable=True,
            ),
            sa.Column(
                "job_uid",
                sa.String(length=64),
                nullable=True,
            ),
            sa.Column(
                "method",
                sa.String(length=12),
                nullable=True,
            ),
            sa.Column(
                "path",
                sa.String(length=500),
                nullable=True,
            ),
            sa.Column(
                "status_code",
                sa.Integer(),
                nullable=True,
            ),
            sa.Column(
                "duration_ms",
                sa.Float(),
                nullable=True,
            ),
            sa.Column(
                "client_ip_hash",
                sa.String(length=128),
                nullable=True,
            ),
            sa.Column(
                "exception_type",
                sa.String(length=160),
                nullable=True,
            ),
            sa.Column(
                "exception_message",
                sa.Text(),
                nullable=True,
            ),
            sa.Column(
                "metadata_json",
                sa.JSON(),
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
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint(
                "event_uid",
                name=(
                    "uq_application_event_logs_event_uid"
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
    Create Version 46 structured application logs.

    Safe for local SQLite environments where SQLAlchemy
    metadata may create the table before Alembic runs.
    """

    _create_table()


def downgrade() -> None:
    """
    Remove Version 46 structured application logs.
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