from __future__ import annotations

import hmac
import re
from datetime import (
    datetime,
    timedelta,
    timezone,
)
from typing import Any

from jose import JWTError, jwt
from passlib.context import CryptContext

from app.core.config import settings


DEFAULT_ACCESS_TOKEN_EXPIRE_MINUTES = 30

JWT_TOKEN_TYPE = "access"
JWT_REFRESH_TOKEN_TYPE = "refresh"

MINIMUM_PASSWORD_LENGTH = 10
MAXIMUM_PASSWORD_LENGTH = 128

MAXIMUM_BCRYPT_PASSWORD_BYTES = 72

PASSWORD_COMPLEXITY_PATTERN = re.compile(
    r"^(?=.*[a-z])(?=.*[A-Z])(?=.*\d)"
    r"(?=.*[^A-Za-z0-9]).+$"
)

JWT_CLOCK_SKEW_SECONDS = 5


pwd_context = CryptContext(
    schemes=["bcrypt"],
    deprecated="auto",
)


def _normalise_token(
    token: str,
) -> str:
    """Return one trimmed JWT string."""

    return str(token or "").strip()


def _normalise_required_claim(
    payload: dict[str, Any],
    claim: str,
) -> str | None:
    """Return one non-empty required JWT claim as text."""

    value = payload.get(claim)

    if value is None:
        return None

    resolved = str(value).strip()

    return resolved or None


def _normalise_datetime(
    value: datetime,
) -> datetime:
    """Return one timezone-aware UTC datetime."""

    if value.tzinfo is None:
        return value.replace(
            tzinfo=timezone.utc
        )

    return value.astimezone(
        timezone.utc
    )


def _validate_password_byte_length(
    password: str,
) -> None:
    """
    Reject passwords that exceed bcrypt's safe 72-byte limit.

    bcrypt truncates input after 72 bytes. Rejecting longer values
    prevents two different long passwords from producing equivalent
    bcrypt input.
    """

    password_bytes = password.encode(
        "utf-8"
    )

    if (
        len(password_bytes)
        > MAXIMUM_BCRYPT_PASSWORD_BYTES
    ):
        raise ValueError(
            "Password must not exceed "
            f"{MAXIMUM_BCRYPT_PASSWORD_BYTES} UTF-8 bytes."
        )


def validate_password_strength(
    password: str,
) -> str:
    """Validate and return one strong plain-text password."""

    resolved_password = str(
        password or ""
    )

    if not resolved_password:
        raise ValueError(
            "Password cannot be empty."
        )

    if "\x00" in resolved_password:
        raise ValueError(
            "Password contains an invalid null character."
        )

    if (
        len(resolved_password)
        < MINIMUM_PASSWORD_LENGTH
    ):
        raise ValueError(
            "Password must contain at least "
            f"{MINIMUM_PASSWORD_LENGTH} characters."
        )

    if (
        len(resolved_password)
        > MAXIMUM_PASSWORD_LENGTH
    ):
        raise ValueError(
            "Password must not exceed "
            f"{MAXIMUM_PASSWORD_LENGTH} characters."
        )

    _validate_password_byte_length(
        resolved_password
    )

    if not PASSWORD_COMPLEXITY_PATTERN.match(
        resolved_password
    ):
        raise ValueError(
            "Password must include at least one uppercase letter, "
            "one lowercase letter, one number, and one special character."
        )

    return resolved_password


def hash_password(
    password: str,
    *,
    validate_strength: bool = True,
) -> str:
    """Hash a plain-text password using bcrypt."""

    resolved_password = str(
        password or ""
    )

    if validate_strength:
        resolved_password = (
            validate_password_strength(
                resolved_password
            )
        )
    else:
        if not resolved_password:
            raise ValueError(
                "Password cannot be empty."
            )

        if "\x00" in resolved_password:
            raise ValueError(
                "Password contains an invalid null character."
            )

        _validate_password_byte_length(
            resolved_password
        )

    return pwd_context.hash(
        resolved_password
    )


def decode_refresh_token(
    token: str,
) -> dict[str, Any] | None:
    """
    Decode and validate one refresh-token JWT.

    Returns None when the token is invalid, expired, incomplete,
    or not a refresh token.
    """

    resolved = _normalise_token(
        token
    )

    if not resolved:
        return None

    try:
        payload = jwt.decode(
            resolved,
            settings.SECRET_KEY,
            algorithms=[
                settings.ALGORITHM
            ],
            options={
                "verify_signature": True,
                "verify_exp": True,
                "verify_iat": True,
                "verify_nbf": True,
                "verify_jti": True,
                "require_exp": True,
                "require_iat": True,
                "require_nbf": True,
                "require_jti": True,
                "leeway": JWT_CLOCK_SKEW_SECONDS,
            },
        )
    except JWTError:
        return None

    if (
        payload.get("type")
        != JWT_REFRESH_TOKEN_TYPE
    ):
        return None

    required_claims = (
        "jti",
        "sid",
        "fid",
        "sub",
        "user_id",
        "password_version",
    )

    for claim in required_claims:
        if (
            _normalise_required_claim(
                payload,
                claim,
            )
            is None
        ):
            return None

    return payload


