"""
Blue-Trading-AI
Version 29
test_version_29_api.py

Run this file while the FastAPI server is running:

    python test_version_29_api.py

Default API:
    http://127.0.0.1:8000

This script tests:
- Main API home
- Version 29 learning analytics home
- Learning analytics health
- Full analytics summary
- Symbol analytics
- Session analytics
- Market-condition analytics
- BUY/SELL direction analytics
- Confidence calibration
- Risk:Reward analytics
- Win/loss streak analytics
- Learning health score
- Version 28 persistence health and status
- Version 27 learning health
"""

from __future__ import annotations

import json
import sys
from typing import Any

import requests


BASE_URL = "http://127.0.0.1:8000"
TIMEOUT_SECONDS = 15


TESTS = [
    ("Main API", "GET", "/"),
    (
        "Learning Analytics Home",
        "GET",
        "/learning-analytics/",
    ),
    (
        "Learning Analytics Health",
        "GET",
        "/learning-analytics/health",
    ),
    (
        "Learning Analytics Summary",
        "GET",
        "/learning-analytics/summary",
    ),
    (
        "Symbol Performance",
        "GET",
        "/learning-analytics/symbols",
    ),
    (
        "Session Performance",
        "GET",
        "/learning-analytics/sessions",
    ),
    (
        "Market Condition Performance",
        "GET",
        "/learning-analytics/market-conditions",
    ),
    (
        "Direction Performance",
        "GET",
        "/learning-analytics/directions",
    ),
    (
        "Confidence Calibration",
        "GET",
        "/learning-analytics/confidence-calibration",
    ),
    (
        "Risk Reward Performance",
        "GET",
        "/learning-analytics/risk-reward",
    ),
    (
        "Streak Analysis",
        "GET",
        "/learning-analytics/streaks",
    ),
    (
        "Learning Health Score",
        "GET",
        "/learning-analytics/health-score",
    ),
    (
        "Learning Persistence Health",
        "GET",
        "/learning-persistence/health",
    ),
    (
        "Learning Persistence Status",
        "GET",
        "/learning-persistence/status",
    ),
    (
        "Learning Intelligence Health",
        "GET",
        "/learning-intelligence/health",
    ),
]


def print_separator() -> None:
    print("-" * 72)


def print_json_preview(data: Any) -> None:
    """
    Print a readable response preview without flooding the terminal.
    """

    try:
        formatted = json.dumps(
            data,
            indent=2,
            default=str,
        )
    except TypeError:
        formatted = str(data)

    max_characters = 1800

    if len(formatted) > max_characters:
        formatted = (
            formatted[:max_characters]
            + "\n... response preview shortened ..."
        )

    print(formatted)


def run_test(
    name: str,
    method: str,
    endpoint: str,
) -> bool:
    url = f"{BASE_URL}{endpoint}"

    print_separator()
    print(f"TEST: {name}")
    print(f"{method} {url}")

    try:
        response = requests.request(
            method=method,
            url=url,
            timeout=TIMEOUT_SECONDS,
        )
    except requests.ConnectionError:
        print("[FAIL] Unable to connect to the FastAPI server.")
        print(
            "Start the server first with "
            ".\\start_version_29.ps1"
        )
        return False
    except requests.RequestException as exc:
        print(f"[FAIL] Request error: {exc}")
        return False

    print(f"STATUS: {response.status_code}")

    try:
        body = response.json()
    except ValueError:
        body = response.text

    print_json_preview(body)

    passed = 200 <= response.status_code < 300

    if passed:
        print(f"[PASS] {name}")
    else:
        print(f"[FAIL] {name}")

    return passed


