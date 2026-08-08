from __future__ import annotations

import os
import sys
from typing import Any

import requests

from app.database.connection import SessionLocal
from app.models.role_permission import ROLE_OWNER
from app.models.user import User
from app.services.role_permission_service import (
    ensure_owner_role,
    seed_default_roles_and_permissions,
)


BASE_URL = os.getenv(
    "API_BASE_URL",
    "http://127.0.0.1:8000",
).rstrip("/")

OWNER_EMAIL = os.getenv(
    "OWNER_EMAIL",
    "bluetradingai06@gmail.com",
).strip().lower()

OWNER_PASSWORD = os.getenv(
    "V42_OWNER_PASSWORD",
    "",
)

TIMEOUT = 20


class ValidationFailure(Exception):
    pass


def print_step(number: int, title: str) -> None:
    print(f"\n[{number}/10] {title}")


def require(
    condition: bool,
    message: str,
) -> None:
    if not condition:
        raise ValidationFailure(message)


def json_body(
    response: requests.Response,
) -> dict[str, Any]:
    try:
        payload = response.json()
    except Exception as exc:
        raise ValidationFailure(
            f"Response was not JSON: {response.text[:500]}"
        ) from exc

    require(
        isinstance(payload, dict),
        "Expected a JSON object response.",
    )

    return payload


def prepare_owner_role() -> User:
    db = SessionLocal()

    try:
        seed_default_roles_and_permissions(
            db,
            commit=True,
        )

        owner = (
            db.query(User)
            .filter(User.email == OWNER_EMAIL)
            .first()
        )

        require(
            owner is not None,
            (
                "Owner account was not found. Register the "
                "owner account before running this test."
            ),
        )

        ensure_owner_role(
            db,
            user_id=int(owner.id),
            commit=True,
        )

        return owner
    finally:
        db.close()


def login_owner() -> dict[str, Any]:
    require(
        bool(OWNER_PASSWORD),
        (
            "Set V42_OWNER_PASSWORD in your current PowerShell "
            "session before running this test."
        ),
    )

    response = requests.post(
        f"{BASE_URL}/auth/login",
        data={
            "username": OWNER_EMAIL,
            "password": OWNER_PASSWORD,
        },
        timeout=TIMEOUT,
    )

    require(
        response.status_code == 200,
        (
            "Owner login failed: "
            f"{response.status_code} {response.text}"
        ),
    )

    payload = json_body(response)

    require(
        isinstance(payload.get("access_token"), str)
        and payload["access_token"],
        "Owner login returned no access token.",
    )

    return payload


def auth_headers(
    access_token: str,
) -> dict[str, str]:
    return {
        "Authorization": f"Bearer {access_token}",
    }


