
"""
Blue-Trading-AI
Version 30
verify_database_v30.py

Place this file in the backend root beside main.py.

Run:
    python verify_database_v30.py

Purpose:
- Verify the existing SQLite database safely.
- Confirm the trade_history table contains every Version 30 column.
- Confirm indexes and database connectivity.
- Never delete, reset, or modify trade records.
"""

from __future__ import annotations

import sys
from typing import Any

from sqlalchemy import inspect, text
from sqlalchemy.exc import SQLAlchemyError

from app.database.connection import (
    DATABASE_PATH,
    DATABASE_URL,
    SessionLocal,
    database_health,
    engine,
)


REQUIRED_TRADE_HISTORY_COLUMNS = {
    "id",
    "signal_id",
    "symbol",
    "interval",
    "direction",
    "market_session",
    "market_condition",
    "entry_price",
    "stop_loss",
    "take_profit_1",
    "take_profit_2",
    "confidence",
    "directional_confidence",
    "confirmation_count",
    "trade_quality_score",
    "trade_quality_grade",
    "status",
    "result",
    "trade_allowed",
    "current_price",
    "exit_price",
    "tp1_hit",
    "tp2_hit",
    "stop_loss_hit",
    "profit_loss_points",
    "risk_reward_achieved",
    "trade_duration_seconds",
    "learning_registered",
    "learning_registered_at",
    "learning_result",
    "learning_confidence_adjustment",
    "reason",
    "confirmation_details",
    "engine_version",
    "created_at",
    "updated_at",
    "closed_at",
}


def print_result(
    name: str,
    passed: bool,
    detail: str = "",
) -> bool:
    label = "PASS" if passed else "FAIL"
    suffix = f" - {detail}" if detail else ""
    print(f"[{label}] {name}{suffix}")
    return passed


def verify_database_connection() -> bool:
    try:
        with engine.connect() as connection:
            result = connection.execute(
                text("SELECT 1")
            ).scalar_one()

        return print_result(
            "Database connection",
            result == 1,
            DATABASE_URL,
        )
    except SQLAlchemyError as exc:
        return print_result(
            "Database connection",
            False,
            str(exc),
        )


def verify_database_file() -> bool:
    exists = DATABASE_PATH.exists()

    return print_result(
        "Database file",
        exists,
        str(DATABASE_PATH),
    )


def verify_trade_history_table() -> tuple[bool, set[str]]:
    inspector = inspect(engine)
    tables = set(inspector.get_table_names())

    exists = "trade_history" in tables

    print_result(
        "trade_history table",
        exists,
        (
            "found"
            if exists
            else f"available tables={sorted(tables)}"
        ),
    )

    return exists, tables


def verify_trade_history_columns() -> bool:
    inspector = inspect(engine)

    columns = {
        column["name"]
        for column in inspector.get_columns(
            "trade_history"
        )
    }

    missing = sorted(
        REQUIRED_TRADE_HISTORY_COLUMNS - columns
    )
    extra = sorted(
        columns - REQUIRED_TRADE_HISTORY_COLUMNS
    )

    passed = not missing

    print_result(
        "Version 30 trade_history columns",
        passed,
        (
            "all required columns present"
            if passed
            else f"missing={missing}"
        ),
    )

    if extra:
        print(
            "[INFO] Additional existing columns preserved: "
            f"{extra}"
        )

    return passed


def verify_trade_history_indexes() -> bool:
    inspector = inspect(engine)
    indexes = inspector.get_indexes(
        "trade_history"
    )

    indexed_columns = {
        column
        for index in indexes
        for column in index.get(
            "column_names",
            [],
        )
    }

    important_columns = {
        "signal_id",
        "symbol",
        "interval",
        "direction",
        "status",
        "result",
        "market_session",
        "market_condition",
        "learning_registered",
        "learning_result",
        "created_at",
    }

    missing_indexes = sorted(
        important_columns - indexed_columns
    )

    # Index absence is not destructive or fatal. Report it as advisory.
    passed = True

    print_result(
        "Database index inspection",
        passed,
        (
            "important indexes present"
            if not missing_indexes
            else (
                "database works; optional indexes missing="
                f"{missing_indexes}"
            )
        ),
    )

    return passed


