from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Final

from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    Integer,
    String,
    text,
)

from app.database.connection import Base


ACCOUNT_STATUS_PENDING: Final[str] = "PENDING"
ACCOUNT_STATUS_APPROVED: Final[str] = "APPROVED"
ACCOUNT_STATUS_REJECTED: Final[str] = "REJECTED"
ACCOUNT_STATUS_SUSPENDED: Final[str] = "SUSPENDED"

SUPPORTED_ACCOUNT_STATUSES: Final[set[str]] = {
    ACCOUNT_STATUS_PENDING,
    ACCOUNT_STATUS_APPROVED,
    ACCOUNT_STATUS_REJECTED,
    ACCOUNT_STATUS_SUSPENDED,
}

DEFAULT_MAX_FAILED_LOGIN_ATTEMPTS: Final[int] = 5
DEFAULT_LOGIN_LOCKOUT_MINUTES: Final[int] = 15

MAX_USERNAME_LENGTH: Final[int] = 100
MAX_EMAIL_LENGTH: Final[int] = 255
MAX_PASSWORD_HASH_LENGTH: Final[int] = 255
MAX_APPROVED_BY_LENGTH: Final[int] = 255
MAX_FAILED_LOGIN_ATTEMPTS_LIMIT: Final[int] = 100
MAX_LOGIN_LOCKOUT_MINUTES_LIMIT: Final[int] = 1440


