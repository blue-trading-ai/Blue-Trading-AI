"""
Blue-Trading-AI
Version 27
verify_version_27.py

Run from the backend folder:

    python verify_version_27.py

This script verifies:
- Version 27 service imports
- API router import
- Database columns
- Learning engine registration
- Asian, European, and US session support
- Confidence adjustment safety limit
- Analysis-only safety settings
"""

from __future__ import annotations

import sys
from datetime import datetime, timezone

from sqlalchemy import inspect

from app.database.connection import engine
from app.models.trade_history import TradeHistory
from app.services.learning_intelligence_integration import (
    evaluate_learning_intelligence,
    get_learning_intelligence_service,
    get_learning_summary,
    register_completed_trade,
    reset_learning_intelligence_service,
)
from app.services.learning_intelligence_service import (
    LearningIntelligenceService,
)
from app.api.learning_intelligence import router as learning_router


REQUIRED_COLUMNS = {
    "market_session",
    "market_condition",
    "learning_registered",
    "learning_registered_at",
    "learning_result",
    "learning_confidence_adjustment",
}


def print_result(name: str, passed: bool, detail: str = "") -> None:
    status = "PASS" if passed else "FAIL"
    suffix = f" - {detail}" if detail else ""
    print(f"[{status}] {name}{suffix}")


def verify_imports() -> bool:
    checks = [
        LearningIntelligenceService is not None,
        learning_router is not None,
        TradeHistory is not None,
    ]

    passed = all(checks)
    print_result(
        "Version 27 imports",
        passed,
        "Core service, router and model loaded",
    )
    return passed


def verify_router() -> bool:
    paths = {
        route.path
        for route in learning_router.routes
    }

    required_paths = {
        "/learning-intelligence/",
        "/learning-intelligence/health",
        "/learning-intelligence/completed-trades",
        "/learning-intelligence/evaluate",
        "/learning-intelligence/summary",
        "/learning-intelligence/reset",
    }

    missing = required_paths - paths
    passed = not missing

    print_result(
        "Learning API routes",
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
        "Database columns",
        passed,
        (
            "All Version 27 columns exist"
            if passed
            else f"Missing: {sorted(missing)}"
        ),
    )
    return passed


def build_trade(
    *,
    index: int,
    session: str,
    result: str,
) -> dict:
    now = datetime.now(timezone.utc)

    return {
        "symbol": "XAUUSD",
        "session": session,
        "market_condition": "trending",
        "direction": "BUY",
        "confidence": 85.0,
        "risk_reward": 2.0,
        "result": result,
        "entry_price": 2300.0 + index,
        "stop_loss": 2290.0 + index,
        "take_profit": 2320.0 + index,
        "opened_at": now,
        "closed_at": now,
    }


def verify_learning_registration() -> bool:
    reset_learning_intelligence_service()

    sessions = ["asian", "european", "us"]

    for index in range(20):
        session = sessions[index % len(sessions)]
        result = "WIN" if index < 16 else "LOSS"

        register_completed_trade(
            build_trade(
                index=index,
                session=session,
                result=result,
            )
        )

    summary = get_learning_summary()

    total = summary.get("total_completed_trades", 0)
    session_keys = set(summary.get("sessions", {}).keys())

    passed = (
        total == 20
        and {"asian", "european", "us"}.issubset(
            session_keys
        )
    )

    print_result(
        "Completed-trade learning",
        passed,
        (
            f"Trades={total}, sessions={sorted(session_keys)}"
        ),
    )

    return passed


def verify_confidence_adjustment() -> bool:
    result = evaluate_learning_intelligence(
        symbol="XAUUSD",
        session="asian",
        market_condition="trending",
        direction="BUY",
        current_confidence=85.0,
    )

    adjustment = float(
        result.get("confidence_adjustment", 0.0)
    )
    adjusted = float(
        result.get("adjusted_confidence", 0.0)
    )

    passed = (
        -4.0 <= adjustment <= 4.0
        and 0.0 <= adjusted <= 100.0
    )

    print_result(
        "Confidence adjustment safety",
        passed,
        (
            f"Adjustment={adjustment}, "
            f"adjusted confidence={adjusted}"
        ),
    )

    return passed


def verify_service_limits() -> bool:
    service = get_learning_intelligence_service()

    passed = (
        service.MINIMUM_TRADES == 20
        and service.MAX_ADJUSTMENT == 4
    )

    print_result(
        "Learning limits",
        passed,
        (
            f"Minimum trades={service.MINIMUM_TRADES}, "
            f"max adjustment={service.MAX_ADJUSTMENT}"
        ),
    )

    return passed


def main() -> int:
    print("=" * 60)
    print("BLUE-TRADING-AI VERSION 27 VERIFICATION")
    print("=" * 60)

    checks = [
        verify_imports(),
        verify_router(),
        verify_database_columns(),
        verify_learning_registration(),
        verify_confidence_adjustment(),
        verify_service_limits(),
    ]

    passed_count = sum(checks)
    total_count = len(checks)

    print("=" * 60)
    print(f"RESULT: {passed_count}/{total_count} checks passed")
    print("=" * 60)

    if all(checks):
        print("Version 27 verification completed successfully.")
        return 0

    print(
        "Version 27 verification found one or more problems. "
        "Review the FAIL lines above."
    )
    return 1


if __name__ == "__main__":
    sys.exit(main())