def verify_main_version() -> bool:
    """
    Confirm that the main API reports Version 29.
    """

    try:
        response = requests.get(
            f"{BASE_URL}/",
            timeout=TIMEOUT_SECONDS,
        )
        response.raise_for_status()
        data = response.json()
    except requests.RequestException as exc:
        print(f"[FAIL] Version check request failed: {exc}")
        return False
    except ValueError:
        print("[FAIL] Main API did not return JSON.")
        return False

    version = str(data.get("version", ""))
    safety_version = data.get("safety_version")

    passed = (
        version.startswith("29")
        and safety_version == 29
    )

    print_separator()
    print("VERSION CHECK")
    print(f"version={version}")
    print(f"safety_version={safety_version}")

    if passed:
        print("[PASS] Main API reports Version 29.")
    else:
        print(
            "[FAIL] Main API is not reporting Version 29."
        )

    return passed


def verify_session_names() -> bool:
    """
    Confirm that Asian, European and US sessions exist.
    """

    try:
        response = requests.get(
            f"{BASE_URL}/learning-analytics/sessions",
            timeout=TIMEOUT_SECONDS,
        )
        response.raise_for_status()
        payload = response.json()
    except requests.RequestException as exc:
        print(f"[FAIL] Session check failed: {exc}")
        return False
    except ValueError:
        print("[FAIL] Session endpoint did not return JSON.")
        return False

    data = payload.get("data", {})
    required = {"asian", "european", "us"}
    found = set(data)

    passed = required.issubset(found)

    print_separator()
    print("SESSION COVERAGE CHECK")
    print(f"Found sessions: {sorted(found)}")

    if passed:
        print(
            "[PASS] Asian, European and US sessions exist."
        )
    else:
        print(
            f"[FAIL] Missing sessions: "
            f"{sorted(required - found)}"
        )

    return passed


def verify_v29_safety() -> bool:
    """
    Confirm Version 29 safety settings from the home endpoint.
    """

    try:
        response = requests.get(
            f"{BASE_URL}/learning-analytics/",
            timeout=TIMEOUT_SECONDS,
        )
        response.raise_for_status()
        data = response.json()
    except requests.RequestException as exc:
        print(f"[FAIL] Safety check failed: {exc}")
        return False
    except ValueError:
        print(
            "[FAIL] Analytics home did not return JSON."
        )
        return False

    passed = (
        data.get("minimum_completed_trades") == 20
        and data.get(
            "maximum_confidence_adjustment"
        ) == 4
        and data.get(
            "timeframe_performance_enabled"
        ) is False
        and data.get(
            "strategy_optimization_enabled"
        ) is False
        and data.get(
            "strategy_ranking_enabled"
        ) is False
        and data.get("analysis_only") is True
        and data.get(
            "broker_connection_enabled"
        ) is False
        and data.get(
            "trade_execution_enabled"
        ) is False
    )

    print_separator()
    print("VERSION 29 SAFETY CHECK")
    print(
        "Minimum completed trades:",
        data.get("minimum_completed_trades"),
    )
    print(
        "Maximum confidence adjustment:",
        data.get("maximum_confidence_adjustment"),
    )
    print(
        "Timeframe performance:",
        data.get("timeframe_performance_enabled"),
    )
    print(
        "Strategy optimization:",
        data.get("strategy_optimization_enabled"),
    )
    print(
        "Strategy ranking:",
        data.get("strategy_ranking_enabled"),
    )
    print(
        "Analysis only:",
        data.get("analysis_only"),
    )

    if passed:
        print("[PASS] Version 29 safety settings are correct.")
    else:
        print("[FAIL] One or more safety settings are incorrect.")

    return passed


def main() -> int:
    print("=" * 72)
    print("BLUE-TRADING-AI VERSION 29 API TEST")
    print("=" * 72)
    print(f"API: {BASE_URL}")

    results = []

    for name, method, endpoint in TESTS:
        results.append(
            run_test(name, method, endpoint)
        )

    results.append(verify_main_version())
    results.append(verify_session_names())
    results.append(verify_v29_safety())

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
            "Version 29 API testing completed successfully."
        )
        return 0

    print(
        "One or more API tests failed. "
        "Review the FAIL messages above."
    )
    return 1


if __name__ == "__main__":
    sys.exit(main())

