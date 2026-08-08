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


def bearer(token: str) -> dict[str, str]:
    return {
        "Authorization": f"Bearer {token}",
    }


def require_token_pair(
    response: requests.Response,
    label: str,
) -> tuple[str, str, str]:
    if response.status_code != 200:
        print(f"FAILED: {label} failed.")
        raise SystemExit(1)

    payload = response.json()

    access_token = payload.get("access_token")
    refresh_token = payload.get("refresh_token")
    session_id = (
        payload.get("session", {})
        .get("session_id")
        or payload.get("session_id")
    )

    if not access_token:
        print(f"FAILED: {label} returned no access token.")
        raise SystemExit(1)

    if not refresh_token:
        print(f"FAILED: {label} returned no refresh token.")
        raise SystemExit(1)

    if not session_id:
        print(f"FAILED: {label} returned no session ID.")
        raise SystemExit(1)

    return (
        str(access_token),
        str(refresh_token),
        str(session_id),
    )


def main() -> int:
    print("=" * 70)
    print("BLUE-TRADING-AI VERSION 38 REFRESH TOKEN TEST")
    print("=" * 70)

    owner_email = input(
        "Enter OWNER_EMAIL from your .env: "
    ).strip().lower()

    owner_password = getpass.getpass(
        "Enter owner Blue-Trading-AI password: "
    )

    auth_home = request("GET", "/auth/")
    show("TEST 1 - Authentication Version 38", auth_home)

    if (
        auth_home.status_code != 200
        or auth_home.json().get("auth_version") != 38
    ):
        print("FAILED: Authentication is not Version 38.")
        return 1

    first_login = login(
        owner_email,
        owner_password,
    )
    show("TEST 2 - Login Returns Token Pair", first_login)

    (
        access_token_1,
        refresh_token_1,
        session_id,
    ) = require_token_pair(
        first_login,
        "Initial login",
    )

    me_1 = request(
        "GET",
        "/auth/me",
        headers=bearer(access_token_1),
    )
    show("TEST 3 - Initial Access Token Works", me_1)

    if me_1.status_code != 200:
        print("FAILED: Initial access token does not work.")
        return 1

    refresh_1 = request(
        "POST",
        "/auth/refresh",
        json={
            "refresh_token": refresh_token_1,
        },
    )
    show("TEST 4 - Refresh Token Rotation", refresh_1)

    if refresh_1.status_code != 200:
        print("FAILED: Refresh-token rotation failed.")
        return 1

    (
        access_token_2,
        refresh_token_2,
        rotated_session_id,
    ) = require_token_pair(
        refresh_1,
        "Refresh rotation",
    )

    if rotated_session_id != session_id:
        print("FAILED: Rotation changed the session ID.")
        return 1

    if refresh_token_2 == refresh_token_1:
        print("FAILED: Refresh token was not rotated.")
        return 1

    me_2 = request(
        "GET",
        "/auth/me",
        headers=bearer(access_token_2),
    )
    show("TEST 5 - New Access Token Works", me_2)

    if me_2.status_code != 200:
        print("FAILED: New access token does not work.")
        return 1

    reuse_old = request(
        "POST",
        "/auth/refresh",
        json={
            "refresh_token": refresh_token_1,
        },
    )
    show(
        "TEST 6 - Reusing Old Refresh Token Is Blocked",
        reuse_old,
    )

    if reuse_old.status_code != 401:
        print(
            "FAILED: Reused refresh token was not blocked."
        )
        return 1

    family_revoked = request(
        "POST",
        "/auth/refresh",
        json={
            "refresh_token": refresh_token_2,
        },
    )
    show(
        "TEST 7 - Reuse Revokes Token Family",
        family_revoked,
    )

    if family_revoked.status_code != 401:
        print(
            "FAILED: Refresh-token family was not revoked."
        )
        return 1

    second_login = login(
        owner_email,
        owner_password,
    )
    show(
        "TEST 8 - New Login Creates New Token Family",
        second_login,
    )

    (
        access_token_3,
        refresh_token_3,
        session_id_3,
    ) = require_token_pair(
        second_login,
        "Second login",
    )

    if session_id_3 == session_id:
        print("FAILED: New login reused the old session.")
        return 1

    logout = request(
        "POST",
        "/auth/logout",
        headers=bearer(access_token_3),
    )
    show("TEST 9 - Logout Revokes Session", logout)

    if (
        logout.status_code != 200
        or not logout.json().get("session_revoked")
    ):
        print("FAILED: Logout did not revoke the session.")
        return 1

    refresh_after_logout = request(
        "POST",
        "/auth/refresh",
        json={
            "refresh_token": refresh_token_3,
        },
    )
    show(
        "TEST 10 - Refresh Token Blocked After Logout",
        refresh_after_logout,
    )

    if refresh_after_logout.status_code != 401:
        print(
            "FAILED: Refresh token still works after logout."
        )
        return 1

    print("\n" + "=" * 70)
    print("VERSION 38 REFRESH TOKEN TEST: 10/10 PASSED")
    print("=" * 70)
    print(
        "All test sessions are revoked. "
        "Log in again for normal use."
    )

    return 0


if __name__ == "__main__":
    sys.exit(main())

