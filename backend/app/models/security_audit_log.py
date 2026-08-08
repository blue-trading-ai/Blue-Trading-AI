from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Final

from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
)

from app.database.connection import Base


AUDIT_EVENT_LOGIN_SUCCESS: Final[str] = "LOGIN_SUCCESS"
AUDIT_EVENT_LOGIN_FAILURE: Final[str] = "LOGIN_FAILURE"
AUDIT_EVENT_ACCOUNT_LOCKED: Final[str] = "ACCOUNT_LOCKED"
AUDIT_EVENT_ACCOUNT_UNLOCKED: Final[str] = "ACCOUNT_UNLOCKED"
AUDIT_EVENT_PASSWORD_CHANGED: Final[str] = "PASSWORD_CHANGED"
AUDIT_EVENT_USER_APPROVED: Final[str] = "USER_APPROVED"
AUDIT_EVENT_USER_REJECTED: Final[str] = "USER_REJECTED"
AUDIT_EVENT_USER_SUSPENDED: Final[str] = "USER_SUSPENDED"
AUDIT_EVENT_USER_PENDING: Final[str] = "USER_PENDING"
AUDIT_EVENT_REGISTRATION: Final[str] = "REGISTRATION"
AUDIT_EVENT_PROTECTED_ACCESS: Final[str] = "PROTECTED_ACCESS"

AUDIT_OUTCOME_SUCCESS: Final[str] = "SUCCESS"
AUDIT_OUTCOME_FAILURE: Final[str] = "FAILURE"
AUDIT_OUTCOME_BLOCKED: Final[str] = "BLOCKED"

VALID_AUDIT_EVENT_TYPES: Final[set[str]] = {
    AUDIT_EVENT_LOGIN_SUCCESS,
    AUDIT_EVENT_LOGIN_FAILURE,
    AUDIT_EVENT_ACCOUNT_LOCKED,
    AUDIT_EVENT_ACCOUNT_UNLOCKED,
    AUDIT_EVENT_PASSWORD_CHANGED,
    AUDIT_EVENT_USER_APPROVED,
    AUDIT_EVENT_USER_REJECTED,
    AUDIT_EVENT_USER_SUSPENDED,
    AUDIT_EVENT_USER_PENDING,
    AUDIT_EVENT_REGISTRATION,
    AUDIT_EVENT_PROTECTED_ACCESS,
}

VALID_AUDIT_OUTCOMES: Final[set[str]] = {
    AUDIT_OUTCOME_SUCCESS,
    AUDIT_OUTCOME_FAILURE,
    AUDIT_OUTCOME_BLOCKED,
}

MAX_EVENT_TYPE_LENGTH: Final[int] = 100
MAX_OUTCOME_LENGTH: Final[int] = 20
MAX_EMAIL_LENGTH: Final[int] = 255
MAX_IP_ADDRESS_LENGTH: Final[int] = 64
MAX_USER_AGENT_LENGTH: Final[int] = 500
MAX_REQUEST_PATH_LENGTH: Final[int] = 500
MAX_REQUEST_METHOD_LENGTH: Final[int] = 20
MAX_MESSAGE_LENGTH: Final[int] = 500
MAX_DETAILS_LENGTH: Final[int] = 8000


def utc_now() -> datetime:
    """Return one timezone-aware UTC timestamp."""

    return datetime.now(timezone.utc)


