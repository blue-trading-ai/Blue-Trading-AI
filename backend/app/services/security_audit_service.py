from __future__ import annotations

import json
from collections.abc import Mapping, Sequence
from typing import Any, Final

from fastapi import Request
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.database.connection import SessionLocal
from app.models.security_audit_log import (
    MAX_DETAILS_LENGTH,
    SecurityAuditLog,
)
from app.models.user import User


MAX_MESSAGE_LENGTH: Final[int] = 500
MAX_USER_AGENT_LENGTH: Final[int] = 500
MAX_PATH_LENGTH: Final[int] = 500
MAX_IP_LENGTH: Final[int] = 64
MAX_DETAIL_DEPTH: Final[int] = 5
MAX_DETAIL_ITEMS: Final[int] = 100
MAX_DETAIL_STRING_LENGTH: Final[int] = 1000

SENSITIVE_DETAIL_KEYWORDS: Final[
    tuple[str, ...]
] = (
    "password",
    "passwd",
    "passphrase",
    "hash",
    "token",
    "authorization",
    "cookie",
    "secret",
    "api_key",
    "apikey",
    "credential",
    "session",
    "jwt",
    "private_key",
    "client_secret",
    "smtp_password",
)


def _clean_text(
    value: Any,
    *,
    max_length: int,
) -> str | None:
    """
    Convert one value into bounded, single-line safe text.

    Control characters are replaced to prevent audit-log injection.
    """

    if value is None:
        return None

    raw = str(value)

    cleaned = "".join(
        character
        if character.isprintable()
        and character not in {
            "\r",
            "\n",
            "\t",
        }
        else " "
        for character in raw
    ).strip()

    if not cleaned:
        return None

    return cleaned[:max_length]


def _is_sensitive_detail_key(
    key: Any,
) -> bool:
    normalized = str(
        key or ""
    ).strip().lower()

    return any(
        keyword in normalized
        for keyword in SENSITIVE_DETAIL_KEYWORDS
    )


def _sanitise_detail_value(
    value: Any,
    *,
    depth: int = 0,
) -> Any:
    """
    Recursively sanitize one audit-detail value.
    """

    if depth >= MAX_DETAIL_DEPTH:
        return "[MAX_DEPTH_REACHED]"

    if value is None:
        return None

    if isinstance(
        value,
        (bool, int),
    ):
        return value

    if isinstance(value, float):
        if value != value:
            return "[NON_FINITE_NUMBER]"

        if value in {
            float("inf"),
            float("-inf"),
        }:
            return "[NON_FINITE_NUMBER]"

        return value

    if isinstance(value, str):
        return (
            _clean_text(
                value,
                max_length=(
                    MAX_DETAIL_STRING_LENGTH
                ),
            )
            or ""
        )

    if isinstance(value, Mapping):
        result: dict[str, Any] = {}

        for index, (
            key,
            item,
        ) in enumerate(
            value.items()
        ):
            if index >= MAX_DETAIL_ITEMS:
                result["_truncated"] = True
                break

            safe_key = (
                _clean_text(
                    key,
                    max_length=120,
                )
                or "unnamed"
            )

            if _is_sensitive_detail_key(
                safe_key
            ):
                result[safe_key] = (
                    "[REDACTED]"
                )
            else:
                result[safe_key] = (
                    _sanitise_detail_value(
                        item,
                        depth=depth + 1,
                    )
                )

        return result

    if isinstance(
        value,
        Sequence,
    ) and not isinstance(
        value,
        (
            str,
            bytes,
            bytearray,
        ),
    ):
        items = list(value)[
            :MAX_DETAIL_ITEMS
        ]

        result = [
            _sanitise_detail_value(
                item,
                depth=depth + 1,
            )
            for item in items
        ]

        if len(value) > MAX_DETAIL_ITEMS:
            result.append(
                "[TRUNCATED]"
            )

        return result

    return (
        _clean_text(
            value,
            max_length=(
                MAX_DETAIL_STRING_LENGTH
            ),
        )
        or ""
    )


def _safe_details(
    details: dict[str, Any] | None,
) -> str | None:
    """
    Serialize bounded audit details with recursive redaction.
    """

    if not details:
        return None

    safe_payload = (
        _sanitise_detail_value(
            details
        )
    )

    encoded = json.dumps(
        safe_payload,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
        default=str,
    )

    return encoded[
        :MAX_DETAILS_LENGTH
    ]


def _request_ip(
    request: Request | None,
) -> str | None:
    """
    Resolve the direct ASGI client address.

    Proxy forwarding headers are intentionally not trusted here.
    """

    if (
        request is None
        or request.client is None
    ):
        return None

    return _clean_text(
        request.client.host,
        max_length=MAX_IP_LENGTH,
    )


def _request_user_agent(
    request: Request | None,
) -> str | None:
    if request is None:
        return None

    return _clean_text(
        request.headers.get(
            "user-agent"
        ),
        max_length=MAX_USER_AGENT_LENGTH,
    )


