"""
Blue-Trading-AI
Version 30
verify_version_30.py

Run from the backend folder:

    python verify_version_30.py

This script verifies:
- Existing Version 1-26 service exports still import
- Version 27-29 learning modules still import
- Version 30 confidence guardrail imports
- Version 30 API routes
- 20 completed-trade minimum
- Maximum confidence adjustment of +/-4
- Minimum signal confidence of 80
- No timeframe learning
- No strategy optimization or ranking
- Analysis-only safety
"""

from __future__ import annotations

import sys

from app.api.confidence_guardrail import (
    router as confidence_guardrail_router,
)

from app.services import (
    evaluate_ai_confluence,
    evaluate_context_aware_decision,
    evaluate_dynamic_confidence,
    evaluate_institutional_smc,
    evaluate_master_signal_pipeline,
    evaluate_multi_timeframe_intelligence,
    evaluate_trade_decision,
    get_dashboard_summary,
    get_performance_analytics,
    get_trade_history,
)

from app.services.confidence_guardrail_service import (
    MAXIMUM_CONFIDENCE_ADJUSTMENT,
    MINIMUM_COMPLETED_TRADES,
    MINIMUM_SIGNAL_CONFIDENCE,
    apply_guardrail_to_signal,
    calculate_guarded_confidence,
    get_confidence_guardrail_rules,
)

from app.services.confidence_guardrail_integration import (
    apply_complete_confidence_guardrail,
    enforce_guardrail_decision,
    get_confidence_guardrail_integration_status,
    integrate_confidence_guardrail,
    integrate_guardrail_into_pipeline_result,
    normalise_signal_for_guardrail,
)

