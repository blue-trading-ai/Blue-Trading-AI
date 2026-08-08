from __future__ import annotations

import hashlib
import re
import secrets
from datetime import datetime, timedelta, timezone
from typing import Any, Final, Iterable

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.security_middleware import (
    MAX_REQUEST_ID_LENGTH,
    REQUEST_ID_PATTERN,
)
from app.models.application_event_log import (
    ApplicationEventLog,
    EVENT_TYPE_APPLICATION,
    EVENT_TYPE_BACKGROUND_JOB,
    EVENT_TYPE_DATABASE,
    EVENT_TYPE_HEALTH,
    EVENT_TYPE_HTTP_REQUEST,
    EVENT_TYPE_PERFORMANCE,
    EVENT_TYPE_SECURITY,
    LOG_LEVEL_CRITICAL,
    LOG_LEVEL_DEBUG,
    LOG_LEVEL_ERROR,
    LOG_LEVEL_INFO,
    LOG_LEVEL_WARNING,
    VALID_EVENT_TYPES,
    VALID_LOG_LEVELS,
)


DEFAULT_LOG_RETENTION_DAYS: Final[int] = 30
DEFAULT_SLOW_REQUEST_MS: Final[float] = 1000.0
MAX_METADATA_DEPTH: Final[int] = 5
MAX_COLLECTION_ITEMS: Final[int] = 100
MAX_STRING_LENGTH: Final[int] = 2000
MAX_EVENT_UID_LENGTH: Final[int] = 64
MAX_EVENT_NAME_LENGTH: Final[int] = 120
MAX_SOURCE_LENGTH: Final[int] = 120
MAX_JOB_UID_LENGTH: Final[int] = 64
MAX_METHOD_LENGTH: Final[int] = 12
MAX_PATH_LENGTH: Final[int] = 500
MAX_EXCEPTION_TYPE_LENGTH: Final[int] = 160
MAX_MESSAGE_LENGTH: Final[int] = 8000

EVENT_UID_PATTERN = re.compile(
    r"^[A-Za-z0-9._:-]+$"
)
SENSITIVE_KEYWORDS: Final[tuple[str, ...]] = (
    "password",
    "passwd",
    "secret",
    "token",
    "authorization",
    "cookie",
    "api_key",
    "apikey",
    "smtp_password",
    "refresh_token",
    "access_token",
    "verification_token",
    "reset_token",
    "jwt",
    "credential",
    "session",
    "private_key",
    "client_secret",
)

SENSITIVE_VALUE_PATTERNS: Final[tuple[re.Pattern[str], ...]] = (
    re.compile(
        r"(?i)\bbearer\s+[a-z0-9._\-~+/]+=*\b"
    ),
    re.compile(
        r"(?i)\beyJ[a-zA-Z0-9_\-]{10,}\."
        r"[a-zA-Z0-9_\-]{10,}\."
        r"[a-zA-Z0-9_\-]{10,}\b"
    ),
)


class ApplicationLoggingError(Exception):
    """
    Base exception for secure application logging.
    """


class ApplicationLoggingValidationError(
    ApplicationLoggingError
):
    pass


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _clean_text(
    value: Any,
    *,
    maximum_length: int,
) -> str:
    """
    Return printable, single-line text suitable for persistent logs.
    """

    raw = str(value or "")

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

    return cleaned[:maximum_length]


def _safe_int(
    value: Any,
    *,
    field_name: str,
    minimum: int | None = None,
    maximum: int | None = None,
) -> int:
    """
    Parse and validate one integer logging field.
    """

    if isinstance(value, bool):
        raise ApplicationLoggingValidationError(
            f"{field_name} must be an integer."
        )

    try:
        resolved = int(value)
    except (
        TypeError,
        ValueError,
        OverflowError,
    ) as exc:
        raise ApplicationLoggingValidationError(
            f"{field_name} must be an integer."
        ) from exc

    if minimum is not None and resolved < minimum:
        raise ApplicationLoggingValidationError(
            f"{field_name} is below the minimum allowed value."
        )

    if maximum is not None and resolved > maximum:
        raise ApplicationLoggingValidationError(
            f"{field_name} exceeds the maximum allowed value."
        )

    return resolved


