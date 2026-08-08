from __future__ import annotations

import getpass
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
    print("BLUE-TRADING-AI VERSION 33 PASSWORD SECURITY TEST")
    print("=" * 70)

    email = input(
        "Enter your approved account email: "
    ).strip().lower()

    current_password = getpass.getpass(
        "Enter current Blue-Trading-AI password: "
    )

    new_password = getpass.getpass(
        "Enter a new strong password: "
    )

    confirm_password = getpass.getpass(
        "Confirm the new password: "
    )

    if new_password != confirm_password:
        print("New passwords do not match.")
        return 1

    auth_home = request("GET", "/auth/")
    show("TEST 1 - Authentication Version", auth_home)

    if (
        auth_home.status_code != 200
        or auth_home.json().get("auth_version") != 33
    ):
        print("FAILED: Authentication is not Version 33.")
        return 1

    old_login = login(email, current_password)
    show("TEST 2 - Current Password Login", old_login)

    if old_login.status_code != 200:
        print("FAILED: Current login did not succeed.")
        return 1

    old_token = old_login.json().get("access_token")

    if not old_token:
        print("FAILED: Login returned no access token.")
        return 1

    old_headers = {
        "Authorization": f"Bearer {old_token}",
    }

    before_profile = request(
        "GET",
        "/auth/profile",
        headers=old_headers,
    )
    show("TEST 3 - Old Token Works Before Change", before_profile)

    if before_profile.status_code != 200:
        print("FAILED: Existing token was not valid.")
        return 1

    change = request(
        "POST",
        "/auth/change-password",
        headers=old_headers,
        json={
            "current_password": current_password,
            "new_password": new_password,
        },
    )
    show("TEST 4 - Change Password", change)

    if change.status_code != 200:
        print("FAILED: Password change failed.")
        return 1

    revoked_profile = request(
        "GET",
        "/auth/profile",
        headers=old_headers,
    )
    show("TEST 5 - Old Token Is Revoked", revoked_profile)

    if revoked_profile.status_code != 401:
        print("FAILED: Old token was not revoked.")
        return 1

    old_password_login = login(
        email,
        current_password,
    )
    show("TEST 6 - Old Password Is Rejected", old_password_login)

    if old_password_login.status_code != 401:
        print("FAILED: Old password still works.")
        return 1

    new_login = login(email, new_password)
    show("TEST 7 - New Password Login", new_login)

    if new_login.status_code != 200:
        print("FAILED: New password login failed.")
        return 1

    new_token = new_login.json().get("access_token")

    if not new_token:
        print("FAILED: New login returned no token.")
        return 1

    new_profile = request(
        "GET",
        "/auth/profile",
        headers={
            "Authorization": f"Bearer {new_token}",
        },
    )
    show("TEST 8 - New Token Protected Access", new_profile)

    if new_profile.status_code != 200:
        print("FAILED: New token cannot access protected routes.")
        return 1

    print("\n" + "=" * 70)
    print("VERSION 33 PASSWORD SECURITY TEST: 8/8 PASSED")
    print("=" * 70)
    print(
        "Your account password is now the new password "
        "entered during this test."
    )

    return 0


if __name__ == "__main__":
    sys.exit(main())

