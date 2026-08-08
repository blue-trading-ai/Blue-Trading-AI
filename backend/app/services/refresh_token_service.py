from __future__ import annotations

import hashlib
import secrets
from datetime import datetime, timedelta, timezone
from typing import Final

from fastapi import Request
from sqlalchemy.orm import Session

from app.models.auth_session import AuthSession
from app.models.refresh_token import (
    REFRESH_REVOKE_ALL_DEVICES,
    REFRESH_REVOKE_REUSE_DETECTED,
    REFRESH_REVOKE_SECURITY_EVENT,
    REFRESH_STATUS_ACTIVE,
    REFRESH_STATUS_EXPIRED,
    REFRESH_STATUS_REUSED,
    RefreshToken,
    utc_now,
)


REFRESH_TOKEN_BYTES: Final[int] = 48
TOKEN_ID_BYTES: Final[int] = 24
FAMILY_ID_BYTES: Final[int] = 24

DEFAULT_REFRESH_TOKEN_DAYS: Final[int] = 30

MAX_RAW_TOKEN_LENGTH: Final[int] = 4096
MAX_TOKEN_ID_LENGTH: Final[int] = 64
MAX_FAMILY_ID_LENGTH: Final[int] = 64
MAX_SESSION_ID_LENGTH: Final[int] = 64
MAX_IP_LENGTH: Final[int] = 64
MAX_USER_AGENT_LENGTH: Final[int] = 500
MAX_REVOKE_REASON_LENGTH: Final[int] = 128
MAX_REFRESH_TOKEN_DAYS: Final[int] = 365


class RefreshTokenError(Exception):
    """
    Base exception for refresh-token failures.
    """


class InvalidRefreshTokenError(RefreshTokenError):
    """
    Raised when a refresh token is missing or invalid.
    """


class ExpiredRefreshTokenError(RefreshTokenError):
    """
    Raised when a refresh token has expired.
    """


class RevokedRefreshTokenError(RefreshTokenError):
    """
    Raised when a refresh token was revoked.
    """


class RefreshTokenReuseError(RefreshTokenError):
    """
    Raised when a consumed refresh token is reused.
    """


def generate_refresh_token() -> str:
    """
    Generate one cryptographically secure raw refresh token.
    """

    return secrets.token_urlsafe(
        REFRESH_TOKEN_BYTES
    )


def generate_token_id() -> str:
    """
    Generate one public refresh-token identifier.
    """

    return secrets.token_urlsafe(
        TOKEN_ID_BYTES
    )[:64]


def generate_family_id() -> str:
    """
    Generate one rotation-family identifier.
    """

    return secrets.token_urlsafe(
        FAMILY_ID_BYTES
    )[:64]


def hash_refresh_token(
    raw_token: str,
) -> str:
    """
    Hash a refresh token before database storage.
    """

    resolved = str(raw_token or "").strip()

    if not resolved:
        raise InvalidRefreshTokenError(
            "Refresh token cannot be empty."
        )

    if len(resolved) > MAX_RAW_TOKEN_LENGTH:
        raise InvalidRefreshTokenError(
            "Refresh token exceeds the maximum allowed length."
        )

    return hashlib.sha256(
        resolved.encode("utf-8")
    ).hexdigest()


def get_refresh_token_expiry(
    *,
    days: int = DEFAULT_REFRESH_TOKEN_DAYS,
) -> datetime:
    """
    Return the UTC expiry for a refresh token.
    """

    if isinstance(days, bool):
        raise InvalidRefreshTokenError(
            "Refresh-token lifetime must be a positive integer."
        )

    try:
        resolved_days = int(days)
    except (
        TypeError,
        ValueError,
        OverflowError,
    ) as exc:
        raise InvalidRefreshTokenError(
            "Refresh-token lifetime must be a positive integer."
        ) from exc

    if not (
        1 <= resolved_days <= MAX_REFRESH_TOKEN_DAYS
    ):
        raise InvalidRefreshTokenError(
            "Refresh-token lifetime is outside the allowed range."
        )

    return utc_now() + timedelta(
        days=resolved_days
    )


