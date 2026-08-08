"""
Blue-Trading-AI
Version 30
test_trading_v30_api.py

Run while FastAPI is running:

    python test_trading_v30_api.py

Default API:
    http://127.0.0.1:8000

This script tests:
- Trading API home
- Trading API test endpoint
- Version 30 metadata
- Confidence guardrail flags
- Analysis-only safety
- Live trading signal endpoint response structure

Note:
The live signal test requires your configured market-data provider
to return valid prices and candles for the selected symbol.
"""

from __future__ import annotations

import json
import sys
from typing import Any

import requests


BASE_URL = "http://127.0.0.1:8000"
TIMEOUT_SECONDS = 30
TEST_SYMBOL = "XAUUSD"
TEST_INTERVAL = "1h"


def print_separator() -> None:
    print("-" * 76)


def print_preview(data: Any) -> None:
    try:
        formatted = json.dumps(
            data,
            indent=2,
            default=str,
        )
    except TypeError:
        formatted = str(data)

    if len(formatted) > 2500:
        formatted = (
            formatted[:2500]
            + "\n... response preview shortened ..."
        )

    print(formatted)


def request_json(
    method: str,
    endpoint: str,
) -> tuple[bool, Any, int]:
    try:
        response = requests.request(
            method=method,
            url=f"{BASE_URL}{endpoint}",
            timeout=TIMEOUT_SECONDS,
        )
    except requests.ConnectionError:
        print("[FAIL] Unable to connect to FastAPI.")
        print("Start the backend server first.")
        return False, {}, 0
    except requests.RequestException as exc:
        print(f"[FAIL] Request error: {exc}")
        return False, {}, 0

    try:
        body = response.json()
    except ValueError:
        body = response.text

    return (
        200 <= response.status_code < 300,
        body,
        response.status_code,
    )


def verify_trading_home() -> bool:
    passed, body, status_code = request_json(
        "GET",
        "/trading/",
    )

    print_separator()
    print("TRADING HOME")
    print(f"STATUS: {status_code}")
    print_preview(body)

    result = (
        passed
        and isinstance(body, dict)
        and str(body.get("version", "")).startswith("30")
        and body.get("safety_version") == 30
        and body.get("confidence_guardrail") == "enabled"
        and body.get("analysis_only") is True
        and body.get("broker_connection_enabled") is False
        and body.get("trade_execution_enabled") is False
    )

    print(f"[{'PASS' if result else 'FAIL'}] Trading home")
    return result


def verify_trading_test() -> bool:
    passed, body, status_code = request_json(
        "GET",
        "/trading/test",
    )

    print_separator()
    print("TRADING TEST ENDPOINT")
    print(f"STATUS: {status_code}")
    print_preview(body)

    result = (
        passed
        and isinstance(body, dict)
        and str(body.get("version", "")).startswith("30")
        and body.get("safety_version") == 30
        and body.get("confidence_guardrail") == "enabled"
        and body.get("analysis_only") is True
    )

    print(f"[{'PASS' if result else 'FAIL'}] Trading test")
    return result


def verify_live_signal() -> bool:
    endpoint = (
        f"/trading/signal/{TEST_SYMBOL}"
        f"?interval={TEST_INTERVAL}"
    )

    passed, body, status_code = request_json(
        "GET",
        endpoint,
    )

    print_separator()
    print("LIVE TRADING SIGNAL")
    print(f"GET {BASE_URL}{endpoint}")
    print(f"STATUS: {status_code}")
    print_preview(body)

    if not passed:
        detail = (
            body.get("detail")
            if isinstance(body, dict)
            else body
        )

        print(
            "[WARN] Live signal test could not complete. "
            f"Provider/API detail: {detail}"
        )
        print(
            "[WARN] Static Version 30 route checks may still pass."
        )
        return False

    signal = (
        body.get("signal", {})
        if isinstance(body, dict)
        else {}
    )
    safety = (
        body.get("safety", {})
        if isinstance(body, dict)
        else {}
    )
    history = (
        body.get("signal_history", {})
        if isinstance(body, dict)
        else {}
    )

    result = (
        body.get("safety_version") == 30
        and str(body.get("version", "")).startswith("30")
        and body.get("confidence_guardrail_enabled") is True
        and body.get(
            "timeframe_performance_learning_enabled"
        ) is False
        and isinstance(signal, dict)
        and signal.get("confidence_guardrail_enabled") is True
        and signal.get("analysis_only") is True
        and signal.get("broker_connection_enabled") is False
        and signal.get("trade_execution_enabled") is False
        and safety.get("minimum_confidence") == 80.0
        and safety.get("minimum_confirmations") == 3
        and safety.get(
            "maximum_guardrail_confidence_adjustment"
        ) == 4.0
        and safety.get(
            "minimum_guardrail_completed_trades"
        ) == 20
        and safety.get(
            "minimum_final_guarded_confidence"
        ) == 80.0
        and isinstance(history, dict)
    )

    print(
        f"[{'PASS' if result else 'FAIL'}] "
        "Live Version 30 signal structure"
    )

    return result


def verify_signal_decision_safety() -> bool:
    endpoint = (
        f"/trading/signal/{TEST_SYMBOL}"
        f"?interval={TEST_INTERVAL}"
    )

    passed, body, status_code = request_json(
        "GET",
        endpoint,
    )

    print_separator()
    print("SIGNAL DECISION SAFETY")
    print(f"STATUS: {status_code}")

    if not passed or not isinstance(body, dict):
        print(
            "[FAIL] Unable to inspect the live signal decision."
        )
        return False

    signal = body.get("signal", {})

    if not isinstance(signal, dict):
        print("[FAIL] Signal payload is not a dictionary.")
        return False

    decision = str(
        signal.get(
            "decision",
            signal.get(
                "final_decision",
                signal.get(
                    "direction",
                    signal.get("signal", "NO_TRADE"),
                ),
            ),
        )
        or "NO_TRADE"
    ).upper()

    confidence = float(
        signal.get(
            "confidence",
            signal.get(
                "confidence_score",
                signal.get("final_confidence", 0.0),
            ),
        )
        or 0.0
    )

    trade_allowed = signal.get("trade_allowed")

    safe_decisions = {
        "BUY",
        "SELL",
        "WAIT",
        "NO_TRADE",
        "TRADE_SIGNAL",
    }

    threshold_safe = (
        confidence >= 80.0
        or trade_allowed is False
        or decision in {"WAIT", "NO_TRADE"}
    )

    result = (
        decision in safe_decisions
        and threshold_safe
    )

    print(
        f"Decision={decision}, "
        f"confidence={confidence}, "
        f"trade_allowed={trade_allowed}"
    )
    print(
        f"[{'PASS' if result else 'FAIL'}] "
        "Final decision safety"
    )

    return result


def main() -> int:
    print("=" * 76)
    print("BLUE-TRADING-AI VERSION 30 TRADING API TEST")
    print("=" * 76)
    print(f"API: {BASE_URL}")
    print(f"Symbol: {TEST_SYMBOL}")
    print(f"Interval: {TEST_INTERVAL}")

    results = [
        verify_trading_home(),
        verify_trading_test(),
        verify_live_signal(),
        verify_signal_decision_safety(),
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
            "Version 30 Trading API testing completed "
            "successfully."
        )
        return 0

    print(
        "One or more tests failed. "
        "Review the FAIL or WARN messages above."
    )
    return 1


if __name__ == "__main__":
    sys.exit(main())

