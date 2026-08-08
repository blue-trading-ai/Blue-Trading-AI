from __future__ import annotations

import re
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
    Table,
    UniqueConstraint,
    text,
)
from sqlalchemy.orm import relationship

from app.database.connection import Base


ROLE_OWNER: Final[str] = "OWNER"
ROLE_ADMIN: Final[str] = "ADMIN"
ROLE_ANALYST: Final[str] = "ANALYST"
ROLE_USER: Final[str] = "USER"

SYSTEM_ROLES: Final[set[str]] = {
    ROLE_OWNER,
    ROLE_ADMIN,
    ROLE_ANALYST,
    ROLE_USER,
}

PERMISSION_USER_READ: Final[str] = "user:read"
PERMISSION_USER_APPROVE: Final[str] = "user:approve"
PERMISSION_USER_SUSPEND: Final[str] = "user:suspend"
PERMISSION_ROLE_READ: Final[str] = "role:read"
PERMISSION_ROLE_ASSIGN: Final[str] = "role:assign"
PERMISSION_AUDIT_READ: Final[str] = "audit:read"
PERMISSION_SIGNAL_READ: Final[str] = "signal:read"
PERMISSION_SIGNAL_CREATE: Final[str] = "signal:create"
PERMISSION_SIGNAL_MANAGE: Final[str] = "signal:manage"
PERMISSION_SYSTEM_READ: Final[str] = "system:read"
PERMISSION_SYSTEM_MANAGE: Final[str] = "system:manage"

SYSTEM_PERMISSIONS: Final[set[str]] = {
    PERMISSION_USER_READ,
    PERMISSION_USER_APPROVE,
    PERMISSION_USER_SUSPEND,
    PERMISSION_ROLE_READ,
    PERMISSION_ROLE_ASSIGN,
    PERMISSION_AUDIT_READ,
    PERMISSION_SIGNAL_READ,
    PERMISSION_SIGNAL_CREATE,
    PERMISSION_SIGNAL_MANAGE,
    PERMISSION_SYSTEM_READ,
    PERMISSION_SYSTEM_MANAGE,
}

MAX_ROLE_NAME_LENGTH: Final[int] = 40
MAX_ROLE_DISPLAY_NAME_LENGTH: Final[int] = 100
MAX_PERMISSION_CODE_LENGTH: Final[int] = 100
MAX_PERMISSION_DISPLAY_NAME_LENGTH: Final[int] = 150
MAX_DESCRIPTION_LENGTH: Final[int] = 500
MAX_REVOKE_REASON_LENGTH: Final[int] = 200

ROLE_NAME_PATTERN = re.compile(
    r"^[A-Z][A-Z0-9_]*$"
)

PERMISSION_CODE_PATTERN = re.compile(
    r"^[a-z][a-z0-9_-]*:[a-z][a-z0-9_-]*$"
)


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
    Return printable single-line text.

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


def _positive_int(
    value: Any,
    *,
    field_name: str,
    allow_none: bool = False,
) -> int | None:
    """Resolve one positive integer without accepting booleans."""

    if value is None:
        if allow_none:
            return None

        raise ValueError(
            f"{field_name} is required."
        )

    if isinstance(
        value,
        bool,
    ):
        raise ValueError(
            f"{field_name} must be an integer."
        )

    try:
        resolved = int(
            value
        )
    except (
        TypeError,
        ValueError,
        OverflowError,
    ) as exc:
        raise ValueError(
            f"{field_name} must be an integer."
        ) from exc

    if resolved < 1:
        raise ValueError(
            f"{field_name} must be positive."
        )

    return resolved


def _strict_bool(
    value: Any,
    *,
    field_name: str,
    default: bool,
) -> bool:
    """
    Resolve one boolean without treating arbitrary non-empty strings as True.
    """

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


