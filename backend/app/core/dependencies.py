"""Authentication and database dependencies for Blue-Trading-AI."""

from __future__ import annotations

from collections.abc import Generator
from typing import Any, Final, Mapping

from fastapi import (
    Depends,
    HTTPException,
    Request,
    status,
)
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session

from app.core.security import decode_access_token
from app.database.connection import SessionLocal
from app.models.auth_session import AuthSession
from app.models.user import (
    ACCOUNT_STATUS_APPROVED,
    ACCOUNT_STATUS_PENDING,
    ACCOUNT_STATUS_REJECTED,
    ACCOUNT_STATUS_SUSPENDED,
    User,
)
from app.services.auth_session_service import (
    validate_auth_session,
)


MAXIMUM_EMAIL_LENGTH: Final[int] = 320
MAXIMUM_USERNAME_LENGTH: Final[int] = 150
MAXIMUM_SESSION_ID_LENGTH: Final[int] = 256
MAXIMUM_JWT_ID_LENGTH: Final[int] = 256
MAXIMUM_ACCOUNT_STATUS_LENGTH: Final[int] = 64


oauth2_scheme = OAuth2PasswordBearer(
    tokenUrl="/auth/login",
)


def get_db() -> Generator[Session, None, None]:
    """
    Provide one database session for request dependencies.

    The transaction is rolled back when a dependency or route raises,
    and the SQLAlchemy session is always closed.
    """

    db = SessionLocal()

    try:
        yield db
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


def _credentials_exception(
    detail: str = (
        "Invalid or expired authentication token."
    ),
) -> HTTPException:
    """Build one consistent OAuth2 authentication error."""

    return HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail=detail,
        headers={
            "WWW-Authenticate": "Bearer",
        },
    )


def _approval_exception(
    account_status: str,
) -> HTTPException:
    """Build the correct access error for a non-approved account."""

    resolved_status = str(
        account_status
        or ACCOUNT_STATUS_PENDING
    ).strip().upper()[
        :MAXIMUM_ACCOUNT_STATUS_LENGTH
    ]

    messages = {
        ACCOUNT_STATUS_PENDING: (
            "Your account is pending owner approval."
        ),
        ACCOUNT_STATUS_REJECTED: (
            "Your Blue-Trading-AI access request was rejected."
        ),
        ACCOUNT_STATUS_SUSPENDED: (
            "Your Blue-Trading-AI account is suspended."
        ),
        "INACTIVE": (
            "Your Blue-Trading-AI account is inactive."
        ),
        "BLOCKED": (
            "Your Blue-Trading-AI account is blocked."
        ),
        "DISABLED": (
            "Your Blue-Trading-AI account is disabled."
        ),
    }

    return HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail={
            "message": messages.get(
                resolved_status,
                (
                    "Your account is not approved "
                    "for platform access."
                ),
            ),
            "account_status": resolved_status,
            "owner_approval_required": True,
            "can_access_platform": False,
        },
    )


def _normalise_boolean_claim(
    value: Any,
    *,
    default: bool = False,
) -> bool:
    """Resolve one JWT boolean claim without truthy-string mistakes."""

    if isinstance(value, bool):
        return value

    if isinstance(value, int):
        if value == 1:
            return True

        if value == 0:
            return False

        return default

    if isinstance(value, str):
        normalized = value.strip().lower()

        if normalized in {
            "true",
            "1",
            "yes",
            "approved",
            "enabled",
        }:
            return True

        if normalized in {
            "false",
            "0",
            "no",
            "pending",
            "rejected",
            "disabled",
        }:
            return False

    return default


def _positive_integer_claim(
    payload: Mapping[str, Any],
    claim: str,
    *,
    error_detail: str,
) -> int:
    """Return one required positive integer JWT claim."""

    value = payload.get(claim)

    if isinstance(value, bool):
        raise _credentials_exception(
            error_detail
        )

    try:
        resolved = int(value)
    except (
        TypeError,
        ValueError,
        OverflowError,
    ):
        raise _credentials_exception(
            error_detail
        ) from None

    if resolved < 1:
        raise _credentials_exception(
            error_detail
        )

    return resolved