def verify_sqlite_settings() -> bool:
    try:
        with engine.connect() as connection:
            foreign_keys = connection.execute(
                text("PRAGMA foreign_keys")
            ).scalar()

            journal_mode = connection.execute(
                text("PRAGMA journal_mode")
            ).scalar()

            busy_timeout = connection.execute(
                text("PRAGMA busy_timeout")
            ).scalar()

        passed = (
            int(foreign_keys or 0) == 1
            and str(journal_mode).lower() == "wal"
            and int(busy_timeout or 0) >= 30000
        )

        return print_result(
            "SQLite safety settings",
            passed,
            (
                f"foreign_keys={foreign_keys}, "
                f"journal_mode={journal_mode}, "
                f"busy_timeout={busy_timeout}"
            ),
        )
    except SQLAlchemyError as exc:
        return print_result(
            "SQLite safety settings",
            False,
            str(exc),
        )


def verify_session_factory() -> bool:
    db = SessionLocal()

    try:
        result = db.execute(
            text("SELECT 1")
        ).scalar_one()

        return print_result(
            "SessionLocal",
            result == 1,
            "session query completed",
        )
    except SQLAlchemyError as exc:
        db.rollback()

        return print_result(
            "SessionLocal",
            False,
            str(exc),
        )
    finally:
        db.close()


def show_record_counts() -> None:
    inspector = inspect(engine)

    if "trade_history" not in inspector.get_table_names():
        return

    try:
        with engine.connect() as connection:
            total = connection.execute(
                text(
                    "SELECT COUNT(*) "
                    "FROM trade_history"
                )
            ).scalar_one()

            active = connection.execute(
                text(
                    "SELECT COUNT(*) "
                    "FROM trade_history "
                    "WHERE status = 'ACTIVE'"
                )
            ).scalar_one()

            completed = connection.execute(
                text(
                    "SELECT COUNT(*) "
                    "FROM trade_history "
                    "WHERE status IN "
                    "('CLOSED', 'CANCELLED')"
                )
            ).scalar_one()

            learned = connection.execute(
                text(
                    "SELECT COUNT(*) "
                    "FROM trade_history "
                    "WHERE learning_registered = 1"
                )
            ).scalar_one()

        print(
            "[INFO] Existing records: "
            f"total={total}, "
            f"active={active}, "
            f"completed={completed}, "
            f"learning_registered={learned}"
        )
    except SQLAlchemyError as exc:
        print(
            "[WARN] Could not read record counts: "
            f"{exc}"
        )


def main() -> int:
    print("=" * 76)
    print("BLUE-TRADING-AI VERSION 30 DATABASE VERIFICATION")
    print("=" * 76)

    health: dict[str, Any] = database_health()

    print(f"Database path: {health['database_path']}")
    print(f"Database type: {health['database_type']}")
    print("Mode: READ-ONLY VERIFICATION")
    print("-" * 76)

    connection_passed = verify_database_connection()
    file_passed = verify_database_file()
    table_passed, _ = verify_trade_history_table()

    results = [
        connection_passed,
        file_passed,
        table_passed,
        verify_session_factory(),
        verify_sqlite_settings(),
    ]

    if table_passed:
        results.extend(
            [
                verify_trade_history_columns(),
                verify_trade_history_indexes(),
            ]
        )

    show_record_counts()

    passed_count = sum(results)
    total_count = len(results)

    print("-" * 76)
    print(
        f"FINAL RESULT: {passed_count}/{total_count} "
        "checks passed"
    )
    print("-" * 76)

    if all(results):
        print(
            "Database is ready for Version 30."
        )
        return 0

    print(
        "One or more checks failed. "
        "No database records were changed."
    )
    return 1


if __name__ == "__main__":
    sys.exit(main())