def main() -> int:
    print("=" * 68)
    print("BLUE TRADING AI - VERSION 42 ADMIN DASHBOARD TEST")
    print("=" * 68)

    try:
        print_step(1, "API reports Version 42")

        response = requests.get(
            f"{BASE_URL}/",
            timeout=TIMEOUT,
        )

        require(
            response.status_code == 200,
            (
                "Main API failed: "
                f"{response.status_code} {response.text}"
            ),
        )

        payload = json_body(response)

        require(
            str(payload.get("version")) == "42.0.0",
            f"Expected version 42.0.0, got {payload}",
        )

        print("PASSED")

        print_step(2, "Dashboard rejects anonymous access")

        response = requests.get(
            f"{BASE_URL}/admin/dashboard/",
            timeout=TIMEOUT,
        )

        require(
            response.status_code in {401, 403},
            (
                "Anonymous dashboard access was not blocked: "
                f"{response.status_code} {response.text}"
            ),
        )

        print("PASSED")

        print_step(3, "Owner role is prepared")

        owner = prepare_owner_role()

        require(
            owner.email.strip().lower() == OWNER_EMAIL,
            "Prepared owner email does not match OWNER_EMAIL.",
        )

        print("PASSED")

        print_step(4, "Owner login succeeds")

        login_payload = login_owner()
        access_token = login_payload["access_token"]
        headers = auth_headers(access_token)

        print("PASSED")

        print_step(5, "Dashboard home is available to owner")

        response = requests.get(
            f"{BASE_URL}/admin/dashboard/",
            headers=headers,
            timeout=TIMEOUT,
        )

        require(
            response.status_code == 200,
            (
                "Dashboard home failed: "
                f"{response.status_code} {response.text}"
            ),
        )

        dashboard_home = json_body(response)

        require(
            int(
                dashboard_home.get(
                    "admin_dashboard_version",
                    0,
                )
            )
            == 42,
            (
                "Expected admin_dashboard_version 42, got "
                f"{dashboard_home}"
            ),
        )

        print("PASSED")

        print_step(6, "Overview returns all dashboard sections")

        response = requests.get(
            f"{BASE_URL}/admin/dashboard/overview",
            headers=headers,
            params={
                "security_window_hours": 24,
                "recent_event_limit": 10,
            },
            timeout=TIMEOUT,
        )

        require(
            response.status_code == 200,
            (
                "Dashboard overview failed: "
                f"{response.status_code} {response.text}"
            ),
        )

        overview = json_body(response)
        snapshot = overview.get("snapshot")

        require(
            isinstance(snapshot, dict),
            "Dashboard overview returned no snapshot.",
        )

        for section in {
            "users",
            "sessions",
            "security",
            "roles",
            "account_tokens",
            "recent_security_events",
        }:
            require(
                section in snapshot,
                f"Dashboard snapshot is missing: {section}",
            )

        print("PASSED")

        print_step(7, "User statistics are internally consistent")

        users = snapshot["users"]

        require(
            int(users.get("total_users", -1)) >= 1,
            "Expected at least one user.",
        )

        require(
            int(users.get("active_users", 0))
            + int(users.get("inactive_users", 0))
            == int(users.get("total_users", -1)),
            (
                "Active and inactive user counts do not equal "
                "the total user count."
            ),
        )

        print("PASSED")

        print_step(8, "Session and role statistics are returned")

        sessions = snapshot["sessions"]
        roles = snapshot["roles"]

        for key in {
            "total_sessions",
            "active_sessions",
            "total_refresh_tokens",
            "active_refresh_tokens",
        }:
            require(
                key in sessions,
                f"Session statistics missing: {key}",
            )

        require(
            int(roles.get("active_roles", 0)) >= 4,
            "Expected at least four active system roles.",
        )

        assignments = roles.get(
            "assignments_by_role"
        )

        require(
            isinstance(assignments, dict),
            "assignments_by_role is missing.",
        )
        require(
            ROLE_OWNER in assignments,
            "OWNER role statistics are missing.",
        )

        print("PASSED")

        print_step(9, "Recent event limits are enforced")

        response = requests.get(
            f"{BASE_URL}/admin/dashboard/recent-events",
            headers=headers,
            params={"limit": 5},
            timeout=TIMEOUT,
        )

        require(
            response.status_code == 200,
            (
                "Recent events endpoint failed: "
                f"{response.status_code} {response.text}"
            ),
        )

        recent = json_body(response)
        events = recent.get("events")

        require(
            isinstance(events, list),
            "Recent events response is missing events.",
        )
        require(
            len(events) <= 5,
            "Recent events endpoint exceeded requested limit.",
        )

        print("PASSED")

        print_step(10, "Dashboard does not expose secrets")

        serialized = str(overview).lower()

        for forbidden in {
            "password_hash",
            "hashed_password",
            "refresh_token_hash",
            "token_hash",
            "access_token",
            "smtp_password",
        }:
            require(
                forbidden not in serialized,
                (
                    "Dashboard response exposed forbidden field: "
                    f"{forbidden}"
                ),
            )

        print("PASSED")

        print("\n" + "=" * 68)
        print("VERSION 42 ADMIN DASHBOARD TEST: 10/10 PASSED")
        print("=" * 68)
        return 0

    except requests.RequestException as exc:
        print(f"\nFAILED: API connection error: {exc}")
        return 1
    except ValidationFailure as exc:
        print(f"\nFAILED: {exc}")
        return 1
    except Exception as exc:
        print(
            "\nFAILED: Unexpected error: "
            f"{type(exc).__name__}: {exc}"
        )
        return 1


if __name__ == "__main__":
    sys.exit(main())

