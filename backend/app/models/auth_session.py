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


SESSION_STATUS_ACTIVE: Final[str] = "ACTIVE"
SESSION_STATUS_REVOKED: Final[str] = "REVOKED"
SESSION_STATUS_EXPIRED: Final[str] = "EXPIRED"

SESSION_REVOKE_LOGOUT: Final[str] = "LOGOUT"
SESSION_REVOKE_PASSWORD_CHANGED: Final[str] = "PASSWORD_CHANGED"
SESSION_REVOKE_OWNER_ACTION: Final[str] = "OWNER_ACTION"
SESSION_REVOKE_ACCOUNT_BLOCKED: Final[str] = "ACCOUNT_BLOCKED"
SESSION_REVOKE_SECURITY_EVENT: Final[str] = "SECURITY_EVENT"
SESSION_REVOKE_ALL_DEVICES: Final[str] = "ALL_DEVICES"
SESSION_REVOKE_EXPIRED: Final[str] = "EXPIRED"

MAX_REVOKE_REASON_LENGTH: Final[int] = 100


def utc_now() -> datetime:
    """Return one timezone-aware UTC timestamp."""

    return datetime.now(
        timezone.utc
    )


def _as_utc(
    value: datetime | None,
) -> datetime | None:
    """Return one datetime normalized to timezone-aware UTC."""

    if value is None:
        return None

    if value.tzinfo is None:
        return value.replace(
            tzinfo=timezone.utc
        )

    return value.astimezone(
        timezone.utc
    )


def _normalise_reason(
    reason: str | None,
    *,
    default: str,
) -> str:
    """Return one safe uppercase revocation reason."""

    resolved = str(
        reason or default
    ).strip().upper()

    if not resolved:
        resolved = default

    return resolved[
        :MAX_REVOKE_REASON_LENGTH
    ]


def _positive_integer(
    value: Any,
    *,
    default: int = 1,
) -> int:
    """Resolve one positive integer without accepting booleans."""

    if isinstance(
        value,
        bool,
    ):
        return default

    try:
        resolved = int(
            value
        )
    except (
        TypeError,
        ValueError,
        OverflowError,
    ):
        return default

    return max(
        resolved,
        1,
    )


class AuthSession(Base):
    """
    Database-backed authenticated session.

    Security design:
    - Raw JWT values are never stored.
    - Only a SHA-256 hash of the JWT ID is stored.
    - Each login creates a separate revocable session.
    - Password changes and owner actions can revoke sessions.
    """

    __tablename__ = "auth_sessions"

    id = Column(
        Integer,
        primary_key=True,
        index=True,
    )

    session_id = Column(
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

    token_jti_hash = Column(
        String(64),
        nullable=False,
        unique=True,
        index=True,
    )

    password_version = Column(
        Integer,
        nullable=False,
        default=1,
    )

    status = Column(
        String(20),
        nullable=False,
        default=SESSION_STATUS_ACTIVE,
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

    last_seen_at = Column(
        DateTime(timezone=True),
        nullable=True,
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

    ip_address = Column(
        String(64),
        nullable=True,
    )

    user_agent = Column(
        String(500),
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
            "ix_auth_sessions_user_active",
            "user_id",
            "is_active",
        ),
        Index(
            "ix_auth_sessions_status_expiry",
            "status",
            "expires_at",
        ),
    )

    @property
    def normalized_status(
        self,
    ) -> str:
        """Return the stored session status in normalized form."""

        return str(
            self.status or ""
        ).strip().upper()

    @property
    def is_expired(
        self,
    ) -> bool:
        """Return whether this session has passed its expiry."""

        expires_at = _as_utc(
            self.expires_at
        )

        if expires_at is None:
            return True

        return (
            expires_at
            <= utc_now()
        )

    @property
    def can_authenticate(
        self,
    ) -> bool:
        """Return whether the session may authenticate requests."""

        return (
            self.is_active is True
            and self.normalized_status
            == SESSION_STATUS_ACTIVE
            and self.revoked_at is None
            and not self.is_expired
        )

    def touch(
        self,
    ) -> None:
        """
        Update the last activity timestamp.

        Inactive, revoked, or expired sessions are not modified.
        """

        if not self.can_authenticate:
            return

        now = utc_now()

        self.last_seen_at = now
        self.updated_at = now

    def revoke(
        self,
        *,
        reason: str,
    ) -> None:
        """Revoke this session while preserving the first revocation time."""

        now = utc_now()

        self.is_active = False
        self.status = (
            SESSION_STATUS_REVOKED
        )

        if self.revoked_at is None:
            self.revoked_at = now

        self.revoke_reason = (
            _normalise_reason(
                reason,
                default=(
                    SESSION_REVOKE_SECURITY_EVENT
                ),
            )
        )

        self.updated_at = now

    def mark_expired(
        self,
    ) -> None:
        """Mark an expired session inactive."""

        now = utc_now()

        self.is_active = False
        self.status = (
            SESSION_STATUS_EXPIRED
        )

        if self.revoked_at is None:
            self.revoked_at = now

        if not self.revoke_reason:
            self.revoke_reason = (
                SESSION_REVOKE_EXPIRED
            )

        self.updated_at = now

    def to_public_dict(
        self,
    ) -> dict[str, object]:
        """Return safe session information without token secrets."""

        return {
            "id": self.id,
            "session_id": self.session_id,
            "user_id": self.user_id,
            "status": (
                self.normalized_status
            ),
            "is_active": (
                self.is_active is True
            ),
            "can_authenticate": (
                self.can_authenticate
            ),
            "password_version": (
                _positive_integer(
                    self.password_version,
                    default=1,
                )
            ),
            "issued_at": self.issued_at,
            "expires_at": self.expires_at,
            "last_seen_at": (
                self.last_seen_at
            ),
            "revoked_at": (
                self.revoked_at
            ),
            "revoke_reason": (
                self.revoke_reason
            ),
            "ip_address": (
                self.ip_address
            ),
            "user_agent": (
                self.user_agent
            ),
            "created_at": (
                self.created_at
            ),
            "updated_at": (
                self.updated_at
            ),
        }


__all__ = [
    "AuthSession",
    "MAX_REVOKE_REASON_LENGTH",
    "SESSION_REVOKE_ACCOUNT_BLOCKED",
    "SESSION_REVOKE_ALL_DEVICES",
    "SESSION_REVOKE_EXPIRED",
    "SESSION_REVOKE_LOGOUT",
    "SESSION_REVOKE_OWNER_ACTION",
    "SESSION_REVOKE_PASSWORD_CHANGED",
    "SESSION_REVOKE_SECURITY_EVENT",
    "SESSION_STATUS_ACTIVE",
    "SESSION_STATUS_EXPIRED",
    "SESSION_STATUS_REVOKED",
    "utc_now",
]