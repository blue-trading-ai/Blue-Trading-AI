from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Literal

from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
    Query,
    status,
)
from sqlalchemy import desc, func
from sqlalchemy.orm import Session

from app.api.admin_users import require_owner
from app.core.dependencies import get_db
from app.models.security_audit_log import (
    AUDIT_OUTCOME_BLOCKED,
    AUDIT_OUTCOME_FAILURE,
    AUDIT_OUTCOME_SUCCESS,
    VALID_AUDIT_EVENT_TYPES,
    SecurityAuditLog,
)
from app.models.user import User


AUDIT_API_VERSION = 36
MAX_AUDIT_OFFSET = 100_000


router = APIRouter(
    prefix="/admin/audit-logs",
    tags=["Security Audit Logs - Version 36"],
)


def _public_log(
    log: SecurityAuditLog,
) -> dict[str, Any]:
    return log.to_public_dict()


def _normalise_utc_datetime(
    value: datetime | None,
) -> datetime | None:
    """
    Normalize one optional filter timestamp to timezone-aware UTC.
    """

    if value is None:
        return None

    if value.tzinfo is None:
        return value.replace(
            tzinfo=timezone.utc
        )

    return value.astimezone(
        timezone.utc
    )


def _normalise_event_type(
    value: str | None,
) -> str | None:
    """
    Normalize and validate one optional audit event type.
    """

    if value is None:
        return None

    resolved = str(
        value
    ).strip().upper()

    if not resolved:
        return None

    if (
        resolved
        not in VALID_AUDIT_EVENT_TYPES
    ):
        raise HTTPException(
            status_code=(
                status.HTTP_422_UNPROCESSABLE_ENTITY
            ),
            detail=(
                "Unsupported security audit event type."
            ),
        )

    return resolved


def _normalise_email_filter(
    value: str | None,
) -> str | None:
    if value is None:
        return None

    resolved = str(
        value
    ).strip().lower()

    return resolved or None


def _get_log_or_404(
    db: Session,
    log_id: int,
) -> SecurityAuditLog:
    if log_id < 1:
        raise HTTPException(
            status_code=(
                status.HTTP_404_NOT_FOUND
            ),
            detail=(
                "Security audit log not found."
            ),
        )

    log = (
        db.query(SecurityAuditLog)
        .filter(
            SecurityAuditLog.id
            == log_id
        )
        .first()
    )

    if log is None:
        raise HTTPException(
            status_code=(
                status.HTTP_404_NOT_FOUND
            ),
            detail=(
                "Security audit log not found."
            ),
        )

    return log


@router.get("/")
def audit_home(
    _: User = Depends(require_owner),
) -> dict[str, Any]:
    return {
        "status": "success",
        "message": (
            "Blue-Trading-AI security audit log API "
            "is working."
        ),
        "audit_api_version": (
            AUDIT_API_VERSION
        ),
        "owner_only": True,
        "passwords_logged": False,
        "password_hashes_logged": False,
        "jwt_tokens_logged": False,
        "secret_keys_logged": False,
        "raw_ip_addresses_exposed": False,
        "raw_user_agents_exposed": False,
        "supported_outcomes": [
            AUDIT_OUTCOME_SUCCESS,
            AUDIT_OUTCOME_FAILURE,
            AUDIT_OUTCOME_BLOCKED,
        ],
        "supported_event_types": sorted(
            VALID_AUDIT_EVENT_TYPES
        ),
    }


