"""
Blue-Trading-AI
Version 27
migrate_trade_history_v27.py

Adds Version 27 learning columns to the existing trade_history table.

Run once from the backend folder:

    python migrate_trade_history_v27.py

This script:
- Uses the existing SQLAlchemy engine.
- Detects the active database dialect.
- Adds only missing columns.
- Does not delete existing trade data.
"""

from __future__ import annotations

import logging
from typing import Dict

from sqlalchemy import inspect, text
from sqlalchemy.engine import Engine

from app.database.connection import engine


logging.basicConfig(
    level=logging.INFO,
    format="%(levelname)s: %(message)s",
)

logger = logging.getLogger(__name__)


TABLE_NAME = "trade_history"


COLUMN_DEFINITIONS: Dict[str, Dict[str, str]] = {
    "market_session": {
        "sqlite": "VARCHAR(20)",
        "postgresql": "VARCHAR(20)",
        "mysql": "VARCHAR(20)",
        "default": "VARCHAR(20)",
    },
    "market_condition": {
        "sqlite": "VARCHAR(80)",
        "postgresql": "VARCHAR(80)",
        "mysql": "VARCHAR(80)",
        "default": "VARCHAR(80)",
    },
    "learning_registered": {
        "sqlite": "BOOLEAN NOT NULL DEFAULT 0",
        "postgresql": "BOOLEAN NOT NULL DEFAULT FALSE",
        "mysql": "BOOLEAN NOT NULL DEFAULT FALSE",
        "default": "BOOLEAN NOT NULL DEFAULT FALSE",
    },
    "learning_registered_at": {
        "sqlite": "DATETIME",
        "postgresql": "TIMESTAMP WITH TIME ZONE",
        "mysql": "DATETIME",
        "default": "DATETIME",
    },
    "learning_result": {
        "sqlite": "VARCHAR(20)",
        "postgresql": "VARCHAR(20)",
        "mysql": "VARCHAR(20)",
        "default": "VARCHAR(20)",
    },
    "learning_confidence_adjustment": {
        "sqlite": "FLOAT NOT NULL DEFAULT 0.0",
        "postgresql": "DOUBLE PRECISION NOT NULL DEFAULT 0.0",
        "mysql": "DOUBLE NOT NULL DEFAULT 0.0",
        "default": "FLOAT NOT NULL DEFAULT 0.0",
    },
}


INDEXES = {
    "ix_trade_history_market_session": "market_session",
    "ix_trade_history_market_condition": "market_condition",
    "ix_trade_history_learning_registered": "learning_registered",
    "ix_trade_history_learning_result": "learning_result",
}


def get_existing_columns(database_engine: Engine) -> set[str]:
    inspector = inspect(database_engine)

    if TABLE_NAME not in inspector.get_table_names():
        raise RuntimeError(
            f"Table '{TABLE_NAME}' does not exist. "
            "Start the application once so SQLAlchemy can create it."
        )

    return {
        column["name"]
        for column in inspector.get_columns(TABLE_NAME)
    }


def get_existing_indexes(database_engine: Engine) -> set[str]:
    inspector = inspect(database_engine)

    return {
        index["name"]
        for index in inspector.get_indexes(TABLE_NAME)
        if index.get("name")
    }


def get_column_sql_type(
    column_name: str,
    dialect_name: str,
) -> str:
    definitions = COLUMN_DEFINITIONS[column_name]

    return definitions.get(
        dialect_name,
        definitions["default"],
    )


def add_missing_columns(database_engine: Engine) -> list[str]:
    dialect_name = database_engine.dialect.name
    existing_columns = get_existing_columns(database_engine)
    added_columns: list[str] = []

    with database_engine.begin() as connection:
        for column_name in COLUMN_DEFINITIONS:
            if column_name in existing_columns:
                logger.info(
                    "Column already exists: %s",
                    column_name,
                )
                continue

            sql_type = get_column_sql_type(
                column_name,
                dialect_name,
            )

            statement = text(
                f"ALTER TABLE {TABLE_NAME} "
                f"ADD COLUMN {column_name} {sql_type}"
            )

            connection.execute(statement)
            added_columns.append(column_name)

            logger.info(
                "Added column: %s",
                column_name,
            )

    return added_columns


def create_missing_indexes(database_engine: Engine) -> list[str]:
    existing_indexes = get_existing_indexes(database_engine)
    created_indexes: list[str] = []

    with database_engine.begin() as connection:
        for index_name, column_name in INDEXES.items():
            if index_name in existing_indexes:
                logger.info(
                    "Index already exists: %s",
                    index_name,
                )
                continue

            statement = text(
                f"CREATE INDEX {index_name} "
                f"ON {TABLE_NAME} ({column_name})"
            )

            connection.execute(statement)
            created_indexes.append(index_name)

            logger.info(
                "Created index: %s",
                index_name,
            )

    return created_indexes


def verify_migration(database_engine: Engine) -> None:
    existing_columns = get_existing_columns(database_engine)
    missing_columns = set(COLUMN_DEFINITIONS) - existing_columns

    if missing_columns:
        raise RuntimeError(
            "Migration verification failed. Missing columns: "
            + ", ".join(sorted(missing_columns))
        )

    logger.info(
        "Version 27 migration verification passed."
    )


def run_migration() -> None:
    logger.info(
        "Starting Blue-Trading-AI Version 27 database migration."
    )

    logger.info(
        "Database dialect: %s",
        engine.dialect.name,
    )

    added_columns = add_missing_columns(engine)
    created_indexes = create_missing_indexes(engine)
    verify_migration(engine)

    logger.info(
        "Migration complete. Added %s columns and %s indexes.",
        len(added_columns),
        len(created_indexes),
    )


if __name__ == "__main__":
    try:
        run_migration()
    except Exception:
        logger.exception(
            "Version 27 migration failed."
        )
        raise