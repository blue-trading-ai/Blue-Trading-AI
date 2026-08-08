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


def require_token(
    response: requests.Response,
    label: str,
) -> tuple[str, str]:
    if response.status_code != 200:
        print(f"FAILED: {label} login failed.")
        raise SystemExit(1)

    payload = response.json()
    token = payload.get("access_token")
    session_id = (
        payload.get("session", {})
        .get("session_id")
    )

    if not token or not session_id:
        print(
            f"FAILED: {label} login did not return "
            "a token and session ID."
        )
        raise SystemExit(1)

    return str(token), str(session_id)


def main() -> int:
    print("=" * 70)
    print("BLUE-TRADING-AI VERSION 37 SESSION SECURITY TEST")
    print("=" * 70)

    owner_email = input(
        "Enter OWNER_EMAIL from your .env: "
    ).strip().lower()

    owner_password = getpass.getpass(
        "Enter owner Blue-Trading-AI password: "
    )

    auth_home = request("GET", "/auth/")
    show("TEST 1 - Authentication Version 37", auth_home)

    if (
        auth_home.status_code != 200
        or auth_home.json().get("auth_version") != 37
    ):
        print("FAILED: Authentication is not Version 37.")
        return 1

    login_a = login(owner_email, owner_password)
    show("TEST 2 - Create Session A", login_a)
    token_a, session_a = require_token(
        login_a,
        "Session A",
    )

    login_b = login(owner_email, owner_password)
    show("TEST 3 - Create Session B", login_b)
    token_b, session_b = require_token(
        login_b,
        "Session B",
    )

    if session_a == session_b:
        print("FAILED: Two logins returned the same session ID.")
        return 1

    sessions = request(
        "GET",
        "/auth/sessions",
        headers=bearer(token_a),
    )
    show("TEST 4 - List User Sessions", sessions)

    if sessions.status_code != 200:
        print("FAILED: Session listing failed.")
        return 1

    listed = sessions.json().get("sessions", [])
    listed_ids = {
        str(item.get("session_id"))
        for item in listed
    }

    if not {session_a, session_b}.issubset(listed_ids):
        print(
            "FAILED: Both active sessions were not listed."
        )
        return 1

    revoke_b = request(
        "POST",
        f"/auth/sessions/{session_b}/revoke",
        headers=bearer(token_a),
    )
    show("TEST 5 - Revoke Session B", revoke_b)

    if (
        revoke_b.status_code != 200
        or not revoke_b.json().get("relogin_required") is False
    ):
        print("FAILED: Session B revocation failed.")
        return 1

    blocked_b = request(
        "GET",
        "/auth/me",
        headers=bearer(token_b),
    )
    show("TEST 6 - Revoked Session B Is Blocked", blocked_b)

    if blocked_b.status_code != 401:
        print(
            "FAILED: Revoked Session B was not blocked."
        )
        return 1

    active_a = request(
        "GET",
        "/auth/me",
        headers=bearer(token_a),
    )
    show("TEST 7 - Session A Remains Active", active_a)

    if active_a.status_code != 200:
        print("FAILED: Session A was incorrectly revoked.")
        return 1

    login_c = login(owner_email, owner_password)
    show("TEST 8 - Create Session C", login_c)
    token_c, session_c = require_token(
        login_c,
        "Session C",
    )

    revoke_others = request(
        "POST",
        "/auth/sessions/revoke-all",
        params={"keep_current": "true"},
        headers=bearer(token_a),
    )
    show(
        "TEST 9 - Revoke All Other Devices",
        revoke_others,
    )

    if (
        revoke_others.status_code != 200
        or not revoke_others.json().get(
            "current_session_preserved"
        )
    ):
        print("FAILED: Revoke-all-others failed.")
        return 1

    blocked_c = request(
        "GET",
        "/auth/me",
        headers=bearer(token_c),
    )

    active_a_again = request(
        "GET",
        "/auth/me",
        headers=bearer(token_a),
    )

    if blocked_c.status_code != 401:
        show(
            "TEST 9A - Session C Should Be Blocked",
            blocked_c,
        )
        print("FAILED: Session C remained active.")
        return 1

    if active_a_again.status_code != 200:
        show(
            "TEST 9B - Session A Should Remain Active",
            active_a_again,
        )
        print("FAILED: Current session was not preserved.")
        return 1

    logout_a = request(
        "POST",
        "/auth/logout",
        headers=bearer(token_a),
    )
    show("TEST 10 - Logout Current Session", logout_a)

    if (
        logout_a.status_code != 200
        or not logout_a.json().get("session_revoked")
    ):
        print("FAILED: Logout did not revoke Session A.")
        return 1

    blocked_a = request(
        "GET",
        "/auth/me",
        headers=bearer(token_a),
    )

    if blocked_a.status_code != 401:
        show(
            "TEST 10A - Logged-Out Session Is Blocked",
            blocked_a,
        )
        print("FAILED: Logged-out token still works.")
        return 1

    print("\n" + "=" * 70)
    print("VERSION 37 SESSION SECURITY TEST: 10/10 PASSED")
    print("=" * 70)
    print(
        "All test sessions were revoked. "
        "Log in again for normal use."
    )

    return 0


if __name__ == "__main__":
    sys.exit(main())

