"""
Blue-Trading-AI
Version 28
verify_version_28.py

Run from the backend folder:

    python verify_version_28.py

This script verifies:
- Version 28 persistence imports
- Persistence API routes
- Version 27 learning engine compatibility
- Database trade-history access
- Persistent rebuild from completed trades
- Asian, European, and US session support
- Confidence adjustment safety
- Analysis-only safety settings
"""

from __future__ import annotations

import sys

from sqlalchemy import inspect

from app.api.learning_persistence import (
    router as learning_persistence_router,
)
from app.database.connection import engine
from app.models.trade_history import TradeHistory
from app.services.learning_intelligence_integration import (
    get_learning_intelligence_service,
    get_learning_summary,
    reset_learning_intelligence_service,
)
from app.services.learning_persistence_service import (
    get_learning_persistence_status,
    rebuild_learning_from_database,
)


REQUIRED_COLUMNS = {
    "market_session",
    "market_condition",
    "learning_registered",
    "learning_registered_at",
    "learning_result",
    "learning_confidence_adjustment",
}


def print_result(
    name: str,
    passed: bool,
    detail: str = "",
) -> None:
    status = "PASS" if passed else "FAIL"
    suffix = f" - {detail}" if detail else ""
    print(f"[{status}] {name}{suffix}")


def verify_imports() -> bool:
    passed = all(
        [
            learning_persistence_router is not None,
            TradeHistory is not None,
            get_learning_intelligence_service() is not None,
        ]
    )

    print_result(
        "Version 28 imports",
        passed,
        "Persistence router, model and learning service loaded",
    )
    return passed


def verify_routes() -> bool:
    paths = {
        route.path
        for route in learning_persistence_router.routes
    }

    required = {
        "/learning-persistence/",
        "/learning-persistence/health",
        "/learning-persistence/status",
        "/learning-persistence/rebuild",
        "/learning-persistence/sync",
    }

    missing = required - paths
    passed = not missing

    print_result(
        "Persistence API routes",
        passed,
        (
            "All routes registered"
            if passed
            else f"Missing: {sorted(missing)}"
        ),
    )

    return passed


def verify_database_columns() -> bool:
    inspector = inspect(engine)

    if "trade_history" not in inspector.get_table_names():
        print_result(
            "Database columns",
            False,
            "trade_history table does not exist",
        )
        return False

    existing = {
        column["name"]
        for column in inspector.get_columns("trade_history")
    }

    missing = REQUIRED_COLUMNS - existing
    passed = not missing

    print_result(
        "Version 27/28 database columns",
        passed,
        (
            "All persistent learning columns exist"
            if passed
            else f"Missing: {sorted(missing)}"
        ),
    )

    return passed


def verify_persistence_rebuild() -> bool:
    reset_learning_intelligence_service()

    result = rebuild_learning_from_database(
        reset_engine=True,
    )

    summary = get_learning_summary()

    loaded = int(
        result.get("loaded_completed_trades", 0)
    )
    in_memory = int(
        summary.get("total_completed_trades", 0)
    )

    passed = loaded == in_memory

    print_result(
        "Database learning rebuild",
        passed,
        (
            f"Loaded={loaded}, in-memory={in_memory}"
        ),
    )

    return passed


def verify_persistence_status() -> bool:
    result = get_learning_persistence_status()

    database_eligible = int(
        result.get(
            "database_learning_eligible_trades",
            0,
        )
    )
    in_memory = int(
        result.get(
            "in_memory_learning_trades",
            0,
        )
    )
    restored = bool(
        result.get("learning_restored", False)
    )

    passed = (
        restored
        and database_eligible == in_memory
    )

    print_result(
        "Persistence synchronization",
        passed,
        (
            f"Eligible={database_eligible}, "
            f"in-memory={in_memory}, restored={restored}"
        ),
    )

    return passed


def verify_learning_limits() -> bool:
    service = get_learning_intelligence_service()

    passed = (
        service.MINIMUM_TRADES == 20
        and service.MAX_ADJUSTMENT == 4
    )

    print_result(
        "Learning safety limits",
        passed,
        (
            f"Minimum trades={service.MINIMUM_TRADES}, "
            f"maximum adjustment={service.MAX_ADJUSTMENT}"
        ),
    )

    return passed


def verify_session_support() -> bool:
    status_result = get_learning_persistence_status()

    sessions = set(
        status_result.get(
            "supported_sessions",
            [],
        )
    )

    required_sessions = {
        "asian",
        "european",
        "us",
    }

    passed = required_sessions.issubset(
        sessions
    )

    print_result(
        "Session persistence",
        passed,
        f"Sessions={sorted(sessions)}",
    )

    return passed


def verify_analysis_only() -> bool:
    status_result = get_learning_persistence_status()

    passed = (
        status_result.get("analysis_only") is True
        and status_result.get(
            "broker_connection_enabled"
        ) is False
        and status_result.get(
            "trade_execution_enabled"
        ) is False
    )

    print_result(
        "Analysis-only safety",
        passed,
        "No broker connection or trade execution",
    )

    return passed


def main() -> int:
    print("=" * 60)
    print("BLUE-TRADING-AI VERSION 28 VERIFICATION")
    print("=" * 60)

    checks = [
        verify_imports(),
        verify_routes(),
        verify_database_columns(),
        verify_persistence_rebuild(),
        verify_persistence_status(),
        verify_learning_limits(),
        verify_session_support(),
        verify_analysis_only(),
    ]

    passed_count = sum(checks)
    total_count = len(checks)

    print("=" * 60)
    print(
        f"RESULT: {passed_count}/{total_count} checks passed"
    )
    print("=" * 60)

    if all(checks):
        print(
            "Version 28 verification completed successfully."
        )
        return 0

    print(
        "Version 28 verification found one or more problems. "
        "Review the FAIL lines above."
    )
    return 1


if __name__ == "__main__":
    sys.exit(main())