def _request_path(
    request: Request | None,
) -> str | None:
    if request is None:
        return None

    return _clean_text(
        request.url.path,
        max_length=MAX_PATH_LENGTH,
    )


def _request_method(
    request: Request | None,
) -> str | None:
    if request is None:
        return None

    resolved = _clean_text(
        request.method,
        max_length=20,
    )

    return (
        resolved.upper()
        if resolved
        else None
    )


def _resolved_user_id(
    user: User | None,
) -> int | None:
    if (
        user is None
        or user.id is None
    ):
        return None

    try:
        resolved = int(
            user.id
        )
    except (
        TypeError,
        ValueError,
    ):
        return None

    return (
        resolved
        if resolved > 0
        else None
    )


def _build_security_audit_log(
    *,
    event_type: str,
    outcome: str,
    request: Request | None,
    actor_user: User | None,
    target_user: User | None,
    actor_email: str | None,
    target_email: str | None,
    message: str | None,
    details: dict[str, Any] | None,
    is_security_sensitive: bool,
) -> SecurityAuditLog:
    resolved_actor_email = (
        actor_email
        or (
            actor_user.email
            if actor_user is not None
            else None
        )
    )

    resolved_target_email = (
        target_email
        or (
            target_user.email
            if target_user is not None
            else None
        )
    )

    log = SecurityAuditLog(
        event_type=(
            _clean_text(
                event_type,
                max_length=100,
            )
            or ""
        ),
        outcome=(
            _clean_text(
                outcome,
                max_length=20,
            )
            or ""
        ),
        actor_user_id=(
            _resolved_user_id(
                actor_user
            )
        ),
        actor_email=_clean_text(
            resolved_actor_email,
            max_length=255,
        ),
        target_user_id=(
            _resolved_user_id(
                target_user
            )
        ),
        target_email=_clean_text(
            resolved_target_email,
            max_length=255,
        ),
        ip_address=_request_ip(
            request
        ),
        user_agent=(
            _request_user_agent(
                request
            )
        ),
        request_path=_request_path(
            request
        ),
        request_method=(
            _request_method(
                request
            )
        ),
        message=_clean_text(
            message,
            max_length=MAX_MESSAGE_LENGTH,
        ),
        details=_safe_details(
            details
        ),
        is_security_sensitive=bool(
            is_security_sensitive
        ),
    )

    log.validate_state()

    return log


def create_security_audit_log(
    *,
    db: Session,
    event_type: str,
    outcome: str,
    request: Request | None = None,
    actor_user: User | None = None,
    target_user: User | None = None,
    actor_email: str | None = None,
    target_email: str | None = None,
    message: str | None = None,
    details: dict[str, Any] | None = None,
    is_security_sensitive: bool = True,
    commit: bool = True,
) -> SecurityAuditLog | None:
    """
    Create one security audit event.

    Security-audit failures never replace the primary application
    response or roll back unrelated caller changes.

    When commit=True, the audit row is written through an isolated
    database session. When commit=False, a nested transaction is used
    on the supplied session and the row is flushed but not committed.
    """

    try:
        log = _build_security_audit_log(
            event_type=event_type,
            outcome=outcome,
            request=request,
            actor_user=actor_user,
            target_user=target_user,
            actor_email=actor_email,
            target_email=target_email,
            message=message,
            details=details,
            is_security_sensitive=(
                is_security_sensitive
            ),
        )
    except (
        TypeError,
        ValueError,
    ):
        return None

    if commit:
        audit_db = SessionLocal()

        try:
            audit_db.add(log)
            audit_db.commit()
            audit_db.refresh(log)

            return log
        except SQLAlchemyError:
            audit_db.rollback()
            return None
        finally:
            audit_db.close()

    try:
        with db.begin_nested():
            db.add(log)
            db.flush()

        return log
    except SQLAlchemyError:
        return None


def audit_event(
    *,
    db: Session,
    event_type: str,
    outcome: str,
    request: Request | None = None,
    actor_user: User | None = None,
    target_user: User | None = None,
    actor_email: str | None = None,
    target_email: str | None = None,
    message: str | None = None,
    details: dict[str, Any] | None = None,
) -> SecurityAuditLog | None:
    """
    Convenience wrapper for one isolated committed security event.
    """

    return create_security_audit_log(
        db=db,
        event_type=event_type,
        outcome=outcome,
        request=request,
        actor_user=actor_user,
        target_user=target_user,
        actor_email=actor_email,
        target_email=target_email,
        message=message,
        details=details,
        is_security_sensitive=True,
        commit=True,
    )


__all__ = [
    "MAX_DETAIL_DEPTH",
    "MAX_DETAIL_ITEMS",
    "MAX_DETAILS_LENGTH",
    "MAX_IP_LENGTH",
    "MAX_MESSAGE_LENGTH",
    "MAX_PATH_LENGTH",
    "MAX_USER_AGENT_LENGTH",
    "SENSITIVE_DETAIL_KEYWORDS",
    "audit_event",
    "create_security_audit_log",
]