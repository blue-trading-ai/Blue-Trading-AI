from __future__ import annotations

import getpass
import json
import secrets
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


def login(
    email: str,
    password: str,
) -> requests.Response:
    return request(
        "POST",
        "/auth/login",
        data={
            "username": email,
            "password": password,
        },
        headers={
            "Content-Type":
                "application/x-www-form-urlencoded",
        },
    )


def main() -> int:
    print("=" * 70)
    print("BLUE-TRADING-AI VERSION 35 SECURITY AUDIT TEST")
    print("=" * 70)

    owner_email = input(
        "Enter OWNER_EMAIL from your .env: "
    ).strip().lower()

    owner_password = getpass.getpass(
        "Enter owner Blue-Trading-AI password: "
    )

    auth_home = request("GET", "/auth/")
    show("TEST 1 - Authentication Version", auth_home)

    if (
        auth_home.status_code != 200
        or auth_home.json().get("auth_version") != 35
    ):
        print("FAILED: Authentication is not Version 35.")
        return 1

    owner_login = login(
        owner_email,
        owner_password,
    )
    show("TEST 2 - Owner Login", owner_login)

    if owner_login.status_code != 200:
        print("FAILED: Owner login failed.")
        return 1

    owner_token = owner_login.json().get("access_token")

    if not owner_token:
        print("FAILED: Owner token missing.")
        return 1

    owner_headers = {
        "Authorization": f"Bearer {owner_token}",
    }

    audit_home = request(
        "GET",
        "/admin/audit-logs/",
        headers=owner_headers,
    )
    show("TEST 3 - Owner Audit API Access", audit_home)

    if audit_home.status_code != 200:
        print("FAILED: Owner cannot access audit API.")
        return 1

    unique = secrets.token_hex(4)
    username = f"v35test_{unique}"
    email = f"v35test_{unique}@example.com"
    correct_password = f"V35Strong!{unique}Aa9"
    wrong_password = f"WrongV35!{unique}Aa9"

    registration = request(
        "POST",
        "/auth/register",
        json={
            "username": username,
            "email": email,
            "password": correct_password,
        },
    )
    show("TEST 4 - Register Test User", registration)

    if registration.status_code != 201:
        print("FAILED: Registration failed.")
        return 1

    user_id = registration.json().get("user", {}).get("id")

    if not user_id:
        print("FAILED: Registration returned no user ID.")
        return 1

    approval = request(
        "POST",
        f"/admin/users/{user_id}/approve",
        headers=owner_headers,
    )
    show("TEST 5 - Owner Approves User", approval)

    if approval.status_code != 200:
        print("FAILED: Approval failed.")
        return 1

    failed_login = login(
        email,
        wrong_password,
    )
    show("TEST 6 - Failed Login Is Audited", failed_login)

    if failed_login.status_code != 401:
        print("FAILED: Wrong password did not return HTTP 401.")
        return 1

    successful_login = login(
        email,
        correct_password,
    )
    show("TEST 7 - Successful Login Is Audited", successful_login)

    if successful_login.status_code != 200:
        print("FAILED: Approved user login failed.")
        return 1

    filtered_logs = request(
        "GET",
        "/admin/audit-logs",
        headers=owner_headers,
        params={
            "target_email": email,
            "limit": 100,
        },
    )
    show("TEST 8 - Filter Audit Logs By User", filtered_logs)

    if filtered_logs.status_code != 200:
        print("FAILED: Audit log filtering failed.")
        return 1

    logs = filtered_logs.json().get("logs", [])
    event_types = {
        str(log.get("event_type"))
        for log in logs
    }

    required_events = {
        "REGISTRATION",
        "USER_APPROVED",
        "LOGIN_FAILURE",
        "LOGIN_SUCCESS",
    }

    missing_events = required_events - event_types

    if missing_events:
        print(
            "FAILED: Missing expected audit events: "
            + ", ".join(sorted(missing_events))
        )
        return 1

    summary = request(
        "GET",
        "/admin/audit-logs/summary",
        headers=owner_headers,
    )
    show("TEST 9 - Audit Summary", summary)

    if summary.status_code != 200:
        print("FAILED: Audit summary failed.")
        return 1

    if int(summary.json().get("total_events", 0)) < 4:
        print("FAILED: Audit summary event count is too low.")
        return 1

    event_types_response = request(
        "GET",
        "/admin/audit-logs/event-types",
        headers=owner_headers,
    )
    show("TEST 10 - Audit Event Types", event_types_response)

    if event_types_response.status_code != 200:
        print("FAILED: Event type listing failed.")
        return 1

    listed_event_types = set(
        event_types_response.json().get(
            "event_types",
            [],
        )
    )

    if not required_events.issubset(listed_event_types):
        print(
            "FAILED: Event type endpoint is missing required events."
        )
        return 1

    print("\n" + "=" * 70)
    print("VERSION 35 SECURITY AUDIT TEST: 10/10 PASSED")
    print("=" * 70)
    print(
        f"Test user left APPROVED: {email}"
    )

    return 0


if __name__ == "__main__":
    sys.exit(main())

