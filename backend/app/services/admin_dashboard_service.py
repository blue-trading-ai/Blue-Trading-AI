from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any, Final

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models.account_action_token import (
    AccountActionToken,
    TOKEN_STATUS_ACTIVE,
    TOKEN_STATUS_EXPIRED,
    TOKEN_STATUS_REVOKED,
    TOKEN_STATUS_USED,
)
from app.models.auth_session import AuthSession
from app.models.refresh_token import RefreshToken
from app.models.role_permission import Role, UserRole
from app.models.security_audit_log import (
    AUDIT_EVENT_LOGIN_FAILURE,
    AUDIT_EVENT_PASSWORD_CHANGED,
    AUDIT_OUTCOME_BLOCKED,
    AUDIT_OUTCOME_FAILURE,
    AUDIT_OUTCOME_SUCCESS,
    SecurityAuditLog,
)
from app.models.user import (
    ACCOUNT_STATUS_APPROVED,
    ACCOUNT_STATUS_PENDING,
    ACCOUNT_STATUS_REJECTED,
    ACCOUNT_STATUS_SUSPENDED,
    User,
)


MAX_SECURITY_WINDOW_HOURS: Final[int] = 720
MAX_RECENT_EVENT_LIMIT: Final[int] = 100


def utc_now() -> datetime:
    """Return one timezone-aware UTC timestamp."""

    return datetime.now(timezone.utc)


def _bounded_int(
    value: int,
    *,
    minimum: int,
    maximum: int,
) -> int:
    try:
        resolved = int(value)
    except (
        TypeError,
        ValueError,
    ):
        resolved = minimum

    return max(
        minimum,
        min(
            resolved,
            maximum,
        ),
    )


def _count(
    db: Session,
    model: type,
    *filters: Any,
) -> int:
    query = db.query(
        func.count(model.id)
    )

    if filters:
        query = query.filter(
            *filters
        )

    return int(
        query.scalar()
        or 0
    )


def get_user_statistics(
    db: Session,
) -> dict[str, int]:
    """
    Return user-account totals for the admin dashboard.
    """

    now = utc_now()

    return {
        "total_users": _count(
            db,
            User,
        ),
        "active_users": _count(
            db,
            User,
            User.is_active.is_(True),
        ),
        "inactive_users": _count(
            db,
            User,
            User.is_active.is_(False),
        ),
        "approved_users": _count(
            db,
            User,
            User.account_status
            == ACCOUNT_STATUS_APPROVED,
        ),
        "pending_users": _count(
            db,
            User,
            User.account_status
            == ACCOUNT_STATUS_PENDING,
        ),
        "rejected_users": _count(
            db,
            User,
            User.account_status
            == ACCOUNT_STATUS_REJECTED,
        ),
        "suspended_users": _count(
            db,
            User,
            User.account_status
            == ACCOUNT_STATUS_SUSPENDED,
        ),
        "verified_emails": _count(
            db,
            User,
            User.is_email_verified.is_(True),
        ),
        "unverified_emails": _count(
            db,
            User,
            User.is_email_verified.is_(False),
        ),
        "locked_accounts": _count(
            db,
            User,
            User.locked_until.isnot(None),
            User.locked_until > now,
        ),
    }


def get_session_statistics(
    db: Session,
) -> dict[str, int]:
    """
    Return mutually understandable session and refresh-token totals.
    """

    now = utc_now()

    return {
        "total_sessions": _count(
            db,
            AuthSession,
        ),
        "active_sessions": _count(
            db,
            AuthSession,
            AuthSession.is_active.is_(True),
            AuthSession.expires_at > now,
        ),
        "revoked_sessions": _count(
            db,
            AuthSession,
            AuthSession.is_active.is_(False),
            AuthSession.expires_at > now,
        ),
        "expired_sessions": _count(
            db,
            AuthSession,
            AuthSession.expires_at <= now,
        ),
        "total_refresh_tokens": _count(
            db,
            RefreshToken,
        ),
        "active_refresh_tokens": _count(
            db,
            RefreshToken,
            RefreshToken.is_active.is_(True),
            RefreshToken.expires_at > now,
        ),
        "revoked_refresh_tokens": _count(
            db,
            RefreshToken,
            RefreshToken.is_active.is_(False),
            RefreshToken.expires_at > now,
        ),
        "expired_refresh_tokens": _count(
            db,
            RefreshToken,
            RefreshToken.expires_at <= now,
        ),
    }


