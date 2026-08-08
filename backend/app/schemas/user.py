from __future__ import annotations

import re
from datetime import datetime

from pydantic import (
    BaseModel,
    ConfigDict,
    EmailStr,
    Field,
    field_validator,
)

from app.core.security import (
    MAXIMUM_PASSWORD_LENGTH,
    MINIMUM_PASSWORD_LENGTH,
    validate_password_strength,
)


USERNAME_PATTERN = re.compile(
    r"^[A-Za-z0-9_.-]+$"
)


class UserCreate(BaseModel):
    """
    Registration payload for a new Blue-Trading-AI user.
    """

    model_config = ConfigDict(
        extra="forbid",
        str_strip_whitespace=True,
    )

    username: str = Field(
        ...,
        min_length=3,
        max_length=100,
        examples=["niseanraj"],
    )

    email: EmailStr

    password: str = Field(
        ...,
        min_length=MINIMUM_PASSWORD_LENGTH,
        max_length=MAXIMUM_PASSWORD_LENGTH,
        examples=["StrongPass123!"],
    )

    @field_validator("username")
    @classmethod
    def validate_username(
        cls,
        value: str,
    ) -> str:
        """
        Allow only letters, numbers, underscore, dot, and hyphen.
        """

        cleaned = str(
            value or ""
        ).strip()

        if not USERNAME_PATTERN.fullmatch(
            cleaned
        ):
            raise ValueError(
                "Username may contain only letters, numbers, "
                "underscores, dots, and hyphens."
            )

        return cleaned

    @field_validator("email")
    @classmethod
    def normalise_email(
        cls,
        value: EmailStr,
    ) -> str:
        """Store email addresses in lowercase."""

        return str(
            value
        ).strip().lower()

    @field_validator("password")
    @classmethod
    def validate_password(
        cls,
        value: str,
    ) -> str:
        """Apply the shared backend password policy."""

        return validate_password_strength(
            value
        )


class UserLogin(BaseModel):
    """
    Optional JSON login schema.

    The active /auth/login endpoint uses OAuth2 form fields.
    """

    model_config = ConfigDict(
        extra="forbid",
        str_strip_whitespace=True,
    )

    email: EmailStr

    password: str = Field(
        ...,
        min_length=1,
        max_length=MAXIMUM_PASSWORD_LENGTH,
    )

    @field_validator("email")
    @classmethod
    def normalise_login_email(
        cls,
        value: EmailStr,
    ) -> str:
        return str(
            value
        ).strip().lower()


class UserPublic(BaseModel):
    """
    Safe user information returned by authentication endpoints.
    """

    model_config = ConfigDict(
        from_attributes=True,
        extra="ignore",
    )

    id: int
    username: str
    email: EmailStr

    is_email_verified: bool = False
    email_verified_at: datetime | None = None
    email_verification_requested_at: datetime | None = None

    roles: list[str] = Field(
        default_factory=list
    )
    permissions: list[str] = Field(
        default_factory=list
    )

    is_active: bool
    account_status: str = "PENDING"
    is_approved: bool = False
    can_access_platform: bool = False
    is_owner: bool = False

    password_version: int = 1
    password_changed_at: datetime | None = None

    failed_login_attempts: int = 0
    last_failed_login_at: datetime | None = None
    locked_until: datetime | None = None
    is_login_locked: bool = False
    lockout_seconds_remaining: int = 0

    last_login_at: datetime | None = None
    approved_at: datetime | None = None
    created_at: datetime | None = None

    @field_validator(
        "account_status"
    )
    @classmethod
    def normalize_account_status(
        cls,
        value: str,
    ) -> str:
        resolved = str(
            value or "PENDING"
        ).strip().upper()

        return resolved or "PENDING"


class TokenResponse(BaseModel):
    """
    Authentication token response.

    Extra fields are allowed because login and refresh responses
    include session and refresh-token metadata.
    """

    model_config = ConfigDict(
        extra="allow",
    )

    access_token: str
    refresh_token: str | None = None
    token_type: str = "bearer"
    refresh_token_type: str | None = None
    user: UserPublic | None = None


__all__ = [
    "TokenResponse",
    "UserCreate",
    "UserLogin",
    "UserPublic",
]