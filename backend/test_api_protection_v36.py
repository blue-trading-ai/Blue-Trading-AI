from __future__ import annotations

import json
import sys
from typing import Any

import requests


BASE_URL = "http://127.0.0.1:8000"
TIMEOUT_SECONDS = 20


def request(
    method: str,
    path: str,
    **kwargs: Any,
) -> requests.Response:
    try:
        return requests.request(
            method,
            f"{BASE_URL}{path}",
            timeout=TIMEOUT_SECONDS,
            **kwargs,
        )
    except requests.RequestException as exc:
        print(
            "Could not connect to the backend. Start it with:\n"
            "uvicorn main:app --reload"
        )
        raise SystemExit(1) from exc


def show(
    title: str,
    response: requests.Response,
) -> None:
    print("\n" + "=" * 70)
    print(title)
    print(f"HTTP {response.status_code}")

    try:
        print(
            json.dumps(
                response.json(),
                indent=2,
                default=str,
            )
        )
    except ValueError:
        print(response.text)

    print("Selected headers:")
    for key in [
        "X-Request-ID",
        "X-Process-Time-Ms",
        "X-RateLimit-Limit",
        "X-RateLimit-Remaining",
        "X-RateLimit-Reset",
        "X-RateLimit-Rule",
        "Retry-After",
        "X-Content-Type-Options",
        "X-Frame-Options",
        "Referrer-Policy",
        "Permissions-Policy",
        "Cache-Control",
        "Access-Control-Allow-Origin",
    ]:
        value = response.headers.get(key)
        if value is not None:
            print(f"  {key}: {value}")


def main() -> int:
    print("=" * 70)
    print("BLUE-TRADING-AI VERSION 36 API PROTECTION TEST")
    print("=" * 70)

    home = request("GET", "/")
    show("TEST 1 - Version 36 Home", home)

    if (
        home.status_code != 200
        or home.json().get("version") != "36.0.0"
    ):
        print("FAILED: Backend is not Version 36.")
        return 1

    required_security_headers = {
        "X-Request-ID",
        "X-Process-Time-Ms",
        "X-Content-Type-Options",
        "X-Frame-Options",
        "Referrer-Policy",
        "Permissions-Policy",
    }

    missing = [
        header
        for header in required_security_headers
        if header not in home.headers
    ]

    if missing:
        print(
            "FAILED: Missing security headers: "
            + ", ".join(missing)
        )
        return 1

    if home.headers.get(
        "X-Content-Type-Options"
    ) != "nosniff":
        print("FAILED: nosniff header is incorrect.")
        return 1

    if home.headers.get(
        "X-Frame-Options"
    ) != "DENY":
        print("FAILED: frame protection is incorrect.")
        return 1

    auth_home = request("GET", "/auth/")
    show("TEST 2 - Auth No-Store Cache", auth_home)

    if auth_home.status_code != 200:
        print("FAILED: Auth endpoint unavailable.")
        return 1

    if auth_home.headers.get(
        "Cache-Control"
    ) != "no-store":
        print("FAILED: Auth response is not no-store.")
        return 1

    custom_request_id = "v36-test-request-id"
    request_id_response = request(
        "GET",
        "/health",
        headers={
            "X-Request-ID": custom_request_id,
        },
    )
    show(
        "TEST 3 - Request ID Echo",
        request_id_response,
    )

    if request_id_response.headers.get(
        "X-Request-ID"
    ) != custom_request_id:
        print("FAILED: Request ID was not preserved.")
        return 1

    cors_preflight = request(
        "OPTIONS",
        "/auth/login",
        headers={
            "Origin": "http://localhost:3000",
            "Access-Control-Request-Method": "POST",
            "Access-Control-Request-Headers":
                "content-type",
        },
    )
    show(
        "TEST 4 - Allowed CORS Preflight",
        cors_preflight,
    )

    if cors_preflight.status_code not in {200, 204}:
        print("FAILED: Allowed CORS preflight failed.")
        return 1

    if cors_preflight.headers.get(
        "Access-Control-Allow-Origin"
    ) != "http://localhost:3000":
        print("FAILED: Allowed CORS origin not returned.")
        return 1

    oversized_body = b"x" * (2 * 1024 * 1024 + 1)

    oversized = request(
        "POST",
        "/auth/register",
        data=oversized_body,
        headers={
            "Content-Type": "application/octet-stream",
        },
    )
    show(
        "TEST 5 - Oversized Body Is Blocked",
        oversized,
    )

    if oversized.status_code != 413:
        print("FAILED: Oversized body was not blocked.")
        return 1

    general_rate = request("GET", "/health")
    show(
        "TEST 6 - General Rate-Limit Headers",
        general_rate,
    )

    required_rate_headers = {
        "X-RateLimit-Limit",
        "X-RateLimit-Remaining",
        "X-RateLimit-Reset",
        "X-RateLimit-Rule",
    }

    missing_rate = [
        header
        for header in required_rate_headers
        if header not in general_rate.headers
    ]

    if missing_rate:
        print(
            "FAILED: Missing rate-limit headers: "
            + ", ".join(missing_rate)
        )
        return 1

    if general_rate.headers.get(
        "X-RateLimit-Rule"
    ) != "general":
        print("FAILED: General rate-limit rule is wrong.")
        return 1

    login_responses = []

    for _ in range(11):
        response = request(
            "POST",
            "/auth/login",
            data={
                "username":
                    "v36-rate-limit-test@example.com",
                "password": "WrongPassword123!",
            },
            headers={
                "Content-Type":
                    "application/x-www-form-urlencoded",
            },
        )
        login_responses.append(response)

    final_login_response = login_responses[-1]
    show(
        "TEST 7 - Login Rate Limit",
        final_login_response,
    )

    if final_login_response.status_code != 429:
        print(
            "FAILED: Login endpoint did not return HTTP 429."
        )
        return 1

    if final_login_response.headers.get(
        "X-RateLimit-Rule"
    ) != "login":
        print("FAILED: Login rate-limit rule is wrong.")
        return 1

    if "Retry-After" not in final_login_response.headers:
        print("FAILED: Retry-After header is missing.")
        return 1

    blocked_cors = request(
        "OPTIONS",
        "/auth/login",
        headers={
            "Origin": "https://untrusted-example.invalid",
            "Access-Control-Request-Method": "POST",
            "Access-Control-Request-Headers":
                "content-type",
        },
    )
    show(
        "TEST 8 - Disallowed CORS Origin",
        blocked_cors,
    )

    allowed_origin = blocked_cors.headers.get(
        "Access-Control-Allow-Origin"
    )

    if allowed_origin == "https://untrusted-example.invalid":
        print(
            "FAILED: Untrusted CORS origin was allowed."
        )
        return 1

    if blocked_cors.status_code not in {400, 403}:
        print(
            "FAILED: Disallowed CORS preflight was not rejected."
        )
        return 1

    print("\n" + "=" * 70)
    print("VERSION 36 API PROTECTION TEST: 8/8 PASSED")
    print("=" * 70)

    return 0


if __name__ == "__main__":
    sys.exit(main())