def get_security_statistics(
    db: Session,
    *,
    hours: int = 24,
) -> dict[str, int]:
    """
    Return security-event totals for a recent time window.

    Only event names and outcomes supported by the current audit model
    are counted.
    """

    resolved_hours = _bounded_int(
        hours,
        minimum=1,
        maximum=MAX_SECURITY_WINDOW_HOURS,
    )

    since = utc_now() - timedelta(
        hours=resolved_hours
    )

    common_filter = (
        SecurityAuditLog.created_at
        >= since
    )

    return {
        "window_hours": (
            resolved_hours
        ),
        "security_events": _count(
            db,
            SecurityAuditLog,
            common_filter,
        ),
        "successful_events": _count(
            db,
            SecurityAuditLog,
            common_filter,
            SecurityAuditLog.outcome
            == AUDIT_OUTCOME_SUCCESS,
        ),
        "failed_events": _count(
            db,
            SecurityAuditLog,
            common_filter,
            SecurityAuditLog.outcome
            == AUDIT_OUTCOME_FAILURE,
        ),
        "blocked_events": _count(
            db,
            SecurityAuditLog,
            common_filter,
            SecurityAuditLog.outcome
            == AUDIT_OUTCOME_BLOCKED,
        ),
        "login_failures": _count(
            db,
            SecurityAuditLog,
            common_filter,
            SecurityAuditLog.event_type
            == AUDIT_EVENT_LOGIN_FAILURE,
        ),
        "password_changes": _count(
            db,
            SecurityAuditLog,
            common_filter,
            SecurityAuditLog.event_type
            == AUDIT_EVENT_PASSWORD_CHANGED,
        ),
    }


def get_role_statistics(
    db: Session,
) -> dict[str, Any]:
    """
    Return active role totals and active user assignments.

    Assignment counts are generated in one grouped query.
    """

    rows = (
        db.query(
            Role.name,
            func.count(
                UserRole.id
            ),
        )
        .outerjoin(
            UserRole,
            (
                UserRole.role_id
                == Role.id
            )
            & (
                UserRole.is_active.is_(
                    True
                )
            ),
        )
        .filter(
            Role.is_active.is_(True)
        )
        .group_by(
            Role.id,
            Role.name,
        )
        .order_by(
            Role.name.asc()
        )
        .all()
    )

    assignments_by_role = {
        str(role_name): int(
            assignment_count
            or 0
        )
        for (
            role_name,
            assignment_count,
        ) in rows
        if role_name
    }

    return {
        "active_roles": len(
            assignments_by_role
        ),
        "active_role_assignments": sum(
            assignments_by_role.values()
        ),
        "assignments_by_role": (
            assignments_by_role
        ),
    }


def get_account_token_statistics(
    db: Session,
) -> dict[str, int]:
    """
    Return account-action token totals without overlapping states.
    """

    now = utc_now()

    return {
        "total_account_tokens": _count(
            db,
            AccountActionToken,
        ),
        "active_account_tokens": _count(
            db,
            AccountActionToken,
            AccountActionToken.status
            == TOKEN_STATUS_ACTIVE,
            AccountActionToken.is_active.is_(
                True
            ),
            AccountActionToken.expires_at
            > now,
        ),
        "expired_account_tokens": _count(
            db,
            AccountActionToken,
            (
                AccountActionToken.status
                == TOKEN_STATUS_EXPIRED
            )
            | (
                AccountActionToken.expires_at
                <= now
            ),
        ),
        "used_account_tokens": _count(
            db,
            AccountActionToken,
            AccountActionToken.status
            == TOKEN_STATUS_USED,
        ),
        "revoked_account_tokens": _count(
            db,
            AccountActionToken,
            AccountActionToken.status
            == TOKEN_STATUS_REVOKED,
        ),
    }


def get_recent_security_events(
    db: Session,
    *,
    limit: int = 20,
) -> list[dict[str, Any]]:
    """
    Return privacy-safe recent audit-event metadata.
    """

    resolved_limit = _bounded_int(
        limit,
        minimum=1,
        maximum=MAX_RECENT_EVENT_LIMIT,
    )

    rows = (
        db.query(
            SecurityAuditLog
        )
        .order_by(
            SecurityAuditLog.created_at.desc(),
            SecurityAuditLog.id.desc(),
        )
        .limit(
            resolved_limit
        )
        .all()
    )

    return [
        row.to_public_dict()
        for row in rows
    ]


def get_admin_dashboard_snapshot(
    db: Session,
    *,
    security_window_hours: int = 24,
    recent_event_limit: int = 20,
) -> dict[str, Any]:
    """
    Build the complete secure admin-dashboard snapshot.
    """

    return {
        "generated_at": utc_now(),
        "users": get_user_statistics(
            db
        ),
        "sessions": get_session_statistics(
            db
        ),
        "security": get_security_statistics(
            db,
            hours=security_window_hours,
        ),
        "roles": get_role_statistics(
            db
        ),
        "account_tokens": (
            get_account_token_statistics(
                db
            )
        ),
        "recent_security_events": (
            get_recent_security_events(
                db,
                limit=recent_event_limit,
            )
        ),
    }


__all__ = [
    "MAX_RECENT_EVENT_LIMIT",
    "MAX_SECURITY_WINDOW_HOURS",
    "get_account_token_statistics",
    "get_admin_dashboard_snapshot",
    "get_recent_security_events",
    "get_role_statistics",
    "get_security_statistics",
    "get_session_statistics",
    "get_user_statistics",
    "utc_now",
]