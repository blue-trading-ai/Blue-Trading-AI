from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Final

from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    Index,
    Integer,
    JSON,
    String,
    Text,
    UniqueConstraint,
)

from app.database.connection import Base


JOB_TYPE_MARKET_REFRESH: Final[str] = "MARKET_REFRESH"
JOB_TYPE_SIGNAL_GENERATION: Final[str] = "SIGNAL_GENERATION"
JOB_TYPE_SIGNAL_EXPIRY: Final[str] = "SIGNAL_EXPIRY"
JOB_TYPE_LEARNING_REFRESH: Final[str] = "LEARNING_REFRESH"

JOB_STATUS_PENDING: Final[str] = "PENDING"
JOB_STATUS_RUNNING: Final[str] = "RUNNING"
JOB_STATUS_COMPLETED: Final[str] = "COMPLETED"
JOB_STATUS_FAILED: Final[str] = "FAILED"
JOB_STATUS_CANCELLED: Final[str] = "CANCELLED"
JOB_STATUS_RETRY_WAIT: Final[str] = "RETRY_WAIT"

VALID_JOB_TYPES: Final[set[str]] = {
    JOB_TYPE_MARKET_REFRESH,
    JOB_TYPE_SIGNAL_GENERATION,
    JOB_TYPE_SIGNAL_EXPIRY,
    JOB_TYPE_LEARNING_REFRESH,
}

VALID_JOB_STATUSES: Final[set[str]] = {
    JOB_STATUS_PENDING,
    JOB_STATUS_RUNNING,
    JOB_STATUS_COMPLETED,
    JOB_STATUS_FAILED,
    JOB_STATUS_CANCELLED,
    JOB_STATUS_RETRY_WAIT,
}

TERMINAL_JOB_STATUSES: Final[set[str]] = {
    JOB_STATUS_COMPLETED,
    JOB_STATUS_FAILED,
    JOB_STATUS_CANCELLED,
}

MAX_JOB_UID_LENGTH: Final[int] = 64
MAX_SYMBOL_LENGTH: Final[int] = 40
MAX_TIMEFRAME_LENGTH: Final[int] = 20
MAX_WORKER_NAME_LENGTH: Final[int] = 100
MAX_ERROR_MESSAGE_LENGTH: Final[int] = 4000
MAX_ATTEMPTS: Final[int] = 10
MAX_PRIORITY: Final[int] = 1000
MAX_DURATION_MS: Final[int] = 86_400_000


def utc_now() -> datetime:
    """Return one timezone-aware UTC timestamp."""

    return datetime.now(timezone.utc)


def _as_utc(
    value: datetime | None,
) -> datetime | None:
    """Normalize one optional datetime to timezone-aware UTC."""

    if value is None:
        return None

    if value.tzinfo is None:
        return value.replace(
            tzinfo=timezone.utc
        )

    return value.astimezone(
        timezone.utc
    )


def _normalize_job_uid(
    value: Any,
) -> str:
    """
    Validate the unique public job identifier without silently truncating it.
    """

    raw = str(
        value or ""
    ).strip()

    if not raw:
        raise ValueError(
            "Background job UID is required."
        )

    if len(
        raw
    ) > MAX_JOB_UID_LENGTH:
        raise ValueError(
            "Background job UID is too long."
        )

    if any(
        not character.isprintable()
        or character in {
            "\r",
            "\n",
            "\t",
        }
        for character in raw
    ):
        raise ValueError(
            "Background job UID contains unsupported characters."
        )

    return raw


def _clean_text(
    value: Any,
    *,
    maximum_length: int,
) -> str:
    """
    Return printable, single-line text.

    Control characters are replaced to prevent log injection.
    """

    raw = str(
        value or ""
    )

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

    return cleaned[
        :maximum_length
    ]


def _safe_non_negative_int(
    value: Any,
    *,
    field_name: str,
    maximum: int | None = None,
) -> int:
    if isinstance(
        value,
        bool,
    ):
        raise ValueError(
            f"{field_name} must be an integer."
        )

    try:
        resolved = int(
            value or 0
        )
    except (
        TypeError,
        ValueError,
        OverflowError,
    ) as exc:
        raise ValueError(
            f"{field_name} must be an integer."
        ) from exc

    if resolved < 0:
        raise ValueError(
            f"{field_name} cannot be negative."
        )

    if (
        maximum is not None
        and resolved > maximum
    ):
        raise ValueError(
            f"{field_name} is above the allowed maximum."
        )

    return resolved