def _required_text_claim(
    payload: Mapping[str, Any],
    claim: str,
    *,
    maximum_length: int,
    error_detail: str,
    lowercase: bool = False,
) -> str:
    """Return one required bounded text claim."""

    value = payload.get(claim)

    if not isinstance(value, str):
        raise _credentials_exception(
            error_detail
        )

    resolved = value.strip()

    if lowercase:
        resolved = resolved.lower()

    if (
        not resolved
        or len(resolved) > maximum_length
    ):
        raise _credentials_exception(
            error_detail
        )

    return resolved


def get_token_claims(
    token: str = Depends(oauth2_scheme),
) -> dict[str, Any]:
    """
    Decode and validate JWT identity, session, and password claims.
    """

    payload = decode_access_token(
        token
    )

    if not isinstance(
        payload,
        Mapping,
    ):
        raise _credentials_exception()

    subject = _required_text_claim(
        payload,
        "sub",
        maximum_length=MAXIMUM_EMAIL_LENGTH,
        error_detail=(
            "Authentication token is missing required user claims."
        ),
        lowercase=True,
    )

    raw_email = payload.get(
        "email"
    )

    if raw_email is None:
        email = subject
    else:
        email = _required_text_claim(
            payload,
            "email",
            maximum_length=MAXIMUM_EMAIL_LENGTH,
            error_detail=(
                "Authentication token is missing required user claims."
            ),
            lowercase=True,
        )

    username = _required_text_claim(
        payload,
        "username",
        maximum_length=MAXIMUM_USERNAME_LENGTH,
        error_detail=(
            "Authentication token is missing required user claims."
        ),
    )

    session_id = _required_text_claim(
        payload,
        "sid",
        maximum_length=MAXIMUM_SESSION_ID_LENGTH,
        error_detail=(
            "Authentication token is missing secure session claims."
        ),
    )

    jwt_id = _required_text_claim(
        payload,
        "jti",
        maximum_length=MAXIMUM_JWT_ID_LENGTH,
        error_detail=(
            "Authentication token is missing secure session claims."
        ),
    )

    if subject != email:
        raise _credentials_exception(
            "Authentication token user identity is inconsistent."
        )

    resolved_user_id = _positive_integer_claim(
        payload,
        "user_id",
        error_detail=(
            "Authentication token is missing "
            "a valid user identifier."
        ),
    )

    resolved_password_version = _positive_integer_claim(
        payload,
        "password_version",
        error_detail=(
            "Authentication token is missing "
            "password security claims."
        ),
    )

    account_status = str(
        payload.get(
            "account_status"
        )
        or ""
    ).strip().upper()[
        :MAXIMUM_ACCOUNT_STATUS_LENGTH
    ]

    return {
        "sub": subject,
        "user_id": resolved_user_id,
        "username": username,
        "email": email,
        "account_status": account_status,
        "owner_approved": (
            _normalise_boolean_claim(
                payload.get(
                    "owner_approved"
                ),
                default=False,
            )
        ),
        "password_version": (
            resolved_password_version
        ),
        "session_id": session_id,
        "jwt_id": jwt_id,
    }


