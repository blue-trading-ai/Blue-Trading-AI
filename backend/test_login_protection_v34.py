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
    print("BLUE-TRADING-AI VERSION 34 LOGIN PROTECTION TEST")
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
        or auth_home.json().get("auth_version") != 34
    ):
        print("FAILED: Authentication is not Version 34.")
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

    unique = secrets.token_hex(4)
    username = f"v34test_{unique}"
    email = f"v34test_{unique}@example.com"
    correct_password = f"V34Strong!{unique}Aa9"
    wrong_password = f"WrongV34!{unique}Aa9"

    registration = request(
        "POST",
        "/auth/register",
        json={
            "username": username,
            "email": email,
            "password": correct_password,
        },
    )
    show("TEST 3 - Register Pending User", registration)

    if registration.status_code != 201:
        print("FAILED: Test user registration failed.")
        return 1

    user_id = registration.json().get("user", {}).get("id")

    if not user_id:
        print("FAILED: User ID missing.")
        return 1

    approval = request(
        "POST",
        f"/admin/users/{user_id}/approve",
        headers=owner_headers,
    )
    show("TEST 4 - Approve Test User", approval)

    if approval.status_code != 200:
        print("FAILED: User approval failed.")
        return 1

    for attempt in range(1, 5):
        failed = login(email, wrong_password)
        show(
            f"TEST 5.{attempt} - Failed Login Attempt {attempt}",
            failed,
        )

        if failed.status_code != 401:
            print(
                "FAILED: Attempts 1 to 4 must return HTTP 401."
            )
            return 1

    fifth_failure = login(email, wrong_password)
    show(
        "TEST 6 - Fifth Failure Locks Account",
        fifth_failure,
    )

    if fifth_failure.status_code != 423:
        print(
            "FAILED: Fifth failure did not return HTTP 423."
        )
        return 1

    correct_while_locked = login(
        email,
        correct_password,
    )
    show(
        "TEST 7 - Correct Password Still Blocked While Locked",
        correct_while_locked,
    )

    if correct_while_locked.status_code != 423:
        print(
            "FAILED: Locked account accepted login."
        )
        return 1

    unlock = request(
        "POST",
        f"/admin/users/{user_id}/unlock",
        headers=owner_headers,
    )
    show("TEST 8 - Owner Unlocks User", unlock)

    if unlock.status_code != 200:
        print("FAILED: Owner unlock failed.")
        return 1

    unlocked_login = login(
        email,
        correct_password,
    )
    show("TEST 9 - Login Works After Unlock", unlocked_login)

    if unlocked_login.status_code != 200:
        print(
            "FAILED: Correct login did not work after unlock."
        )
        return 1

    user_token = unlocked_login.json().get("access_token")

    profile = request(
        "GET",
        "/auth/profile",
        headers={
            "Authorization": f"Bearer {user_token}",
        },
    )
    show("TEST 10 - Protected Access After Unlock", profile)

    if profile.status_code != 200:
        print(
            "FAILED: Unlocked user could not access profile."
        )
        return 1

    print("\n" + "=" * 70)
    print("VERSION 34 LOGIN PROTECTION TEST: 10/10 PASSED")
    print("=" * 70)
    print(
        f"Test user left APPROVED and unlocked: {email}"
    )

    return 0


if __name__ == "__main__":
    sys.exit(main())