def _request_metadata(
    request: Request | None,
) -> tuple[str | None, str | None]:
    """
    Extract safe client metadata.

    The direct ASGI client address is used rather than trusting an
    arbitrary X-Forwarded-For header. A production reverse proxy
    should be configured to pass the trusted client address to the
    ASGI server.
    """

    if request is None:
        return None, None

    if request.client is not None:
        resolved_ip = str(
            request.client.host or ""
        ).strip()

        ip_address = (
            resolved_ip[:MAX_IP_LENGTH]
            if resolved_ip
            else None
        )
    else:
        ip_address = None

    raw_user_agent = request.headers.get(
        "user-agent"
    )

    if raw_user_agent:
        resolved_user_agent = str(
            raw_user_agent
        ).strip()

        user_agent = (
            resolved_user_agent[
                :MAX_USER_AGENT_LENGTH
            ]
            if resolved_user_agent
            else None
        )
    else:
        user_agent = None

    return ip_address, user_agent


def create_refresh_token(
    db: Session,
    *,
    user_id: int,
    session_id: str,
    password_version: int,
    request: Request | None = None,
    expires_at: datetime | None = None,
    family_id: str | None = None,
    parent_token_id: str | None = None,
    raw_token: str | None = None,
    token_id: str | None = None,
    commit: bool = True,
) -> tuple[RefreshToken, str]:
    """
    Create one refresh token.

    Returns:
    - stored RefreshToken row
    - raw refresh token, returned once and never persisted
    """

    if isinstance(user_id, bool) or isinstance(
        password_version,
        bool,
    ):
        raise InvalidRefreshTokenError(
            "Refresh-token identity claims are invalid."
        )

    try:
        resolved_user_id = int(user_id)
        resolved_password_version = int(
            password_version
        )
    except (
        TypeError,
        ValueError,
        OverflowError,
    ) as exc:
        raise InvalidRefreshTokenError(
            "Refresh-token identity claims are invalid."
        ) from exc

    if resolved_user_id < 1:
        raise InvalidRefreshTokenError(
            "User ID must be a positive integer."
        )

    if resolved_password_version < 1:
        raise InvalidRefreshTokenError(
            "Password version must be a positive integer."
        )

    resolved_session_id = str(
        session_id or ""
    ).strip()

    if (
        not resolved_session_id
        or len(resolved_session_id)
        > MAX_SESSION_ID_LENGTH
    ):
        raise InvalidRefreshTokenError(
            "Authentication session ID is invalid."
        )

    auth_session = (
        db.query(AuthSession)
        .filter(
            AuthSession.session_id
            == resolved_session_id
        )
        .first()
    )

    if auth_session is None:
        raise InvalidRefreshTokenError(
            "Authentication session does not exist."
        )

    if (
        int(auth_session.user_id)
        != resolved_user_id
    ):
        raise InvalidRefreshTokenError(
            "Authentication session user mismatch."
        )

    if (
        int(
            auth_session.password_version
            or 1
        )
        != resolved_password_version
    ):
        raise RevokedRefreshTokenError(
            "Authentication session password version mismatch."
        )

    if not auth_session.can_authenticate:
        raise RevokedRefreshTokenError(
            "Authentication session is inactive."
        )

    resolved_token = (
        str(raw_token).strip()
        if raw_token
        else generate_refresh_token()
    )

    resolved_token_id = (
        str(token_id).strip()
        if token_id
        else generate_token_id()
    )

    resolved_family_id = (
        str(family_id).strip()
        if family_id
        else generate_family_id()
    )

    if (
        not resolved_token_id
        or len(resolved_token_id)
        > MAX_TOKEN_ID_LENGTH
    ):
        raise InvalidRefreshTokenError(
            "Refresh token ID is invalid."
        )

    if (
        not resolved_family_id
        or len(resolved_family_id)
        > MAX_FAMILY_ID_LENGTH
    ):
        raise InvalidRefreshTokenError(
            "Refresh token family ID is invalid."
        )

    resolved_parent_token_id = (
        str(parent_token_id).strip()
        if parent_token_id
        else None
    )

    if (
        resolved_parent_token_id
        and len(resolved_parent_token_id)
        > MAX_TOKEN_ID_LENGTH
    ):
        raise InvalidRefreshTokenError(
            "Parent refresh token ID is invalid."
        )

    resolved_expiry = (
        expires_at
        if expires_at is not None
        else get_refresh_token_expiry()
    )

    if not isinstance(
        resolved_expiry,
        datetime,
    ):
        raise InvalidRefreshTokenError(
            "Refresh-token expiry must be a datetime."
        )

    if resolved_expiry.tzinfo is None:
        resolved_expiry = resolved_expiry.replace(
            tzinfo=timezone.utc
        )
    else:
        resolved_expiry = resolved_expiry.astimezone(
            timezone.utc
        )

    if resolved_expiry <= utc_now():
        raise ExpiredRefreshTokenError(
            "Refresh-token expiry must be in the future."
        )

    token_hash = hash_refresh_token(
        resolved_token
    )

    existing = (
        db.query(RefreshToken)
        .filter(
            (
                RefreshToken.token_id
                == resolved_token_id
            )
            |
            (
                RefreshToken.token_hash
                == token_hash
            )
        )
        .first()
    )

    if existing is not None:
        raise InvalidRefreshTokenError(
            "Refresh token identifier already exists."
        )

    ip_address, user_agent = _request_metadata(
        request
    )

    now = utc_now()

    record = RefreshToken(
        token_id=resolved_token_id,
        token_hash=token_hash,
        family_id=resolved_family_id,
        parent_token_id=resolved_parent_token_id,
        session_id=resolved_session_id,
        user_id=resolved_user_id,
        password_version=(
            resolved_password_version
        ),
        status=REFRESH_STATUS_ACTIVE,
        is_active=True,
        issued_at=now,
        expires_at=resolved_expiry,
        ip_address=ip_address,
        user_agent=user_agent,
        created_at=now,
        updated_at=now,
    )

    db.add(record)

    if commit:
        try:
            db.commit()
            db.refresh(record)
        except Exception:
            db.rollback()
            raise
    else:
        db.flush()

    return record, resolved_token