def get_current_user(
    request: Request,
    claims: dict[str, Any] = Depends(
        get_token_claims
    ),
    db: Session = Depends(get_db),
) -> User:
    """
    Return the current user only when the JWT and live session remain valid.

    Checks:
    - The database user still exists.
    - Token identity still matches the database.
    - Account remains active and approved.
    - Token password version matches the database.
    - The linked session exists and belongs to the user.
    - The JWT ID matches the stored session hash.
    - The session is active, unrevoked, and unexpired.
    """

    user_id = int(
        claims["user_id"]
    )

    user = (
        db.query(User)
        .filter(
            User.id == user_id
        )
        .first()
    )

    if not user:
        raise _credentials_exception(
            "The user linked to this token no longer exists."
        )

    database_email = str(
        user.email or ""
    ).strip().lower()

    database_username = str(
        user.username or ""
    ).strip()

    if (
        not database_email
        or len(database_email) > MAXIMUM_EMAIL_LENGTH
        or database_email
        != claims["email"]
    ):
        raise _credentials_exception(
            "Authentication token user identity is inconsistent."
        )

    if (
        not database_username
        or len(database_username) > MAXIMUM_USERNAME_LENGTH
        or database_username
        != claims["username"]
    ):
        raise _credentials_exception(
            "Authentication token username is inconsistent."
        )

    database_account_status = str(
        user.account_status
        or ACCOUNT_STATUS_PENDING
    ).strip().upper()[
        :MAXIMUM_ACCOUNT_STATUS_LENGTH
    ]

    if (
        user.is_active is not True
        or database_account_status
        != ACCOUNT_STATUS_APPROVED
    ):
        raise _approval_exception(
            database_account_status
        )

    raw_password_version = (
        user.password_version
        if user.password_version is not None
        else 1
    )

    if isinstance(
        raw_password_version,
        bool,
    ):
        raise _credentials_exception(
            "User password security state is invalid."
        )

    try:
        database_password_version = int(
            raw_password_version
        )
    except (
        TypeError,
        ValueError,
        OverflowError,
    ):
        raise _credentials_exception(
            "User password security state is invalid."
        ) from None

    if database_password_version < 1:
        raise _credentials_exception(
            "User password security state is invalid."
        )

    token_password_version = int(
        claims[
            "password_version"
        ]
    )

    if (
        token_password_version
        != database_password_version
    ):
        raise _credentials_exception(
            "Your password has changed. Please log in again."
        )

    auth_session = validate_auth_session(
        db,
        session_id=claims[
            "session_id"
        ],
        jwt_id=claims[
            "jwt_id"
        ],
        user_id=int(
            user.id
        ),
        password_version=(
            database_password_version
        ),
        touch=True,
        commit=True,
    )

    if auth_session is None:
        raise _credentials_exception(
            "This login session is expired, revoked or invalid. "
            "Please log in again."
        )

    if (
        int(auth_session.user_id)
        != int(user.id)
    ):
        raise _credentials_exception(
            "Authenticated session user mismatch."
        )

    request.state.auth_session = (
        auth_session
    )
    request.state.auth_session_id = (
        auth_session.session_id
    )
    request.state.auth_token_claims = (
        dict(claims)
    )
    request.state.current_user_id = int(
        user.id
    )

    return user


def get_current_auth_session(
    request: Request,
    current_user: User = Depends(
        get_current_user
    ),
) -> AuthSession:
    """
    Return the validated database session attached to the request.
    """

    auth_session = getattr(
        request.state,
        "auth_session",
        None,
    )

    if not isinstance(
        auth_session,
        AuthSession,
    ):
        raise _credentials_exception(
            "Authenticated session context is unavailable."
        )

    if (
        int(auth_session.user_id)
        != int(current_user.id)
    ):
        raise _credentials_exception(
            "Authenticated session user mismatch."
        )

    return auth_session


def require_authenticated_user(
    current_user: User = Depends(
        get_current_user
    ),
) -> User:
    """
    Require an active, approved user with a live session.
    """

    return current_user


def require_approved_user(
    current_user: User = Depends(
        get_current_user
    ),
) -> User:
    """
    Explicit alias for routes requiring owner-approved access.
    """

    return current_user


__all__ = [
    "get_current_auth_session",
    "get_current_user",
    "get_db",
    "get_token_claims",
    "oauth2_scheme",
    "require_approved_user",
    "require_authenticated_user",
]