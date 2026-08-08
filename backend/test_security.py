from __future__ import annotations

from app.core.security import (
    create_access_token,
    hash_password,
    verify_password,
)


TEST_PASSWORD = "BlueAI2026!"


def test_password_hashing() -> None:
    hashed_password = hash_password(
        TEST_PASSWORD
    )

    assert hashed_password
    assert isinstance(
        hashed_password,
        str,
    )
    assert hashed_password != TEST_PASSWORD


def test_password_verification() -> None:
    hashed_password = hash_password(
        TEST_PASSWORD
    )

    assert verify_password(
        TEST_PASSWORD,
        hashed_password,
    ) is True

    assert verify_password(
        "WrongPassword2026!",
        hashed_password,
    ) is False


def test_access_token_creation() -> None:
    token = create_access_token(
        {
            "username": "test_user",
        }
    )

    assert token
    assert isinstance(
        token,
        str,
    )
    assert token.count(".") == 2