def _safe_float(
    value: Any,
    *,
    field_name: str,
    minimum: float | None = None,
    maximum: float | None = None,
) -> float:
    """
    Parse and validate one finite numeric logging field.
    """

    if isinstance(value, bool):
        raise ApplicationLoggingValidationError(
            f"{field_name} must be numeric."
        )

    try:
        resolved = float(value)
    except (
        TypeError,
        ValueError,
        OverflowError,
    ) as exc:
        raise ApplicationLoggingValidationError(
            f"{field_name} must be numeric."
        ) from exc

    if resolved != resolved or resolved in {
        float("inf"),
        float("-inf"),
    }:
        raise ApplicationLoggingValidationError(
            f"{field_name} must be finite."
        )

    if minimum is not None and resolved < minimum:
        raise ApplicationLoggingValidationError(
            f"{field_name} is below the minimum allowed value."
        )

    if maximum is not None and resolved > maximum:
        raise ApplicationLoggingValidationError(
            f"{field_name} exceeds the maximum allowed value."
        )

    return resolved


def generate_event_uid() -> str:
    return (
        "EVT-"
        + secrets.token_urlsafe(24)
        .replace("-", "")
        .replace("_", "")[:40]
        .upper()
    )


def _normalise_key(
    key: Any,
) -> str:
    return str(key or "").strip().lower()


def is_sensitive_key(
    key: Any,
) -> bool:
    resolved = _normalise_key(key)

    return any(
        keyword in resolved
        for keyword in SENSITIVE_KEYWORDS
    )


def redact_sensitive_text(
    value: Any,
) -> str:
    """
    Redact common token and Authorization patterns.
    """

    text = _clean_text(
        value,
        maximum_length=MAX_STRING_LENGTH,
    )

    for pattern in SENSITIVE_VALUE_PATTERNS:
        text = pattern.sub(
            "[REDACTED]",
            text,
        )

    return text[:MAX_STRING_LENGTH]


def sanitise_metadata(
    value: Any,
    *,
    depth: int = 0,
) -> Any:
    """
    Recursively remove secrets from structured metadata.
    """

    if depth >= MAX_METADATA_DEPTH:
        return "[MAX_DEPTH_REACHED]"

    if value is None:
        return None

    if isinstance(value, bool):
        return value

    if isinstance(value, int):
        return value

    if isinstance(value, float):
        if value != value or value in {
            float("inf"),
            float("-inf"),
        }:
            return "[NON_FINITE_NUMBER]"
        return value

    if isinstance(value, str):
        return redact_sensitive_text(value)

    if isinstance(value, dict):
        result: dict[str, Any] = {}

        for index, (key, item) in enumerate(
            value.items()
        ):
            if index >= MAX_COLLECTION_ITEMS:
                result["_truncated"] = True
                break

            key_text = _clean_text(
                key,
                maximum_length=120,
            )

            if is_sensitive_key(key):
                result[key_text] = "[REDACTED]"
            else:
                result[key_text] = sanitise_metadata(
                    item,
                    depth=depth + 1,
                )

        return result

    if isinstance(
        value,
        (list, tuple, set),
    ):
        items = list(value)[
            :MAX_COLLECTION_ITEMS
        ]

        result = [
            sanitise_metadata(
                item,
                depth=depth + 1,
            )
            for item in items
        ]

        if len(value) > MAX_COLLECTION_ITEMS:
            result.append("[TRUNCATED]")

        return result

    return redact_sensitive_text(value)


def hash_client_ip(
    client_ip: str | None,
) -> str | None:
    """
    Hash a normalized client IP with an application-specific secret.

    A predictable public fallback salt is intentionally not used.
    """

    resolved_ip = _clean_text(
        client_ip,
        maximum_length=64,
    )

    if not resolved_ip:
        return None

    configured_salt = str(
        getattr(
            settings,
            "LOG_IP_HASH_SALT",
            "",
        )
        or settings.SECRET_KEY
    ).strip()

    if not configured_salt:
        raise ApplicationLoggingValidationError(
            "Client IP hashing salt is not configured."
        )

    value = (
        f"{configured_salt}:{resolved_ip}"
    ).encode("utf-8")

    return hashlib.sha256(value).hexdigest()


def normalise_level(
    level: str,
) -> str:
    resolved = str(
        level or LOG_LEVEL_INFO
    ).strip().upper()

    if resolved not in VALID_LOG_LEVELS:
        raise ApplicationLoggingValidationError(
            "Application log level is invalid."
        )

    return resolved


