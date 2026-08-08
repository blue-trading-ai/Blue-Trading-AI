from __future__ import annotations

import hashlib
import secrets
from datetime import datetime, timedelta, timezone
from typing import Final

from fastapi import Request
from sqlalchemy.orm import Session

from app.models.account_action_token import (
    AccountActionToken,
    TOKEN_PURPOSE_EMAIL_VERIFICATION,
    TOKEN_PURPOSE_PASSWORD_RESET,
    MAX_EMAIL_LENGTH,
    MAX_TOKEN_ID_LENGTH,
    TOKEN_REVOKE_REPLACED,
    TOKEN_REVOKE_SECURITY_EVENT,
    TOKEN_STATUS_ACTIVE,
    TOKEN_STATUS_EXPIRED,
)


ACCOUNT_TOKEN_BYTES: Final[int] = 48
TOKEN_ID_BYTES: Final[int] = 24
EMAIL_VERIFICATION_TOKEN_HOURS: Final[int] = 24
PASSWORD_RESET_TOKEN_MINUTES: Final[int] = 30
MAX_IP_LENGTH: Final[int] = 64
MAX_USER_AGENT_LENGTH: Final[int] = 500
MAX_RAW_TOKEN_LENGTH: Final[int] = 4096
MIN_RAW_TOKEN_LENGTH: Final[int] = 32

SUPPORTED_PURPOSES: Final[set[str]] = {
    TOKEN_PURPOSE_EMAIL_VERIFICATION,
    TOKEN_PURPOSE_PASSWORD_RESET,
}


class AccountActionTokenError(Exception):
    """
    Base exception for one-time account token failures.
    """


class InvalidAccountActionTokenError(
    AccountActionTokenError
):
    """
    Raised when a token is missing, malformed or unknown.
    """


class ExpiredAccountActionTokenError(
    AccountActionTokenError
):
    """
    Raised when a token has expired.
    """


class UsedAccountActionTokenError(
    AccountActionTokenError
):
    """
    Raised when a token was already consumed.
    """


class RevokedAccountActionTokenError(
    AccountActionTokenError
):
    """
    Raised when a token was revoked.
    """


def utc_now() -> datetime:
    """
    Return one timezone-aware UTC timestamp.
    """

    return datetime.now(timezone.utc)


def _normalise_positive_user_id(
    user_id: int,
) -> int:
    """Validate and return one positive user identifier."""

    try:
        resolved = int(user_id)
    except (TypeError, ValueError) as exc:
        raise ValueError(
            "User ID must be an integer."
        ) from exc

    if resolved < 1:
        raise ValueError(
            "User ID must be positive."
        )

    return resolved


def _normalise_raw_token(
    raw_token: str,
) -> str:
    """Validate and normalize one raw account-action token."""

    resolved = str(
        raw_token or ""
    ).strip()

    if not resolved:
        raise InvalidAccountActionTokenError(
            "Account-action token cannot be empty."
        )

    if len(resolved) < MIN_RAW_TOKEN_LENGTH:
        raise InvalidAccountActionTokenError(
            "Account-action token is malformed."
        )

    if len(resolved) > MAX_RAW_TOKEN_LENGTH:
        raise InvalidAccountActionTokenError(
            "Account-action token is too long."
        )

    if any(
        character.isspace()
        for character in resolved
    ):
        raise InvalidAccountActionTokenError(
            "Account-action token is malformed."
        )

    return resolved


def _normalise_email(
    email: str,
) -> str:
    """Validate and normalize one email address."""

    resolved = str(
        email or ""
    ).strip().lower()

    if (
        not resolved
        or len(resolved) > MAX_EMAIL_LENGTH
        or "@" not in resolved
    ):
        raise ValueError(
            "A valid email address is required."
        )

    return resolved


def _normalise_token_id(
    token_id: str,
) -> str:
    """Validate and normalize one public token identifier."""

    resolved = str(
        token_id or ""
    ).strip()

    if not resolved:
        raise InvalidAccountActionTokenError(
            "Token ID cannot be empty."
        )

    if len(resolved) > MAX_TOKEN_ID_LENGTH:
        raise InvalidAccountActionTokenError(
            "Token ID is too long."
        )

    if any(
        character.isspace()
        for character in resolved
    ):
        raise InvalidAccountActionTokenError(
            "Token ID is malformed."
        )

    return resolved


def generate_account_action_token() -> str:
    """
    Generate one cryptographically secure raw token.
    """

    return secrets.token_urlsafe(
        ACCOUNT_TOKEN_BYTES
    )


def generate_token_id() -> str:
    """
    Generate one public token identifier.
    """

    return secrets.token_urlsafe(
        TOKEN_ID_BYTES
    )[:64]


def hash_account_action_token(
    raw_token: str,
) -> str:
    """
    Hash a raw token before database storage.
    """

    resolved = _normalise_raw_token(
        raw_token
    )

    return hashlib.sha256(
        resolved.encode("utf-8")
    ).hexdigest()