def get_refresh_token_by_raw(
    db: Session,
    *,
    raw_token: str,
) -> RefreshToken | None:
    """
    Fetch a refresh token using its stored hash.
    """

    token_hash = hash_refresh_token(
        raw_token
    )

    return (
        db.query(RefreshToken)
        .filter(
            RefreshToken.token_hash == token_hash
        )
        .first()
    )


def revoke_refresh_family(
    db: Session,
    *,
    family_id: str,
    reason: str = REFRESH_REVOKE_SECURITY_EVENT,
    mark_reuse: bool = False,
    commit: bool = True,
) -> int:
    """
    Revoke every active token in one rotation family.\n\n    ``mark_reuse`` is retained for API compatibility. Reuse status belongs\n    to the token that was actually replayed; other family members are revoked.\n    """

    resolved_family_id = str(
        family_id or ""
    ).strip()

    if (
        not resolved_family_id
        or len(resolved_family_id)
        > MAX_FAMILY_ID_LENGTH
    ):
        return 0

    resolved_reason = str(
        reason or REFRESH_REVOKE_SECURITY_EVENT
    ).strip()[:MAX_REVOKE_REASON_LENGTH]

    records = (
        db.query(RefreshToken)
        .filter(
            RefreshToken.family_id
            == resolved_family_id
        )
        .all()
    )

    changed = 0

    for record in records:
        if not record.is_active:
            continue

        record.revoke(
            reason=resolved_reason
        )
        changed += 1

    if changed:
        if commit:
            try:
                db.commit()
            except Exception:
                db.rollback()
                raise
        else:
            db.flush()

    return changed


