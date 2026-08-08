from __future__ import annotations

import os
import secrets
import sys
from typing import Any

import requests
from sqlalchemy import inspect

from app.database.connection import SessionLocal, engine
from app.models.account_action_token import AccountActionToken
from app.models.user import User


BASE_URL = os.getenv(
    "API_BASE_URL",
    "http://127.0.0.1:8000",
).rstrip("/")

OWNER_EMAIL = os.getenv(
    "OWNER_EMAIL",
    "bluetradingai06@gmail.com",
).strip().lower()

TEST_PASSWORD = os.getenv(
    "V39_TEST_PASSWORD",
    "Version39!SecurePassword1",
)

NEW_PASSWORD = os.getenv(
    "V39_NEW_PASSWORD",
    "Version39!ChangedPassword2",
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


def json_body(response: requests.Response) -> dict[str, Any]:
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


def unique_email() -> str:
    suffix = secrets.token_hex(5)

    return f"v39.test.{suffix}@example.com"


def register_user(
    session: requests.Session,
    *,
    username: str,
    email: str,
    password: str,
) -> dict[str, Any]:
    response = session.post(
        f"{BASE_URL}/auth/register",
        json={
            "username": username,
            "email": email,
            "password": password,
        },
        timeout=TIMEOUT,
    )

    require(
        response.status_code in {200, 201},
        (
            "Registration failed: "
            f"{response.status_code} {response.text}"
        ),
    )

    return json_body(response)


def login(
    session: requests.Session,
    *,
    email: str,
    password: str,
) -> requests.Response:
    return session.post(
        f"{BASE_URL}/auth/login",
        data={
            "username": email,
            "password": password,
        },
        timeout=TIMEOUT,
    )


def approve_test_user(
    email: str,
) -> User:
    db = SessionLocal()

    try:
        user = (
            db.query(User)
            .filter(User.email == email)
            .first()
        )

        require(
            user is not None,
            "Registered test user was not found in the database.",
        )

        if hasattr(user, "approve"):
            user.approve(
                approved_by=OWNER_EMAIL
            )
        else:
            user.is_approved = True
            user.is_active = True
            if hasattr(user, "account_status"):
                user.account_status = "APPROVED"

        db.commit()
        db.refresh(user)

        return user
    finally:
        db.close()


def main() -> int:
    print("=" * 66)
    print("BLUE TRADING AI - VERSION 39 ACCOUNT RECOVERY TEST")
    print("=" * 66)

    session = requests.Session()
    test_email = unique_email()
    test_username = (
        "v39test_" + secrets.token_hex(5)
    )

    try:
        print_step(1, "API reports Version 39")

        response = session.get(
            f"{BASE_URL}/auth/",
            timeout=TIMEOUT,
        )
        require(
            response.status_code == 200,
            (
                "Auth home failed: "
                f"{response.status_code} {response.text}"
            ),
        )

        auth_home = json_body(response)

        require(
            int(auth_home.get("auth_version", 0)) == 39,
            f"Expected auth_version 39, got {auth_home}",
        )
        require(
            auth_home.get("email_verification_enabled")
            is True,
            "Email verification is not enabled.",
        )
        require(
            auth_home.get("password_reset_enabled")
            is True,
            "Password reset is not enabled.",
        )
        print("PASSED")

        print_step(2, "Database contains Version 39 schema")

        inspector = inspect(engine)

        require(
            "account_action_tokens"
            in inspector.get_table_names(),
            "account_action_tokens table is missing.",
        )

        user_columns = {
            column["name"]
            for column in inspector.get_columns("users")
        }

        for required_column in {
            "is_email_verified",
            "email_verified_at",
            "email_verification_requested_at",
        }:
            require(
                required_column in user_columns,
                f"users.{required_column} is missing.",
            )

        print("PASSED")

        print_step(3, "Registration creates verification token")

        registration = register_user(
            session,
            username=test_username,
            email=test_email,
            password=TEST_PASSWORD,
        )

        verification_token = registration.get(
            "development_verification_token"
        )

        require(
            isinstance(verification_token, str)
            and len(verification_token) >= 20,
            (
                "Registration returned no development "
                "verification token. Confirm "
                "EXPOSE_DEVELOPMENT_TOKENS=true."
            ),
        )

        db = SessionLocal()

        try:
            user = (
                db.query(User)
                .filter(User.email == test_email)
                .first()
            )

            require(
                user is not None,
                "Registered user is missing.",
            )
            require(
                bool(user.is_email_verified) is False,
                "New user should start unverified.",
            )

            stored_token = (
                db.query(AccountActionToken)
                .filter(
                    AccountActionToken.user_id
                    == int(user.id),
                    AccountActionToken.purpose
                    == "EMAIL_VERIFICATION",
                    AccountActionToken.is_active.is_(True),
                )
                .first()
            )

            require(
                stored_token is not None,
                "Verification token record was not stored.",
            )
            require(
                stored_token.token_hash
                != verification_token,
                "Raw verification token was stored in the database.",
            )
        finally:
            db.close()

        print("PASSED")

        print_step(4, "Email verification succeeds")

        response = session.post(
            f"{BASE_URL}/auth/verify-email",
            json={
                "token": verification_token,
            },
            timeout=TIMEOUT,
        )

        require(
            response.status_code == 200,
            (
                "Email verification failed: "
                f"{response.status_code} {response.text}"
            ),
        )

        verification_result = json_body(response)

        require(
            verification_result.get("email_verified") is True,
            "Email-verification response did not confirm success.",
        )

        db = SessionLocal()

        try:
            user = (
                db.query(User)
                .filter(User.email == test_email)
                .first()
            )

            require(
                user is not None
                and bool(user.is_email_verified) is True,
                "User was not marked email verified.",
            )
        finally:
            db.close()

        print("PASSED")

        print_step(5, "Verification token is single-use")

        response = session.post(
            f"{BASE_URL}/auth/verify-email",
            json={
                "token": verification_token,
            },
            timeout=TIMEOUT,
        )

        require(
            response.status_code in {401, 409, 410},
            (
                "Used verification token was accepted: "
                f"{response.status_code} {response.text}"
            ),
        )

        print("PASSED")

        print_step(6, "Forgot-password response hides account existence")

        unknown_email = unique_email()

        known_response = session.post(
            f"{BASE_URL}/auth/forgot-password",
            json={"email": test_email},
            timeout=TIMEOUT,
        )
        unknown_response = session.post(
            f"{BASE_URL}/auth/forgot-password",
            json={"email": unknown_email},
            timeout=TIMEOUT,
        )

        require(
            known_response.status_code == 200,
            (
                "Known-email forgot-password failed: "
                f"{known_response.status_code} "
                f"{known_response.text}"
            ),
        )
        require(
            unknown_response.status_code == 200,
            (
                "Unknown-email forgot-password failed: "
                f"{unknown_response.status_code} "
                f"{unknown_response.text}"
            ),
        )

        known_payload = json_body(known_response)
        unknown_payload = json_body(unknown_response)

        require(
            known_payload.get("message")
            == unknown_payload.get("message"),
            "Forgot-password messages reveal account existence.",
        )

        reset_token = known_payload.get(
            "development_password_reset_token"
        )

        require(
            isinstance(reset_token, str)
            and len(reset_token) >= 20,
            (
                "Forgot-password returned no development reset "
                "token. Confirm EXPOSE_DEVELOPMENT_TOKENS=true."
            ),
        )

        require(
            "development_password_reset_token"
            not in unknown_payload,
            "Unknown account received a reset token.",
        )

        print("PASSED")

        print_step(7, "Test user can be approved and logged in")

        approve_test_user(test_email)

        login_response = login(
            session,
            email=test_email,
            password=TEST_PASSWORD,
        )

        require(
            login_response.status_code == 200,
            (
                "Login before reset failed: "
                f"{login_response.status_code} "
                f"{login_response.text}"
            ),
        )

        login_payload = json_body(login_response)
        old_access_token = login_payload.get(
            "access_token"
        )
        old_refresh_token = login_payload.get(
            "refresh_token"
        )

        require(
            isinstance(old_access_token, str)
            and old_access_token,
            "Login returned no access token.",
        )
        require(
            isinstance(old_refresh_token, str)
            and old_refresh_token,
            "Login returned no refresh token.",
        )

        print("PASSED")

        print_step(8, "Password reset succeeds and revokes sessions")

        response = session.post(
            f"{BASE_URL}/auth/reset-password",
            json={
                "token": reset_token,
                "new_password": NEW_PASSWORD,
            },
            timeout=TIMEOUT,
        )

        require(
            response.status_code == 200,
            (
                "Password reset failed: "
                f"{response.status_code} {response.text}"
            ),
        )

        reset_result = json_body(response)

        require(
            reset_result.get("relogin_required") is True,
            "Password reset did not require relogin.",
        )
        require(
            int(reset_result.get("revoked_sessions", 0)) >= 1,
            "Password reset did not revoke the active session.",
        )
        require(
            int(
                reset_result.get(
                    "revoked_refresh_tokens",
                    0,
                )
            )
            >= 1,
            "Password reset did not revoke refresh tokens.",
        )

        print("PASSED")

        print_step(9, "Old password and old refresh token are rejected")

        old_login = login(
            session,
            email=test_email,
            password=TEST_PASSWORD,
        )

        require(
            old_login.status_code in {400, 401, 403, 423},
            (
                "Old password was accepted after reset: "
                f"{old_login.status_code} {old_login.text}"
            ),
        )

        refresh_response = session.post(
            f"{BASE_URL}/auth/refresh",
            json={
                "refresh_token": old_refresh_token,
            },
            timeout=TIMEOUT,
        )

        require(
            refresh_response.status_code
            in {400, 401, 403, 409},
            (
                "Old refresh token was accepted after reset: "
                f"{refresh_response.status_code} "
                f"{refresh_response.text}"
            ),
        )

        print("PASSED")

        print_step(10, "New password works and reset token is single-use")

        new_login = login(
            session,
            email=test_email,
            password=NEW_PASSWORD,
        )

        require(
            new_login.status_code == 200,
            (
                "New password login failed: "
                f"{new_login.status_code} {new_login.text}"
            ),
        )

        reused_reset = session.post(
            f"{BASE_URL}/auth/reset-password",
            json={
                "token": reset_token,
                "new_password": TEST_PASSWORD,
            },
            timeout=TIMEOUT,
        )

        require(
            reused_reset.status_code in {401, 409, 410},
            (
                "Used reset token was accepted: "
                f"{reused_reset.status_code} "
                f"{reused_reset.text}"
            ),
        )

        print("PASSED")

        print("\n" + "=" * 66)
        print("VERSION 39 ACCOUNT RECOVERY TEST: 10/10 PASSED")
        print("=" * 66)
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

