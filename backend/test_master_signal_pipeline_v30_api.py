"""
Blue-Trading-AI
Version 30
test_master_signal_pipeline_v30_api.py

Run this while FastAPI is running:

    python test_master_signal_pipeline_v30_api.py

Default API:
    http://127.0.0.1:8000
"""

from __future__ import annotations

import json
import sys
from typing import Any, Dict

import requests


BASE_URL = "http://127.0.0.1:8000"
TIMEOUT_SECONDS = 20


def print_separator() -> None:
    print("-" * 72)


def print_preview(data: Any) -> None:
    try:
        formatted = json.dumps(
            data,
            indent=2,
            default=str,
        )
    except TypeError:
        formatted = str(data)

    if len(formatted) > 2200:
        formatted = (
            formatted[:2200]
            + "\n... response preview shortened ..."
        )

    print(formatted)


def request_json(
    method: str,
    endpoint: str,
    payload: Dict[str, Any] | None = None,
) -> tuple[bool, Any, int]:
    try:
        response = requests.request(
            method=method,
            url=f"{BASE_URL}{endpoint}",
            json=payload,
            timeout=TIMEOUT_SECONDS,
        )
    except requests.ConnectionError:
        print("[FAIL] Unable to connect to FastAPI.")
        print("Start the server first.")
        return False, {}, 0
    except requests.RequestException as exc:
        print(f"[FAIL] Request error: {exc}")
        return False, {}, 0

    try:
        body = response.json()
    except ValueError:
        body = response.text

    passed = 200 <= response.status_code < 300
    return passed, body, response.status_code


def build_payload(confidence: float) -> Dict[str, Any]:
    direction = "BUY"

    return {
        "signal_id": "V30-API-TEST-001",
        "symbol": "XAUUSD",
        "timeframe": "H1",
        "market_context": {
            "decision": direction,
            "context_approved": True,
            "context_score": 90.0,
            "market_session": "US",
            "high_risk_environment": False,
        },
        "institutional_smc": {
            "decision": direction,
            "institutional_approved": True,
            "institutional_score": 90.0,
        },
        "ai_confluence": {
            "decision": direction,
            "signal_approved": True,
            "ai_confluence_score": 90.0,
        },
        "multi_timeframe": {
            "decision": direction,
            "multi_timeframe_approved": True,
            "alignment_score": 90.0,
            "hierarchy_conflict": False,
        },
        "dynamic_confidence": {
            "decision": direction,
            "signal_approved": True,
            "dynamic_confidence": confidence,
            "ranking_score": 90.0,
            "confirmation_count": 4,
            "weak_signal_quality": False,
        },
        "risk_management": {
            "decision": direction,
            "risk_management_approved": True,
            "risk_reward_ratio": 2.0,
        },
        "market_structure": {
            "decision": direction,
        },
        "momentum_analysis": {
            "decision": direction,
        },
        "pattern_analysis": {
            "decision": direction,
        },
        "market_regime": {
            "decision": direction,
            "market_regime_approved": True,
            "regime_score": 90.0,
            "market_condition": "trending",
            "fake_breakout_detected": False,
            "blocks_signal": False,
        },
        "symbol_winrate": {
            "confidence_adjustment": 0.0,
        },
        "learning_intelligence": {
            "confidence_adjustment": 0.0,
            "recommendation": {
                "recommend_wait": False,
                "stronger_confirmation": False,
            },
        },
    }


def verify_home() -> bool:
    passed, body, status_code = request_json(
        "GET",
        "/master-signal/",
    )

    print_separator()
    print("MASTER SIGNAL HOME")
    print(f"STATUS: {status_code}")
    print_preview(body)

    result = (
        passed
        and isinstance(body, dict)
        and body.get("safety_version") == 30
        and body.get("confidence_guardrail_enabled") is True
        and body.get("minimum_final_confidence") == 80.0
        and body.get("maximum_guardrail_adjustment") == 4.0
        and body.get("analysis_only") is True
    )

    print(f"[{'PASS' if result else 'FAIL'}] Master signal home")
    return result