from app.services.learning_analytics_service import (
    get_learning_analytics_summary,
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


def verify_old_service_exports() -> bool:
    exports = [
        get_trade_history,
        get_performance_analytics,
        get_dashboard_summary,
        evaluate_trade_decision,
        evaluate_context_aware_decision,
        evaluate_institutional_smc,
        evaluate_ai_confluence,
        evaluate_multi_timeframe_intelligence,
        evaluate_dynamic_confidence,
        evaluate_master_signal_pipeline,
    ]

    passed = all(callable(item) for item in exports)

    print_result(
        "Version 1-26 service exports",
        passed,
        f"Loaded {len(exports)} representative exports",
    )

    return passed


def verify_learning_versions() -> bool:
    service = get_learning_intelligence_service()
    persistence = get_learning_persistence_status()
    analytics = get_learning_analytics_summary()

    passed = (
        service is not None
        and isinstance(persistence, dict)
        and isinstance(analytics, dict)
    )

    print_result(
        "Version 27-29 compatibility",
        passed,
        "Learning, persistence and analytics loaded",
    )

    return passed


def verify_v30_imports() -> bool:
    items = [
        calculate_guarded_confidence,
        apply_guardrail_to_signal,
        get_confidence_guardrail_rules,
        confidence_guardrail_router,
    ]

    passed = all(item is not None for item in items)

    print_result(
        "Version 30 imports",
        passed,
        "Guardrail service and API router loaded",
    )

    return passed


def verify_routes() -> bool:
    paths = {
        route.path
        for route in confidence_guardrail_router.routes
    }

    required = {
        "/confidence-guardrail/",
        "/confidence-guardrail/health",
        "/confidence-guardrail/rules",
        "/confidence-guardrail/evaluate",
        "/confidence-guardrail/apply-to-signal",
    }

    missing = required - paths
    passed = not missing

    print_result(
        "Version 30 API routes",
        passed,
        (
            "All routes registered"
            if passed
            else f"Missing: {sorted(missing)}"
        ),
    )

    return passed


def verify_constants() -> bool:
    passed = (
        MINIMUM_COMPLETED_TRADES == 20
        and MAXIMUM_CONFIDENCE_ADJUSTMENT == 4.0
        and MINIMUM_SIGNAL_CONFIDENCE == 80.0
    )

    print_result(
        "Version 30 constants",
        passed,
        (
            f"minimum trades={MINIMUM_COMPLETED_TRADES}, "
            f"max adjustment={MAXIMUM_CONFIDENCE_ADJUSTMENT}, "
            f"minimum confidence={MINIMUM_SIGNAL_CONFIDENCE}"
        ),
    )

    return passed


def verify_no_trade_below_threshold() -> bool:
    result = calculate_guarded_confidence(
        base_confidence=79.0,
        symbol="XAUUSD",
        market_session="asian",
        market_condition="trending",
        direction="BUY",
        symbol_performance={},
        session_performance={},
        market_condition_performance={},
        direction_performance={},
    )

    passed = (
        result.adjusted_confidence == 79.0
        and result.trade_allowed is False
        and result.decision == "NO_TRADE"
    )

    print_result(
        "Below-80 confidence block",
        passed,
        (
            f"adjusted={result.adjusted_confidence}, "
            f"decision={result.decision}"
        ),
    )

    return passed


def verify_trade_at_threshold() -> bool:
    result = calculate_guarded_confidence(
        base_confidence=80.0,
        symbol="BTCUSD",
        market_session="us",
        market_condition="breakout",
        direction="SELL",
        symbol_performance={},
        session_performance={},
        market_condition_performance={},
        direction_performance={},
    )

    passed = (
        result.adjusted_confidence == 80.0
        and result.trade_allowed is True
        and result.decision == "TRADE_SIGNAL"
    )

    print_result(
        "80-confidence approval",
        passed,
        (
            f"adjusted={result.adjusted_confidence}, "
            f"decision={result.decision}"
        ),
    )

    return passed


def verify_minimum_trade_requirement() -> bool:
    result = calculate_guarded_confidence(
        base_confidence=85.0,
        symbol="GBPUSD",
        market_session="european",
        market_condition="trending",
        direction="BUY",
        symbol_performance={
            "GBPUSD": {
                "completed_trades": 19,
                "win_rate": 90.0,
            }
        },
        session_performance={
            "european": {
                "completed_trades": 19,
                "win_rate": 90.0,
            }
        },
        market_condition_performance={
            "trending": {
                "completed_trades": 19,
                "win_rate": 90.0,
            }
        },
        direction_performance={
            "BUY": {
                "completed_trades": 19,
                "win_rate": 90.0,
            }
        },
    )

    passed = (
        result.applied_adjustment == 0.0
        and result.adjusted_confidence == 85.0
        and all(
            factor.eligible is False
            for factor in result.factors
        )
    )

    print_result(
        "20-trade minimum enforcement",
        passed,
        f"adjustment={result.applied_adjustment}",
    )

    return passed


def verify_positive_adjustment_cap() -> bool:
    strong_record = {
        "completed_trades": 50,
        "win_rate": 80.0,
    }

    result = calculate_guarded_confidence(
        base_confidence=90.0,
        symbol="XAUUSD",
        market_session="us",
        market_condition="breakout",
        direction="BUY",
        symbol_performance={
            "XAUUSD": strong_record,
        },
        session_performance={
            "us": strong_record,
        },
        market_condition_performance={
            "breakout": strong_record,
        },
        direction_performance={
            "BUY": strong_record,
        },
    )

    passed = (
        result.applied_adjustment <= 4.0
        and result.adjusted_confidence <= 100.0
    )

    print_result(
        "Positive confidence cap",
        passed,
        (
            f"raw={result.raw_adjustment}, "
            f"applied={result.applied_adjustment}, "
            f"adjusted={result.adjusted_confidence}"
        ),
    )

    return passed


def verify_negative_adjustment_cap() -> bool:
    weak_record = {
        "completed_trades": 50,
        "win_rate": 20.0,
    }

    result = calculate_guarded_confidence(
        base_confidence=85.0,
        symbol="XAUUSD",
        market_session="asian",
        market_condition="ranging",
        direction="SELL",
        symbol_performance={
            "XAUUSD": weak_record,
        },
        session_performance={
            "asian": weak_record,
        },
        market_condition_performance={
            "ranging": weak_record,
        },
        direction_performance={
            "SELL": weak_record,
        },
    )

    passed = (
        result.applied_adjustment >= -4.0
        and result.adjusted_confidence >= 0.0
    )

    print_result(
        "Negative confidence cap",
        passed,
        (
            f"raw={result.raw_adjustment}, "
            f"applied={result.applied_adjustment}, "
            f"adjusted={result.adjusted_confidence}"
        ),
    )

    return passed


def verify_signal_application() -> bool:
    signal = {
        "symbol": "XAUUSD",
        "market_session": "asian",
        "market_condition": "trending",
        "direction": "BUY",
        "confidence": 82.0,
    }

    updated = apply_guardrail_to_signal(
        signal=signal,
        analytics_summary={
            "symbol_performance": {},
            "session_performance": {},
            "market_condition_performance": {},
            "direction_performance": {},
        },
    )

    passed = (
        signal["confidence"] == 82.0
        and updated["confidence"] == 82.0
        and "confidence_guardrail_v30" in updated
        and updated["trade_allowed"] is True
    )

    print_result(
        "Signal guardrail integration",
        passed,
        "Original signal preserved and guarded copy returned",
    )

    return passed


def verify_rules_and_safety() -> bool:
    rules = get_confidence_guardrail_rules()

    passed = (
        rules.get("minimum_completed_trades") == 20
        and rules.get(
            "maximum_confidence_adjustment"
        ) == 4.0
        and rules.get(
            "minimum_signal_confidence"
        ) == 80.0
        and rules.get(
            "timeframe_performance_enabled"
        ) is False
        and rules.get(
            "strategy_optimization_enabled"
        ) is False
        and rules.get(
            "strategy_ranking_enabled"
        ) is False
        and rules.get("analysis_only") is True
        and rules.get(
            "broker_connection_enabled"
        ) is False
        and rules.get(
            "trade_execution_enabled"
        ) is False
    )

    print_result(
        "Version 30 safety rules",
        passed,
        "Analysis-only guardrails verified",
    )

    return passed



def verify_guardrail_integration_imports() -> bool:
    functions = [
        apply_complete_confidence_guardrail,
        enforce_guardrail_decision,
        get_confidence_guardrail_integration_status,
        integrate_confidence_guardrail,
        integrate_guardrail_into_pipeline_result,
        normalise_signal_for_guardrail,
    ]

    passed = all(callable(item) for item in functions)

    print_result(
        "Version 30 integration imports",
        passed,
        f"Loaded {len(functions)} integration functions",
    )

    return passed


def verify_signal_normalisation() -> bool:
    original = {
        "symbol": "XAUUSD",
        "confidence_score": 84.0,
        "signal": "BUY",
        "session": "asian",
        "market_regime": "trending",
    }

    normalised = normalise_signal_for_guardrail(original)

    passed = (
        normalised.get("confidence") == 84.0
        and normalised.get("direction") == "BUY"
        and normalised.get("market_session") == "asian"
        and normalised.get("market_condition") == "trending"
        and "confidence" not in original
    )

    print_result(
        "Signal field normalisation",
        passed,
        "Aliases mapped without changing original signal",
    )

    return passed


def verify_complete_guardrail_integration() -> bool:
    original = {
        "symbol": "BTCUSD",
        "confidence": 79.0,
        "direction": "SELL",
        "market_session": "us",
        "market_condition": "breakout",
    }

    guarded = apply_complete_confidence_guardrail(original)

    passed = (
        original.get("confidence") == 79.0
        and guarded.get("confidence_guardrail_applied") is True
        and guarded.get("confidence_guardrail_version") == 30
        and guarded.get("trade_allowed") is False
        and guarded.get("decision") == "NO_TRADE"
        and guarded.get("signal_status") == "BLOCKED"
    )

    print_result(
        "Complete guardrail integration",
        passed,
        (
            f"decision={guarded.get('decision')}, "
            f"status={guarded.get('signal_status')}"
        ),
    )

    return passed


def verify_nested_pipeline_integration() -> bool:
    pipeline_result = {
        "status": "success",
        "signal": {
            "symbol": "GBPUSD",
            "confidence": 82.0,
            "direction": "BUY",
            "market_session": "european",
            "market_condition": "trending",
        },
    }

    integrated = integrate_guardrail_into_pipeline_result(
        pipeline_result
    )

    nested_signal = integrated.get("signal", {})

    passed = (
        integrated.get("confidence_guardrail_applied") is True
        and integrated.get("confidence_guardrail_version") == 30
        and nested_signal.get(
            "confidence_guardrail_applied"
        ) is True
        and nested_signal.get("trade_allowed") is True
        and "confidence_guardrail_v30" in nested_signal
        and "confidence_guardrail_applied" not in pipeline_result
    )

    print_result(
        "Nested pipeline integration",
        passed,
        "Nested signal guarded and source result preserved",
    )

    return passed


def verify_integration_status() -> bool:
    integration_status = (
        get_confidence_guardrail_integration_status()
    )

    passed = (
        integration_status.get("status") == "ready"
        and integration_status.get("version") == 30
        and integration_status.get(
            "pipeline_integration_enabled"
        ) is True
        and integration_status.get(
            "original_signal_mutation_enabled"
        ) is False
        and integration_status.get("analysis_only") is True
        and integration_status.get(
            "broker_connection_enabled"
        ) is False
        and integration_status.get(
            "trade_execution_enabled"
        ) is False
    )

    print_result(
        "Guardrail integration status",
        passed,
        "Pipeline integration is ready and analysis-only",
    )

    return passed

def main() -> int:
    print("=" * 64)
    print("BLUE-TRADING-AI VERSION 30 VERIFICATION")
    print("=" * 64)

    checks = [
        verify_old_service_exports(),
        verify_learning_versions(),
        verify_v30_imports(),
        verify_routes(),
        verify_constants(),
        verify_no_trade_below_threshold(),
        verify_trade_at_threshold(),
        verify_minimum_trade_requirement(),
        verify_positive_adjustment_cap(),
        verify_negative_adjustment_cap(),
        verify_signal_application(),
        verify_guardrail_integration_imports(),
        verify_signal_normalisation(),
        verify_complete_guardrail_integration(),
        verify_nested_pipeline_integration(),
        verify_integration_status(),
        verify_rules_and_safety(),
    ]

    passed_count = sum(checks)
    total_count = len(checks)

    print("=" * 64)
    print(
        f"RESULT: {passed_count}/{total_count} checks passed"
    )
    print("=" * 64)

    if all(checks):
        print(
            "Version 30 verification completed successfully."
        )
        return 0

    print(
        "Version 30 verification found one or more problems. "
        "Review the FAIL lines above."
    )
    return 1


if __name__ == "__main__":
    sys.exit(main())