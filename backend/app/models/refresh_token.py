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


REFRESH_STATUS_ACTIVE: Final[str] = "ACTIVE"
REFRESH_STATUS_ROTATED: Final[str] = "ROTATED"
REFRESH_STATUS_REVOKED: Final[str] = "REVOKED"
REFRESH_STATUS_EXPIRED: Final[str] = "EXPIRED"
REFRESH_STATUS_REUSED: Final[str] = "REUSED"

REFRESH_REVOKE_LOGOUT: Final[str] = "LOGOUT"
REFRESH_REVOKE_ROTATED: Final[str] = "ROTATED"
REFRESH_REVOKE_PASSWORD_CHANGED: Final[str] = "PASSWORD_CHANGED"
REFRESH_REVOKE_OWNER_ACTION: Final[str] = "OWNER_ACTION"
REFRESH_REVOKE_ACCOUNT_BLOCKED: Final[str] = "ACCOUNT_BLOCKED"
REFRESH_REVOKE_SECURITY_EVENT: Final[str] = "SECURITY_EVENT"
REFRESH_REVOKE_REUSE_DETECTED: Final[str] = "REUSE_DETECTED"
REFRESH_REVOKE_ALL_DEVICES: Final[str] = "ALL_DEVICES"
REFRESH_REVOKE_EXPIRED: Final[str] = "EXPIRED"

MAX_TOKEN_ID_LENGTH: Final[int] = 64
MAX_REVOKE_REASON_LENGTH: Final[int] = 100


def _non_negative_integer(
    value: Any,
    *,
    default: int = 0,
) -> int:
    """Resolve one non-negative integer without accepting booleans."""

    if isinstance(value, bool):
        return default

    try:
        resolved = int(value)
    except (
        TypeError,
        ValueError,
        OverflowError,
    ):
        return default

    return max(
        resolved,
        0,
    )


def utc_now() -> datetime:
    """Return one timezone-aware UTC timestamp."""

    return datetime.now(timezone.utc)


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


def _normalise_token_id(
    value: str,
    *,
    field_name: str,
) -> str:
    """Validate and normalize one refresh-token identifier."""

    resolved = str(
        value or ""
    ).strip()

    if not resolved:
        raise ValueError(
            f"{field_name} cannot be empty."
        )

    if (
        len(resolved)
        > MAX_TOKEN_ID_LENGTH
    ):
        raise ValueError(
            f"{field_name} cannot exceed "
            f"{MAX_TOKEN_ID_LENGTH} characters."
        )

    return resolved