def verify_password(
    plain_password: str,
    hashed_password: str,
) -> bool:
    """Verify a plain-text password against a stored hash."""

    if (
        not plain_password
        or not hashed_password
    ):
        return False

    resolved_password = str(
        plain_password
    )

    try:
        _validate_password_byte_length(
            resolved_password
        )
    except ValueError:
        return False

    try:
        return pwd_context.verify(
            resolved_password,
            str(hashed_password),
        )
    except (
        ValueError,
        TypeError,
    ):
        return False


def password_needs_rehash(
    hashed_password: str,
) -> bool:
    """Return whether a stored password hash should be upgraded."""

    if not hashed_password:
        return True

    try:
        return pwd_context.needs_update(
            hashed_password
        )
    except (
        ValueError,
        TypeError,
    ):
        return True


def verify_and_update_password(
    plain_password: str,
    hashed_password: str,
) -> tuple[bool, str | None]:
    """Verify a password and optionally return an upgraded hash."""

    if (
        not plain_password
        or not hashed_password
    ):
        return False, None

    resolved_password = str(
        plain_password
    )

    try:
        _validate_password_byte_length(
            resolved_password
        )
    except ValueError:
        return False, None

    try:
        verified, new_hash = (
            pwd_context.verify_and_update(
                resolved_password,
                str(hashed_password),
            )
        )
    except (
        ValueError,
        TypeError,
    ):
        return False, None

    return bool(verified), new_hash


def passwords_match(
    first_password: str,
    second_password: str,
) -> bool:
    """Compare two plain-text password values safely."""

    first = str(
        first_password or ""
    )

    second = str(
        second_password or ""
    )

    if not first or not second:
        return False

    return hmac.compare_digest(
        first.encode("utf-8"),
        second.encode("utf-8"),
    )


def ensure_password_changed(
    *,
    current_password: str,
    new_password: str,
    current_password_hash: str,
) -> str:
    """Validate one password-change request."""

    if not verify_password(
        current_password,
        current_password_hash,
    ):
        raise ValueError(
            "Current password is incorrect."
        )

    validated_new_password = (
        validate_password_strength(
            new_password
        )
    )

    if verify_password(
        validated_new_password,
        current_password_hash,
    ):
        raise ValueError(
            "New password must be different from the current password."
        )

    return validated_new_password


def get_access_token_expiry_minutes() -> int:
    """Return the configured access-token lifetime."""

    configured_value = getattr(
        settings,
        "ACCESS_TOKEN_EXPIRE_MINUTES",
        DEFAULT_ACCESS_TOKEN_EXPIRE_MINUTES,
    )

    try:
        resolved_value = int(
            configured_value
        )
    except (
        TypeError,
        ValueError,
    ):
        resolved_value = (
            DEFAULT_ACCESS_TOKEN_EXPIRE_MINUTES
        )

    return max(
        resolved_value,
        1,
    )


def get_access_token_expiry(
    expires_delta: timedelta | None = None,
) -> datetime:
    """Return the exact UTC expiry used for an access token."""

    now = datetime.now(
        timezone.utc
    )

    return now + (
        expires_delta
        if expires_delta is not None
        else timedelta(
            minutes=(
                get_access_token_expiry_minutes()
            )
        )
    )


def create_access_token(
    data: dict[str, Any],
    expires_delta: timedelta | None = None,
    *,
    session_id: str | None = None,
    jwt_id: str | None = None,
    expires_at: datetime | None = None,
) -> str:
    """
    Create a signed JWT access token.

    Optional database-session claims:
    - sid: public session identifier
    - jti: cryptographically secure JWT identifier
    """

    now = datetime.now(
        timezone.utc
    )

    if expires_at is not None:
        expire = _normalise_datetime(
            expires_at
        )
    else:
        expire = get_access_token_expiry(
            expires_delta
        )

    if expire <= now:
        raise ValueError(
            "Access-token expiry must be in the future."
        )

    to_encode = dict(data)

    if session_id is not None:
        resolved_session_id = str(
            session_id
        ).strip()

        if not resolved_session_id:
            raise ValueError(
                "Session ID cannot be empty."
            )

        to_encode["sid"] = (
            resolved_session_id
        )

    if jwt_id is not None:
        resolved_jwt_id = str(
            jwt_id
        ).strip()

        if not resolved_jwt_id:
            raise ValueError(
                "JWT ID cannot be empty."
            )

        to_encode["jti"] = (
            resolved_jwt_id
        )

    to_encode.update(
        {
            "exp": expire,
            "iat": now,
            "nbf": now,
            "type": JWT_TOKEN_TYPE,
        }
    )

    return jwt.encode(
        to_encode,
        settings.SECRET_KEY,
        algorithm=(
            settings.ALGORITHM
        ),
    )


