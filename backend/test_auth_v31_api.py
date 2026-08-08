"""
Blue-Trading-AI
Version 31
test_auth_v31_api.py

Run while FastAPI is running:

    python test_auth_v31_api.py

Default API:
    http://127.0.0.1:8000

This script creates a temporary test account using a unique email.
It does not delete existing users.
"""

from __future__ import annotations

import json
import secrets
import sys
from typing import Any

import requests


BASE_URL = "http://127.0.0.1:8000"
TIMEOUT_SECONDS = 20

UNIQUE_CODE = secrets.token_hex(4)
TEST_USERNAME = f"v31_user_{UNIQUE_CODE}"
TEST_EMAIL = f"v31_{UNIQUE_CODE}@example.com"
TEST_PASSWORD = "SecurePass123!"


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

    if len(formatted) > 2200:
        formatted = (
            formatted[:2200]
            + "\n... response preview shortened ..."
        )

    print(formatted)


def request_json(
    method: str,
    endpoint: str,
    *,
    json_payload: dict[str, Any] | None = None,
    form_payload: dict[str, Any] | None = None,
    headers: dict[str, str] | None = None,
) -> tuple[int, Any]:
    try:
        response = requests.request(
            method=method,
            url=f"{BASE_URL}{endpoint}",
            json=json_payload,
            data=form_payload,
            headers=headers,
            timeout=TIMEOUT_SECONDS,
        )
    except requests.ConnectionError:
        print("[FAIL] Unable to connect to FastAPI.")
        print("Start the server first:")
        print("python -m uvicorn main:app --reload")
        return 0, {}
    except requests.RequestException as exc:
        print(f"[FAIL] Request error: {exc}")
        return 0, {}

    try:
        body = response.json()
    except ValueError:
        body = response.text

    return response.status_code, body


def verify_auth_home() -> bool:
    status_code, body = request_json(
        "GET",
        "/auth/",
    )

    print_separator()
    print("AUTH HOME")
    print(f"STATUS: {status_code}")
    print_preview(body)

    passed = (
        status_code == 200
        and isinstance(body, dict)
        and body.get("auth_version") == 31
        and body.get("password_hashing_enabled") is True
        and body.get("jwt_authentication_enabled") is True
        and body.get("protected_routes_enabled") is True
    )

    print(f"[{'PASS' if passed else 'FAIL'}] Auth home")
    return passed


def verify_registration() -> bool:
    status_code, body = request_json(
        "POST",
        "/auth/register",
        json_payload={
            "username": TEST_USERNAME,
            "email": TEST_EMAIL,
            "password": TEST_PASSWORD,
        },
    )

    print_separator()
    print("USER REGISTRATION")
    print(f"STATUS: {status_code}")
    print_preview(body)

    user = (
        body.get("user", {})
        if isinstance(body, dict)
        else {}
    )

    passed = (
        status_code == 201
        and body.get("status") == "success"
        and user.get("username") == TEST_USERNAME
        and user.get("email") == TEST_EMAIL
        and "hashed_password" not in user
        and "password" not in user
    )

    print(f"[{'PASS' if passed else 'FAIL'}] Registration")
    return passed


def verify_duplicate_registration() -> bool:
    status_code, body = request_json(
        "POST",
        "/auth/register",
        json_payload={
            "username": TEST_USERNAME,
            "email": TEST_EMAIL,
            "password": TEST_PASSWORD,
        },
    )

    print_separator()
    print("DUPLICATE REGISTRATION")
    print(f"STATUS: {status_code}")
    print_preview(body)

    passed = status_code == 409

    print(
        f"[{'PASS' if passed else 'FAIL'}] "
        "Duplicate account blocked"
    )
    return passed


def verify_weak_password_rejected() -> bool:
    status_code, body = request_json(
        "POST",
        "/auth/register",
        json_payload={
            "username": f"weak_{UNIQUE_CODE}",
            "email": f"weak_{UNIQUE_CODE}@example.com",
            "password": "password",
        },
    )

    print_separator()
    print("WEAK PASSWORD")
    print(f"STATUS: {status_code}")
    print_preview(body)

    passed = status_code == 422

    print(
        f"[{'PASS' if passed else 'FAIL'}] "
        "Weak password rejected"
    )
    return passed