def normalise_event_type(
    event_type: str,
) -> str:
    resolved = str(
        event_type or EVENT_TYPE_APPLICATION
    ).strip().upper()

    if resolved not in VALID_EVENT_TYPES:
        raise ApplicationLoggingValidationError(
            "Application event type is invalid."
        )

    return resolved


def create_application_event(
    db: Session,
    *,
    level: str = LOG_LEVEL_INFO,
    event_type: str = EVENT_TYPE_APPLICATION,
    event_name: str,
    message: str,
    source: str | None = None,
    request_id: str | None = None,
    user_id: int | None = None,
    job_uid: str | None = None,
    method: str | None = None,
    path: str | None = None,
    status_code: int | None = None,
    duration_ms: float | None = None,
    client_ip: str | None = None,
    exception_type: str | None = None,
    exception_message: str | None = None,
    metadata: dict[str, Any] | None = None,
    event_uid: str | None = None,
    commit: bool = True,
) -> ApplicationEventLog:
    """
    Store one sanitised structured application event.
    """

    resolved_uid = _clean_text(
        event_uid or generate_event_uid(),
        maximum_length=MAX_EVENT_UID_LENGTH,
    )

    if (
        not resolved_uid
        or not EVENT_UID_PATTERN.fullmatch(
            resolved_uid
        )
    ):
        raise ApplicationLoggingValidationError(
            "Event UID is invalid."
        )

    if (
        db.query(ApplicationEventLog)
        .filter(
            ApplicationEventLog.event_uid
            == resolved_uid
        )
        .first()
        is not None
    ):
        raise ApplicationLoggingValidationError(
            "Event UID already exists."
        )

    resolved_name = _clean_text(
        event_name,
        maximum_length=MAX_EVENT_NAME_LENGTH,
    )

    if not resolved_name:
        raise ApplicationLoggingValidationError(
            "Event name is required."
        )

    resolved_message = redact_sensitive_text(
        message
    ).strip()

    if not resolved_message:
        raise ApplicationLoggingValidationError(
            "Event message is required."
        )

    resolved_duration = None

    if duration_ms is not None:
        resolved_duration = _safe_float(
            duration_ms,
            field_name="Duration",
            minimum=0.0,
            maximum=86_400_000.0,
        )

    resolved_user_id = None

    if user_id is not None:
        resolved_user_id = _safe_int(
            user_id,
            field_name="User ID",
            minimum=1,
        )

    resolved_status_code = None

    if status_code is not None:
        resolved_status_code = _safe_int(
            status_code,
            field_name="Status code",
            minimum=100,
            maximum=599,
        )

    resolved_request_id = None

    if request_id:
        resolved_request_id = _clean_text(
            request_id,
            maximum_length=MAX_REQUEST_ID_LENGTH,
        )

        if not REQUEST_ID_PATTERN.fullmatch(
            resolved_request_id
        ):
            raise ApplicationLoggingValidationError(
                "Request ID is invalid."
            )

    record = ApplicationEventLog(
        event_uid=resolved_uid,
        level=normalise_level(level),
        event_type=normalise_event_type(
            event_type
        ),
        event_name=resolved_name,
        message=resolved_message[:MAX_MESSAGE_LENGTH],
        source=(
            redact_sensitive_text(source)[:MAX_SOURCE_LENGTH]
            if source
            else None
        ),
        request_id=resolved_request_id,
        user_id=resolved_user_id,
        job_uid=(
            _clean_text(
                job_uid,
                maximum_length=MAX_JOB_UID_LENGTH,
            )
            if job_uid
            else None
        ),
        method=(
            _clean_text(
                method,
                maximum_length=MAX_METHOD_LENGTH,
            ).upper()
            if method
            else None
        ),
        path=(
            redact_sensitive_text(path)[:MAX_PATH_LENGTH]
            if path
            else None
        ),
        status_code=resolved_status_code,
        duration_ms=resolved_duration,
        client_ip_hash=hash_client_ip(
            client_ip
        ),
        exception_type=(
            _clean_text(
                exception_type,
                maximum_length=MAX_EXCEPTION_TYPE_LENGTH,
            )
            if exception_type
            else None
        ),
        exception_message=(
            redact_sensitive_text(
                exception_message
            )[:8000]
            if exception_message
            else None
        ),
        metadata_json=(
            sanitise_metadata(metadata)
            if metadata is not None
            else None
        ),
    )

    try:
        record.validate_state()
    except ValueError as exc:
        raise ApplicationLoggingValidationError(
            str(exc)
        ) from exc

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

    return record


