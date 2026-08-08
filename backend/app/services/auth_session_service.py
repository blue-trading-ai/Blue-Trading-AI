"""Database-backed authentication session service for Blue-Trading-AI."""

from __future__ import annotations

import hashlib
import secrets
from datetime import datetime, timezone
from typing import Any, Final

from fastapi import Request
from sqlalchemy.orm import Session

from app.models.auth_session import (
    AuthSession,
    SESSION_REVOKE_ALL_DEVICES,
    SESSION_REVOKE_SECURITY_EVENT,
    SESSION_STATUS_ACTIVE,
    SESSION_STATUS_EXPIRED,
    utc_now,
)


SESSION_ID_BYTES: Final[int] = 24
JWT_ID_BYTES: Final[int] = 32

MAX_SESSION_ID_LENGTH: Final[int] = 64
MAX_JWT_ID_LENGTH: Final[int] = 256
MAX_IP_LENGTH: Final[int] = 64
MAX_USER_AGENT_LENGTH: Final[int] = 500
MAX_REVOKE_REASON_LENGTH: Final[int] = 128
MAX_SESSION_LIST_LIMIT: Final[int] = 250


def _positive_int(
    value: Any,
    *,
    field_name: str,
) -> int:
    if isinstance(value, bool):
        raise ValueError(
            f"{field_name} must be a positive integer."
        )

    try:
        resolved = int(value)
    except (
        TypeError,
        ValueError,
        OverflowError,
    ) as exc:
        raise ValueError(
            f"{field_name} must be a positive integer."
        ) from exc

    if resolved < 1:
        raise ValueError(
            f"{field_name} must be a positive integer."
        )

    return resolved


def _bounded_identifier(
    value: Any,
    *,
    field_name: str,
    maximum_length: int,
) -> str:
    if not isinstance(value, str):
        raise ValueError(
            f"{field_name} must be a string."
        )

    resolved = value.strip()

    if not resolved:
        raise ValueError(
            f"{field_name} cannot be empty."
        )

    if len(resolved) > maximum_length:
        raise ValueError(
            f"{field_name} exceeds the maximum allowed length."
        )

    return resolved


def _bounded_reason(
    value: Any,
) -> str:
    resolved = str(
        value or SESSION_REVOKE_SECURITY_EVENT
    ).strip()

    if not resolved:
        resolved = SESSION_REVOKE_SECURITY_EVENT

    return resolved[
        :MAX_REVOKE_REASON_LENGTH
    ]


def generate_session_id() -> str:
    """
    Generate a public session identifier.

    The session ID identifies a login session but is not itself
    sufficient to authenticate a request.
    """

    return secrets.token_urlsafe(
        SESSION_ID_BYTES
    )[:MAX_SESSION_ID_LENGTH]


def generate_jwt_id() -> str:
    """
    Generate a cryptographically secure JWT ID.
    """

    return secrets.token_urlsafe(
        JWT_ID_BYTES
    )


def hash_jwt_id(
    jwt_id: str,
) -> str:
    """
    Hash a JWT ID before database storage.

    Raw JWT IDs and raw access tokens are never persisted.
    """

    resolved = _bounded_identifier(
        jwt_id,
        field_name="JWT ID",
        maximum_length=MAX_JWT_ID_LENGTH,
    )

    return hashlib.sha256(
        resolved.encode("utf-8")
    ).hexdigest()


def _normalise_datetime(
    value: datetime,
) -> datetime:
    """
    Return one timezone-aware UTC datetime.
    """

    if not isinstance(
        value,
        datetime,
    ):
        raise TypeError(
            "Session expiry must be a datetime."
        )

    if value.tzinfo is None:
        return value.replace(
            tzinfo=timezone.utc
        )

    return value.astimezone(
        timezone.utc
    )