class User(Base):
    """
    Store Blue-Trading-AI user accounts.

    Version 39 security rules:
    - Owner-controlled approval remains required.
    - Email verification status is tracked separately.
    - Password changes revoke older JWT and refresh tokens.
    - Failed logins are counted.
    - Repeated failures temporarily lock the account.
    - Successful login clears failed-login state.
    """

    __tablename__ = "users"

    id = Column(
        Integer,
        primary_key=True,
        index=True,
    )

    username = Column(
        String(100),
        unique=True,
        index=True,
        nullable=False,
    )

    email = Column(
        String(255),
        unique=True,
        index=True,
        nullable=False,
    )

    is_email_verified = Column(
        Boolean,
        default=False,
        server_default=text("0"),
        nullable=False,
        index=True,
    )

    email_verified_at = Column(
        DateTime(timezone=True),
        nullable=True,
    )

    email_verification_requested_at = Column(
        DateTime(timezone=True),
        nullable=True,
    )

    hashed_password = Column(
        String(255),
        nullable=False,
    )

    password_version = Column(
        Integer,
        default=1,
        nullable=False,
    )

    password_changed_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    failed_login_attempts = Column(
        Integer,
        default=0,
        nullable=False,
    )

    last_failed_login_at = Column(
        DateTime(timezone=True),
        nullable=True,
    )

    locked_until = Column(
        DateTime(timezone=True),
        nullable=True,
    )

    last_login_at = Column(
        DateTime(timezone=True),
        nullable=True,
    )

    is_active = Column(
        Boolean,
        default=True,
        nullable=False,
    )

    account_status = Column(
        String(20),
        default=ACCOUNT_STATUS_PENDING,
        index=True,
        nullable=False,
    )

    approved_at = Column(
        DateTime(timezone=True),
        nullable=True,
    )

    approved_by = Column(
        String(255),
        nullable=True,
    )

    rejected_at = Column(
        DateTime(timezone=True),
        nullable=True,
    )

    suspended_at = Column(
        DateTime(timezone=True),
        nullable=True,
    )

    access_status_updated_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    created_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    @staticmethod
    def normalise_account_status(
        status: str,
    ) -> str:
        resolved_status = str(
            status or ""
        ).strip().upper()

        if resolved_status not in SUPPORTED_ACCOUNT_STATUSES:
            raise ValueError(
                "Account status must be PENDING, APPROVED, "
                "REJECTED, or SUSPENDED."
            )

        return resolved_status

    @staticmethod
    def _utc_now() -> datetime:
        return datetime.now(timezone.utc)

    @property
    def normalized_account_status(self) -> str:
        """
        Return the stored account status in normalized form.
        """

        return str(
            self.account_status
            or ACCOUNT_STATUS_PENDING
        ).strip().upper()

    @property
    def is_approved(self) -> bool:
        return (
            bool(self.is_active)
            and self.normalized_account_status
            == ACCOUNT_STATUS_APPROVED
        )

    @property
    def can_access_platform(self) -> bool:
        return self.is_approved and not self.is_login_locked

    @property
    def is_login_locked(self) -> bool:
        if self.locked_until is None:
            return False

        locked_until = self.locked_until

        if locked_until.tzinfo is None:
            locked_until = locked_until.replace(
                tzinfo=timezone.utc
            )

        return locked_until > self._utc_now()

    @property
    def lockout_seconds_remaining(self) -> int:
        if not self.is_login_locked or self.locked_until is None:
            return 0

        locked_until = self.locked_until

        if locked_until.tzinfo is None:
            locked_until = locked_until.replace(
                tzinfo=timezone.utc
            )

        remaining = (
            locked_until - self._utc_now()
        ).total_seconds()

        return max(int(remaining), 0)

    def register_email_verification_request(
        self,
    ) -> None:
        """
        Record when a verification token was requested.
        """

        self.email_verification_requested_at = (
            self._utc_now()
        )

    def mark_email_verified(self) -> None:
        """
        Mark the current email address verified.
        """

        now = self._utc_now()

        self.is_email_verified = True
        self.email_verified_at = now
        self.email_verification_requested_at = None

    def mark_email_unverified(self) -> None:
        """
        Mark the email unverified, for example after an email change.
        """

        self.is_email_verified = False
        self.email_verified_at = None
        self.email_verification_requested_at = None

    def approve(
        self,
        *,
        approved_by: str,
    ) -> None:
        now = self._utc_now()

        self.account_status = ACCOUNT_STATUS_APPROVED
        self.is_active = True
        self.approved_at = now
        resolved_approved_by = str(
            approved_by or ""
        ).strip() or "owner"

        self.approved_by = (
            resolved_approved_by[
                :MAX_APPROVED_BY_LENGTH
            ]
        )
        self.rejected_at = None
        self.suspended_at = None
        self.access_status_updated_at = now

    def reject(self) -> None:
        now = self._utc_now()

        self.account_status = ACCOUNT_STATUS_REJECTED
        self.is_active = False
        self.rejected_at = now
        self.suspended_at = None
        self.access_status_updated_at = now

    def suspend(self) -> None:
        now = self._utc_now()

        self.account_status = ACCOUNT_STATUS_SUSPENDED
        self.is_active = False
        self.suspended_at = now
        self.access_status_updated_at = now

    def set_pending(self) -> None:
        now = self._utc_now()

        self.account_status = ACCOUNT_STATUS_PENDING
        self.is_active = True
        self.approved_at = None
        self.approved_by = None
        self.rejected_at = None
        self.suspended_at = None
        self.access_status_updated_at = now

    def deactivate(self) -> None:
        self.is_active = False
        self.access_status_updated_at = self._utc_now()

    def activate(self) -> None:
        self.is_active = True
        self.access_status_updated_at = self._utc_now()

    def register_password_change(self) -> None:
        current_version = int(
            self.password_version or 0
        )

        self.password_version = current_version + 1
        self.password_changed_at = self._utc_now()
        self.clear_login_failures()

    def set_password_hash(
        self,
        new_password_hash: str,
    ) -> None:
        resolved_hash = str(
            new_password_hash or ""
        ).strip()

        if not resolved_hash:
            raise ValueError(
                "Password hash cannot be empty."
            )

        if (
            len(resolved_hash)
            > MAX_PASSWORD_HASH_LENGTH
        ):
            raise ValueError(
                "Password hash exceeds the maximum supported length."
            )

        self.hashed_password = resolved_hash
        self.register_password_change()

    def register_failed_login(
        self,
        *,
        max_attempts: int = DEFAULT_MAX_FAILED_LOGIN_ATTEMPTS,
        lockout_minutes: int = DEFAULT_LOGIN_LOCKOUT_MINUTES,
    ) -> None:
        """
        Count one failed login and lock when the limit is reached.
        """

        now = self._utc_now()

        try:
            resolved_max_attempts = int(
                max_attempts
            )
        except (TypeError, ValueError):
            resolved_max_attempts = (
                DEFAULT_MAX_FAILED_LOGIN_ATTEMPTS
            )

        try:
            resolved_lockout_minutes = int(
                lockout_minutes
            )
        except (TypeError, ValueError):
            resolved_lockout_minutes = (
                DEFAULT_LOGIN_LOCKOUT_MINUTES
            )

        resolved_max_attempts = min(
            max(
                resolved_max_attempts,
                1,
            ),
            MAX_FAILED_LOGIN_ATTEMPTS_LIMIT,
        )

        resolved_lockout_minutes = min(
            max(
                resolved_lockout_minutes,
                1,
            ),
            MAX_LOGIN_LOCKOUT_MINUTES_LIMIT,
        )

        self.failed_login_attempts = int(
            self.failed_login_attempts or 0
        ) + 1

        self.last_failed_login_at = now

        if self.failed_login_attempts >= resolved_max_attempts:
            self.locked_until = now + timedelta(
                minutes=resolved_lockout_minutes
            )

    def clear_login_failures(self) -> None:
        self.failed_login_attempts = 0
        self.last_failed_login_at = None
        self.locked_until = None

    def register_successful_login(self) -> None:
        self.last_login_at = self._utc_now()
        self.clear_login_failures()

    def unlock_login(self) -> None:
        self.clear_login_failures()

    def to_public_dict(self) -> dict[str, object]:
        return {
            "id": self.id,
            "username": self.username,
            "email": self.email,
            "is_email_verified": bool(
                self.is_email_verified
            ),
            "email_verified_at": self.email_verified_at,
            "email_verification_requested_at": (
                self.email_verification_requested_at
            ),
            "is_active": self.is_active,
            "account_status": self.normalized_account_status,
            "is_approved": self.is_approved,
            "can_access_platform": self.can_access_platform,
            "password_version": self.password_version,
            "password_changed_at": self.password_changed_at,
            "failed_login_attempts": self.failed_login_attempts,
            "last_failed_login_at": self.last_failed_login_at,
            "locked_until": self.locked_until,
            "is_login_locked": self.is_login_locked,
            "lockout_seconds_remaining": (
                self.lockout_seconds_remaining
            ),
            "last_login_at": self.last_login_at,
            "approved_at": self.approved_at,
            "approved_by": self.approved_by,
            "rejected_at": self.rejected_at,
            "suspended_at": self.suspended_at,
            "access_status_updated_at": (
                self.access_status_updated_at
            ),
            "created_at": self.created_at,
        }

    def __repr__(self) -> str:
        return (
            "<User("
            f"id={self.id}, "
            f"username='{self.username}', "
            f"email='{self.email}', "
            f"is_email_verified={self.is_email_verified}, "
            f"account_status='{self.normalized_account_status}', "
            f"password_version={self.password_version}, "
            f"failed_login_attempts={self.failed_login_attempts}, "
            f"is_active={self.is_active}"
            ")>"
        )


__all__ = [
    "ACCOUNT_STATUS_APPROVED",
    "ACCOUNT_STATUS_PENDING",
    "ACCOUNT_STATUS_REJECTED",
    "ACCOUNT_STATUS_SUSPENDED",
    "DEFAULT_LOGIN_LOCKOUT_MINUTES",
    "DEFAULT_MAX_FAILED_LOGIN_ATTEMPTS",
    "MAX_APPROVED_BY_LENGTH",
    "MAX_EMAIL_LENGTH",
    "MAX_FAILED_LOGIN_ATTEMPTS_LIMIT",
    "MAX_LOGIN_LOCKOUT_MINUTES_LIMIT",
    "MAX_PASSWORD_HASH_LENGTH",
    "MAX_USERNAME_LENGTH",
    "SUPPORTED_ACCOUNT_STATUSES",
    "User",
]