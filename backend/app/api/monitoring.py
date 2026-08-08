from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Final

from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
    Path,
    Query,
    status,
)
from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
)
from sqlalchemy.orm import Session

from app.core.permission_dependencies import (
    require_permission_dependency,
)
from app.core.security_middleware import (
    MAX_REQUEST_ID_LENGTH,
)
from app.database.connection import get_db
from app.models.application_event_log import (
    ApplicationEventLog,
)
from app.models.role_permission import (
    PERMISSION_SYSTEM_MANAGE,
    PERMISSION_SYSTEM_READ,
)
from app.services.application_logging_service import (
    ApplicationLoggingValidationError,
    DEFAULT_LOG_RETENTION_DAYS,
    DEFAULT_SLOW_REQUEST_MS,
    EVENT_UID_PATTERN,
    MAX_EVENT_UID_LENGTH,
    event_public_payload,
    events_public_payload,
    get_monitoring_summary,
    get_slow_requests,
    list_application_events,
    prune_old_application_events,
)


MONITORING_API_VERSION = 47
MAX_MONITORING_OFFSET: Final[int] = 100_000


router = APIRouter(
    prefix="/monitoring",
    tags=["Production Monitoring - Version 47"],
)


class LogPruneRequest(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
    )

    retention_days: int = Field(
        default=DEFAULT_LOG_RETENTION_DAYS,
        ge=1,
        le=3650,
    )