def _strict_bool(
    value: Any,
    *,
    field_name: str,
    default: bool,
) -> bool:
    """Resolve one Boolean without arbitrary Python truthiness."""

    if value is None:
        return default

    if isinstance(
        value,
        bool,
    ):
        return value

    if isinstance(
        value,
        int,
    ) and value in {
        0,
        1,
    }:
        return bool(
            value
        )

    if isinstance(
        value,
        str,
    ):
        normalized = (
            value.strip()
            .lower()
        )

        if normalized in {
            "true",
            "1",
            "yes",
            "on",
        }:
            return True

        if normalized in {
            "false",
            "0",
            "no",
            "off",
        }:
            return False

    raise ValueError(
        f"{field_name} must be a boolean."
    )


class BackgroundJob(Base):
    """
    Persistent background-processing job.

    Security and reliability:
    - Stores job metadata, never credentials.
    - Tracks retries, failures, timing, and ownership.
    - Supports market refresh and signal-generation workflows.
    - Does not execute broker orders.
    """

    __tablename__ = "background_jobs"

    id = Column(
        Integer,
        primary_key=True,
        index=True,
    )

    job_uid = Column(
        String(64),
        nullable=False,
        unique=True,
        index=True,
    )

    job_type = Column(
        String(40),
        nullable=False,
        index=True,
    )

    status = Column(
        String(30),
        nullable=False,
        default=JOB_STATUS_PENDING,
        index=True,
    )

    symbol = Column(
        String(40),
        nullable=True,
        index=True,
    )

    timeframe = Column(
        String(20),
        nullable=True,
        index=True,
    )

    payload = Column(
        JSON,
        nullable=True,
    )

    result_payload = Column(
        JSON,
        nullable=True,
    )

    error_message = Column(
        Text,
        nullable=True,
    )

    attempt_count = Column(
        Integer,
        nullable=False,
        default=0,
        index=True,
    )

    max_attempts = Column(
        Integer,
        nullable=False,
        default=3,
    )

    priority = Column(
        Integer,
        nullable=False,
        default=100,
        index=True,
    )

    is_recurring = Column(
        Boolean,
        nullable=False,
        default=False,
        index=True,
    )

    scheduled_at = Column(
        DateTime(timezone=True),
        nullable=False,
        default=utc_now,
        index=True,
    )

    started_at = Column(
        DateTime(timezone=True),
        nullable=True,
        index=True,
    )

    finished_at = Column(
        DateTime(timezone=True),
        nullable=True,
        index=True,
    )

    retry_at = Column(
        DateTime(timezone=True),
        nullable=True,
        index=True,
    )

    heartbeat_at = Column(
        DateTime(timezone=True),
        nullable=True,
        index=True,
    )

    duration_ms = Column(
        Integer,
        nullable=True,
    )

    worker_name = Column(
        String(100),
        nullable=True,
        index=True,
    )

    created_at = Column(
        DateTime(timezone=True),
        nullable=False,
        default=utc_now,
    )

    updated_at = Column(
        DateTime(timezone=True),
        nullable=False,
        default=utc_now,
        onupdate=utc_now,
    )

    __table_args__ = (
        UniqueConstraint(
            "job_uid",
            name="uq_background_jobs_job_uid",
        ),
        Index(
            "ix_background_jobs_status_schedule",
            "status",
            "scheduled_at",
        ),
        Index(
            "ix_background_jobs_type_status",
            "job_type",
            "status",
        ),
        Index(
            "ix_background_jobs_symbol_timeframe",
            "symbol",
            "timeframe",
        ),
        Index(
            "ix_background_jobs_priority_schedule",
            "priority",
            "scheduled_at",
        ),
    )

    @property
    def normalized_status(self) -> str:
        return _clean_text(
            self.status or JOB_STATUS_PENDING,
            maximum_length=30,
        ).upper()

    @property
    def is_terminal(self) -> bool:
        return (
            self.normalized_status
            in TERMINAL_JOB_STATUSES
        )

    def normalise(self) -> None:
        self.job_uid = _normalize_job_uid(
            self.job_uid
        )

        self.job_type = _clean_text(
            self.job_type,
            maximum_length=40,
        ).upper()

        self.status = self.normalized_status

        self.symbol = (
            _clean_text(
                self.symbol,
                maximum_length=MAX_SYMBOL_LENGTH,
            ).upper()
            or None
        )

        self.timeframe = (
            _clean_text(
                self.timeframe,
                maximum_length=MAX_TIMEFRAME_LENGTH,
            )
            or None
        )

        self.error_message = (
            _clean_text(
                self.error_message,
                maximum_length=MAX_ERROR_MESSAGE_LENGTH,
            )
            or None
        )

        self.worker_name = (
            _clean_text(
                self.worker_name,
                maximum_length=MAX_WORKER_NAME_LENGTH,
            )
            or None
        )

        self.attempt_count = _safe_non_negative_int(
            self.attempt_count,
            field_name="Attempt count",
        )

        self.max_attempts = _safe_non_negative_int(
            self.max_attempts,
            field_name="Maximum attempts",
            maximum=MAX_ATTEMPTS,
        )

        self.priority = _safe_non_negative_int(
            self.priority,
            field_name="Priority",
            maximum=MAX_PRIORITY,
        )

        if self.duration_ms is not None:
            self.duration_ms = _safe_non_negative_int(
                self.duration_ms,
                field_name="Duration",
                maximum=MAX_DURATION_MS,
            )

        self.is_recurring = _strict_bool(
            self.is_recurring,
            field_name="is_recurring",
            default=False,
        )

        self.scheduled_at = (
            _as_utc(
                self.scheduled_at
            )
            or utc_now()
        )

        self.started_at = _as_utc(
            self.started_at
        )

        self.finished_at = _as_utc(
            self.finished_at
        )

        self.retry_at = _as_utc(
            self.retry_at
        )

        self.heartbeat_at = _as_utc(
            self.heartbeat_at
        )

        self.created_at = (
            _as_utc(
                self.created_at
            )
            or utc_now()
        )

        self.updated_at = (
            _as_utc(
                self.updated_at
            )
            or utc_now()
        )

    def validate_state(self) -> None:
        """Normalize and validate the stored background-job state."""

        self.normalise()

        if not self.job_uid:
            raise ValueError(
                "Background job UID is required."
            )

        if self.job_type not in VALID_JOB_TYPES:
            raise ValueError(
                "Invalid background job type."
            )

        if self.status not in VALID_JOB_STATUSES:
            raise ValueError(
                "Invalid background job status."
            )

        if self.max_attempts < 1:
            raise ValueError(
                "Maximum attempts must be at least one."
            )

        if self.attempt_count > self.max_attempts:
            raise ValueError(
                "Attempt count cannot exceed maximum attempts."
            )

        if self.priority < 1:
            raise ValueError(
                "Priority must be at least one."
            )

        if (
            self.status == JOB_STATUS_RUNNING
            and self.started_at is None
        ):
            raise ValueError(
                "Running job must have started_at."
            )

        if (
            self.status
            in TERMINAL_JOB_STATUSES
            and self.finished_at is None
        ):
            raise ValueError(
                "Terminal job must have finished_at."
            )

        if (
            self.status == JOB_STATUS_RETRY_WAIT
            and self.retry_at is None
        ):
            raise ValueError(
                "Retry-wait job must have retry_at."
            )

        if (
            self.status != JOB_STATUS_RETRY_WAIT
            and self.retry_at is not None
        ):
            raise ValueError(
                "Only retry-wait jobs may have retry_at."
            )

        if (
            self.finished_at is not None
            and self.started_at is not None
            and self.finished_at < self.started_at
        ):
            raise ValueError(
                "finished_at cannot be earlier than started_at."
            )

    def mark_running(
        self,
        *,
        worker_name: str,
    ) -> None:
        if self.normalized_status not in {
            JOB_STATUS_PENDING,
            JOB_STATUS_RETRY_WAIT,
        }:
            raise ValueError(
                "Only pending or retry-wait jobs can start."
            )

        current_attempts = _safe_non_negative_int(
            self.attempt_count,
            field_name="Attempt count",
        )

        max_attempts = _safe_non_negative_int(
            self.max_attempts,
            field_name="Maximum attempts",
            maximum=MAX_ATTEMPTS,
        )

        if current_attempts >= max_attempts:
            raise ValueError(
                "Maximum job attempts have been reached."
            )

        now = utc_now()

        self.status = JOB_STATUS_RUNNING
        self.started_at = now
        self.finished_at = None
        self.retry_at = None
        self.heartbeat_at = now
        self.worker_name = (
            _clean_text(
                worker_name or "default-worker",
                maximum_length=MAX_WORKER_NAME_LENGTH,
            )
            or "default-worker"
        )
        self.attempt_count = (
            current_attempts
            + 1
        )
        self.updated_at = now

    def mark_completed(
        self,
        *,
        result_payload: dict | None = None,
        duration_ms: int | None = None,
    ) -> None:
        if (
            self.normalized_status
            != JOB_STATUS_RUNNING
        ):
            raise ValueError(
                "Only a running job can be completed."
            )

        now = utc_now()

        self.status = JOB_STATUS_COMPLETED
        self.result_payload = result_payload
        self.error_message = None
        self.finished_at = now
        self.retry_at = None
        self.duration_ms = (
            None
            if duration_ms is None
            else _safe_non_negative_int(
                duration_ms,
                field_name="Duration",
                maximum=MAX_DURATION_MS,
            )
        )
        self.heartbeat_at = now
        self.updated_at = now

    def mark_failed(
        self,
        *,
        error_message: str,
        retry_at: datetime | None = None,
        duration_ms: int | None = None,
    ) -> None:
        if (
            self.normalized_status
            != JOB_STATUS_RUNNING
        ):
            raise ValueError(
                "Only a running job can fail."
            )

        now = utc_now()

        self.error_message = (
            _clean_text(
                error_message
                or "Background job failed.",
                maximum_length=MAX_ERROR_MESSAGE_LENGTH,
            )
            or "Background job failed."
        )
        self.finished_at = now
        self.duration_ms = (
            None
            if duration_ms is None
            else _safe_non_negative_int(
                duration_ms,
                field_name="Duration",
                maximum=MAX_DURATION_MS,
            )
        )
        self.heartbeat_at = now

        resolved_retry_at = _as_utc(
            retry_at
        )

        current_attempts = _safe_non_negative_int(
            self.attempt_count,
            field_name="Attempt count",
        )
        maximum_attempts = _safe_non_negative_int(
            self.max_attempts,
            field_name="Maximum attempts",
            maximum=MAX_ATTEMPTS,
        )

        if maximum_attempts < 1:
            raise ValueError(
                "Maximum attempts must be at least one."
            )

        if (
            resolved_retry_at is not None
            and current_attempts
            < maximum_attempts
        ):
            if resolved_retry_at <= now:
                raise ValueError(
                    "retry_at must be in the future."
                )

            self.status = JOB_STATUS_RETRY_WAIT
            self.retry_at = resolved_retry_at
        else:
            self.status = JOB_STATUS_FAILED
            self.retry_at = None

        self.updated_at = now

    def cancel(self) -> None:
        if self.is_terminal:
            raise ValueError(
                "Terminal jobs cannot be cancelled."
            )

        now = utc_now()

        self.status = JOB_STATUS_CANCELLED
        self.finished_at = now
        self.retry_at = None
        self.updated_at = now

    def touch_heartbeat(self) -> None:
        if (
            self.normalized_status
            != JOB_STATUS_RUNNING
        ):
            raise ValueError(
                "Only a running job can update its heartbeat."
            )

        now = utc_now()

        self.heartbeat_at = now
        self.updated_at = now

    def to_public_dict(self) -> dict[str, object]:
        """
        Return safe metadata without internal payloads or error text.
        """

        return {
            "id": self.id,
            "job_uid": self.job_uid,
            "job_type": self.job_type,
            "status": self.status,
            "symbol": self.symbol,
            "timeframe": self.timeframe,
            "payload_present": bool(
                self.payload
            ),
            "result_payload_present": bool(
                self.result_payload
            ),
            "error_present": bool(
                self.error_message
            ),
            "attempt_count": self.attempt_count,
            "max_attempts": self.max_attempts,
            "priority": self.priority,
            "is_recurring": (
                self.is_recurring is True
            ),
            "scheduled_at": self.scheduled_at,
            "started_at": self.started_at,
            "finished_at": self.finished_at,
            "retry_at": self.retry_at,
            "heartbeat_at": self.heartbeat_at,
            "duration_ms": self.duration_ms,
            "worker_name": self.worker_name,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }


__all__ = [
    "BackgroundJob",
    "JOB_STATUS_CANCELLED",
    "JOB_STATUS_COMPLETED",
    "JOB_STATUS_FAILED",
    "JOB_STATUS_PENDING",
    "JOB_STATUS_RETRY_WAIT",
    "JOB_STATUS_RUNNING",
    "JOB_TYPE_LEARNING_REFRESH",
    "JOB_TYPE_MARKET_REFRESH",
    "JOB_TYPE_SIGNAL_EXPIRY",
    "JOB_TYPE_SIGNAL_GENERATION",
    "MAX_ATTEMPTS",
    "MAX_DURATION_MS",
    "MAX_PRIORITY",
    "TERMINAL_JOB_STATUSES",
    "VALID_JOB_STATUSES",
    "VALID_JOB_TYPES",
    "utc_now",
]