def _request_metadata(
    request: Request | None,
) -> tuple[str | None, str | None]:
    """
    Extract safe client metadata from a FastAPI request.

    The direct ASGI client address is used instead of trusting
    X-Forwarded-For from arbitrary internet clients. A production
    reverse proxy should be configured to provide the trusted client
    address to the ASGI server.
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


def create_auth_session(
    db: Session,
    *,
    user_id: int,
    password_version: int,
    expires_at: datetime,
    request: Request | None = None,
    session_id: str | None = None,
    jwt_id: str | None = None,
    commit: bool = True,
) -> tuple[AuthSession, str]:
    """
    Create one database-backed login session.

    The caller owns the lifetime policy and supplies ``expires_at``.
    This service validates and stores that expiry without silently
    shortening or extending it.

    Returns:
    - the stored AuthSession model
    - the raw JWT ID to embed in the signed JWT

    The raw JWT ID is returned once and is never stored.
    """

    resolved_user_id = _positive_int(
        user_id,
        field_name="User ID",
    )

    resolved_password_version = _positive_int(
        password_version,
        field_name="Password version",
    )

    resolved_expiry = _normalise_datetime(
        expires_at
    )

    if resolved_expiry <= utc_now():
        raise ValueError(
            "Session expiry must be in the future."
        )

    if session_id is None:
        resolved_session_id = (
            generate_session_id()
        )
    else:
        resolved_session_id = (
            _bounded_identifier(
                session_id,
                field_name="Session ID",
                maximum_length=(
                    MAX_SESSION_ID_LENGTH
                ),
            )
        )

    if jwt_id is None:
        resolved_jwt_id = (
            generate_jwt_id()
        )
    else:
        resolved_jwt_id = (
            _bounded_identifier(
                jwt_id,
                field_name="JWT ID",
                maximum_length=(
                    MAX_JWT_ID_LENGTH
                ),
            )
        )

    token_jti_hash = hash_jwt_id(
        resolved_jwt_id
    )

    existing_session_id = (
        db.query(AuthSession)
        .filter(
            AuthSession.session_id
            == resolved_session_id
        )
        .first()
    )

    if existing_session_id:
        raise ValueError(
            "Session ID already exists."
        )

    existing_jti = (
        db.query(AuthSession)
        .filter(
            AuthSession.token_jti_hash
            == token_jti_hash
        )
        .first()
    )

    if existing_jti:
        raise ValueError(
            "JWT ID already exists."
        )

    ip_address, user_agent = (
        _request_metadata(
            request
        )
    )

    now = utc_now()

    auth_session = AuthSession(
        session_id=resolved_session_id,
        user_id=resolved_user_id,
        token_jti_hash=token_jti_hash,
        password_version=(
            resolved_password_version
        ),
        status=SESSION_STATUS_ACTIVE,
        is_active=True,
        issued_at=now,
        expires_at=resolved_expiry,
        last_seen_at=now,
        ip_address=ip_address,
        user_agent=user_agent,
        created_at=now,
        updated_at=now,
    )

    db.add(auth_session)

    if commit:
        try:
            db.commit()
            db.refresh(auth_session)
        except Exception:
            db.rollback()
            raise
    else:
        db.flush()

    return (
        auth_session,
        resolved_jwt_id,
    )


def get_session_by_id(
    db: Session,
    *,
    session_id: str,
) -> AuthSession | None:
    """
    Fetch a session by its public session identifier.
    """

    try:
        resolved = _bounded_identifier(
            session_id,
            field_name="Session ID",
            maximum_length=(
                MAX_SESSION_ID_LENGTH
            ),
        )
    except ValueError:
        return None

    return (
        db.query(AuthSession)
        .filter(
            AuthSession.session_id
            == resolved
        )
        .first()
    )


def get_session_by_jwt_id(
    db: Session,
    *,
    jwt_id: str,
) -> AuthSession | None:
    """
    Fetch a session using the hash of a JWT ID.
    """

    try:
        resolved = _bounded_identifier(
            jwt_id,
            field_name="JWT ID",
            maximum_length=(
                MAX_JWT_ID_LENGTH
            ),
        )
    except ValueError:
        return None

    return (
        db.query(AuthSession)
        .filter(
            AuthSession.token_jti_hash
            == hash_jwt_id(
                resolved
            )
        )
        .first()
    )


def validate_auth_session(
    db: Session,
    *,
    session_id: str,
    jwt_id: str,
    user_id: int,
    password_version: int,
    touch: bool = True,
    commit: bool = True,
) -> AuthSession | None:
    """
    Validate that a JWT is linked to one active database session.

    Returns None when:
    - the session is missing;
    - the JWT ID does not match;
    - the user does not match;
    - the password version changed;
    - the session was revoked;
    - the session expired.
    """

    try:
        resolved_user_id = (
            _positive_int(
                user_id,
                field_name="User ID",
            )
        )
        resolved_password_version = (
            _positive_int(
                password_version,
                field_name=(
                    "Password version"
                ),
            )
        )
        resolved_jwt_id = (
            _bounded_identifier(
                jwt_id,
                field_name="JWT ID",
                maximum_length=(
                    MAX_JWT_ID_LENGTH
                ),
            )
        )
    except ValueError:
        return None

    auth_session = get_session_by_id(
        db,
        session_id=session_id,
    )

    if auth_session is None:
        return None

    stored_hash = str(
        auth_session.token_jti_hash
        or ""
    ).strip()

    if not stored_hash:
        return None

    try:
        presented_hash = hash_jwt_id(
            resolved_jwt_id
        )
    except ValueError:
        return None

    if not secrets.compare_digest(
        stored_hash,
        presented_hash,
    ):
        return None

    try:
        session_user_id = int(
            auth_session.user_id
        )
        session_password_version = int(
            auth_session.password_version
            if auth_session.password_version
            is not None
            else 1
        )
    except (
        TypeError,
        ValueError,
        OverflowError,
    ):
        return None

    if (
        session_user_id
        != resolved_user_id
    ):
        return None

    if (
        session_password_version
        != resolved_password_version
    ):
        return None

    if auth_session.is_expired:
        if (
            auth_session.status
            != SESSION_STATUS_EXPIRED
            or auth_session.is_active
        ):
            auth_session.mark_expired()

            if commit:
                try:
                    db.commit()
                except Exception:
                    db.rollback()
                    raise
            else:
                db.flush()

        return None

    if not auth_session.can_authenticate:
        return None

    if touch:
        auth_session.touch()

        if commit:
            try:
                db.commit()
                db.refresh(
                    auth_session
                )
            except Exception:
                db.rollback()
                raise
        else:
            db.flush()

    return auth_session


def revoke_auth_session(
    db: Session,
    *,
    session_id: str,
    reason: str = (
        SESSION_REVOKE_SECURITY_EVENT
    ),
    user_id: int | None = None,
    commit: bool = True,
) -> bool:
    """
    Revoke one session.

    Supplying user_id prevents a user from revoking another
    user's session by guessing a session ID.
    """

    auth_session = get_session_by_id(
        db,
        session_id=session_id,
    )

    if auth_session is None:
        return False

    if user_id is not None:
        try:
            resolved_user_id = (
                _positive_int(
                    user_id,
                    field_name="User ID",
                )
            )
        except ValueError:
            return False

        if (
            int(auth_session.user_id)
            != resolved_user_id
        ):
            return False

    if not auth_session.is_active:
        return True

    auth_session.revoke(
        reason=_bounded_reason(
            reason
        )
    )

    if commit:
        try:
            db.commit()
            db.refresh(auth_session)
        except Exception:
            db.rollback()
            raise
    else:
        db.flush()

    return True


def revoke_all_user_sessions(
    db: Session,
    *,
    user_id: int,
    reason: str = (
        SESSION_REVOKE_ALL_DEVICES
    ),
    exclude_session_id: str | None = None,
    commit: bool = True,
) -> int:
    """
    Revoke every active session for one user.

    An optional current session may be excluded.
    """

    resolved_user_id = _positive_int(
        user_id,
        field_name="User ID",
    )

    query = (
        db.query(AuthSession)
        .filter(
            AuthSession.user_id
            == resolved_user_id,
            AuthSession.is_active.is_(
                True
            ),
        )
    )

    if exclude_session_id:
        try:
            resolved_excluded = (
                _bounded_identifier(
                    exclude_session_id,
                    field_name=(
                        "Excluded session ID"
                    ),
                    maximum_length=(
                        MAX_SESSION_ID_LENGTH
                    ),
                )
            )
        except ValueError:
            resolved_excluded = None

        if resolved_excluded:
            query = query.filter(
                AuthSession.session_id
                != resolved_excluded
            )

    sessions = query.all()
    revoked_count = 0
    resolved_reason = _bounded_reason(
        reason
    )

    for auth_session in sessions:
        auth_session.revoke(
            reason=resolved_reason
        )
        revoked_count += 1

    if revoked_count:
        if commit:
            try:
                db.commit()
            except Exception:
                db.rollback()
                raise
        else:
            db.flush()

    return revoked_count


def expire_old_sessions(
    db: Session,
    *,
    commit: bool = True,
) -> int:
    """
    Mark expired active sessions inactive.
    """

    now = utc_now()

    sessions = (
        db.query(AuthSession)
        .filter(
            AuthSession.is_active.is_(
                True
            ),
            AuthSession.expires_at
            <= now,
        )
        .all()
    )

    for auth_session in sessions:
        auth_session.mark_expired()

    if sessions:
        if commit:
            try:
                db.commit()
            except Exception:
                db.rollback()
                raise
        else:
            db.flush()

    return len(
        sessions
    )


def list_user_sessions(
    db: Session,
    *,
    user_id: int,
    active_only: bool = False,
    limit: int = 100,
) -> list[AuthSession]:
    """
    List a user's most recent sessions safely.
    """

    resolved_user_id = _positive_int(
        user_id,
        field_name="User ID",
    )

    if isinstance(limit, bool):
        resolved_limit = 100
    else:
        try:
            resolved_limit = int(
                limit
            )
        except (
            TypeError,
            ValueError,
            OverflowError,
        ):
            resolved_limit = 100

    resolved_limit = min(
        max(
            resolved_limit,
            1,
        ),
        MAX_SESSION_LIST_LIMIT,
    )

    query = (
        db.query(AuthSession)
        .filter(
            AuthSession.user_id
            == resolved_user_id
        )
    )

    if active_only is True:
        query = query.filter(
            AuthSession.is_active.is_(
                True
            ),
            AuthSession.status
            == SESSION_STATUS_ACTIVE,
            AuthSession.expires_at
            > utc_now(),
        )

    return (
        query
        .order_by(
            AuthSession.created_at.desc()
        )
        .limit(
            resolved_limit
        )
        .all()
    )


def session_public_payload(
    auth_session: AuthSession,
    *,
    current_session_id: str | None = None,
) -> dict[str, Any]:
    """
    Return safe session information for an API response.
    """

    if not isinstance(
        auth_session,
        AuthSession,
    ):
        raise TypeError(
            "auth_session must be an AuthSession instance."
        )

    payload = (
        auth_session.to_public_dict()
    )

    current_matches = False

    if current_session_id:
        resolved_current = str(
            current_session_id
        ).strip()

        stored_session_id = str(
            auth_session.session_id
            or ""
        ).strip()

        if (
            resolved_current
            and stored_session_id
            and len(resolved_current)
            <= MAX_SESSION_ID_LENGTH
        ):
            current_matches = (
                secrets.compare_digest(
                    stored_session_id,
                    resolved_current,
                )
            )

    payload["is_current"] = (
        current_matches
    )

    return payload


__all__ = [
    "JWT_ID_BYTES",
    "MAX_IP_LENGTH",
    "MAX_JWT_ID_LENGTH",
    "MAX_SESSION_ID_LENGTH",
    "MAX_USER_AGENT_LENGTH",
    "SESSION_ID_BYTES",
    "create_auth_session",
    "expire_old_sessions",
    "generate_jwt_id",
    "generate_session_id",
    "get_session_by_id",
    "get_session_by_jwt_id",
    "hash_jwt_id",
    "list_user_sessions",
    "revoke_all_user_sessions",
    "revoke_auth_session",
    "session_public_payload",
    "validate_auth_session",
]