role_permissions = Table(
    "role_permissions",
    Base.metadata,
    Column(
        "role_id",
        Integer,
        ForeignKey(
            "roles.id",
            ondelete="CASCADE",
        ),
        primary_key=True,
    ),
    Column(
        "permission_id",
        Integer,
        ForeignKey(
            "permissions.id",
            ondelete="CASCADE",
        ),
        primary_key=True,
    ),
    Column(
        "created_at",
        DateTime(timezone=True),
        nullable=False,
        default=utc_now,
        server_default=text("CURRENT_TIMESTAMP"),
    ),
    Index(
        "ix_role_permissions_role_permission",
        "role_id",
        "permission_id",
        unique=True,
    ),
)


class Role(Base):
    __tablename__ = "roles"

    id = Column(
        Integer,
        primary_key=True,
        index=True,
    )

    name = Column(
        String(40),
        nullable=False,
        index=True,
    )

    display_name = Column(
        String(100),
        nullable=False,
    )

    description = Column(
        String(500),
        nullable=True,
    )

    is_system = Column(
        Boolean,
        nullable=False,
        default=False,
        server_default=text("0"),
        index=True,
    )

    is_active = Column(
        Boolean,
        nullable=False,
        default=True,
        server_default=text("1"),
        index=True,
    )

    created_at = Column(
        DateTime(timezone=True),
        nullable=False,
        default=utc_now,
        server_default=text("CURRENT_TIMESTAMP"),
    )

    updated_at = Column(
        DateTime(timezone=True),
        nullable=False,
        default=utc_now,
        server_default=text("CURRENT_TIMESTAMP"),
        onupdate=utc_now,
    )

    permissions = relationship(
        "Permission",
        secondary=role_permissions,
        back_populates="roles",
        lazy="selectin",
    )

    user_assignments = relationship(
        "UserRole",
        back_populates="role",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )

    __table_args__ = (
        UniqueConstraint(
            "name",
            name="uq_roles_name",
        ),
    )

    def normalise(self) -> None:
        self.name = _clean_text(
            self.name,
            maximum_length=MAX_ROLE_NAME_LENGTH,
        ).upper()

        self.display_name = _clean_text(
            self.display_name,
            maximum_length=(
                MAX_ROLE_DISPLAY_NAME_LENGTH
            ),
        )

        self.description = (
            _clean_text(
                self.description,
                maximum_length=MAX_DESCRIPTION_LENGTH,
            )
            or None
        )

        self.is_system = _strict_bool(
            self.is_system,
            field_name="Role is_system",
            default=False,
        )

        self.is_active = _strict_bool(
            self.is_active,
            field_name="Role is_active",
            default=True,
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
        """Normalize and validate this role."""

        self.normalise()

        if (
            not self.name
            or not ROLE_NAME_PATTERN.fullmatch(
                self.name
            )
        ):
            raise ValueError(
                "Role name is invalid."
            )

        if not self.display_name:
            raise ValueError(
                "Role display name is required."
            )

        if (
            self.is_system
            and self.name not in SYSTEM_ROLES
        ):
            raise ValueError(
                "System role name is unsupported."
            )

    def to_public_dict(
        self,
    ) -> dict[str, object]:
        return {
            "id": self.id,
            "name": self.name,
            "display_name": (
                self.display_name
            ),
            "description": (
                self.description
            ),
            "is_system": (
                self.is_system is True
            ),
            "is_active": (
                self.is_active is True
            ),
            "permissions": sorted(
                {
                    permission.code
                    for permission in (
                        self.permissions or []
                    )
                    if (
                        permission.is_active is True
                        and permission.code
                    )
                }
            ),
            "created_at": (
                self.created_at
            ),
            "updated_at": (
                self.updated_at
            ),
        }


class Permission(Base):
    __tablename__ = "permissions"

    id = Column(
        Integer,
        primary_key=True,
        index=True,
    )

    code = Column(
        String(100),
        nullable=False,
        index=True,
    )

    display_name = Column(
        String(150),
        nullable=False,
    )

    description = Column(
        String(500),
        nullable=True,
    )

    is_system = Column(
        Boolean,
        nullable=False,
        default=True,
        server_default=text("1"),
        index=True,
    )

    is_active = Column(
        Boolean,
        nullable=False,
        default=True,
        server_default=text("1"),
        index=True,
    )

    created_at = Column(
        DateTime(timezone=True),
        nullable=False,
        default=utc_now,
        server_default=text("CURRENT_TIMESTAMP"),
    )

    updated_at = Column(
        DateTime(timezone=True),
        nullable=False,
        default=utc_now,
        server_default=text("CURRENT_TIMESTAMP"),
        onupdate=utc_now,
    )

    roles = relationship(
        "Role",
        secondary=role_permissions,
        back_populates="permissions",
        lazy="selectin",
    )

    __table_args__ = (
        UniqueConstraint(
            "code",
            name="uq_permissions_code",
        ),
    )

    def normalise(self) -> None:
        self.code = _clean_text(
            self.code,
            maximum_length=MAX_PERMISSION_CODE_LENGTH,
        ).lower()

        self.display_name = _clean_text(
            self.display_name,
            maximum_length=(
                MAX_PERMISSION_DISPLAY_NAME_LENGTH
            ),
        )

        self.description = (
            _clean_text(
                self.description,
                maximum_length=MAX_DESCRIPTION_LENGTH,
            )
            or None
        )

        self.is_system = _strict_bool(
            self.is_system,
            field_name="Permission is_system",
            default=True,
        )

        self.is_active = _strict_bool(
            self.is_active,
            field_name="Permission is_active",
            default=True,
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
        """Normalize and validate this permission."""

        self.normalise()

        if (
            not self.code
            or not PERMISSION_CODE_PATTERN.fullmatch(
                self.code
            )
        ):
            raise ValueError(
                "Permission code is invalid."
            )

        if not self.display_name:
            raise ValueError(
                "Permission display name is required."
            )

        if (
            self.is_system
            and self.code
            not in SYSTEM_PERMISSIONS
        ):
            raise ValueError(
                "System permission code is unsupported."
            )

    def to_public_dict(
        self,
    ) -> dict[str, object]:
        return {
            "id": self.id,
            "code": self.code,
            "display_name": (
                self.display_name
            ),
            "description": (
                self.description
            ),
            "is_system": (
                self.is_system is True
            ),
            "is_active": (
                self.is_active is True
            ),
            "created_at": (
                self.created_at
            ),
            "updated_at": (
                self.updated_at
            ),
        }


class UserRole(Base):
    __tablename__ = "user_roles"

    id = Column(
        Integer,
        primary_key=True,
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

    role_id = Column(
        Integer,
        ForeignKey(
            "roles.id",
            ondelete="CASCADE",
        ),
        nullable=False,
        index=True,
    )

    assigned_by_user_id = Column(
        Integer,
        ForeignKey(
            "users.id",
            ondelete="SET NULL",
        ),
        nullable=True,
        index=True,
    )

    is_active = Column(
        Boolean,
        nullable=False,
        default=True,
        server_default=text("1"),
        index=True,
    )

    assigned_at = Column(
        DateTime(timezone=True),
        nullable=False,
        default=utc_now,
        server_default=text("CURRENT_TIMESTAMP"),
    )

    revoked_at = Column(
        DateTime(timezone=True),
        nullable=True,
    )

    revoke_reason = Column(
        String(MAX_REVOKE_REASON_LENGTH),
        nullable=True,
    )

    role = relationship(
        "Role",
        back_populates="user_assignments",
        lazy="joined",
    )

    user = relationship(
        "User",
        foreign_keys=[user_id],
        lazy="joined",
    )

    assigned_by = relationship(
        "User",
        foreign_keys=[assigned_by_user_id],
        lazy="joined",
    )

    __table_args__ = (
        UniqueConstraint(
            "user_id",
            "role_id",
            name="uq_user_roles_user_role",
        ),
        Index(
            "ix_user_roles_user_active",
            "user_id",
            "is_active",
        ),
        Index(
            "ix_user_roles_role_active",
            "role_id",
            "is_active",
        ),
    )

    def normalise(self) -> None:
        self.user_id = _positive_int(
            self.user_id,
            field_name="User ID",
        )

        self.role_id = _positive_int(
            self.role_id,
            field_name="Role ID",
        )

        self.assigned_by_user_id = (
            _positive_int(
                self.assigned_by_user_id,
                field_name=(
                    "Assigned-by user ID"
                ),
                allow_none=True,
            )
        )

        self.is_active = _strict_bool(
            self.is_active,
            field_name="User role is_active",
            default=True,
        )

        self.assigned_at = (
            _as_utc(
                self.assigned_at
            )
            or utc_now()
        )

        self.revoked_at = _as_utc(
            self.revoked_at
        )

        self.revoke_reason = (
            _clean_text(
                self.revoke_reason,
                maximum_length=(
                    MAX_REVOKE_REASON_LENGTH
                ),
            )
            or None
        )

    def validate_state(self) -> None:
        """Normalize and validate this user-role assignment."""

        self.normalise()

        if self.is_active is True:
            if self.revoked_at is not None:
                raise ValueError(
                    "Active role assignment cannot have revoked_at."
                )

            if self.revoke_reason is not None:
                raise ValueError(
                    "Active role assignment cannot have a revoke reason."
                )
        else:
            if self.revoked_at is None:
                raise ValueError(
                    "Inactive role assignment must have revoked_at."
                )

            if not self.revoke_reason:
                raise ValueError(
                    "Inactive role assignment must have a revoke reason."
                )

    def revoke(
        self,
        *,
        reason: str,
    ) -> None:
        if self.is_active is not True:
            return

        resolved_reason = _clean_text(
            reason or "OWNER_ACTION",
            maximum_length=(
                MAX_REVOKE_REASON_LENGTH
            ),
        )

        if not resolved_reason:
            resolved_reason = (
                "OWNER_ACTION"
            )

        self.is_active = False
        self.revoked_at = utc_now()
        self.revoke_reason = (
            resolved_reason
        )

    def reactivate(
        self,
        *,
        assigned_by_user_id: int | None,
    ) -> None:
        self.is_active = True
        self.assigned_by_user_id = (
            _positive_int(
                assigned_by_user_id,
                field_name=(
                    "Assigned-by user ID"
                ),
                allow_none=True,
            )
        )
        self.assigned_at = utc_now()
        self.revoked_at = None
        self.revoke_reason = None

    def to_public_dict(
        self,
    ) -> dict[str, object]:
        return {
            "id": self.id,
            "user_id": self.user_id,
            "role_id": self.role_id,
            "role": (
                self.role.to_public_dict()
                if self.role is not None
                else None
            ),
            "assigned_by_user_id": (
                self.assigned_by_user_id
            ),
            "is_active": (
                self.is_active is True
            ),
            "assigned_at": (
                self.assigned_at
            ),
            "revoked_at": (
                self.revoked_at
            ),
            "revoke_reason": (
                self.revoke_reason
            ),
        }


__all__ = [
    "Permission",
    "Role",
    "UserRole",
    "ROLE_ADMIN",
    "ROLE_ANALYST",
    "ROLE_OWNER",
    "ROLE_USER",
    "SYSTEM_PERMISSIONS",
    "SYSTEM_ROLES",
    "PERMISSION_AUDIT_READ",
    "PERMISSION_ROLE_ASSIGN",
    "PERMISSION_ROLE_READ",
    "PERMISSION_SIGNAL_CREATE",
    "PERMISSION_SIGNAL_MANAGE",
    "PERMISSION_SIGNAL_READ",
    "PERMISSION_SYSTEM_MANAGE",
    "PERMISSION_SYSTEM_READ",
    "PERMISSION_USER_APPROVE",
    "PERMISSION_USER_READ",
    "PERMISSION_USER_SUSPEND",
    "PERMISSION_CODE_PATTERN",
    "ROLE_NAME_PATTERN",
    "role_permissions",
    "utc_now",
]