def log_http_request(
    db: Session,
    *,
    request_id: str,
    method: str,
    path: str,
    status_code: int,
    duration_ms: float,
    client_ip: str | None = None,
    user_id: int | None = None,
    metadata: dict[str, Any] | None = None,
    commit: bool = True,
) -> ApplicationEventLog:
    """
    Store one sanitised HTTP request event.
    """

    if status_code >= 500:
        level = LOG_LEVEL_ERROR
    elif status_code >= 400:
        level = LOG_LEVEL_WARNING
    else:
        level = LOG_LEVEL_INFO

    return create_application_event(
        db,
        level=level,
        event_type=EVENT_TYPE_HTTP_REQUEST,
        event_name="http_request_completed",
        message=(
            f"{_clean_text(method, maximum_length=MAX_METHOD_LENGTH).upper()} "
            f"{redact_sensitive_text(path)[:MAX_PATH_LENGTH]} "
            f"completed with {int(status_code)}"
        ),
        source="http_middleware",
        request_id=request_id,
        user_id=user_id,
        method=method,
        path=path,
        status_code=status_code,
        duration_ms=duration_ms,
        client_ip=client_ip,
        metadata=metadata,
        commit=commit,
    )


def log_exception(
    db: Session,
    *,
    event_name: str,
    exception: Exception,
    source: str | None = None,
    request_id: str | None = None,
    user_id: int | None = None,
    job_uid: str | None = None,
    metadata: dict[str, Any] | None = None,
    critical: bool = False,
    commit: bool = True,
) -> ApplicationEventLog:
    """
    Store one sanitised exception event.
    """

    return create_application_event(
        db,
        level=(
            LOG_LEVEL_CRITICAL
            if critical
            else LOG_LEVEL_ERROR
        ),
        event_type=EVENT_TYPE_APPLICATION,
        event_name=event_name,
        message="Application exception recorded.",
        source=source,
        request_id=request_id,
        user_id=user_id,
        job_uid=job_uid,
        exception_type=type(exception).__name__,
        exception_message=None,
        metadata={
            **(
                metadata
                if isinstance(metadata, dict)
                else {}
            ),
            "raw_exception_message_logged": False,
        },
        commit=commit,
    )


def log_background_job_event(
    db: Session,
    *,
    job_uid: str,
    event_name: str,
    message: str,
    level: str = LOG_LEVEL_INFO,
    duration_ms: float | None = None,
    metadata: dict[str, Any] | None = None,
    commit: bool = True,
) -> ApplicationEventLog:
    return create_application_event(
        db,
        level=level,
        event_type=EVENT_TYPE_BACKGROUND_JOB,
        event_name=event_name,
        message=message,
        source="background_worker",
        job_uid=job_uid,
        duration_ms=duration_ms,
        metadata=metadata,
        commit=commit,
    )


def list_application_events(
    db: Session,
    *,
    level: str | None = None,
    event_type: str | None = None,
    event_name: str | None = None,
    request_id: str | None = None,
    job_uid: str | None = None,
    status_code: int | None = None,
    created_after: datetime | None = None,
    created_before: datetime | None = None,
    limit: int = 100,
    offset: int = 0,
) -> list[ApplicationEventLog]:
    query = db.query(ApplicationEventLog)

    if level:
        query = query.filter(
            ApplicationEventLog.level
            == normalise_level(level)
        )

    if event_type:
        query = query.filter(
            ApplicationEventLog.event_type
            == normalise_event_type(
                event_type
            )
        )

    if event_name:
        resolved_event_name = _clean_text(
            event_name,
            maximum_length=MAX_EVENT_NAME_LENGTH,
        )
        query = query.filter(
            ApplicationEventLog.event_name
            == resolved_event_name
        )

    if request_id:
        resolved_request_id = _clean_text(
            request_id,
            maximum_length=MAX_REQUEST_ID_LENGTH,
        )

        if not REQUEST_ID_PATTERN.fullmatch(
            resolved_request_id
        ):
            raise ApplicationLoggingValidationError(
                "Request ID is invalid."
            )

        query = query.filter(
            ApplicationEventLog.request_id
            == resolved_request_id
        )

    if job_uid:
        resolved_job_uid = _clean_text(
            job_uid,
            maximum_length=MAX_JOB_UID_LENGTH,
        )
        query = query.filter(
            ApplicationEventLog.job_uid
            == resolved_job_uid
        )

    if status_code is not None:
        resolved_status_code = _safe_int(
            status_code,
            field_name="Status code",
            minimum=100,
            maximum=599,
        )
        query = query.filter(
            ApplicationEventLog.status_code
            == resolved_status_code
        )

    if created_after is not None:
        query = query.filter(
            ApplicationEventLog.created_at
            >= created_after
        )

    if created_before is not None:
        query = query.filter(
            ApplicationEventLog.created_at
            <= created_before
        )

    return (
        query.order_by(
            ApplicationEventLog.created_at.desc(),
            ApplicationEventLog.id.desc(),
        )
        .offset(
            max(
                0,
                _safe_int(
                    offset,
                    field_name="Offset",
                ),
            )
        )
        .limit(
            max(
                1,
                min(
                    _safe_int(
                        limit,
                        field_name="Limit",
                    ),
                    500,
                ),
            )
        )
        .all()
    )


