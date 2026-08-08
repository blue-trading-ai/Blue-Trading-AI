"""
Blue-Trading-AI
Version 30
test_version_30_api.py

Run while the FastAPI server is running:

    python test_version_30_api.py

Default API:
    http://127.0.0.1:8000
"""

from __future__ import annotations

import json
import sys
from typing import Any

import requests


BASE_URL = "http://127.0.0.1:8000"
TIMEOUT_SECONDS = 15


def print_separator() -> None:
    print("-" * 72)


def print_preview(data: Any) -> None:
    try:
        formatted = json.dumps(data, indent=2, default=str)
    except TypeError:
        formatted = str(data)

    if len(formatted) > 1800:
        formatted = (
            formatted[:1800]
            + "\n... response preview shortened ..."
        )

    print(formatted)


def request_json(
    method: str,
    endpoint: str,
    payload: dict[str, Any] | None = None,
) -> tuple[bool, Any, int]:
    url = f"{BASE_URL}{endpoint}"

    try:
        response = requests.request(
            method=method,
            url=url,
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


def run_basic_test(
    name: str,
    method: str,
    endpoint: str,
    payload: dict[str, Any] | None = None,
) -> bool:
    print_separator()
    print(f"TEST: {name}")
    print(f"{method} {BASE_URL}{endpoint}")

    passed, body, status_code = request_json(
        method,
        endpoint,
        payload,
    )

    print(f"STATUS: {status_code}")
    print_preview(body)

    print(f"[{'PASS' if passed else 'FAIL'}] {name}")
    return passed


def verify_main_version() -> bool:
    passed, body, _ = request_json("GET", "/")

    version = str(body.get("version", "")) if isinstance(body, dict) else ""
    safety_version = body.get("safety_version") if isinstance(body, dict) else None

    result = (
        passed
        and version.startswith("30")
        and safety_version == 30
    )

    print_separator()
    print("VERSION CHECK")
    print(f"version={version}")
    print(f"safety_version={safety_version}")
    print(f"[{'PASS' if result else 'FAIL'}] Version 30 active")

    return result


def verify_rules() -> bool:
    passed, body, _ = request_json(
        "GET",
        "/confidence-guardrail/rules",
    )

    data = body.get("data", {}) if isinstance(body, dict) else {}

    result = (
        passed
        and data.get("minimum_completed_trades") == 20
        and data.get("maximum_confidence_adjustment") == 4.0
        and data.get("minimum_signal_confidence") == 80.0
        and data.get("timeframe_performance_enabled") is False
        and data.get("strategy_optimization_enabled") is False
        and data.get("strategy_ranking_enabled") is False
        and data.get("analysis_only") is True
    )

    print_separator()
    print("RULES CHECK")
    print_preview(data)
    print(f"[{'PASS' if result else 'FAIL'}] Guardrail rules")

    return result


def verify_below_threshold() -> bool:
    payload = {
        "base_confidence": 79,
        "symbol": "XAUUSD",
        "market_session": "asian",
        "market_condition": "trending",
        "direction": "BUY",
    }

    passed, body, _ = request_json(
        "POST",
        "/confidence-guardrail/evaluate",
        payload,
    )

    data = body.get("data", {}) if isinstance(body, dict) else {}

    result = (
        passed
        and data.get("trade_allowed") is False
        and data.get("decision") == "NO_TRADE"
    )

    print_separator()
    print("BELOW-80 CHECK")
    print_preview(data)
    print(f"[{'PASS' if result else 'FAIL'}] Below 80 blocked")

    return result


def verify_apply_complete() -> bool:
    payload = {
        "signal": {
            "symbol": "BTCUSD",
            "confidence": 79,
            "direction": "SELL",
            "market_session": "us",
            "market_condition": "breakout",
        }
    }

    passed, body, _ = request_json(
        "POST",
        "/confidence-guardrail/apply-complete",
        payload,
    )

    data = body.get("data", {}) if isinstance(body, dict) else {}

    result = (
        passed
        and data.get("confidence_guardrail_applied") is True
        and data.get("confidence_guardrail_version") == 30
        and data.get("trade_allowed") is False
        and data.get("decision") == "NO_TRADE"
        and data.get("signal_status") == "BLOCKED"
    )

    print_separator()
    print("COMPLETE GUARDRAIL CHECK")
    print_preview(data)
    print(f"[{'PASS' if result else 'FAIL'}] Complete guardrail")

    return result


def verify_pipeline_integration() -> bool:
    payload = {
        "pipeline_result": {
            "status": "success",
            "signal": {
                "symbol": "GBPUSD",
                "confidence": 82,
                "direction": "BUY",
                "market_session": "european",
                "market_condition": "trending",
            },
        }
    }

    passed, body, _ = request_json(
        "POST",
        "/confidence-guardrail/apply-to-pipeline",
        payload,
    )

    data = body.get("data", {}) if isinstance(body, dict) else {}
    nested_signal = data.get("signal", {}) if isinstance(data, dict) else {}

    result = (
        passed
        and data.get("confidence_guardrail_applied") is True
        and data.get("confidence_guardrail_version") == 30
        and nested_signal.get("confidence_guardrail_applied") is True
        and nested_signal.get("trade_allowed") is True
        and "confidence_guardrail_v30" in nested_signal
    )

    print_separator()
    print("PIPELINE INTEGRATION CHECK")
    print_preview(data)
    print(f"[{'PASS' if result else 'FAIL'}] Pipeline integration")

    return result


def verify_integration_status() -> bool:
    passed, body, _ = request_json(
        "GET",
        "/confidence-guardrail/integration-status",
    )

    data = body.get("data", {}) if isinstance(body, dict) else {}

    result = (
        passed
        and data.get("status") == "ready"
        and data.get("version") == 30
        and data.get("pipeline_integration_enabled") is True
        and data.get("original_signal_mutation_enabled") is False
        and data.get("analysis_only") is True
        and data.get("broker_connection_enabled") is False
        and data.get("trade_execution_enabled") is False
    )

    print_separator()
    print("INTEGRATION STATUS CHECK")
    print_preview(data)
    print(f"[{'PASS' if result else 'FAIL'}] Integration status")

    return result


def main() -> int:
    print("=" * 72)
    print("BLUE-TRADING-AI VERSION 30 API TEST")
    print("=" * 72)
    print(f"API: {BASE_URL}")

    results = [
        run_basic_test(
            "Main API",
            "GET",
            "/",
        ),
        run_basic_test(
            "Guardrail Home",
            "GET",
            "/confidence-guardrail/",
        ),
        run_basic_test(
            "Guardrail Health",
            "GET",
            "/confidence-guardrail/health",
        ),
        run_basic_test(
            "Guardrail Rules",
            "GET",
            "/confidence-guardrail/rules",
        ),
        run_basic_test(
            "Integration Status",
            "GET",
            "/confidence-guardrail/integration-status",
        ),
        run_basic_test(
            "Evaluate Guardrail",
            "POST",
            "/confidence-guardrail/evaluate",
            {
                "base_confidence": 85,
                "symbol": "XAUUSD",
                "market_session": "asian",
                "market_condition": "trending",
                "direction": "BUY",
            },
        ),
        run_basic_test(
            "Apply to Signal",
            "POST",
            "/confidence-guardrail/apply-to-signal",
            {
                "signal": {
                    "symbol": "XAUUSD",
                    "confidence": 82,
                    "direction": "BUY",
                    "market_session": "asian",
                    "market_condition": "trending",
                }
            },
        ),
        run_basic_test(
            "Apply Complete",
            "POST",
            "/confidence-guardrail/apply-complete",
            {
                "signal": {
                    "symbol": "BTCUSD",
                    "confidence": 79,
                    "direction": "SELL",
                    "market_session": "us",
                    "market_condition": "breakout",
                }
            },
        ),
        run_basic_test(
            "Apply to Pipeline",
            "POST",
            "/confidence-guardrail/apply-to-pipeline",
            {
                "pipeline_result": {
                    "signal": {
                        "symbol": "GBPUSD",
                        "confidence": 82,
                        "direction": "BUY",
                        "market_session": "european",
                        "market_condition": "trending",
                    }
                }
            },
        ),
        verify_main_version(),
        verify_rules(),
        verify_below_threshold(),
        verify_apply_complete(),
        verify_pipeline_integration(),
        verify_integration_status(),
    ]

    passed_count = sum(results)
    total_count = len(results)

    print_separator()
    print(
        f"FINAL RESULT: {passed_count}/{total_count} tests passed"
    )
    print_separator()

    if all(results):
        print("Version 30 API testing completed successfully.")
        return 0

    print("One or more tests failed. Review the FAIL lines above.")
    return 1


if __name__ == "__main__":
    sys.exit(main())