def login() -> tuple[bool, str]:
    status_code, body = request_json(
        "POST",
        "/auth/login",
        form_payload={
            "username": TEST_EMAIL,
            "password": TEST_PASSWORD,
            "grant_type": "password",
        },
    )

    print_separator()
    print("USER LOGIN")
    print(f"STATUS: {status_code}")
    print_preview(body)

    token = (
        body.get("access_token", "")
        if isinstance(body, dict)
        else ""
    )

    passed = (
        status_code == 200
        and bool(token)
        and body.get("token_type") == "bearer"
        and isinstance(body.get("user"), dict)
    )

    print(f"[{'PASS' if passed else 'FAIL'}] Login")
    return passed, token


def verify_wrong_password() -> bool:
    status_code, body = request_json(
        "POST",
        "/auth/login",
        form_payload={
            "username": TEST_EMAIL,
            "password": "WrongPassword123!",
            "grant_type": "password",
        },
    )

    print_separator()
    print("WRONG PASSWORD")
    print(f"STATUS: {status_code}")
    print_preview(body)

    passed = (
        status_code == 401
        and isinstance(body, dict)
        and body.get("detail") == "Incorrect email or password."
    )

    print(
        f"[{'PASS' if passed else 'FAIL'}] "
        "Wrong password rejected"
    )
    return passed


def verify_profile(token: str) -> bool:
    status_code, body = request_json(
        "GET",
        "/auth/profile",
        headers={
            "Authorization": f"Bearer {token}",
        },
    )

    print_separator()
    print("PROTECTED PROFILE")
    print(f"STATUS: {status_code}")
    print_preview(body)

    user = (
        body.get("user", {})
        if isinstance(body, dict)
        else {}
    )

    passed = (
        status_code == 200
        and body.get("status") == "success"
        and user.get("email") == TEST_EMAIL
        and user.get("username") == TEST_USERNAME
    )

    print(
        f"[{'PASS' if passed else 'FAIL'}] "
        "Protected profile"
    )
    return passed


def verify_me(token: str) -> bool:
    status_code, body = request_json(
        "GET",
        "/auth/me",
        headers={
            "Authorization": f"Bearer {token}",
        },
    )

    print_separator()
    print("CURRENT USER")
    print(f"STATUS: {status_code}")
    print_preview(body)

    passed = (
        status_code == 200
        and isinstance(body, dict)
        and body.get("email") == TEST_EMAIL
        and body.get("username") == TEST_USERNAME
        and body.get("sub") == TEST_EMAIL
    )

    print(f"[{'PASS' if passed else 'FAIL'}] Current user")
    return passed


def verify_invalid_token() -> bool:
    status_code, body = request_json(
        "GET",
        "/auth/profile",
        headers={
            "Authorization": "Bearer invalid.jwt.token",
        },
    )

    print_separator()
    print("INVALID TOKEN")
    print(f"STATUS: {status_code}")
    print_preview(body)

    passed = status_code == 401

    print(
        f"[{'PASS' if passed else 'FAIL'}] "
        "Invalid token rejected"
    )
    return passed


def verify_missing_token() -> bool:
    status_code, body = request_json(
        "GET",
        "/auth/profile",
    )

    print_separator()
    print("MISSING TOKEN")
    print(f"STATUS: {status_code}")
    print_preview(body)

    passed = status_code == 401

    print(
        f"[{'PASS' if passed else 'FAIL'}] "
        "Missing token rejected"
    )
    return passed


def main() -> int:
    print("=" * 76)
    print("BLUE-TRADING-AI VERSION 31 AUTHENTICATION API TEST")
    print("=" * 76)
    print(f"API: {BASE_URL}")
    print(f"Temporary username: {TEST_USERNAME}")
    print(f"Temporary email: {TEST_EMAIL}")

    results = [
        verify_auth_home(),
        verify_registration(),
        verify_duplicate_registration(),
        verify_weak_password_rejected(),
    ]

    login_passed, token = login()
    results.append(login_passed)
    results.append(verify_wrong_password())

    if login_passed and token:
        results.extend(
            [
                verify_profile(token),
                verify_me(token),
            ]
        )
    else:
        results.extend([False, False])

    results.extend(
        [
            verify_invalid_token(),
            verify_missing_token(),
        ]
    )

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
            "Version 31 Authentication API testing "
            "completed successfully."
        )
        return 0

    print(
        "One or more tests failed. "
        "Review the FAIL lines above."
    )
    return 1


if __name__ == "__main__":
    sys.exit(main())