def _clean_text(
    value: Any,
    *,
    maximum_length: int,
) -> str:
    """
    Return printable, single-line text suitable for audit storage.

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


def _strict_optional_text(
    value: Any,
    *,
    field_name: str,
    maximum_length: int,
) -> str | None:
    """
    Validate optional text without silently truncating security-relevant values.
    """

    if value is None:
        return None

    resolved = str(
        value
    ).strip()

    if not resolved:
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


def _optional_text(
    value: Any,
    *,
    maximum_length: int,
) -> str | None:
    resolved = _clean_text(
        value,
        maximum_length=maximum_length,
    )

    return resolved or None


def _normalise_email(
    value: Any,
) -> str | None:
    resolved = _strict_optional_text(
        value,
        field_name="Email",
        maximum_length=MAX_EMAIL_LENGTH,
    )

    if resolved is None:
        return None

    return resolved.lower()


def _mask_email(
    value: str | None,
) -> str | None:
    """
    Return one privacy-preserving email representation.
    """

    if not value:
        return None

    local, separator, domain = (
        value.partition("@")
    )

    if not separator:
        return "[REDACTED]"

    if len(local) <= 2:
        masked_local = (
            local[:1]
            + "*"
        )
    else:
        masked_local = (
            local[:1]
            + "*" * min(
                len(local) - 2,
                6,
            )
            + local[-1:]
        )

    return (
        f"{masked_local}@{domain}"
    )


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


class SecurityAuditLog(Base):
    """
    Store security-relevant Blue-Trading-AI events.

    Privacy rules:
    - Never stores passwords, password hashes, or JWT tokens.
    - Public payloads do not expose raw IP addresses, user agents,
      full email addresses, or free-form internal details.
    """

    __tablename__ = "security_audit_logs"

    id = Column(
        Integer,
        primary_key=True,
        index=True,
    )

    event_type = Column(
        String(100),
        index=True,
        nullable=False,
    )

    outcome = Column(
        String(20),
        index=True,
        nullable=False,
    )

    actor_user_id = Column(
        Integer,
        ForeignKey(
            "users.id",
            ondelete="SET NULL",
        ),
        index=True,
        nullable=True,
    )

    actor_email = Column(
        String(255),
        index=True,
        nullable=True,
    )

    target_user_id = Column(
        Integer,
        ForeignKey(
            "users.id",
            ondelete="SET NULL",
        ),
        index=True,
        nullable=True,
    )

    target_email = Column(
        String(255),
        index=True,
        nullable=True,
    )

    ip_address = Column(
        String(64),
        nullable=True,
    )

    user_agent = Column(
        String(500),
        nullable=True,
    )

    request_path = Column(
        String(500),
        nullable=True,
    )

    request_method = Column(
        String(20),
        nullable=True,
    )

    message = Column(
        String(500),
        nullable=True,
    )

    details = Column(
        Text,
        nullable=True,
    )

    is_security_sensitive = Column(
        Boolean,
        default=True,
        nullable=False,
    )

    created_at = Column(
        DateTime(timezone=True),
        default=utc_now,
        index=True,
        nullable=False,
    )

    def normalise(self) -> None:
        """Normalize scalar fields before validation and storage."""

        self.event_type = _clean_text(
            self.event_type,
            maximum_length=MAX_EVENT_TYPE_LENGTH,
        ).upper()

        self.outcome = _clean_text(
            self.outcome,
            maximum_length=MAX_OUTCOME_LENGTH,
        ).upper()

        self.actor_email = (
            _normalise_email(
                self.actor_email
            )
        )

        self.target_email = (
            _normalise_email(
                self.target_email
            )
        )

        self.ip_address = (
            _strict_optional_text(
                self.ip_address,
                field_name="IP address",
                maximum_length=MAX_IP_ADDRESS_LENGTH,
            )
        )

        self.user_agent = (
            _strict_optional_text(
                self.user_agent,
                field_name="User agent",
                maximum_length=MAX_USER_AGENT_LENGTH,
            )
        )

        self.request_path = (
            _strict_optional_text(
                self.request_path,
                field_name="Request path",
                maximum_length=MAX_REQUEST_PATH_LENGTH,
            )
        )

        self.request_method = (
            _strict_optional_text(
                self.request_method,
                field_name="Request method",
                maximum_length=MAX_REQUEST_METHOD_LENGTH,
            )
        )

        if self.request_method:
            self.request_method = (
                self.request_method.upper()
            )

        self.message = (
            _optional_text(
                self.message,
                maximum_length=MAX_MESSAGE_LENGTH,
            )
        )

        self.details = (
            _optional_text(
                self.details,
                maximum_length=MAX_DETAILS_LENGTH,
            )
        )

        if self.actor_user_id is not None:
            if isinstance(
                self.actor_user_id,
                bool,
            ):
                raise ValueError(
                    "Actor user ID must be an integer."
                )

            try:
                self.actor_user_id = int(
                    self.actor_user_id
                )
            except (
                TypeError,
                ValueError,
                OverflowError,
            ) as exc:
                raise ValueError(
                    "Actor user ID must be an integer."
                ) from exc

        if self.target_user_id is not None:
            if isinstance(
                self.target_user_id,
                bool,
            ):
                raise ValueError(
                    "Target user ID must be an integer."
                )

            try:
                self.target_user_id = int(
                    self.target_user_id
                )
            except (
                TypeError,
                ValueError,
                OverflowError,
            ) as exc:
                raise ValueError(
                    "Target user ID must be an integer."
                ) from exc

        self.is_security_sensitive = _strict_bool(
            self.is_security_sensitive,
            field_name="is_security_sensitive",
            default=True,
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

    def validate_state(self) -> None:
        """Normalize and validate this security-audit record."""

        self.normalise()

        if (
            self.event_type
            not in VALID_AUDIT_EVENT_TYPES
        ):
            raise ValueError(
                "Invalid security audit event type."
            )

        if (
            self.outcome
            not in VALID_AUDIT_OUTCOMES
        ):
            raise ValueError(
                "Invalid security audit outcome."
            )

        if (
            self.actor_user_id is not None
            and self.actor_user_id < 1
        ):
            raise ValueError(
                "Actor user ID must be positive."
            )

        if (
            self.target_user_id is not None
            and self.target_user_id < 1
        ):
            raise ValueError(
                "Target user ID must be positive."
            )

        if (
            self.request_method is not None
            and not self.request_method.isalpha()
        ):
            raise ValueError(
                "Request method contains invalid characters."
            )

    def to_public_dict(
        self,
    ) -> dict[str, object]:
        """
        Return safe audit metadata.

        Raw IP addresses, user agents, and internal details are not
        included in public API responses.
        """

        return {
            "id": self.id,
            "event_type": self.event_type,
            "outcome": self.outcome,
            "actor_user_id": (
                self.actor_user_id
            ),
            "actor_email": _mask_email(
                self.actor_email
            ),
            "target_user_id": (
                self.target_user_id
            ),
            "target_email": _mask_email(
                self.target_email
            ),
            "ip_address_present": bool(
                self.ip_address
            ),
            "user_agent_present": bool(
                self.user_agent
            ),
            "request_path": (
                self.request_path
            ),
            "request_method": (
                self.request_method
            ),
            "message": self.message,
            "details_recorded": bool(
                self.details
            ),
            "is_security_sensitive": (
                self.is_security_sensitive is True
            ),
            "created_at": self.created_at,
        }

    def __repr__(self) -> str:
        return (
            "<SecurityAuditLog("
            f"id={self.id}, "
            f"event_type='{self.event_type}', "
            f"outcome='{self.outcome}', "
            f"actor_user_id={self.actor_user_id}, "
            f"target_user_id={self.target_user_id}"
            ")>"
        )


__all__ = [
    "AUDIT_EVENT_ACCOUNT_LOCKED",
    "AUDIT_EVENT_ACCOUNT_UNLOCKED",
    "AUDIT_EVENT_LOGIN_FAILURE",
    "AUDIT_EVENT_LOGIN_SUCCESS",
    "AUDIT_EVENT_PASSWORD_CHANGED",
    "AUDIT_EVENT_PROTECTED_ACCESS",
    "AUDIT_EVENT_REGISTRATION",
    "AUDIT_EVENT_USER_APPROVED",
    "AUDIT_EVENT_USER_PENDING",
    "AUDIT_EVENT_USER_REJECTED",
    "AUDIT_EVENT_USER_SUSPENDED",
    "AUDIT_OUTCOME_BLOCKED",
    "AUDIT_OUTCOME_FAILURE",
    "AUDIT_OUTCOME_SUCCESS",
    "MAX_DETAILS_LENGTH",
    "VALID_AUDIT_EVENT_TYPES",
    "VALID_AUDIT_OUTCOMES",
    "SecurityAuditLog",
    "utc_now",
]