def normalise_purpose(
    purpose: str,
) -> str:
    """
    Validate and normalise a token purpose.
    """

    resolved = str(purpose or "").strip().upper()

    if resolved not in SUPPORTED_PURPOSES:
        raise ValueError(
            "Unsupported account-action token purpose."
        )

    return resolved


def get_token_expiry(
    *,
    purpose: str,
) -> datetime:
    """
    Return the default expiry for a token purpose.
    """

    resolved_purpose = normalise_purpose(
        purpose
    )

    if (
        resolved_purpose
        == TOKEN_PURPOSE_EMAIL_VERIFICATION
    ):
        return utc_now() + timedelta(
            hours=EMAIL_VERIFICATION_TOKEN_HOURS
        )

    return utc_now() + timedelta(
        minutes=PASSWORD_RESET_TOKEN_MINUTES
    )


def _request_metadata(
    request: Request | None,
) -> tuple[str | None, str | None]:
    """
    Extract bounded request metadata.

    Proxy forwarding headers are intentionally not trusted. A
    production reverse proxy must configure the ASGI server to
    provide the trusted client address.
    """

    if request is None:
        return None, None

    if request.client is not None:
        ip_address = str(
            request.client.host or ""
        ).strip()[:MAX_IP_LENGTH] or None
    else:
        ip_address = None

    user_agent = request.headers.get(
        "user-agent"
    )

    if user_agent:
        user_agent = "".join(
            character
            if character.isprintable()
            and character not in {
                "\r",
                "\n",
                "\t",
            }
            else " "
            for character in str(user_agent)
        ).strip()[:MAX_USER_AGENT_LENGTH] or None
    else:
        user_agent = None

    return ip_address, user_agent


def revoke_active_tokens(
    db: Session,
    *,
    user_id: int,
    purpose: str,
    reason: str = TOKEN_REVOKE_REPLACED,
    commit: bool = True,
) -> int:
    """
    Revoke active tokens for one user and purpose.
    """

    resolved_purpose = normalise_purpose(
        purpose
    )
    resolved_user_id = (
        _normalise_positive_user_id(
            user_id
        )
    )

    records = (
        db.query(AccountActionToken)
        .filter(
            AccountActionToken.user_id
            == resolved_user_id,
            AccountActionToken.purpose
            == resolved_purpose,
            AccountActionToken.is_active.is_(
                True
            ),
        )
        .all()
    )

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


