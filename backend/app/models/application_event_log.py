from __future__ import annotations

import math
import re
from datetime import datetime, timezone
from typing import Any, Final

from sqlalchemy import (
    Column,
    DateTime,
    Float,
    Index,
    Integer,
    JSON,
    String,
    Text,
)

from app.database.connection import Base


LOG_LEVEL_DEBUG: Final[str] = "DEBUG"
LOG_LEVEL_INFO: Final[str] = "INFO"
LOG_LEVEL_WARNING: Final[str] = "WARNING"
LOG_LEVEL_ERROR: Final[str] = "ERROR"
LOG_LEVEL_CRITICAL: Final[str] = "CRITICAL"

EVENT_TYPE_APPLICATION: Final[str] = "APPLICATION"
EVENT_TYPE_HTTP_REQUEST: Final[str] = "HTTP_REQUEST"
EVENT_TYPE_BACKGROUND_JOB: Final[str] = "BACKGROUND_JOB"
EVENT_TYPE_DATABASE: Final[str] = "DATABASE"
EVENT_TYPE_SECURITY: Final[str] = "SECURITY"
EVENT_TYPE_PERFORMANCE: Final[str] = "PERFORMANCE"
EVENT_TYPE_HEALTH: Final[str] = "HEALTH"

VALID_LOG_LEVELS: Final[set[str]] = {
    LOG_LEVEL_DEBUG,
    LOG_LEVEL_INFO,
    LOG_LEVEL_WARNING,
    LOG_LEVEL_ERROR,
    LOG_LEVEL_CRITICAL,
}

VALID_EVENT_TYPES: Final[set[str]] = {
    EVENT_TYPE_APPLICATION,
    EVENT_TYPE_HTTP_REQUEST,
    EVENT_TYPE_BACKGROUND_JOB,
    EVENT_TYPE_DATABASE,
    EVENT_TYPE_SECURITY,
    EVENT_TYPE_PERFORMANCE,
    EVENT_TYPE_HEALTH,
}

MAX_EVENT_UID_LENGTH: Final[int] = 64
MAX_EVENT_NAME_LENGTH: Final[int] = 120
MAX_MESSAGE_LENGTH: Final[int] = 8000
MAX_SOURCE_LENGTH: Final[int] = 120
MAX_REQUEST_ID_LENGTH: Final[int] = 80
MAX_JOB_UID_LENGTH: Final[int] = 64
MAX_METHOD_LENGTH: Final[int] = 12
MAX_PATH_LENGTH: Final[int] = 500
MAX_CLIENT_IP_HASH_LENGTH: Final[int] = 128
MAX_EXCEPTION_TYPE_LENGTH: Final[int] = 160
MAX_EXCEPTION_MESSAGE_LENGTH: Final[int] = 8000
MAX_DURATION_MS: Final[float] = 86_400_000.0

SAFE_IDENTIFIER_PATTERN = re.compile(
    r"^[A-Za-z0-9._:-]+$"
)


def utc_now() -> datetime:
    """Return one timezone-aware UTC timestamp."""

    return datetime.now(timezone.utc)


def _normalize_unique_identifier(
    value: Any,
    *,
    field_name: str,
    maximum_length: int,
    required: bool = False,
) -> str | None:
    """
    Validate a persisted identifier without silently truncating it.
    """

    if value is None:
        if required:
            raise ValueError(
                f"{field_name} is required."
            )
        return None

    resolved = str(
        value
    ).strip()

    if not resolved:
        if required:
            raise ValueError(
                f"{field_name} is required."
            )
        return None

    if len(
        resolved
    ) > maximum_length:
        raise ValueError(
            f"{field_name} is too long."
        )

    if any(
        not character.isprintable()
        or character in {
            "\r",
            "\n",
            "\t",
        }
        for character in resolved
    ):
        raise ValueError(
            f"{field_name} contains unsupported characters."
        )

    return resolved