def verify_test_endpoint() -> bool:
    passed, body, status_code = request_json(
        "GET",
        "/master-signal/test",
    )

    print_separator()
    print("MASTER SIGNAL TEST ENDPOINT")
    print(f"STATUS: {status_code}")
    print_preview(body)

    features = body.get("features", []) if isinstance(body, dict) else []

    result = (
        passed
        and body.get("safety_version") == 30
        and "confidence_guardrail_v30" in features
        and body.get("minimum_confirmations") == 3
        and body.get("minimum_risk_reward_ratio") == 1.5
        and body.get(
            "minimum_completed_trades_for_guardrail"
        ) == 20
        and body.get("maximum_guardrail_adjustment") == 4.0
    )

    print(f"[{'PASS' if result else 'FAIL'}] Master signal test")
    return result


def verify_approved_signal() -> bool:
    passed, body, status_code = request_json(
        "POST",
        "/master-signal/evaluate",
        build_payload(85.0),
    )

    print_separator()
    print("APPROVED SIGNAL TEST")
    print(f"STATUS: {status_code}")
    print_preview(body)

    result = (
        passed
        and isinstance(body, dict)
        and body.get("safety_version") == 30
        and body.get("signal_approved") is True
        and body.get("final_decision") == "BUY"
        and body.get("guardrail_passed") is True
        and body.get("guardrail_final_confidence", 0.0) >= 80.0
        and body.get("analysis_only") is True
        and "confidence_guardrail_v30" in body
    )

    print(f"[{'PASS' if result else 'FAIL'}] Approved signal")
    return result


def verify_below_threshold_signal() -> bool:
    passed, body, status_code = request_json(
        "POST",
        "/master-signal/evaluate",
        build_payload(79.0),
    )

    print_separator()
    print("BELOW-80 SIGNAL TEST")
    print(f"STATUS: {status_code}")
    print_preview(body)

    blocking_reasons = (
        body.get("blocking_reasons", [])
        if isinstance(body, dict)
        else []
    )

    result = (
        passed
        and body.get("signal_approved") is False
        and body.get("final_decision") == "WAIT"
        and body.get("guardrail_passed") is False
        and any(
            "Confidence Guardrail rejected" in str(reason)
            for reason in blocking_reasons
        )
    )

    print(f"[{'PASS' if result else 'FAIL'}] Below-80 blocked")
    return result


def verify_guardrail_fields() -> bool:
    passed, body, status_code = request_json(
        "POST",
        "/master-signal/evaluate",
        build_payload(85.0),
    )

    print_separator()
    print("GUARDRAIL OUTPUT FIELDS")
    print(f"STATUS: {status_code}")

    adjustments = (
        body.get("confidence_adjustments", {})
        if isinstance(body, dict)
        else {}
    )
    checks = (
        body.get("safety_checks", {})
        if isinstance(body, dict)
        else {}
    )
    rules = (
        body.get("safety_rules", {})
        if isinstance(body, dict)
        else {}
    )
    engines = (
        body.get("engine_results", {})
        if isinstance(body, dict)
        else {}
    )

    result = (
        passed
        and "confidence_guardrail_v30" in adjustments
        and checks.get("confidence_guardrail_passed") is True
        and checks.get(
            "confidence_guardrail_adjustment_within_limit"
        ) is True
        and rules.get(
            "maximum_confidence_guardrail_adjustment"
        ) == 4.0
        and rules.get(
            "confidence_guardrail_minimum_completed_trades"
        ) == 20
        and rules.get(
            "confidence_guardrail_minimum_confidence"
        ) == 80.0
        and "confidence_guardrail_v30" in engines
    )

    print_preview(
        {
            "confidence_adjustments": adjustments,
            "safety_checks": checks,
            "safety_rules": rules,
        }
    )
    print(f"[{'PASS' if result else 'FAIL'}] Guardrail fields")
    return result


def main() -> int:
    print("=" * 72)
    print("BLUE-TRADING-AI MASTER SIGNAL PIPELINE V30 API TEST")
    print("=" * 72)
    print(f"API: {BASE_URL}")

    results = [
        verify_home(),
        verify_test_endpoint(),
        verify_approved_signal(),
        verify_below_threshold_signal(),
        verify_guardrail_fields(),
    ]

    passed_count = sum(results)
    total_count = len(results)

    print_separator()
    print(
        f"FINAL RESULT: {passed_count}/{total_count} "
        "tests passed"
    )
    print_separator()

    if all(results):
        print(
            "Master Signal Pipeline Version 30 API "
            "testing completed successfully."
        )
        return 0

    print(
        "One or more tests failed. Review the FAIL lines above."
    )
    return 1


if __name__ == "__main__":
    sys.exit(main())