def create_refresh_token_jwt(
    data: dict[str, Any],
    *,
    token_id: str,
    session_id: str,
    family_id: str,
    expires_at: datetime,
) -> str:
    """
    Create a signed refresh-token JWT.

    Refresh-token claims:
    - jti: refresh-token identifier
    - sid: authentication-session identifier
    - fid: refresh-token family identifier
    - type: refresh
    """

    now = datetime.now(
        timezone.utc
    )

    resolved_expiry = (
        _normalise_datetime(
            expires_at
        )
    )

    if resolved_expiry <= now:
        raise ValueError(
            "Refresh-token expiry must be in the future."
        )

    resolved_token_id = str(
        token_id or ""
    ).strip()

    resolved_session_id = str(
        session_id or ""
    ).strip()

    resolved_family_id = str(
        family_id or ""
    ).strip()

    if not resolved_token_id:
        raise ValueError(
            "Refresh token ID cannot be empty."
        )

    if not resolved_session_id:
        raise ValueError(
            "Session ID cannot be empty."
        )

    if not resolved_family_id:
        raise ValueError(
            "Refresh-token family ID cannot be empty."
        )

    to_encode = dict(data)

    to_encode.update(
        {
            "jti": resolved_token_id,
            "sid": resolved_session_id,
            "fid": resolved_family_id,
            "exp": resolved_expiry,
            "iat": now,
            "nbf": now,
            "type": (
                JWT_REFRESH_TOKEN_TYPE
            ),
        }
    )

    return jwt.encode(
        to_encode,
        settings.SECRET_KEY,
        algorithm=(
            settings.ALGORITHM
        ),
    )


def decode_access_token(
    token: str,
) -> dict[str, Any] | None:
    """Decode and validate one JWT access token."""

    resolved = _normalise_token(
        token
    )

    if not resolved:
        return None

    try:
        payload = jwt.decode(
            resolved,
            settings.SECRET_KEY,
            algorithms=[
                settings.ALGORITHM
            ],
            options={
                "verify_signature": True,
                "verify_exp": True,
                "verify_nbf": True,
                "verify_iat": True,
                "verify_jti": True,
                "require_exp": True,
                "require_iat": True,
                "require_nbf": True,
                "leeway": JWT_CLOCK_SKEW_SECONDS,
            },
        )
    except JWTError:
        return None

    if (
        payload.get("type")
        != JWT_TOKEN_TYPE
    ):
        return None

    session_id = payload.get(
        "sid"
    )

    jwt_id = payload.get(
        "jti"
    )

    if (
        session_id is None
    ) != (
        jwt_id is None
    ):
        return None

    if session_id is not None:
        if (
            _normalise_required_claim(
                payload,
                "sid",
            )
            is None
        ):
            return None

        if (
            _normalise_required_claim(
                payload,
                "jti",
            )
            is None
        ):
            return None

    return payload


def utc_now() -> datetime:
    """Return a timezone-aware UTC timestamp."""

    return datetime.now(
        timezone.utc
    )


__all__ = [
    "DEFAULT_ACCESS_TOKEN_EXPIRE_MINUTES",
    "JWT_CLOCK_SKEW_SECONDS",
    "JWT_REFRESH_TOKEN_TYPE",
    "JWT_TOKEN_TYPE",
    "MAXIMUM_BCRYPT_PASSWORD_BYTES",
    "MAXIMUM_PASSWORD_LENGTH",
    "MINIMUM_PASSWORD_LENGTH",
    "PASSWORD_COMPLEXITY_PATTERN",
    "create_access_token",
    "create_refresh_token_jwt",
    "decode_access_token",
    "decode_refresh_token",
    "ensure_password_changed",
    "get_access_token_expiry",
    "get_access_token_expiry_minutes",
    "hash_password",
    "password_needs_rehash",
    "passwords_match",
    "pwd_context",
    "utc_now",
    "validate_password_strength",
    "verify_and_update_password",
    "verify_password",
]