def validate_refresh_token(
    db: Session,
    *,
    raw_token: str,
    user_id: int | None = None,
    session_id: str | None = None,
    password_version: int | None = None,
) -> RefreshToken:
    """
    Validate one refresh token.

    Reuse of a rotated or revoked token triggers family revocation.
    """

    record = get_refresh_token_by_raw(
        db,
        raw_token=raw_token,
    )

    if record is None:
        raise InvalidRefreshTokenError(
            "Refresh token is invalid."
        )

    if record.is_expired:
        if record.status != REFRESH_STATUS_EXPIRED:
            record.mark_expired()
            db.commit()

        raise ExpiredRefreshTokenError(
            "Refresh token has expired."
        )

    if not record.can_refresh:
        was_rotated = bool(
            getattr(
                record,
                "replacement_token_id",
                None,
            )
        )

        was_reused = (
            str(record.status).strip().upper()
            == REFRESH_STATUS_REUSED
        )

        if was_rotated or was_reused:
            if not was_reused:
                record.mark_reused()

            revoke_refresh_family(
                db,
                family_id=record.family_id,
                reason=REFRESH_REVOKE_REUSE_DETECTED,
                mark_reuse=False,
                commit=True,
            )

            raise RefreshTokenReuseError(
                "Refresh token reuse was detected."
            )

        raise RevokedRefreshTokenError(
            "Refresh token has been revoked."
        )

    if user_id is not None:
        if isinstance(user_id, bool):
            raise InvalidRefreshTokenError(
                "Refresh token user mismatch."
            )

        try:
            resolved_user_id = int(user_id)
        except (
            TypeError,
            ValueError,
            OverflowError,
        ) as exc:
            raise InvalidRefreshTokenError(
                "Refresh token user mismatch."
            ) from exc

        if (
            resolved_user_id < 1
            or int(record.user_id)
            != resolved_user_id
        ):
            raise InvalidRefreshTokenError(
                "Refresh token user mismatch."
            )

    if session_id is not None:
        resolved_session_id = str(
            session_id
        ).strip()

        if (
            not resolved_session_id
            or len(resolved_session_id)
            > MAX_SESSION_ID_LENGTH
            or str(record.session_id)
            != resolved_session_id
        ):
            raise InvalidRefreshTokenError(
                "Refresh token session mismatch."
            )

    if password_version is not None:
        if isinstance(
            password_version,
            bool,
        ):
            raise RevokedRefreshTokenError(
                "Password version changed."
            )

        try:
            resolved_password_version = int(
                password_version
            )
        except (
            TypeError,
            ValueError,
            OverflowError,
        ) as exc:
            raise RevokedRefreshTokenError(
                "Password version changed."
            ) from exc

        if (
            resolved_password_version < 1
            or int(record.password_version)
            != resolved_password_version
        ):
            raise RevokedRefreshTokenError(
                "Password version changed."
            )

    auth_session = (
        db.query(AuthSession)
        .filter(
            AuthSession.session_id
            == record.session_id
        )
        .first()
    )

    if auth_session is None:
        raise InvalidRefreshTokenError(
            "Authentication session is missing."
        )

    if not auth_session.can_authenticate:
        raise RevokedRefreshTokenError(
            "Authentication session is inactive."
        )

    if int(auth_session.user_id) != int(
        record.user_id
    ):
        raise InvalidRefreshTokenError(
            "Authentication session user mismatch."
        )

    if (
        int(
            auth_session.password_version
            or 1
        )
        != int(
            record.password_version
            or 1
        )
    ):
        raise RevokedRefreshTokenError(
            "Authentication session password version changed."
        )

    return record


def rotate_refresh_token(
    db: Session,
    *,
    raw_token: str,
    request: Request | None = None,
    expires_at: datetime | None = None,
    commit: bool = True,
) -> tuple[RefreshToken, RefreshToken, str]:
    """
    Consume one valid refresh token and issue its replacement.

    Returns:
    - old token record
    - new token record
    - new raw refresh token
    """

    current = validate_refresh_token(
        db,
        raw_token=raw_token,
    )

    replacement_id = generate_token_id()

    new_record, new_raw_token = create_refresh_token(
        db,
        user_id=int(current.user_id),
        session_id=current.session_id,
        password_version=int(
            current.password_version
        ),
        request=request,
        expires_at=(
            expires_at
            if expires_at is not None
            else current.expires_at
        ),
        family_id=current.family_id,
        parent_token_id=current.token_id,
        token_id=replacement_id,
        commit=False,
    )

    current.mark_rotated(
        replacement_token_id=replacement_id
    )

    if commit:
        try:
            db.commit()
            db.refresh(current)
            db.refresh(new_record)
        except Exception:
            db.rollback()
            raise
    else:
        db.flush()

    return current, new_record, new_raw_token


