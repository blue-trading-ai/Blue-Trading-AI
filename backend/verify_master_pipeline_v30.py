"""
Blue-Trading-AI
Version 30
verify_master_pipeline_v30.py

Place in the backend root beside main.py, then run:

    python verify_master_pipeline_v30.py

This verifies that the real master signal pipeline:
- Reports safety version 30
- Applies the Version 30 confidence guardrail
- Preserves the 80% minimum-confidence rule
- Preserves the minimum 3 confirmations rule
- Preserves the minimum 1.5 Risk:Reward rule
- Returns analysis-only output
"""

from __future__ import annotations

import sys
from typing import Any, Dict

from app.services.master_signal_pipeline_service import (
    evaluate_master_signal_pipeline,
)


def approved_engine(
    decision: str,
    score_name: str,
    score: float,
) -> Dict[str, Any]:
    return {
        "decision": decision,
        "signal_approved": True,
        "approved": True,
        score_name: score,
    }


def build_pipeline_result(
    confidence: float,
) -> Dict[str, Any]:
    direction = "BUY"

    return evaluate_master_signal_pipeline(
        signal_id="V30-PIPELINE-TEST",
        symbol="XAUUSD",
        timeframe="H1",
        market_context={
            "decision": direction,
            "context_approved": True,
            "context_score": 90.0,
            "market_session": "US",
            "high_risk_environment": False,
        },
        institutional_smc={
            "decision": direction,
            "institutional_approved": True,
            "institutional_score": 90.0,
        },
        ai_confluence={
            "decision": direction,
            "signal_approved": True,
            "ai_confluence_score": 90.0,
        },
        multi_timeframe={
            "decision": direction,
            "multi_timeframe_approved": True,
            "alignment_score": 90.0,
            "hierarchy_conflict": False,
        },
        dynamic_confidence={
            "decision": direction,
            "signal_approved": True,
            "dynamic_confidence": confidence,
            "ranking_score": 90.0,
            "confirmation_count": 4,
            "weak_signal_quality": False,
        },
        risk_management={
            "decision": direction,
            "risk_management_approved": True,
            "risk_reward_ratio": 2.0,
        },
        market_structure={
            "decision": direction,
        },
        momentum_analysis={
            "decision": direction,
        },
        pattern_analysis={
            "decision": direction,
        },
        market_regime={
            "decision": direction,
            "market_regime_approved": True,
            "regime_score": 90.0,
            "market_condition": "trending",
            "fake_breakout_detected": False,
            "blocks_signal": False,
        },
        symbol_winrate={
            "confidence_adjustment": 0.0,
        },
        learning_intelligence={
            "confidence_adjustment": 0.0,
            "recommendation": {
                "recommend_wait": False,
                "stronger_confirmation": False,
            },
        },
    )


def print_result(
    name: str,
    passed: bool,
    detail: str = "",
) -> bool:
    label = "PASS" if passed else "FAIL"
    suffix = f" - {detail}" if detail else ""
    print(f"[{label}] {name}{suffix}")
    return passed


def verify_approved_signal() -> bool:
    result = build_pipeline_result(85.0)

    checks = [
        result.get("safety_version") == 30,
        result.get("signal_approved") is True,
        result.get("final_decision") == "BUY",
        result.get("guardrail_passed") is True,
        result.get("guardrail_final_confidence", 0) >= 80.0,
        result.get("analysis_only") is True,
        "confidence_guardrail_v30" in result,
    ]

    return print_result(
        "Approved Version 30 pipeline signal",
        all(checks),
        (
            f"decision={result.get('final_decision')}, "
            f"confidence={result.get('guardrail_final_confidence')}"
        ),
    )


def verify_below_threshold_signal() -> bool:
    result = build_pipeline_result(79.0)

    blocking_reasons = result.get("blocking_reasons", [])

    checks = [
        result.get("signal_approved") is False,
        result.get("final_decision") == "WAIT",
        result.get("guardrail_passed") is False,
        any(
            "Confidence Guardrail rejected" in str(reason)
            for reason in blocking_reasons
        ),
    ]

    return print_result(
        "Below-80 pipeline signal blocked",
        all(checks),
        (
            f"decision={result.get('final_decision')}, "
            f"guardrail_passed={result.get('guardrail_passed')}"
        ),
    )


def verify_safety_rules() -> bool:
    result = build_pipeline_result(85.0)
    rules = result.get("safety_rules", {})
    checks = result.get("safety_checks", {})

    passed = (
        rules.get("minimum_final_confidence") == 80.0
        and rules.get("minimum_confirmations") == 3
        and rules.get("minimum_risk_reward_ratio") == 1.5
        and rules.get(
            "maximum_confidence_guardrail_adjustment"
        ) == 4.0
        and rules.get(
            "confidence_guardrail_minimum_completed_trades"
        ) == 20
        and rules.get(
            "confidence_guardrail_minimum_confidence"
        ) == 80.0
        and rules.get("broker_connection_enabled") is False
        and rules.get("trade_execution_enabled") is False
        and checks.get("confidence_guardrail_passed") is True
    )

    return print_result(
        "Master-pipeline safety rules",
        passed,
        "80 confidence, 3 confirmations, RR 1.5, adjustment +/-4",
    )


def verify_guardrail_output() -> bool:
    result = build_pipeline_result(85.0)
    guardrail = result.get("confidence_guardrail_v30", {})
    adjustments = result.get("confidence_adjustments", {})
    engines = result.get("engine_results", {})

    passed = (
        isinstance(guardrail, dict)
        and guardrail.get(
            "confidence_guardrail_applied"
        ) is True
        and guardrail.get(
            "confidence_guardrail_version"
        ) == 30
        and "confidence_guardrail_v30" in adjustments
        and "confidence_guardrail_v30" in engines
    )

    return print_result(
        "Guardrail output fields",
        passed,
        "Top-level, adjustments and engine result fields present",
    )


def main() -> int:
    print("=" * 68)
    print("BLUE-TRADING-AI MASTER PIPELINE VERSION 30 VERIFICATION")
    print("=" * 68)

    results = [
        verify_approved_signal(),
        verify_below_threshold_signal(),
        verify_safety_rules(),
        verify_guardrail_output(),
    ]

    passed_count = sum(results)
    total_count = len(results)

    print("=" * 68)
    print(f"RESULT: {passed_count}/{total_count} checks passed")
    print("=" * 68)

    if all(results):
        print("Master pipeline Version 30 integration is working.")
        return 0

    print("One or more checks failed. Review the FAIL lines above.")
    return 1


if __name__ == "__main__":
    sys.exit(main())