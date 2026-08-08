"""
Blue-Trading-AI
Version 29
verify_version_29.py

Run from the backend folder:

    python verify_version_29.py

This script verifies:
- Version 29 analytics imports
- Learning analytics API routes
- Version 28 persistence compatibility
- Symbol, session, direction, confidence and Risk:Reward analytics
- Learning health score
- Confidence adjustment safety
- Analysis-only safety settings
"""

from __future__ import annotations

import sys

from app.api.learning_analytics import (
    router as learning_analytics_router,
)
from app.services.learning_analytics_service import (
    get_confidence_calibration,
    get_direction_performance,
    get_learning_analytics_summary,
    get_learning_health,
    get_market_condition_performance,
    get_risk_reward_performance,
    get_session_performance,
    get_streak_analysis,
    get_symbol_performance,
)
from app.services.learning_intelligence_integration import (
    get_learning_intelligence_service,
)
from app.services.learning_persistence_service import (
    get_learning_persistence_status,
)


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
            learning_analytics_router is not None,
            get_learning_intelligence_service() is not None,
        ]
    )

    print_result(
        "Version 29 imports",
        passed,
        "Analytics router and learning service loaded",
    )
    return passed


def verify_routes() -> bool:
    paths = {
        route.path
        for route in learning_analytics_router.routes
    }

    required = {
        "/learning-analytics/",
        "/learning-analytics/health",
        "/learning-analytics/summary",
        "/learning-analytics/symbols",
        "/learning-analytics/sessions",
        "/learning-analytics/market-conditions",
        "/learning-analytics/directions",
        "/learning-analytics/confidence-calibration",
        "/learning-analytics/risk-reward",
        "/learning-analytics/streaks",
        "/learning-analytics/health-score",
    }

    missing = required - paths
    passed = not missing

    print_result(
        "Learning analytics API routes",
        passed,
        (
            "All routes registered"
            if passed
            else f"Missing: {sorted(missing)}"
        ),
    )

    return passed


def verify_summary() -> bool:
    summary = get_learning_analytics_summary()

    required_keys = {
        "symbol_performance",
        "session_performance",
        "market_condition_performance",
        "direction_performance",
        "confidence_calibration",
        "risk_reward_performance",
        "streak_analysis",
        "learning_health",
        "rules",
        "safety",
    }

    missing = required_keys - set(summary)
    passed = not missing

    print_result(
        "Analytics summary",
        passed,
        (
            "All analytics sections available"
            if passed
            else f"Missing: {sorted(missing)}"
        ),
    )

    return passed


def verify_session_analytics() -> bool:
    sessions = get_session_performance()

    required_sessions = {
        "asian",
        "european",
        "us",
    }

    passed = required_sessions.issubset(
        set(sessions)
    )

    print_result(
        "Session analytics",
        passed,
        f"Sessions={sorted(sessions)}",
    )

    return passed


def verify_direction_analytics() -> bool:
    directions = get_direction_performance()

    passed = {
        "BUY",
        "SELL",
    }.issubset(set(directions))

    print_result(
        "Direction analytics",
        passed,
        f"Directions={sorted(directions)}",
    )

    return passed


def verify_confidence_calibration() -> bool:
    calibration = get_confidence_calibration()

    expected_bands = {
        "below_75",
        "75_79",
        "80_84",
        "85_89",
        "90_94",
        "95_100",
    }

    passed = expected_bands.issubset(
        set(calibration)
    )

    print_result(
        "Confidence calibration",
        passed,
        f"Bands={sorted(calibration)}",
    )

    return passed


def verify_risk_reward_analytics() -> bool:
    risk_reward = get_risk_reward_performance()

    expected_bands = {
        "below_1",
        "1_1_49",
        "1_5_1_99",
        "2_2_99",
        "3_plus",
    }

    passed = expected_bands.issubset(
        set(risk_reward)
    )

    print_result(
        "Risk:Reward analytics",
        passed,
        f"Bands={sorted(risk_reward)}",
    )

    return passed


def verify_learning_health() -> bool:
    health = get_learning_health()

    score = float(
        health.get("score", 0.0)
    )
    grade = str(
        health.get("grade", "")
    )

    passed = (
        0.0 <= score <= 100.0
        and grade in {"A", "B", "C", "D", "F"}
    )

    print_result(
        "Learning health score",
        passed,
        f"Score={score}, grade={grade}",
    )

    return passed


def verify_streak_analysis() -> bool:
    streaks = get_streak_analysis()

    required = {
        "current_win_streak",
        "current_loss_streak",
        "highest_win_streak",
        "highest_loss_streak",
        "loss_streak_risk_level",
        "recommendation",
    }

    passed = required.issubset(
        set(streaks)
    )

    print_result(
        "Streak analytics",
        passed,
        (
            f"Current loss streak="
            f"{streaks.get('current_loss_streak', 0)}"
        ),
    )

    return passed


def verify_persistence_compatibility() -> bool:
    status = get_learning_persistence_status()

    passed = bool(
        status.get("learning_restored", False)
    )

    print_result(
        "Version 28 persistence compatibility",
        passed,
        (
            f"Restored={status.get('learning_restored')}, "
            f"in-memory={status.get('in_memory_learning_trades')}"
        ),
    )

    return passed


def verify_rules_and_safety() -> bool:
    summary = get_learning_analytics_summary()

    rules = summary.get("rules", {})
    safety = summary.get("safety", {})

    passed = (
        rules.get("minimum_completed_trades") == 20
        and rules.get(
            "maximum_confidence_adjustment"
        ) == 4
        and rules.get(
            "timeframe_performance_enabled"
        ) is False
        and rules.get(
            "strategy_optimization_enabled"
        ) is False
        and rules.get(
            "strategy_ranking_enabled"
        ) is False
        and safety.get("analysis_only") is True
        and safety.get(
            "broker_connection_enabled"
        ) is False
        and safety.get(
            "trade_execution_enabled"
        ) is False
    )

    print_result(
        "Version 29 safety rules",
        passed,
        "20-trade minimum, ±4 adjustment, analysis only",
    )

    return passed


def verify_public_functions() -> bool:
    symbol_data = get_symbol_performance()
    market_data = get_market_condition_performance()

    passed = (
        isinstance(symbol_data, dict)
        and isinstance(market_data, dict)
    )

    print_result(
        "Analytics public functions",
        passed,
        (
            f"Symbols={len(symbol_data)}, "
            f"conditions={len(market_data)}"
        ),
    )

    return passed


def main() -> int:
    print("=" * 60)
    print("BLUE-TRADING-AI VERSION 29 VERIFICATION")
    print("=" * 60)

    checks = [
        verify_imports(),
        verify_routes(),
        verify_summary(),
        verify_session_analytics(),
        verify_direction_analytics(),
        verify_confidence_calibration(),
        verify_risk_reward_analytics(),
        verify_learning_health(),
        verify_streak_analysis(),
        verify_persistence_compatibility(),
        verify_rules_and_safety(),
        verify_public_functions(),
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
            "Version 29 verification completed successfully."
        )
        return 0

    print(
        "Version 29 verification found one or more problems. "
        "Review the FAIL lines above."
    )
    return 1


if __name__ == "__main__":
    sys.exit(main())