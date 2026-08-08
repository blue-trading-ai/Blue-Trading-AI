from __future__ import annotations

import getpass
import json
import secrets
import sys
from typing import Any

import requests


BASE_URL = "http://127.0.0.1:8000"
TIMEOUT_SECONDS = 20


def print_result(
    title: str,
    response: requests.Response,
) -> None:
    print(f"\n{'=' * 70}")
    print(title)
    print(f"HTTP {response.status_code}")

    try:
        payload = response.json()
        print(json.dumps(payload, indent=2, default=str))
    except ValueError:
        print(response.text)


def request(
    method: str,
    path: str,
    **kwargs: Any,
) -> requests.Response:
    url = f"{BASE_URL}{path}"

    try:
        return requests.request(
            method=method,
            url=url,
            timeout=TIMEOUT_SECONDS,
            **kwargs,
        )
    except requests.RequestException as exc:
        print(
            "\nERROR: Could not connect to Blue-Trading-AI.\n"
            "Start the backend first with:\n"
            "uvicorn main:app --reload\n"
        )
        raise SystemExit(1) from exc


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
            "Content-Type": "application/x-www-form-urlencoded",
        },
    )


def main() -> int:
    print("=" * 70)
    print("BLUE-TRADING-AI VERSION 32 OWNER APPROVAL TEST")
    print("=" * 70)

    owner_email = input(
        "Enter OWNER_EMAIL from your .env: "
    ).strip().lower()

    owner_password = getpass.getpass(
        "Enter the owner account password: "
    )

    if not owner_email or not owner_password:
        print("Owner email and password are required.")
        return 1

    # ---------------------------------------------------------
    # TEST 1: Authentication API reports Version 32
    # ---------------------------------------------------------

    response = request(
        "GET",
        "/auth/",
    )
    print_result(
        "TEST 1 - Authentication API",
        response,
    )

    if response.status_code != 200:
        print("FAILED: Authentication API is unavailable.")
        return 1

    auth_payload = response.json()

    if auth_payload.get("auth_version") != 32:
        print(
            "FAILED: /auth/ is not reporting Version 32."
        )
        return 1

    # ---------------------------------------------------------
    # TEST 2: Owner login
    # ---------------------------------------------------------

    owner_login = login(
        owner_email,
        owner_password,
    )
    print_result(
        "TEST 2 - Owner Login",
        owner_login,
    )

    if owner_login.status_code != 200:
        print(
            "\nOwner login failed.\n"
            "Confirm that:\n"
            "1. OWNER_EMAIL exactly matches the owner account email.\n"
            "2. The password is correct.\n"
            "3. The owner account exists.\n"
        )
        return 1

    owner_payload = owner_login.json()
    owner_token = owner_payload.get("access_token")

    if not owner_token:
        print("FAILED: Owner login returned no JWT token.")
        return 1

    owner_headers = {
        "Authorization": f"Bearer {owner_token}",
    }

    # ---------------------------------------------------------
    # TEST 3: Owner admin access
    # ---------------------------------------------------------

    admin_home = request(
        "GET",
        "/admin/users/",
        headers=owner_headers,
    )
    print_result(
        "TEST 3 - Owner Admin Access",
        admin_home,
    )

    if admin_home.status_code != 200:
        print(
            "FAILED: Owner could not access the admin API."
        )
        return 1

    # ---------------------------------------------------------
    # Create a unique normal test user
    # ---------------------------------------------------------

    unique = secrets.token_hex(4)
    test_username = f"v32test_{unique}"
    test_email = f"v32test_{unique}@example.com"
    test_password = f"TestV32!{unique}Aa9"

    # ---------------------------------------------------------
    # TEST 4: Normal registration becomes pending
    # ---------------------------------------------------------

    registration = request(
        "POST",
        "/auth/register",
        json={
            "username": test_username,
            "email": test_email,
            "password": test_password,
        },
    )
    print_result(
        "TEST 4 - Register Pending User",
        registration,
    )

    if registration.status_code != 201:
        print("FAILED: Test user registration failed.")
        return 1

    registration_payload = registration.json()
    registered_user = registration_payload.get(
        "user",
        {},
    )
    user_id = registered_user.get("id")

    if (
        registered_user.get("account_status")
        != "PENDING"
    ):
        print(
            "FAILED: New user did not start as PENDING."
        )
        return 1

    if not user_id:
        print("FAILED: Registration returned no user ID.")
        return 1

    # ---------------------------------------------------------
    # TEST 5: Pending user login must be blocked
    # ---------------------------------------------------------

    pending_login = login(
        test_email,
        test_password,
    )
    print_result(
        "TEST 5 - Pending Login Is Blocked",
        pending_login,
    )

    if pending_login.status_code != 403:
        print(
            "FAILED: Pending user was not blocked with HTTP 403."
        )
        return 1

    # ---------------------------------------------------------
    # TEST 6: Owner approves user
    # ---------------------------------------------------------

    approval = request(
        "POST",
        f"/admin/users/{user_id}/approve",
        headers=owner_headers,
    )
    print_result(
        "TEST 6 - Owner Approves User",
        approval,
    )

    if approval.status_code != 200:
        print("FAILED: Owner approval failed.")
        return 1

    approved_user = approval.json().get(
        "user",
        {},
    )

    if (
        approved_user.get("account_status")
        != "APPROVED"
    ):
        print(
            "FAILED: User status did not become APPROVED."
        )
        return 1

    # ---------------------------------------------------------
    # TEST 7: Approved user can log in
    # ---------------------------------------------------------

    approved_login = login(
        test_email,
        test_password,
    )
    print_result(
        "TEST 7 - Approved User Login",
        approved_login,
    )

    if approved_login.status_code != 200:
        print(
            "FAILED: Approved user could not log in."
        )
        return 1

    approved_token = approved_login.json().get(
        "access_token"
    )

    if not approved_token:
        print(
            "FAILED: Approved user received no JWT token."
        )
        return 1

    approved_headers = {
        "Authorization": f"Bearer {approved_token}",
    }

    # ---------------------------------------------------------
    # TEST 8: Approved user can access protected profile
    # ---------------------------------------------------------

    profile = request(
        "GET",
        "/auth/profile",
        headers=approved_headers,
    )
    print_result(
        "TEST 8 - Approved Protected Access",
        profile,
    )

    if profile.status_code != 200:
        print(
            "FAILED: Approved user could not access profile."
        )
        return 1

    # ---------------------------------------------------------
    # TEST 9: Owner suspends user
    # ---------------------------------------------------------

    suspension = request(
        "POST",
        f"/admin/users/{user_id}/suspend",
        headers=owner_headers,
    )
    print_result(
        "TEST 9 - Owner Suspends User",
        suspension,
    )

    if suspension.status_code != 200:
        print("FAILED: User suspension failed.")
        return 1

    # ---------------------------------------------------------
    # TEST 10: Existing JWT is immediately blocked
    # ---------------------------------------------------------

    blocked_profile = request(
        "GET",
        "/auth/profile",
        headers=approved_headers,
    )
    print_result(
        "TEST 10 - Suspended Existing Token Is Blocked",
        blocked_profile,
    )

    if blocked_profile.status_code != 403:
        print(
            "FAILED: Suspended user's existing token still worked."
        )
        return 1

    print("\n" + "=" * 70)
    print("VERSION 32 OWNER APPROVAL TEST: 10/10 PASSED")
    print("=" * 70)
    print(
        f"Test user left in SUSPENDED state: {test_email}"
    )

    return 0


if __name__ == "__main__":
    sys.exit(main())

