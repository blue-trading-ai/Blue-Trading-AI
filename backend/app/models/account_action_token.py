from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Final

from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
)
from sqlalchemy.orm import relationship

from app.database.connection import Base


TOKEN_PURPOSE_EMAIL_VERIFICATION: Final[str] = (
    "EMAIL_VERIFICATION"
)
TOKEN_PURPOSE_PASSWORD_RESET: Final[str] = (
    "PASSWORD_RESET"
)

TOKEN_STATUS_ACTIVE: Final[str] = "ACTIVE"
TOKEN_STATUS_USED: Final[str] = "USED"
TOKEN_STATUS_REVOKED: Final[str] = "REVOKED"
TOKEN_STATUS_EXPIRED: Final[str] = "EXPIRED"

TOKEN_REVOKE_REPLACED: Final[str] = "REPLACED"
TOKEN_REVOKE_PASSWORD_CHANGED: Final[str] = (
    "PASSWORD_CHANGED"
)
TOKEN_REVOKE_OWNER_ACTION: Final[str] = "OWNER_ACTION"
TOKEN_REVOKE_ACCOUNT_BLOCKED: Final[str] = (
    "ACCOUNT_BLOCKED"
)
TOKEN_REVOKE_SECURITY_EVENT: Final[str] = (
    "SECURITY_EVENT"
)
TOKEN_REVOKE_EXPIRED: Final[str] = "EXPIRED"

VALID_TOKEN_PURPOSES: Final[set[str]] = {
    TOKEN_PURPOSE_EMAIL_VERIFICATION,
    TOKEN_PURPOSE_PASSWORD_RESET,
}

VALID_TOKEN_STATUSES: Final[set[str]] = {
    TOKEN_STATUS_ACTIVE,
    TOKEN_STATUS_USED,
    TOKEN_STATUS_REVOKED,
    TOKEN_STATUS_EXPIRED,
}

MAX_TOKEN_ID_LENGTH: Final[int] = 64
MAX_TOKEN_HASH_LENGTH: Final[int] = 64
MAX_EMAIL_LENGTH: Final[int] = 255
MAX_REVOKE_REASON_LENGTH: Final[int] = 100
MAX_IP_LENGTH: Final[int] = 64
MAX_USER_AGENT_LENGTH: Final[int] = 500


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