def revoke_session_refresh_tokens(
    db: Session,
    *,
    session_id: str,
    reason: str = REFRESH_REVOKE_SECURITY_EVENT,
    commit: bool = True,
) -> int:
    """
    Revoke all active refresh tokens for one session.
    """

    resolved_session_id = str(
        session_id or ""
    ).strip()

    if (
        not resolved_session_id
        or len(resolved_session_id)
        > MAX_SESSION_ID_LENGTH
    ):
        return 0

    resolved_reason = str(
        reason or REFRESH_REVOKE_SECURITY_EVENT
    ).strip()[:MAX_REVOKE_REASON_LENGTH]

    records = (
        db.query(RefreshToken)
        .filter(
            RefreshToken.session_id
            == resolved_session_id,
            RefreshToken.is_active.is_(True),
        )
        .all()
    )

    for record in records:
        record.revoke(
            reason=resolved_reason
        )

    if records:
        if commit:
            try:
                db.commit()
            except Exception:
                db.rollback()
                raise
        else:
            db.flush()

    return len(records)


def revoke_all_user_refresh_tokens(
    db: Session,
    *,
    user_id: int,
    reason: str = REFRESH_REVOKE_ALL_DEVICES,
    exclude_session_id: str | None = None,
    commit: bool = True,
) -> int:
    """
    Revoke all active refresh tokens for one user.
    """

    query = (
        db.query(RefreshToken)
        .filter(
            RefreshToken.user_id == int(user_id),
            RefreshToken.is_active.is_(True),
        )
    )

    if exclude_session_id:
        query = query.filter(
            RefreshToken.session_id
            != str(exclude_session_id).strip()
        )

    records = query.all()

    for record in records:
        record.revoke(
            reason=reason
        )

    if records:
        if commit:
            try:
                db.commit()
            except Exception:
                db.rollback()
                raise
        else:
            db.flush()

    return len(records)


def expire_old_refresh_tokens(
    db: Session,
    *,
    commit: bool = True,
) -> int:
    """
    Mark expired active refresh tokens inactive.
    """

    now = utc_now()

    records = (
        db.query(RefreshToken)
        .filter(
            RefreshToken.is_active.is_(True),
            RefreshToken.expires_at <= now,
        )
        .all()
    )

    for record in records:
        record.mark_expired()

    if records:
        if commit:
            try:
                db.commit()
            except Exception:
                db.rollback()
                raise
        else:
            db.flush()

    return len(records)


def refresh_token_public_payload(
    record: RefreshToken,
) -> dict[str, object]:
    """
    Return safe refresh-token metadata.
    """

    return record.to_public_dict()


__all__ = [
    "DEFAULT_REFRESH_TOKEN_DAYS",
    "ExpiredRefreshTokenError",
    "FAMILY_ID_BYTES",
    "InvalidRefreshTokenError",
    "MAX_FAMILY_ID_LENGTH",
    "MAX_IP_LENGTH",
    "MAX_RAW_TOKEN_LENGTH",
    "MAX_SESSION_ID_LENGTH",
    "MAX_TOKEN_ID_LENGTH",
    "MAX_USER_AGENT_LENGTH",
    "MAX_REFRESH_TOKEN_DAYS",
    "MAX_REVOKE_REASON_LENGTH",
    "REFRESH_TOKEN_BYTES",
    "RefreshTokenError",
    "RefreshTokenReuseError",
    "RevokedRefreshTokenError",
    "TOKEN_ID_BYTES",
    "create_refresh_token",
    "expire_old_refresh_tokens",
    "generate_family_id",
    "generate_refresh_token",
    "generate_token_id",
    "get_refresh_token_by_raw",
    "get_refresh_token_expiry",
    "hash_refresh_token",
    "refresh_token_public_payload",
    "revoke_all_user_refresh_tokens",
    "revoke_refresh_family",
    "revoke_session_refresh_tokens",
    "rotate_refresh_token",
    "validate_refresh_token",
]