def _clean_text(
    value: Any,
    *,
    maximum_length: int,
) -> str:
    """
    Return printable, single-line text for persistent logging.

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


def _normalise_optional_text(
    value: Any,
    *,
    maximum_length: int,
) -> str | None:
    resolved = _clean_text(
        value,
        maximum_length=maximum_length,
    )

    return resolved or None


def _validate_identifier(
    value: str | None,
    *,
    field_name: str,
    required: bool = False,
) -> None:
    if value is None:
        if required:
            raise ValueError(
                f"{field_name} is required."
            )
        return

    if not SAFE_IDENTIFIER_PATTERN.fullmatch(
        value
    ):
        raise ValueError(
            f"{field_name} contains invalid characters."
        )


class ApplicationEventLog(Base):
    """
    Structured production application event.

    Privacy rules:
    - Never stores passwords, access tokens, refresh tokens,
      reset tokens, verification tokens, API secrets, or SMTP secrets.
    - Never stores complete Authorization or Cookie headers.
    - Never stores raw request bodies.
    - Raw exception messages are excluded from public payloads.
    """

    __tablename__ = "application_event_logs"

    id = Column(
        Integer,
        primary_key=True,
        index=True,
    )

    event_uid = Column(
        String(64),
        nullable=False,
        unique=True,
        index=True,
    )

    level = Column(
        String(20),
        nullable=False,
        default=LOG_LEVEL_INFO,
        index=True,
    )

    event_type = Column(
        String(40),
        nullable=False,
        default=EVENT_TYPE_APPLICATION,
        index=True,
    )

    event_name = Column(
        String(120),
        nullable=False,
        index=True,
    )

    message = Column(
        Text,
        nullable=False,
    )

    source = Column(
        String(120),
        nullable=True,
        index=True,
    )

    request_id = Column(
        String(80),
        nullable=True,
        index=True,
    )

    user_id = Column(
        Integer,
        nullable=True,
        index=True,
    )

    job_uid = Column(
        String(64),
        nullable=True,
        index=True,
    )

    method = Column(
        String(12),
        nullable=True,
        index=True,
    )

    path = Column(
        String(500),
        nullable=True,
        index=True,
    )

    status_code = Column(
        Integer,
        nullable=True,
        index=True,
    )

    duration_ms = Column(
        Float,
        nullable=True,
        index=True,
    )

    client_ip_hash = Column(
        String(128),
        nullable=True,
        index=True,
    )

    exception_type = Column(
        String(160),
        nullable=True,
        index=True,
    )

    exception_message = Column(
        Text,
        nullable=True,
    )

    metadata_json = Column(
        JSON,
        nullable=True,
    )

    created_at = Column(
        DateTime(timezone=True),
        nullable=False,
        default=utc_now,
        index=True,
    )

    __table_args__ = (
        Index(
            "ix_application_event_logs_level_created",
            "level",
            "created_at",
        ),
        Index(
            "ix_application_event_logs_type_created",
            "event_type",
            "created_at",
        ),
        Index(
            "ix_application_event_logs_request_path",
            "request_id",
            "path",
        ),
        Index(
            "ix_application_event_logs_status_duration",
            "status_code",
            "duration_ms",
        ),
        Index(
            "ix_application_event_logs_job_created",
            "job_uid",
            "created_at",
        ),
    )

    def normalise(self) -> None:
        """Normalize all scalar fields before validation and storage."""

        self.event_uid = str(
            _normalize_unique_identifier(
                self.event_uid,
                field_name="Event UID",
                maximum_length=MAX_EVENT_UID_LENGTH,
                required=True,
            )
        )

        self.level = _clean_text(
            self.level or LOG_LEVEL_INFO,
            maximum_length=20,
        ).upper()

        self.event_type = _clean_text(
            self.event_type
            or EVENT_TYPE_APPLICATION,
            maximum_length=40,
        ).upper()

        self.event_name = _clean_text(
            self.event_name
            or "unnamed_event",
            maximum_length=MAX_EVENT_NAME_LENGTH,
        )

        self.message = _clean_text(
            self.message
            or "No message provided.",
            maximum_length=MAX_MESSAGE_LENGTH,
        )

        self.source = (
            _normalise_optional_text(
                self.source,
                maximum_length=MAX_SOURCE_LENGTH,
            )
        )

        self.request_id = (
            _normalize_unique_identifier(
                self.request_id,
                field_name="Request ID",
                maximum_length=MAX_REQUEST_ID_LENGTH,
                required=False,
            )
        )

        self.job_uid = (
            _normalize_unique_identifier(
                self.job_uid,
                field_name="Job UID",
                maximum_length=MAX_JOB_UID_LENGTH,
                required=False,
            )
        )

        self.method = (
            _normalise_optional_text(
                self.method,
                maximum_length=MAX_METHOD_LENGTH,
            )
        )

        if self.method:
            self.method = self.method.upper()

        self.path = (
            _normalise_optional_text(
                self.path,
                maximum_length=MAX_PATH_LENGTH,
            )
        )

        self.client_ip_hash = (
            _normalise_optional_text(
                self.client_ip_hash,
                maximum_length=MAX_CLIENT_IP_HASH_LENGTH,
            )
        )

        self.exception_type = (
            _normalise_optional_text(
                self.exception_type,
                maximum_length=MAX_EXCEPTION_TYPE_LENGTH,
            )
        )

        self.exception_message = (
            _normalise_optional_text(
                self.exception_message,
                maximum_length=MAX_EXCEPTION_MESSAGE_LENGTH,
            )
        )

        if self.user_id is not None:
            if isinstance(
                self.user_id,
                bool,
            ):
                raise ValueError(
                    "User ID must be an integer."
                )

            try:
                self.user_id = int(
                    self.user_id
                )
            except (
                TypeError,
                ValueError,
                OverflowError,
            ) as exc:
                raise ValueError(
                    "User ID must be an integer."
                ) from exc

        if self.status_code is not None:
            if isinstance(
                self.status_code,
                bool,
            ):
                raise ValueError(
                    "Status code must be an integer."
                )

            try:
                self.status_code = int(
                    self.status_code
                )
            except (
                TypeError,
                ValueError,
                OverflowError,
            ) as exc:
                raise ValueError(
                    "Status code must be an integer."
                ) from exc

        if self.duration_ms is not None:
            if isinstance(
                self.duration_ms,
                bool,
            ):
                raise ValueError(
                    "Duration must be numeric."
                )

            try:
                self.duration_ms = float(
                    self.duration_ms
                )
            except (
                TypeError,
                ValueError,
                OverflowError,
            ) as exc:
                raise ValueError(
                    "Duration must be numeric."
                ) from exc

    def validate_state(self) -> None:
        """Normalize and validate this event before persistence."""

        self.normalise()

        _validate_identifier(
            self.event_uid,
            field_name="Event UID",
            required=True,
        )

        _validate_identifier(
            self.request_id,
            field_name="Request ID",
        )

        _validate_identifier(
            self.job_uid,
            field_name="Job UID",
        )

        if (
            self.level
            not in VALID_LOG_LEVELS
        ):
            raise ValueError(
                "Invalid application log level."
            )

        if (
            self.event_type
            not in VALID_EVENT_TYPES
        ):
            raise ValueError(
                "Invalid application event type."
            )

        if not self.event_name:
            raise ValueError(
                "Event name is required."
            )

        if not self.message:
            raise ValueError(
                "Event message is required."
            )

        if (
            self.user_id is not None
            and self.user_id < 1
        ):
            raise ValueError(
                "User ID must be positive."
            )

        if (
            self.status_code is not None
            and not (
                100
                <= self.status_code
                <= 599
            )
        ):
            raise ValueError(
                "HTTP status code must be between 100 and 599."
            )

        if self.duration_ms is not None:
            if not math.isfinite(
                self.duration_ms
            ):
                raise ValueError(
                    "Duration must be finite."
                )

            if self.duration_ms < 0:
                raise ValueError(
                    "Duration cannot be negative."
                )

            if (
                self.duration_ms
                > MAX_DURATION_MS
            ):
                raise ValueError(
                    "Duration exceeds the maximum supported value."
                )

        if (
            self.client_ip_hash is not None
            and not re.fullmatch(
                r"[A-Fa-f0-9]{64,128}",
                self.client_ip_hash,
            )
        ):
            raise ValueError(
                "Client IP hash is invalid."
            )

        if self.created_at is None:
            self.created_at = utc_now()
        elif self.created_at.tzinfo is None:
            self.created_at = (
                self.created_at.replace(
                    tzinfo=timezone.utc
                )
            )
        else:
            self.created_at = (
                self.created_at.astimezone(
                    timezone.utc
                )
            )

    def to_public_dict(
        self,
    ) -> dict[str, object]:
        """
        Return safe event metadata.

        The raw exception message and client IP hash are not exposed.
        """

        return {
            "id": self.id,
            "event_uid": self.event_uid,
            "level": self.level,
            "event_type": self.event_type,
            "event_name": self.event_name,
            "message": self.message,
            "source": self.source,
            "request_id": self.request_id,
            "user_id": self.user_id,
            "job_uid": self.job_uid,
            "method": self.method,
            "path": self.path,
            "status_code": self.status_code,
            "duration_ms": self.duration_ms,
            "client_ip_hash_present": bool(
                self.client_ip_hash
            ),
            "exception_type": (
                self.exception_type
            ),
            "exception_message_recorded": bool(
                self.exception_message
            ),
            "metadata": self.metadata_json,
            "created_at": self.created_at,
        }


__all__ = [
    "ApplicationEventLog",
    "EVENT_TYPE_APPLICATION",
    "EVENT_TYPE_BACKGROUND_JOB",
    "EVENT_TYPE_DATABASE",
    "EVENT_TYPE_HEALTH",
    "EVENT_TYPE_HTTP_REQUEST",
    "EVENT_TYPE_PERFORMANCE",
    "EVENT_TYPE_SECURITY",
    "LOG_LEVEL_CRITICAL",
    "LOG_LEVEL_DEBUG",
    "LOG_LEVEL_ERROR",
    "LOG_LEVEL_INFO",
    "LOG_LEVEL_WARNING",
    "MAX_DURATION_MS",
    "SAFE_IDENTIFIER_PATTERN",
    "VALID_EVENT_TYPES",
    "VALID_LOG_LEVELS",
    "utc_now",
]