def _normalise_utc_datetime(
    value: datetime | None,
) -> datetime | None:
    """
    Normalize one optional query timestamp to timezone-aware UTC.
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


def _normalise_event_uid(
    value: str,
) -> str:
    """
    Validate one application-event identifier.
    """

    resolved = str(
        value or ""
    ).strip()

    if (
        not resolved
        or len(resolved)
        > MAX_EVENT_UID_LENGTH
        or not EVENT_UID_PATTERN.fullmatch(
            resolved
        )
    ):
        raise HTTPException(
            status_code=(
                status.HTTP_422_UNPROCESSABLE_ENTITY
            ),
            detail=(
                "Application event identifier is invalid."
            ),
        )

    return resolved


@router.get(
    "/",
    dependencies=[
        Depends(
            require_permission_dependency(
                PERMISSION_SYSTEM_READ
            )
        )
    ],
)
def monitoring_home() -> dict[str, Any]:
    return {
        "status": "ok",
        "monitoring_api_version": (
            MONITORING_API_VERSION
        ),
        "structured_logging_enabled": True,
        "request_monitoring_enabled": True,
        "slow_request_detection_enabled": True,
        "sensitive_data_redaction_enabled": True,
        "client_ip_hashing_enabled": True,
        "request_body_logging_enabled": False,
        "authorization_header_logging_enabled": False,
        "cookie_header_logging_enabled": False,
        "default_slow_request_ms": (
            DEFAULT_SLOW_REQUEST_MS
        ),
        "default_log_retention_days": (
            DEFAULT_LOG_RETENTION_DAYS
        ),
        "permission_protected": True,
    }


@router.get(
    "/summary",
    dependencies=[
        Depends(
            require_permission_dependency(
                PERMISSION_SYSTEM_READ
            )
        )
    ],
)
def monitoring_summary(
    hours: int = Query(
        default=24,
        ge=1,
        le=24 * 30,
    ),
    slow_request_ms: float = Query(
        default=DEFAULT_SLOW_REQUEST_MS,
        ge=0,
        le=600_000,
    ),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    return {
        "status": "success",
        "monitoring_version": (
            MONITORING_API_VERSION
        ),
        "summary": get_monitoring_summary(
            db,
            hours=hours,
            slow_request_ms=(
                slow_request_ms
            ),
        ),
    }


@router.get(
    "/events",
    dependencies=[
        Depends(
            require_permission_dependency(
                PERMISSION_SYSTEM_READ
            )
        )
    ],
)
def monitoring_events(
    level: str | None = Query(
        default=None,
        max_length=20,
    ),
    event_type: str | None = Query(
        default=None,
        max_length=40,
    ),
    event_name: str | None = Query(
        default=None,
        max_length=120,
    ),
    request_id: str | None = Query(
        default=None,
        max_length=MAX_REQUEST_ID_LENGTH,
    ),
    job_uid: str | None = Query(
        default=None,
        max_length=64,
    ),
    status_code: int | None = Query(
        default=None,
        ge=100,
        le=599,
    ),
    created_after: datetime | None = Query(
        default=None
    ),
    created_before: datetime | None = Query(
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
        le=MAX_MONITORING_OFFSET,
    ),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    resolved_after = (
        _normalise_utc_datetime(
            created_after
        )
    )
    resolved_before = (
        _normalise_utc_datetime(
            created_before
        )
    )

    if (
        resolved_after is not None
        and resolved_before is not None
        and resolved_after
        > resolved_before
    ):
        raise HTTPException(
            status_code=(
                status.HTTP_422_UNPROCESSABLE_ENTITY
            ),
            detail=(
                "created_after cannot be later than created_before."
            ),
        )

    try:
        events = list_application_events(
            db,
            level=level,
            event_type=event_type,
            event_name=event_name,
            request_id=request_id,
            job_uid=job_uid,
            status_code=status_code,
            created_after=resolved_after,
            created_before=resolved_before,
            limit=limit,
            offset=offset,
        )
    except ApplicationLoggingValidationError as exc:
        raise HTTPException(
            status_code=(
                status.HTTP_422_UNPROCESSABLE_ENTITY
            ),
            detail=str(exc),
        ) from exc

    return {
        "status": "success",
        "count": len(events),
        "limit": limit,
        "offset": offset,
        "events": events_public_payload(
            events
        ),
    }


@router.get(
    "/events/{event_uid}",
    dependencies=[
        Depends(
            require_permission_dependency(
                PERMISSION_SYSTEM_READ
            )
        )
    ],
)
def monitoring_event_detail(
    event_uid: str = Path(
        ...,
        min_length=1,
        max_length=MAX_EVENT_UID_LENGTH,
    ),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    resolved_event_uid = (
        _normalise_event_uid(
            event_uid
        )
    )

    event = (
        db.query(
            ApplicationEventLog
        )
        .filter(
            ApplicationEventLog.event_uid
            == resolved_event_uid
        )
        .first()
    )

    if event is None:
        raise HTTPException(
            status_code=(
                status.HTTP_404_NOT_FOUND
            ),
            detail=(
                "Application event does not exist."
            ),
        )

    return {
        "status": "success",
        "event": event_public_payload(
            event
        ),
    }


@router.get(
    "/slow-requests",
    dependencies=[
        Depends(
            require_permission_dependency(
                PERMISSION_SYSTEM_READ
            )
        )
    ],
)
def monitoring_slow_requests(
    threshold_ms: float = Query(
        default=DEFAULT_SLOW_REQUEST_MS,
        ge=0,
        le=600_000,
    ),
    hours: int = Query(
        default=24,
        ge=1,
        le=24 * 30,
    ),
    limit: int = Query(
        default=50,
        ge=1,
        le=500,
    ),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    events = get_slow_requests(
        db,
        threshold_ms=threshold_ms,
        hours=hours,
        limit=limit,
    )

    return {
        "status": "success",
        "threshold_ms": threshold_ms,
        "window_hours": hours,
        "count": len(events),
        "events": events_public_payload(
            events
        ),
    }


@router.get(
    "/health",
    dependencies=[
        Depends(
            require_permission_dependency(
                PERMISSION_SYSTEM_READ
            )
        )
    ],
)
def monitoring_health(
    hours: int = Query(
        default=1,
        ge=1,
        le=24,
    ),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    summary = get_monitoring_summary(
        db,
        hours=hours,
        slow_request_ms=(
            DEFAULT_SLOW_REQUEST_MS
        ),
    )

    server_error_requests = int(
        summary.get(
            "server_error_requests",
            0,
        )
        or 0
    )

    error_events = int(
        summary.get(
            "error_events",
            0,
        )
        or 0
    )

    request_error_rate = float(
        summary.get(
            "request_error_rate",
            0.0,
        )
        or 0.0
    )

    slow_requests = int(
        summary.get(
            "slow_requests",
            0,
        )
        or 0
    )

    average_request_ms = float(
        summary.get(
            "average_request_ms",
            0.0,
        )
        or 0.0
    )

    maximum_request_ms = float(
        summary.get(
            "maximum_request_ms",
            0.0,
        )
        or 0.0
    )

    critical = (
        server_error_requests > 0
        or error_events >= 10
    )

    degraded = (
        not critical
        and (
            request_error_rate >= 10
            or slow_requests >= 10
        )
    )

    if critical:
        health_status = "critical"
    elif degraded:
        health_status = "degraded"
    else:
        health_status = "healthy"

    return {
        "status": "success",
        "health_status": (
            health_status
        ),
        "window_hours": hours,
        "checks": {
            "server_error_requests": (
                server_error_requests
            ),
            "error_events": (
                error_events
            ),
            "request_error_rate": (
                request_error_rate
            ),
            "slow_requests": (
                slow_requests
            ),
            "average_request_ms": (
                average_request_ms
            ),
            "maximum_request_ms": (
                maximum_request_ms
            ),
        },
        "broker_execution_enabled": False,
    }


@router.post(
    "/prune",
    dependencies=[
        Depends(
            require_permission_dependency(
                PERMISSION_SYSTEM_MANAGE
            )
        )
    ],
)
def monitoring_prune(
    payload: LogPruneRequest,
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    try:
        deleted = (
            prune_old_application_events(
                db,
                retention_days=(
                    payload.retention_days
                ),
                commit=True,
            )
        )
    except ApplicationLoggingValidationError as exc:
        raise HTTPException(
            status_code=(
                status.HTTP_422_UNPROCESSABLE_ENTITY
            ),
            detail=str(exc),
        ) from exc

    return {
        "status": "success",
        "message": (
            "Old application events pruned."
        ),
        "retention_days": (
            payload.retention_days
        ),
        "deleted_events": int(
            deleted
        ),
    }


__all__ = [
    "EVENT_UID_PATTERN",
    "LogPruneRequest",
    "MAX_EVENT_UID_LENGTH",
    "MAX_MONITORING_OFFSET",
    "MONITORING_API_VERSION",
    "router",
]