@router.get("")
def list_audit_logs(
    event_type: str | None = Query(
        default=None,
        max_length=100,
    ),
    outcome: Literal[
        "SUCCESS",
        "FAILURE",
        "BLOCKED",
    ]
    | None = Query(default=None),
    actor_email: str | None = Query(
        default=None,
        max_length=255,
    ),
    target_email: str | None = Query(
        default=None,
        max_length=255,
    ),
    date_from: datetime | None = Query(
        default=None
    ),
    date_to: datetime | None = Query(
        default=None
    ),
    limit: int = Query(
        default=100,
        ge=1,
        le=500,
    ),
    offset: int = Query(
        default=0,
        ge=0,
        le=MAX_AUDIT_OFFSET,
    ),
    db: Session = Depends(get_db),
    _: User = Depends(require_owner),
) -> dict[str, Any]:
    """
    List security audit logs with validated optional filters.
    """

    resolved_event_type = (
        _normalise_event_type(
            event_type
        )
    )

    resolved_actor_email = (
        _normalise_email_filter(
            actor_email
        )
    )

    resolved_target_email = (
        _normalise_email_filter(
            target_email
        )
    )

    resolved_date_from = (
        _normalise_utc_datetime(
            date_from
        )
    )

    resolved_date_to = (
        _normalise_utc_datetime(
            date_to
        )
    )

    if (
        resolved_date_from is not None
        and resolved_date_to is not None
        and resolved_date_from
        > resolved_date_to
    ):
        raise HTTPException(
            status_code=(
                status.HTTP_422_UNPROCESSABLE_ENTITY
            ),
            detail=(
                "date_from cannot be later than date_to."
            ),
        )

    query = db.query(
        SecurityAuditLog
    )

    if resolved_event_type:
        query = query.filter(
            SecurityAuditLog.event_type
            == resolved_event_type
        )

    if outcome:
        query = query.filter(
            SecurityAuditLog.outcome
            == outcome
        )

    if resolved_actor_email:
        query = query.filter(
            func.lower(
                SecurityAuditLog.actor_email
            )
            == resolved_actor_email
        )

    if resolved_target_email:
        query = query.filter(
            func.lower(
                SecurityAuditLog.target_email
            )
            == resolved_target_email
        )

    if resolved_date_from:
        query = query.filter(
            SecurityAuditLog.created_at
            >= resolved_date_from
        )

    if resolved_date_to:
        query = query.filter(
            SecurityAuditLog.created_at
            <= resolved_date_to
        )

    total = int(
        query.count()
    )

    logs = (
        query.order_by(
            desc(
                SecurityAuditLog.created_at
            ),
            desc(
                SecurityAuditLog.id
            ),
        )
        .offset(offset)
        .limit(limit)
        .all()
    )

    return {
        "status": "success",
        "total": total,
        "limit": limit,
        "offset": offset,
        "filters": {
            "event_type": (
                resolved_event_type
            ),
            "outcome": outcome,
            "actor_email": (
                resolved_actor_email
            ),
            "target_email": (
                resolved_target_email
            ),
            "date_from": (
                resolved_date_from
            ),
            "date_to": (
                resolved_date_to
            ),
        },
        "logs": [
            _public_log(log)
            for log in logs
        ],
    }


@router.get("/summary")
def audit_summary(
    db: Session = Depends(get_db),
    _: User = Depends(require_owner),
) -> dict[str, Any]:
    """
    Return security audit totals and recent activity.
    """

    total_events = int(
        db.query(
            func.count(
                SecurityAuditLog.id
            )
        ).scalar()
        or 0
    )

    success_events = int(
        db.query(
            func.count(
                SecurityAuditLog.id
            )
        )
        .filter(
            SecurityAuditLog.outcome
            == AUDIT_OUTCOME_SUCCESS
        )
        .scalar()
        or 0
    )

    failure_events = int(
        db.query(
            func.count(
                SecurityAuditLog.id
            )
        )
        .filter(
            SecurityAuditLog.outcome
            == AUDIT_OUTCOME_FAILURE
        )
        .scalar()
        or 0
    )

    blocked_events = int(
        db.query(
            func.count(
                SecurityAuditLog.id
            )
        )
        .filter(
            SecurityAuditLog.outcome
            == AUDIT_OUTCOME_BLOCKED
        )
        .scalar()
        or 0
    )

    event_type_rows = (
        db.query(
            SecurityAuditLog.event_type,
            func.count(
                SecurityAuditLog.id
            ),
        )
        .group_by(
            SecurityAuditLog.event_type
        )
        .order_by(
            desc(
                func.count(
                    SecurityAuditLog.id
                )
            )
        )
        .all()
    )

    recent_logs = (
        db.query(SecurityAuditLog)
        .order_by(
            desc(
                SecurityAuditLog.created_at
            ),
            desc(
                SecurityAuditLog.id
            ),
        )
        .limit(10)
        .all()
    )

    return {
        "status": "success",
        "total_events": total_events,
        "outcomes": {
            "success": success_events,
            "failure": failure_events,
            "blocked": blocked_events,
        },
        "event_type_counts": {
            str(event_type): int(count)
            for (
                event_type,
                count,
            ) in event_type_rows
            if event_type
        },
        "recent_logs": [
            _public_log(log)
            for log in recent_logs
        ],
    }


@router.get("/event-types")
def list_event_types(
    db: Session = Depends(get_db),
    _: User = Depends(require_owner),
) -> dict[str, Any]:
    rows = (
        db.query(
            SecurityAuditLog.event_type
        )
        .distinct()
        .order_by(
            SecurityAuditLog.event_type.asc()
        )
        .all()
    )

    stored_event_types = {
        str(row[0]).strip().upper()
        for row in rows
        if row[0]
    }

    return {
        "status": "success",
        "event_types": sorted(
            VALID_AUDIT_EVENT_TYPES
            | stored_event_types
        ),
    }


@router.get("/{log_id}")
def get_audit_log(
    log_id: int,
    db: Session = Depends(get_db),
    _: User = Depends(require_owner),
) -> dict[str, Any]:
    log = _get_log_or_404(
        db,
        log_id,
    )

    return {
        "status": "success",
        "log": _public_log(log),
    }


__all__ = [
    "AUDIT_API_VERSION",
    "MAX_AUDIT_OFFSET",
    "router",
]