def get_monitoring_summary(
    db: Session,
    *,
    hours: int = 24,
    slow_request_ms: float = (
        DEFAULT_SLOW_REQUEST_MS
    ),
) -> dict[str, Any]:
    """
    Return production monitoring metrics.
    """

    resolved_hours = min(
        _safe_int(
            hours,
            field_name="Hours",
            minimum=1,
        ),
        24 * 30,
    )

    resolved_slow_request_ms = _safe_float(
        slow_request_ms,
        field_name="Slow request threshold",
        minimum=0.0,
        maximum=86_400_000.0,
    )

    cutoff = utc_now() - timedelta(
        hours=resolved_hours
    )

    base_filter = (
        ApplicationEventLog.created_at >= cutoff
    )

    total_events = int(
        db.query(
            func.count(ApplicationEventLog.id)
        )
        .filter(base_filter)
        .scalar()
        or 0
    )

    error_events = int(
        db.query(
            func.count(ApplicationEventLog.id)
        )
        .filter(
            base_filter,
            ApplicationEventLog.level.in_(
                [
                    LOG_LEVEL_ERROR,
                    LOG_LEVEL_CRITICAL,
                ]
            ),
        )
        .scalar()
        or 0
    )

    warning_events = int(
        db.query(
            func.count(ApplicationEventLog.id)
        )
        .filter(
            base_filter,
            ApplicationEventLog.level
            == LOG_LEVEL_WARNING,
        )
        .scalar()
        or 0
    )

    request_count = int(
        db.query(
            func.count(ApplicationEventLog.id)
        )
        .filter(
            base_filter,
            ApplicationEventLog.event_type
            == EVENT_TYPE_HTTP_REQUEST,
        )
        .scalar()
        or 0
    )

    server_error_requests = int(
        db.query(
            func.count(ApplicationEventLog.id)
        )
        .filter(
            base_filter,
            ApplicationEventLog.event_type
            == EVENT_TYPE_HTTP_REQUEST,
            ApplicationEventLog.status_code >= 500,
        )
        .scalar()
        or 0
    )

    client_error_requests = int(
        db.query(
            func.count(ApplicationEventLog.id)
        )
        .filter(
            base_filter,
            ApplicationEventLog.event_type
            == EVENT_TYPE_HTTP_REQUEST,
            ApplicationEventLog.status_code.between(
                400,
                499,
            ),
        )
        .scalar()
        or 0
    )

    slow_requests = int(
        db.query(
            func.count(ApplicationEventLog.id)
        )
        .filter(
            base_filter,
            ApplicationEventLog.event_type
            == EVENT_TYPE_HTTP_REQUEST,
            ApplicationEventLog.duration_ms
            >= resolved_slow_request_ms,
        )
        .scalar()
        or 0
    )

    average_request_ms = (
        db.query(
            func.avg(
                ApplicationEventLog.duration_ms
            )
        )
        .filter(
            base_filter,
            ApplicationEventLog.event_type
            == EVENT_TYPE_HTTP_REQUEST,
            ApplicationEventLog.duration_ms.isnot(
                None
            ),
        )
        .scalar()
    )

    maximum_request_ms = (
        db.query(
            func.max(
                ApplicationEventLog.duration_ms
            )
        )
        .filter(
            base_filter,
            ApplicationEventLog.event_type
            == EVENT_TYPE_HTTP_REQUEST,
            ApplicationEventLog.duration_ms.isnot(
                None
            ),
        )
        .scalar()
    )

    request_error_rate = (
        round(
            (
                (
                    server_error_requests
                    + client_error_requests
                )
                / request_count
                * 100
            ),
            2,
        )
        if request_count > 0
        else 0.0
    )

    return {
        "window_hours": resolved_hours,
        "total_events": total_events,
        "error_events": error_events,
        "warning_events": warning_events,
        "request_count": request_count,
        "server_error_requests": (
            server_error_requests
        ),
        "client_error_requests": (
            client_error_requests
        ),
        "request_error_rate": (
            request_error_rate
        ),
        "slow_request_threshold_ms": (
            resolved_slow_request_ms
        ),
        "slow_requests": slow_requests,
        "average_request_ms": round(
            float(average_request_ms or 0),
            2,
        ),
        "maximum_request_ms": round(
            float(maximum_request_ms or 0),
            2,
        ),
    }