def create_account_action_token(
    db: Session,
    *,
    user_id: int,
    email: str,
    purpose: str,
    request: Request | None = None,
    expires_at: datetime | None = None,
    raw_token: str | None = None,
    token_id: str | None = None,
    revoke_previous: bool = True,
    commit: bool = True,
) -> tuple[AccountActionToken, str]:
    """
    Create one secure single-use account token.

    Returns:
    - stored database record
    - raw token returned once and never persisted
    """

    resolved_user_id = (
        _normalise_positive_user_id(
            user_id
        )
    )
    resolved_email = _normalise_email(
        email
    )

    resolved_purpose = normalise_purpose(
        purpose
    )

    if revoke_previous:
        revoke_active_tokens(
            db,
            user_id=resolved_user_id,
            purpose=resolved_purpose,
            reason=TOKEN_REVOKE_REPLACED,
            commit=False,
        )

    resolved_raw_token = _normalise_raw_token(
        raw_token
        if raw_token is not None
        else generate_account_action_token()
    )

    resolved_token_id = _normalise_token_id(
        token_id
        if token_id is not None
        else generate_token_id()
    )

    resolved_expiry = (
        expires_at
        if expires_at is not None
        else get_token_expiry(
            purpose=resolved_purpose
        )
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
        raise ExpiredAccountActionTokenError(
            "Token expiry must be in the future."
        )

    token_hash = hash_account_action_token(
        resolved_raw_token
    )

    existing = (
        db.query(AccountActionToken)
        .filter(
            (
                AccountActionToken.token_id
                == resolved_token_id
            )
            |
            (
                AccountActionToken.token_hash
                == token_hash
            )
        )
        .first()
    )

    if existing is not None:
        raise InvalidAccountActionTokenError(
            "Token identifier already exists."
        )

    request_ip, user_agent = _request_metadata(
        request
    )

    now = utc_now()

    record = AccountActionToken(
        token_id=resolved_token_id,
        token_hash=token_hash,
        user_id=resolved_user_id,
        email=resolved_email,
        purpose=resolved_purpose,
        status=TOKEN_STATUS_ACTIVE,
        is_active=True,
        issued_at=now,
        expires_at=resolved_expiry,
        request_ip=request_ip,
        user_agent=user_agent,
        created_at=now,
        updated_at=now,
    )

    record.validate_state()
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

    return record, resolved_raw_token


def get_token_record(
    db: Session,
    *,
    raw_token: str,
    purpose: str | None = None,
    lock_for_update: bool = False,
) -> AccountActionToken | None:
    """
    Fetch a token record using its stored hash.
    """

    token_hash = hash_account_action_token(
        raw_token
    )

    query = (
        db.query(AccountActionToken)
        .filter(
            AccountActionToken.token_hash
            == token_hash
        )
    )

    if purpose is not None:
        query = query.filter(
            AccountActionToken.purpose
            == normalise_purpose(purpose)
        )

    if lock_for_update:
        query = query.with_for_update()

    return query.first()


def validate_account_action_token(
    db: Session,
    *,
    raw_token: str,
    purpose: str,
    user_id: int | None = None,
    email: str | None = None,
    lock_for_update: bool = False,
) -> AccountActionToken:
    """
    Validate one account-action token without consuming it.
    """

    resolved_purpose = normalise_purpose(
        purpose
    )

    record = get_token_record(
        db,
        raw_token=raw_token,
        purpose=resolved_purpose,
        lock_for_update=lock_for_update,
    )

    if record is None:
        raise InvalidAccountActionTokenError(
            "Token is invalid."
        )

    if record.is_expired:
        if record.status != TOKEN_STATUS_EXPIRED:
            record.mark_expired()

        raise ExpiredAccountActionTokenError(
            "Token has expired."
        )

    if record.used_at is not None:
        raise UsedAccountActionTokenError(
            "Token was already used."
        )

    if not record.can_be_used:
        raise RevokedAccountActionTokenError(
            "Token is revoked or inactive."
        )

    if (
        user_id is not None
        and int(record.user_id)
        != _normalise_positive_user_id(
            user_id
        )
    ):
        raise InvalidAccountActionTokenError(
            "Token user mismatch."
        )

    if email is not None:
        resolved_email = _normalise_email(
            email
        )

        if record.email != resolved_email:
            raise InvalidAccountActionTokenError(
                "Token email mismatch."
            )

    return record


def consume_account_action_token(
    db: Session,
    *,
    raw_token: str,
    purpose: str,
    user_id: int | None = None,
    email: str | None = None,
    commit: bool = True,
) -> AccountActionToken:
    """
    Validate and permanently consume a token.
    """

    record = validate_account_action_token(
        db,
        raw_token=raw_token,
        purpose=purpose,
        user_id=user_id,
        email=email,
        lock_for_update=True,
    )

    record.mark_used()
    record.validate_state()

    if commit:
        try:
            db.commit()
            db.refresh(record)
        except Exception:
            db.rollback()
            raise
    else:
        db.flush()

    return record


def expire_old_tokens(
    db: Session,
    *,
    commit: bool = True,
) -> int:
    """
    Mark expired active tokens inactive.
    """

    now = utc_now()

    records = (
        db.query(AccountActionToken)
        .filter(
            AccountActionToken.is_active.is_(
                True
            ),
            AccountActionToken.expires_at <= now,
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


def revoke_all_user_tokens(
    db: Session,
    *,
    user_id: int,
    reason: str = TOKEN_REVOKE_SECURITY_EVENT,
    commit: bool = True,
) -> int:
    """
    Revoke every active account-action token for one user.
    """

    resolved_user_id = (
        _normalise_positive_user_id(
            user_id
        )
    )

    records = (
        db.query(AccountActionToken)
        .filter(
            AccountActionToken.user_id
            == resolved_user_id,
            AccountActionToken.is_active.is_(
                True
            ),
        )
        .all()
    )

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


def account_action_token_public_payload(
    record: AccountActionToken,
) -> dict[str, object]:
    """
    Return safe token metadata without hashes or raw values.
    """

    return record.to_public_dict()


__all__ = [
    "ACCOUNT_TOKEN_BYTES",
    "EMAIL_VERIFICATION_TOKEN_HOURS",
    "ExpiredAccountActionTokenError",
    "InvalidAccountActionTokenError",
    "MAX_IP_LENGTH",
    "MAX_RAW_TOKEN_LENGTH",
    "MAX_USER_AGENT_LENGTH",
    "MIN_RAW_TOKEN_LENGTH",
    "PASSWORD_RESET_TOKEN_MINUTES",
    "SUPPORTED_PURPOSES",
    "TOKEN_ID_BYTES",
    "AccountActionTokenError",
    "RevokedAccountActionTokenError",
    "UsedAccountActionTokenError",
    "account_action_token_public_payload",
    "consume_account_action_token",
    "create_account_action_token",
    "expire_old_tokens",
    "generate_account_action_token",
    "generate_token_id",
    "get_token_expiry",
    "get_token_record",
    "hash_account_action_token",
    "normalise_purpose",
    "revoke_active_tokens",
    "revoke_all_user_tokens",
    "utc_now",
    "validate_account_action_token",
]