def _clean_text(
    value: Any,
    *,
    maximum_length: int,
) -> str:
    """
    Return printable, single-line text.

    Control characters are replaced to prevent log or audit injection.
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


def _normalise_token_id(
    value: Any,
) -> str:
    """
    Normalize one token identifier without silently truncating it.
    """

    resolved = _clean_text(
        value,
        maximum_length=(
            MAX_TOKEN_ID_LENGTH + 1
        ),
    )

    if not resolved:
        raise ValueError(
            "Token ID is required."
        )

    if len(
        resolved
    ) > MAX_TOKEN_ID_LENGTH:
        raise ValueError(
            "Token ID exceeds the maximum supported length."
        )

    return resolved


def _normalise_reason(
    reason: str | None,
) -> str:
    resolved = _clean_text(
        reason
        or TOKEN_REVOKE_SECURITY_EVENT,
        maximum_length=(
            MAX_REVOKE_REASON_LENGTH
        ),
    ).upper()

    return (
        resolved
        or TOKEN_REVOKE_SECURITY_EVENT
    )


def _mask_email(
    value: str | None,
) -> str | None:
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


class AccountActionToken(Base):
    """
    One-time token for email verification or password reset.

    Security design:
    - Raw token values are never stored.
    - Only SHA-256 token hashes are persisted.
    - Tokens are single-use.
    - Tokens expire automatically.
    - Newer tokens can revoke older active tokens.
    """

    __tablename__ = "account_action_tokens"

    id = Column(
        Integer,
        primary_key=True,
        index=True,
    )

    token_id = Column(
        String(64),
        nullable=False,
        unique=True,
        index=True,
    )

    token_hash = Column(
        String(64),
        nullable=False,
        unique=True,
        index=True,
    )

    user_id = Column(
        Integer,
        ForeignKey(
            "users.id",
            ondelete="CASCADE",
        ),
        nullable=False,
        index=True,
    )

    email = Column(
        String(255),
        nullable=False,
        index=True,
    )

    purpose = Column(
        String(40),
        nullable=False,
        index=True,
    )

    status = Column(
        String(20),
        nullable=False,
        default=TOKEN_STATUS_ACTIVE,
        index=True,
    )

    is_active = Column(
        Boolean,
        nullable=False,
        default=True,
        index=True,
    )

    issued_at = Column(
        DateTime(timezone=True),
        nullable=False,
        default=utc_now,
    )

    expires_at = Column(
        DateTime(timezone=True),
        nullable=False,
        index=True,
    )

    used_at = Column(
        DateTime(timezone=True),
        nullable=True,
        index=True,
    )

    revoked_at = Column(
        DateTime(timezone=True),
        nullable=True,
        index=True,
    )

    revoke_reason = Column(
        String(MAX_REVOKE_REASON_LENGTH),
        nullable=True,
    )

    request_ip = Column(
        String(MAX_IP_LENGTH),
        nullable=True,
    )

    user_agent = Column(
        String(MAX_USER_AGENT_LENGTH),
        nullable=True,
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

    user = relationship(
        "User",
        foreign_keys=[user_id],
        lazy="joined",
    )

    __table_args__ = (
        Index(
            "ix_account_action_tokens_user_purpose_active",
            "user_id",
            "purpose",
            "is_active",
        ),
        Index(
            "ix_account_action_tokens_email_purpose",
            "email",
            "purpose",
        ),
        Index(
            "ix_account_action_tokens_status_expiry",
            "status",
            "expires_at",
        ),
    )

    @property
    def normalized_purpose(self) -> str:
        return _clean_text(
            self.purpose,
            maximum_length=40,
        ).upper()

    @property
    def normalized_status(self) -> str:
        return _clean_text(
            self.status,
            maximum_length=20,
        ).upper()

    @property
    def is_expired(self) -> bool:
        """Return whether the token is past its expiry time."""

        expires_at = _as_utc(
            self.expires_at
        )

        if expires_at is None:
            return True

        return expires_at <= utc_now()

    @property
    def can_be_used(self) -> bool:
        """Return whether this token may complete its action."""

        return (
            self.is_active is True
            and self.normalized_status
            == TOKEN_STATUS_ACTIVE
            and self.used_at is None
            and self.revoked_at is None
            and not self.is_expired
        )

    def normalise(self) -> None:
        """Normalize scalar fields before validation."""

        self.token_id = (
            _normalise_token_id(
                self.token_id
            )
        )

        self.token_hash = _clean_text(
            self.token_hash,
            maximum_length=MAX_TOKEN_HASH_LENGTH,
        ).lower()

        self.email = _clean_text(
            self.email,
            maximum_length=MAX_EMAIL_LENGTH,
        ).lower()

        self.purpose = (
            self.normalized_purpose
        )

        self.status = (
            self.normalized_status
        )

        self.revoke_reason = (
            _clean_text(
                self.revoke_reason,
                maximum_length=(
                    MAX_REVOKE_REASON_LENGTH
                ),
            ).upper()
            or None
        )

        self.request_ip = (
            _clean_text(
                self.request_ip,
                maximum_length=MAX_IP_LENGTH,
            )
            or None
        )

        self.user_agent = (
            _clean_text(
                self.user_agent,
                maximum_length=(
                    MAX_USER_AGENT_LENGTH
                ),
            )
            or None
        )

        self.issued_at = (
            _as_utc(
                self.issued_at
            )
            or utc_now()
        )

        self.expires_at = _as_utc(
            self.expires_at
        )

        self.used_at = _as_utc(
            self.used_at
        )

        self.revoked_at = _as_utc(
            self.revoked_at
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
        """Normalize and validate the stored token state."""

        self.normalise()

        if not self.token_id:
            raise ValueError(
                "Token ID is required."
            )

        if len(self.token_hash) != 64:
            raise ValueError(
                "Token hash must be a 64-character SHA-256 hash."
            )

        if any(
            character
            not in "0123456789abcdef"
            for character in self.token_hash
        ):
            raise ValueError(
                "Token hash must contain hexadecimal characters only."
            )

        if (
            self.user_id is None
            or isinstance(
                self.user_id,
                bool,
            )
        ):
            raise ValueError(
                "User ID must be a positive integer."
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

        if self.user_id < 1:
            raise ValueError(
                "User ID must be positive."
            )

        if (
            self.purpose
            not in VALID_TOKEN_PURPOSES
        ):
            raise ValueError(
                "Invalid account action token purpose."
            )

        if (
            self.status
            not in VALID_TOKEN_STATUSES
        ):
            raise ValueError(
                "Invalid account action token status."
            )

        if not self.email or "@" not in self.email:
            raise ValueError(
                "A valid email address is required."
            )

        if self.expires_at is None:
            raise ValueError(
                "Token expiry is required."
            )

        if (
            self.expires_at
            <= self.issued_at
        ):
            raise ValueError(
                "Token expiry must be later than issue time."
            )

        if (
            self.status
            == TOKEN_STATUS_ACTIVE
        ):
            if (
                self.is_active is not True
                or self.used_at is not None
                or self.revoked_at is not None
            ):
                raise ValueError(
                    "Active token state is inconsistent."
                )

        if (
            self.status
            == TOKEN_STATUS_USED
            and self.used_at is None
        ):
            raise ValueError(
                "Used token must have used_at."
            )

        if (
            self.status
            == TOKEN_STATUS_REVOKED
            and self.revoked_at is None
        ):
            raise ValueError(
                "Revoked token must have revoked_at."
            )

    def mark_used(self) -> None:
        """Mark this token consumed."""

        if not self.can_be_used:
            raise ValueError(
                "Only an active, unexpired token can be used."
            )

        now = utc_now()

        self.is_active = False
        self.status = TOKEN_STATUS_USED
        self.used_at = now
        self.updated_at = now

    def revoke(
        self,
        *,
        reason: str,
    ) -> None:
        """Revoke this token."""

        if (
            self.normalized_status
            == TOKEN_STATUS_USED
        ):
            raise ValueError(
                "A used token cannot be revoked."
            )

        now = utc_now()

        self.is_active = False
        self.status = TOKEN_STATUS_REVOKED

        if self.revoked_at is None:
            self.revoked_at = now

        self.revoke_reason = (
            _normalise_reason(
                reason
            )
        )
        self.updated_at = now

    def mark_expired(self) -> None:
        """Mark this token expired."""

        if (
            self.normalized_status
            in {
                TOKEN_STATUS_USED,
                TOKEN_STATUS_REVOKED,
            }
        ):
            return

        now = utc_now()

        self.is_active = False
        self.status = TOKEN_STATUS_EXPIRED

        if self.revoked_at is None:
            self.revoked_at = now

        if not self.revoke_reason:
            self.revoke_reason = (
                TOKEN_REVOKE_EXPIRED
            )

        self.updated_at = now

    def to_public_dict(
        self,
    ) -> dict[str, object]:
        """
        Return safe metadata without token secrets or request metadata.
        """

        return {
            "id": self.id,
            "token_id": self.token_id,
            "user_id": self.user_id,
            "email": _mask_email(
                self.email
            ),
            "purpose": (
                self.normalized_purpose
            ),
            "status": (
                self.normalized_status
            ),
            "is_active": (
                self.is_active is True
            ),
            "can_be_used": (
                self.can_be_used
            ),
            "issued_at": self.issued_at,
            "expires_at": self.expires_at,
            "used_at": self.used_at,
            "revoked_at": self.revoked_at,
            "revoke_reason": (
                self.revoke_reason
            ),
            "request_ip_present": bool(
                self.request_ip
            ),
            "user_agent_present": bool(
                self.user_agent
            ),
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }


__all__ = [
    "AccountActionToken",
    "TOKEN_PURPOSE_EMAIL_VERIFICATION",
    "TOKEN_PURPOSE_PASSWORD_RESET",
    "TOKEN_REVOKE_ACCOUNT_BLOCKED",
    "TOKEN_REVOKE_EXPIRED",
    "TOKEN_REVOKE_OWNER_ACTION",
    "TOKEN_REVOKE_PASSWORD_CHANGED",
    "TOKEN_REVOKE_REPLACED",
    "TOKEN_REVOKE_SECURITY_EVENT",
    "TOKEN_STATUS_ACTIVE",
    "TOKEN_STATUS_EXPIRED",
    "TOKEN_STATUS_REVOKED",
    "TOKEN_STATUS_USED",
    "VALID_TOKEN_PURPOSES",
    "VALID_TOKEN_STATUSES",
    "utc_now",
]