class RefreshToken(Base):
    """
    Database-backed refresh token with rotation and reuse detection.

    Security design:
    - Raw refresh tokens are never stored.
    - Only SHA-256 token hashes are persisted.
    - Every token belongs to one login session.
    - Tokens are grouped into a rotation family.
    - Rotated-token reuse can revoke the entire family.
    """

    __tablename__ = "refresh_tokens"

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

    family_id = Column(
        String(64),
        nullable=False,
        index=True,
    )

    parent_token_id = Column(
        String(64),
        nullable=True,
        index=True,
    )

    replaced_by_token_id = Column(
        String(64),
        nullable=True,
        index=True,
    )

    session_id = Column(
        String(64),
        ForeignKey(
            "auth_sessions.session_id",
            ondelete="CASCADE",
        ),
        nullable=False,
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

    password_version = Column(
        Integer,
        nullable=False,
        default=1,
    )

    status = Column(
        String(20),
        nullable=False,
        default=REFRESH_STATUS_ACTIVE,
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

    last_used_at = Column(
        DateTime(timezone=True),
        nullable=True,
    )

    rotated_at = Column(
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

    reuse_detected_at = Column(
        DateTime(timezone=True),
        nullable=True,
        index=True,
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

    auth_session = relationship(
        "AuthSession",
        foreign_keys=[session_id],
        lazy="joined",
    )

    __table_args__ = (
        Index(
            "ix_refresh_tokens_user_active",
            "user_id",
            "is_active",
        ),
        Index(
            "ix_refresh_tokens_session_active",
            "session_id",
            "is_active",
        ),
        Index(
            "ix_refresh_tokens_family_status",
            "family_id",
            "status",
        ),
        Index(
            "ix_refresh_tokens_status_expiry",
            "status",
            "expires_at",
        ),
    )

    @property
    def normalized_status(self) -> str:
        """Return the stored refresh-token status in normalized form."""

        return str(
            self.status or ""
        ).strip().upper()

    @property
    def replacement_token_id(
        self,
    ) -> str | None:
        """
        Compatibility alias for the replacement token identifier.

        The persisted database column remains replaced_by_token_id.
        """

        return self.replaced_by_token_id

    @property
    def is_expired(self) -> bool:
        """Return whether this refresh token has expired."""

        expires_at = _as_utc(
            self.expires_at
        )

        if expires_at is None:
            return True

        return expires_at <= utc_now()

    @property
    def can_refresh(self) -> bool:
        """Return whether this token may issue a new token pair."""

        return (
            self.is_active is True
            and self.normalized_status
            == REFRESH_STATUS_ACTIVE
            and self.revoked_at is None
            and self.reuse_detected_at is None
            and not self.is_expired
        )

    def touch(self) -> None:
        """
        Record successful refresh-token use.

        Inactive, rotated, revoked, reused, or expired tokens
        are not modified.
        """

        if not self.can_refresh:
            return

        now = utc_now()

        self.last_used_at = now
        self.updated_at = now

    def mark_rotated(
        self,
        *,
        replacement_token_id: str,
    ) -> None:
        """Mark this token consumed and replaced."""

        resolved_replacement_id = (
            _normalise_token_id(
                replacement_token_id,
                field_name=(
                    "Replacement token ID"
                ),
            )
        )

        current_token_id = str(
            self.token_id
            or ""
        ).strip()

        if (
            current_token_id
            and resolved_replacement_id
            == current_token_id
        ):
            raise ValueError(
                "Replacement token ID cannot match the current token ID."
            )

        now = utc_now()

        self.is_active = False
        self.status = REFRESH_STATUS_ROTATED
        self.rotated_at = now
        self.last_used_at = now
        self.replaced_by_token_id = (
            resolved_replacement_id
        )
        self.revoke_reason = (
            REFRESH_REVOKE_ROTATED
        )
        self.updated_at = now

    def revoke(
        self,
        *,
        reason: str,
    ) -> None:
        """Revoke this refresh token."""

        now = utc_now()

        self.is_active = False
        self.status = REFRESH_STATUS_REVOKED

        if self.revoked_at is None:
            self.revoked_at = now

        self.revoke_reason = (
            _normalise_reason(
                reason,
                default=(
                    REFRESH_REVOKE_SECURITY_EVENT
                ),
            )
        )
        self.updated_at = now

    def mark_expired(self) -> None:
        """Mark this token expired and inactive."""

        now = utc_now()

        self.is_active = False
        self.status = REFRESH_STATUS_EXPIRED

        if self.revoked_at is None:
            self.revoked_at = now

        if not self.revoke_reason:
            self.revoke_reason = (
                REFRESH_REVOKE_EXPIRED
            )

        self.updated_at = now

    def mark_reused(self) -> None:
        """Mark suspicious reuse of a consumed token."""

        now = utc_now()

        self.is_active = False
        self.status = REFRESH_STATUS_REUSED

        if self.reuse_detected_at is None:
            self.reuse_detected_at = now

        if self.revoked_at is None:
            self.revoked_at = now

        self.revoke_reason = (
            REFRESH_REVOKE_REUSE_DETECTED
        )
        self.updated_at = now

    def to_public_dict(
        self,
    ) -> dict[str, object]:
        """Return safe metadata without token secrets or hashes."""

        return {
            "id": self.id,
            "token_id": self.token_id,
            "family_id": self.family_id,
            "parent_token_id": (
                self.parent_token_id
            ),
            "replaced_by_token_id": (
                self.replaced_by_token_id
            ),
            "session_id": self.session_id,
            "user_id": self.user_id,
            "password_version": max(
                _non_negative_integer(
                    self.password_version,
                    default=1,
                ),
                1,
            ),
            "status": (
                self.normalized_status
            ),
            "is_active": (
                self.is_active is True
            ),
            "can_refresh": (
                self.can_refresh
            ),
            "issued_at": self.issued_at,
            "expires_at": self.expires_at,
            "last_used_at": (
                self.last_used_at
            ),
            "rotated_at": self.rotated_at,
            "revoked_at": self.revoked_at,
            "revoke_reason": (
                self.revoke_reason
            ),
            "reuse_detected_at": (
                self.reuse_detected_at
            ),
            "ip_address": self.ip_address,
            "user_agent": self.user_agent,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }


__all__ = [
    "MAX_REVOKE_REASON_LENGTH",
    "MAX_TOKEN_ID_LENGTH",
    "REFRESH_REVOKE_ACCOUNT_BLOCKED",
    "REFRESH_REVOKE_ALL_DEVICES",
    "REFRESH_REVOKE_EXPIRED",
    "REFRESH_REVOKE_LOGOUT",
    "REFRESH_REVOKE_OWNER_ACTION",
    "REFRESH_REVOKE_PASSWORD_CHANGED",
    "REFRESH_REVOKE_REUSE_DETECTED",
    "REFRESH_REVOKE_ROTATED",
    "REFRESH_REVOKE_SECURITY_EVENT",
    "REFRESH_STATUS_ACTIVE",
    "REFRESH_STATUS_EXPIRED",
    "REFRESH_STATUS_REUSED",
    "REFRESH_STATUS_REVOKED",
    "REFRESH_STATUS_ROTATED",
    "RefreshToken",
    "utc_now",
]