def get_slow_requests(
    db: Session,
    *,
    threshold_ms: float = (
        DEFAULT_SLOW_REQUEST_MS
    ),
    hours: int = 24,
    limit: int = 50,
) -> list[ApplicationEventLog]:
    resolved_hours = min(
        _safe_int(
            hours,
            field_name="Hours",
            minimum=1,
        ),
        24 * 30,
    )
    resolved_threshold_ms = _safe_float(
        threshold_ms,
        field_name="Threshold",
        minimum=0.0,
        maximum=86_400_000.0,
    )
    resolved_limit = min(
        _safe_int(
            limit,
            field_name="Limit",
            minimum=1,
        ),
        500,
    )

    cutoff = utc_now() - timedelta(
        hours=resolved_hours
    )

    return (
        db.query(ApplicationEventLog)
        .filter(
            ApplicationEventLog.event_type
            == EVENT_TYPE_HTTP_REQUEST,
            ApplicationEventLog.created_at
            >= cutoff,
            ApplicationEventLog.duration_ms
            >= resolved_threshold_ms,
        )
        .order_by(
            ApplicationEventLog.duration_ms.desc(),
            ApplicationEventLog.created_at.desc(),
        )
        .limit(
            resolved_limit
        )
        .all()
    )


def prune_old_application_events(
    db: Session,
    *,
    retention_days: int = (
        DEFAULT_LOG_RETENTION_DAYS
    ),
    commit: bool = True,
) -> int:
    """
    Delete events older than the configured retention.
    """

    resolved_days = min(
        _safe_int(
            retention_days,
            field_name="Retention days",
            minimum=1,
        ),
        3650,
    )
    cutoff = utc_now() - timedelta(
        days=resolved_days
    )

    deleted = (
        db.query(ApplicationEventLog)
        .filter(
            ApplicationEventLog.created_at
            < cutoff
        )
        .delete(
            synchronize_session=False
        )
    )

    if commit:
        db.commit()
    else:
        db.flush()

    return int(deleted or 0)


def event_public_payload(
    event: ApplicationEventLog,
) -> dict[str, object]:
    return event.to_public_dict()


def events_public_payload(
    events: Iterable[ApplicationEventLog],
) -> list[dict[str, object]]:
    return [
        event_public_payload(event)
        for event in events
    ]


__all__ = [
    "DEFAULT_LOG_RETENTION_DAYS",
    "DEFAULT_SLOW_REQUEST_MS",
    "MAX_EVENT_UID_LENGTH",
    "MAX_REQUEST_ID_LENGTH",
    "ApplicationLoggingError",
    "ApplicationLoggingValidationError",
    "create_application_event",
    "event_public_payload",
    "events_public_payload",
    "generate_event_uid",
    "get_monitoring_summary",
    "get_slow_requests",
    "hash_client_ip",
    "is_sensitive_key",
    "list_application_events",
    "log_background_job_event",
    "log_exception",
    "log_http_request",
    "normalise_event_type",
    "normalise_level",
    "prune_old_application_events",
    "redact_sensitive_text",
    "sanitise_metadata",
    "utc_now",
]