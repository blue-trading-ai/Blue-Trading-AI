"""
Blue-Trading-AI
Version 49
test_version_28_api.py

Run this after the FastAPI server is running:

    python test_version_28_api.py

Or run with pytest:

    python -m pytest test_version_28_api.py -q

The script tests:

- Main API home
- Learning intelligence health
- Learning persistence health
- Learning persistence status
- Learning confidence evaluation
- OWNER protection on manual persistence synchronization
"""

from __future__ import annotations

import json
import os
import sys
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


BASE_URL = os.getenv(
    "API_BASE_URL",
    "http://127.0.0.1:8000",
).rstrip("/")

EXPECTED_API_VERSION = "49.0.0"
TIMEOUT_SECONDS = 15


def request_json(
    method: str,
    path: str,
    payload: dict[str, Any] | None = None,
) -> tuple[int, dict[str, Any]]:
    """Send one HTTP request and return its status code and JSON body."""

    body = None
    headers = {
        "Accept": "application/json",
    }

    if payload is not None:
        body = json.dumps(
            payload
        ).encode(
            "utf-8"
        )
        headers[
            "Content-Type"
        ] = "application/json"

    request = Request(
        url=f"{BASE_URL}{path}",
        data=body,
        headers=headers,
        method=method.upper(),
    )

    try:
        with urlopen(
            request,
            timeout=TIMEOUT_SECONDS,
        ) as response:
            raw = (
                response.read()
                .decode("utf-8")
            )
            parsed = (
                json.loads(raw)
                if raw
                else {}
            )

            if not isinstance(
                parsed,
                dict,
            ):
                parsed = {
                    "data": parsed,
                }

            return (
                response.status,
                parsed,
            )

    except HTTPError as exc:
        raw = (
            exc.read()
            .decode(
                "utf-8"
            )
        )

        try:
            parsed = (
                json.loads(raw)
                if raw
                else {}
            )
        except json.JSONDecodeError:
            parsed = {
                "raw_response": raw,
            }

        if not isinstance(
            parsed,
            dict,
        ):
            parsed = {
                "data": parsed,
            }

        return (
            exc.code,
            parsed,
        )


def print_result(
    name: str,
    passed: bool,
    detail: str,
) -> None:
    status_text = (
        "PASS"
        if passed
        else "FAIL"
    )

    print(
        f"[{status_text}] "
        f"{name} - {detail}"
    )


def check_home() -> bool:
    status_code, data = request_json(
        "GET",
        "/",
    )

    version = str(
        data.get(
            "version",
            "",
        )
    )

    passed = (
        status_code == 200
        and version
        == EXPECTED_API_VERSION
    )

    print_result(
        "Main API",
        passed,
        (
            f"HTTP={status_code}, "
            f"version={version}, "
            f"expected={EXPECTED_API_VERSION}"
        ),
    )

    return passed


def test_home() -> None:
    assert check_home() is True


def check_learning_health() -> bool:
    status_code, data = request_json(
        "GET",
        "/learning-intelligence/health",
    )

    passed = (
        status_code == 200
        and data.get(
            "status"
        ) == "healthy"
    )

    print_result(
        "Learning intelligence health",
        passed,
        f"HTTP={status_code}",
    )

    return passed


def test_learning_health() -> None:
    assert (
        check_learning_health()
        is True
    )


def check_persistence_health() -> bool:
    status_code, data = request_json(
        "GET",
        "/learning-persistence/health",
    )

    passed = (
        status_code == 200
        and data.get(
            "status"
        ) == "healthy"
        and data.get(
            "database_restore_ready"
        )
        is True
    )

    print_result(
        "Learning persistence health",
        passed,
        f"HTTP={status_code}",
    )

    return passed


def test_persistence_health() -> None:
    assert (
        check_persistence_health()
        is True
    )


def check_persistence_status() -> bool:
    status_code, data = request_json(
        "GET",
        "/learning-persistence/status",
    )

    eligible = data.get(
        "database_learning_eligible_trades",
        0,
    )

    in_memory = data.get(
        "in_memory_learning_trades",
        0,
    )

    restored = data.get(
        "learning_restored",
        False,
    )

    passed = (
        status_code == 200
        and restored is True
        and eligible == in_memory
    )

    print_result(
        "Persistence synchronization",
        passed,
        (
            f"HTTP={status_code}, "
            f"eligible={eligible}, "
            f"in-memory={in_memory}, "
            f"restored={restored}"
        ),
    )

    return passed


def test_persistence_status() -> None:
    assert (
        check_persistence_status()
        is True
    )


def check_learning_evaluation() -> bool:
    status_code, data = request_json(
        "POST",
        "/learning-intelligence/evaluate",
        {
            "symbol": "XAUUSD",
            "session": "asian",
            "market_condition": "trending",
            "direction": "BUY",
            "current_confidence": 85.0,
        },
    )

    response_data = data.get(
        "data",
        {},
    )

    if not isinstance(
        response_data,
        dict,
    ):
        response_data = {}

    adjustment = float(
        response_data.get(
            "confidence_adjustment",
            0.0,
        )
    )

    adjusted_confidence = float(
        response_data.get(
            "adjusted_confidence",
            0.0,
        )
    )

    passed = (
        status_code == 200
        and -4.0
        <= adjustment
        <= 4.0
        and 0.0
        <= adjusted_confidence
        <= 100.0
    )

    print_result(
        "Learning confidence safety",
        passed,
        (
            f"HTTP={status_code}, "
            f"adjustment={adjustment}, "
            f"adjusted={adjusted_confidence}"
        ),
    )

    return passed


def test_learning_evaluation() -> None:
    assert (
        check_learning_evaluation()
        is True
    )


def check_manual_sync() -> bool:
    """
    Verify that the destructive manual sync endpoint is not public.

    No bearer token is intentionally supplied here. A correctly secured
    endpoint must reject this request with HTTP 401.
    """

    status_code, data = request_json(
        "POST",
        "/learning-persistence/sync",
    )

    detail = data.get(
        "detail"
    )

    passed = (
        status_code == 401
    )

    print_result(
        "Manual persistence sync OWNER protection",
        passed,
        (
            f"HTTP={status_code}, "
            f"expected=401, "
            f"detail={detail!r}"
        ),
    )

    return passed


def test_manual_sync() -> None:
    assert (
        check_manual_sync()
        is True
    )


def main() -> int:
    print(
        "=" * 60
    )
    print(
        "BLUE-TRADING-AI VERSION 49 API TEST"
    )
    print(
        "=" * 60
    )

    try:
        checks = [
            check_home(),
            check_learning_health(),
            check_persistence_health(),
            check_persistence_status(),
            check_learning_evaluation(),
            check_manual_sync(),
        ]
    except URLError as exc:
        print(
            "[FAIL] Unable to connect to the FastAPI server: "
            f"{exc}"
        )
        print(
            "Start the backend first with: "
            "uvicorn main:app --host 127.0.0.1 --port 8000"
        )
        return 1
    except Exception as exc:
        print(
            "[FAIL] Unexpected test error: "
            f"{type(exc).__name__}: {exc}"
        )
        return 1

    passed_count = sum(
        checks
    )
    total_count = len(
        checks
    )

    print(
        "=" * 60
    )
    print(
        f"RESULT: {passed_count}/{total_count} tests passed"
    )
    print(
        "=" * 60
    )

    if all(
        checks
    ):
        print(
            "Version 49 API testing completed successfully."
        )
        return 0

    print(
        "One or more API tests failed. Review the FAIL lines."
    )
    return 1


if __name__ == "__main__":
    sys.exit(
        main()
    )