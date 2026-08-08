from __future__ import annotations

from dataclasses import dataclass
from typing import Final, Iterable

from sqlalchemy.orm import Session

from app.models.role_permission import (
    Permission,
    Role,
    UserRole,
    PERMISSION_AUDIT_READ,
    PERMISSION_ROLE_ASSIGN,
    PERMISSION_ROLE_READ,
    PERMISSION_SIGNAL_CREATE,
    PERMISSION_SIGNAL_MANAGE,
    PERMISSION_SIGNAL_READ,
    PERMISSION_SYSTEM_MANAGE,
    PERMISSION_SYSTEM_READ,
    PERMISSION_USER_APPROVE,
    PERMISSION_USER_READ,
    PERMISSION_USER_SUSPEND,
    ROLE_ADMIN,
    ROLE_ANALYST,
    ROLE_OWNER,
    ROLE_USER,
    SYSTEM_PERMISSIONS,
    SYSTEM_ROLES,
    PERMISSION_CODE_PATTERN,
    ROLE_NAME_PATTERN,
)
from app.models.user import User


DEFAULT_PERMISSION_METADATA: Final[
    dict[str, tuple[str, str]]
] = {
    PERMISSION_USER_READ: (
        "Read Users",
        "View user accounts and account status.",
    ),
    PERMISSION_USER_APPROVE: (
        "Approve Users",
        "Approve or reject pending user accounts.",
    ),
    PERMISSION_USER_SUSPEND: (
        "Suspend Users",
        "Suspend or restore user accounts.",
    ),
    PERMISSION_ROLE_READ: (
        "Read Roles",
        "View roles, permissions, and assignments.",
    ),
    PERMISSION_ROLE_ASSIGN: (
        "Assign Roles",
        "Assign and revoke non-owner roles.",
    ),
    PERMISSION_AUDIT_READ: (
        "Read Security Audits",
        "View security audit events and access logs.",
    ),
    PERMISSION_SIGNAL_READ: (
        "Read Signals",
        "View trading signals and signal history.",
    ),
    PERMISSION_SIGNAL_CREATE: (
        "Create Signals",
        "Generate and store trading signals.",
    ),
    PERMISSION_SIGNAL_MANAGE: (
        "Manage Signals",
        "Manage signal records and signal outcomes.",
    ),
    PERMISSION_SYSTEM_READ: (
        "Read System",
        "View backend health and system metadata.",
    ),
    PERMISSION_SYSTEM_MANAGE: (
        "Manage System",
        "Manage protected system settings.",
    ),
}


DEFAULT_ROLE_METADATA: Final[
    dict[str, tuple[str, str, set[str]]]
] = {
    ROLE_OWNER: (
        "Owner",
        "Full platform control. This role is reserved for the owner.",
        set(SYSTEM_PERMISSIONS),
    ),
    ROLE_ADMIN: (
        "Administrator",
        "Manage users, audits, roles, and trading records without owner-only system control.",
        {
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
        },
    ),
    ROLE_ANALYST: (
        "Analyst",
        "View and create trading analysis and signals.",
        {
            PERMISSION_SIGNAL_READ,
            PERMISSION_SIGNAL_CREATE,
            PERMISSION_SYSTEM_READ,
        },
    ),
    ROLE_USER: (
        "User",
        "Standard approved user access.",
        {
            PERMISSION_SIGNAL_READ,
            PERMISSION_SYSTEM_READ,
        },
    ),
}


class RolePermissionError(Exception):
    """
    Base exception for role and permission failures.
    """


class RoleNotFoundError(RolePermissionError):
    pass


class PermissionDeniedError(RolePermissionError):
    pass


class OwnerRoleProtectionError(RolePermissionError):
    pass


class InvalidRoleAssignmentError(RolePermissionError):
    pass


@dataclass(frozen=True)
class AccessSnapshot:
    user_id: int
    roles: tuple[str, ...]
    permissions: tuple[str, ...]
    is_owner: bool

    def has_role(self, role_name: str) -> bool:
        return str(role_name or "").strip().upper() in self.roles

    def has_permission(self, permission_code: str) -> bool:
        return (
            str(permission_code or "").strip().lower()
            in self.permissions
        )

    def to_dict(self) -> dict[str, object]:
        return {
            "user_id": self.user_id,
            "roles": list(self.roles),
            "permissions": list(self.permissions),
            "is_owner": self.is_owner,
        }


def _normalise_positive_id(
    value: int,
    *,
    field_name: str,
    allow_none: bool = False,
) -> int | None:
    """Validate and return one positive integer identifier."""

    if value is None:
        if allow_none:
            return None

        raise InvalidRoleAssignmentError(
            f"{field_name} is required."
        )

    if isinstance(
        value,
        bool,
    ):
        raise InvalidRoleAssignmentError(
            f"{field_name} must be an integer."
        )

    try:
        resolved = int(value)
    except (
        TypeError,
        ValueError,
        OverflowError,
    ) as exc:
        raise InvalidRoleAssignmentError(
            f"{field_name} must be an integer."
        ) from exc

    if resolved < 1:
        raise InvalidRoleAssignmentError(
            f"{field_name} must be positive."
        )

    return resolved


def normalise_role_name(role_name: str) -> str:
    resolved = str(role_name or "").strip().upper()

    if (
        not resolved
        or not ROLE_NAME_PATTERN.fullmatch(
            resolved
        )
    ):
        raise InvalidRoleAssignmentError(
            "Role name is invalid."
        )

    return resolved


def normalise_permission_code(
    permission_code: str,
) -> str:
    resolved = str(
        permission_code or ""
    ).strip().lower()

    if (
        not resolved
        or not PERMISSION_CODE_PATTERN.fullmatch(
            resolved
        )
    ):
        raise PermissionDeniedError(
            "Permission code is invalid."
        )

    return resolved


def seed_default_roles_and_permissions(
    db: Session,
    *,
    commit: bool = True,
) -> dict[str, int]:
    """
    Create or repair all system permissions and roles.
    """

    created_permissions = 0
    created_roles = 0
    updated_roles = 0

    permission_map: dict[str, Permission] = {}

    for code in sorted(SYSTEM_PERMISSIONS):
        metadata = DEFAULT_PERMISSION_METADATA[code]

        permission = (
            db.query(Permission)
            .filter(Permission.code == code)
            .first()
        )

        if permission is None:
            permission = Permission(
                code=code,
                display_name=metadata[0],
                description=metadata[1],
                is_system=True,
                is_active=True,
            )
            permission.validate_state()
            db.add(permission)
            db.flush()
            created_permissions += 1
        else:
            permission.display_name = metadata[0]
            permission.description = metadata[1]
            permission.is_system = True
            permission.is_active = True
            permission.validate_state()

        permission_map[code] = permission

    for role_name in (
        ROLE_OWNER,
        ROLE_ADMIN,
        ROLE_ANALYST,
        ROLE_USER,
    ):
        display_name, description, codes = (
            DEFAULT_ROLE_METADATA[role_name]
        )

        role = (
            db.query(Role)
            .filter(Role.name == role_name)
            .first()
        )

        if role is None:
            role = Role(
                name=role_name,
                display_name=display_name,
                description=description,
                is_system=True,
                is_active=True,
            )
            role.validate_state()
            db.add(role)
            db.flush()
            created_roles += 1
        else:
            role.display_name = display_name
            role.description = description
            role.is_system = True
            role.is_active = True
            role.validate_state()
            updated_roles += 1

        role.permissions = [
            permission_map[code]
            for code in sorted(codes)
        ]

    if commit:
        try:
            db.commit()
        except Exception:
            db.rollback()
            raise
    else:
        db.flush()

    return {
        "created_permissions": created_permissions,
        "created_roles": created_roles,
        "updated_roles": updated_roles,
    }


def get_role(
    db: Session,
    *,
    role_name: str,
    active_only: bool = True,
) -> Role | None:
    resolved = normalise_role_name(role_name)

    query = db.query(Role).filter(
        Role.name == resolved
    )

    if active_only:
        query = query.filter(
            Role.is_active.is_(True)
        )

    return query.first()


def get_user_active_assignments(
    db: Session,
    *,
    user_id: int,
) -> list[UserRole]:
    resolved_user_id = _normalise_positive_id(
        user_id,
        field_name="User ID",
    )

    return (
        db.query(UserRole)
        .join(Role, UserRole.role_id == Role.id)
        .filter(
            UserRole.user_id == resolved_user_id,
            UserRole.is_active.is_(True),
            Role.is_active.is_(True),
        )
        .all()
    )


def get_user_role_names(
    db: Session,
    *,
    user_id: int,
) -> set[str]:
    return {
        assignment.role.name
        for assignment in get_user_active_assignments(
            db,
            user_id=user_id,
        )
        if assignment.role is not None
    }


def get_user_permission_codes(
    db: Session,
    *,
    user_id: int,
) -> set[str]:
    permissions: set[str] = set()

    for assignment in get_user_active_assignments(
        db,
        user_id=user_id,
    ):
        if assignment.role is None:
            continue

        for permission in assignment.role.permissions:
            if permission.is_active:
                permissions.add(permission.code)

    return permissions


def get_access_snapshot(
    db: Session,
    *,
    user_id: int,
) -> AccessSnapshot:
    resolved_user_id = _normalise_positive_id(
        user_id,
        field_name="User ID",
    )

    roles = tuple(
        sorted(
            get_user_role_names(
                db,
                user_id=resolved_user_id,
            )
        )
    )

    permissions = tuple(
        sorted(
            get_user_permission_codes(
                db,
                user_id=resolved_user_id,
            )
        )
    )

    return AccessSnapshot(
        user_id=resolved_user_id,
        roles=roles,
        permissions=permissions,
        is_owner=ROLE_OWNER in roles,
    )


def user_has_role(
    db: Session,
    *,
    user_id: int,
    role_name: str,
) -> bool:
    return (
        normalise_role_name(role_name)
        in get_user_role_names(
            db,
            user_id=user_id,
        )
    )


def user_has_permission(
    db: Session,
    *,
    user_id: int,
    permission_code: str,
) -> bool:
    return (
        normalise_permission_code(permission_code)
        in get_user_permission_codes(
            db,
            user_id=user_id,
        )
    )


def require_role(
    db: Session,
    *,
    user_id: int,
    role_name: str,
) -> AccessSnapshot:
    snapshot = get_access_snapshot(
        db,
        user_id=user_id,
    )

    if not snapshot.has_role(role_name):
        raise PermissionDeniedError(
            f"Required role: {normalise_role_name(role_name)}"
        )

    return snapshot


def require_permission(
    db: Session,
    *,
    user_id: int,
    permission_code: str,
) -> AccessSnapshot:
    snapshot = get_access_snapshot(
        db,
        user_id=user_id,
    )

    if snapshot.is_owner:
        return snapshot

    if not snapshot.has_permission(permission_code):
        raise PermissionDeniedError(
            "Required permission: "
            + normalise_permission_code(
                permission_code
            )
        )

    return snapshot


def assign_role_to_user(
    db: Session,
    *,
    user_id: int,
    role_name: str,
    assigned_by_user_id: int | None,
    allow_owner_role: bool = False,
    commit: bool = True,
) -> UserRole:
    """
    Assign or reactivate one role.
    """

    resolved_user_id = _normalise_positive_id(
        user_id,
        field_name="User ID",
    )
    resolved_assigner_id = _normalise_positive_id(
        assigned_by_user_id,
        field_name="Assigned-by user ID",
        allow_none=True,
    )

    role = get_role(
        db,
        role_name=role_name,
        active_only=True,
    )

    if role is None:
        raise RoleNotFoundError(
            "Role does not exist."
        )

    if (
        role.name == ROLE_OWNER
        and not allow_owner_role
    ):
        raise OwnerRoleProtectionError(
            "Owner role assignment is protected."
        )

    user = (
        db.query(User)
        .filter(User.id == resolved_user_id)
        .first()
    )

    if user is None:
        raise InvalidRoleAssignmentError(
            "User does not exist."
        )

    if resolved_assigner_id is not None:
        assigner_exists = (
            db.query(User.id)
            .filter(
                User.id == resolved_assigner_id
            )
            .first()
        )

        if assigner_exists is None:
            raise InvalidRoleAssignmentError(
                "Assigning user does not exist."
            )

    assignment = (
        db.query(UserRole)
        .filter(
            UserRole.user_id == resolved_user_id,
            UserRole.role_id == int(role.id),
        )
        .with_for_update()
        .first()
    )

    if assignment is None:
        assignment = UserRole(
            user_id=resolved_user_id,
            role_id=int(role.id),
            assigned_by_user_id=(
                resolved_assigner_id
            ),
            is_active=True,
        )
        db.add(assignment)
    elif not assignment.is_active:
        assignment.reactivate(
            assigned_by_user_id=(
                resolved_assigner_id
            )
        )

    assignment.validate_state()

    if commit:
        try:
            db.commit()
            db.refresh(assignment)
        except Exception:
            db.rollback()
            raise
    else:
        db.flush()

    return assignment


def revoke_role_from_user(
    db: Session,
    *,
    user_id: int,
    role_name: str,
    reason: str,
    allow_owner_role: bool = False,
    commit: bool = True,
) -> UserRole:
    """
    Revoke one active role assignment.
    """

    resolved_user_id = _normalise_positive_id(
        user_id,
        field_name="User ID",
    )
    resolved_role = normalise_role_name(
        role_name
    )

    if (
        resolved_role == ROLE_OWNER
        and not allow_owner_role
    ):
        raise OwnerRoleProtectionError(
            "Owner role revocation is protected."
        )

    role = get_role(
        db,
        role_name=resolved_role,
        active_only=False,
    )

    if role is None:
        raise RoleNotFoundError(
            "Role does not exist."
        )

    assignment = (
        db.query(UserRole)
        .filter(
            UserRole.user_id == resolved_user_id,
            UserRole.role_id == int(role.id),
            UserRole.is_active.is_(True),
        )
        .with_for_update()
        .first()
    )

    if assignment is None:
        raise InvalidRoleAssignmentError(
            "Active role assignment does not exist."
        )

    assignment.revoke(
        reason=reason
    )
    assignment.validate_state()

    if commit:
        try:
            db.commit()
            db.refresh(assignment)
        except Exception:
            db.rollback()
            raise
    else:
        db.flush()

    return assignment


def ensure_default_user_role(
    db: Session,
    *,
    user_id: int,
    assigned_by_user_id: int | None = None,
    commit: bool = True,
) -> UserRole:
    """
    Ensure one approved account has the standard USER role.
    """

    return assign_role_to_user(
        db,
        user_id=user_id,
        role_name=ROLE_USER,
        assigned_by_user_id=assigned_by_user_id,
        allow_owner_role=False,
        commit=commit,
    )


def ensure_owner_role(
    db: Session,
    *,
    user_id: int,
    commit: bool = True,
) -> UserRole:
    """
    Assign the protected OWNER role during trusted setup only.
    """

    return assign_role_to_user(
        db,
        user_id=user_id,
        role_name=ROLE_OWNER,
        assigned_by_user_id=user_id,
        allow_owner_role=True,
        commit=commit,
    )


def list_roles(
    db: Session,
    *,
    active_only: bool = True,
) -> list[Role]:
    query = db.query(Role)

    if active_only:
        query = query.filter(
            Role.is_active.is_(True)
        )

    return query.order_by(Role.name.asc()).all()


def list_permissions(
    db: Session,
    *,
    active_only: bool = True,
) -> list[Permission]:
    query = db.query(Permission)

    if active_only:
        query = query.filter(
            Permission.is_active.is_(True)
        )

    return query.order_by(
        Permission.code.asc()
    ).all()


def users_with_role(
    db: Session,
    *,
    role_name: str,
) -> list[int]:
    role = get_role(
        db,
        role_name=role_name,
        active_only=True,
    )

    if role is None:
        return []

    return sorted(
        {
            int(row.user_id)
            for row in (
                db.query(UserRole)
            .filter(
                UserRole.role_id == int(role.id),
                UserRole.is_active.is_(True),
            )
                .all()
            )
        }
    )


def user_has_any_permission(
    db: Session,
    *,
    user_id: int,
    permission_codes: Iterable[str],
) -> bool:
    owned = get_user_permission_codes(
        db,
        user_id=user_id,
    )

    requested = {
        normalise_permission_code(code)
        for code in permission_codes
    }

    return bool(
        owned.intersection(requested)
    )


__all__ = [
    "AccessSnapshot",
    "InvalidRoleAssignmentError",
    "OwnerRoleProtectionError",
    "PermissionDeniedError",
    "RoleNotFoundError",
    "RolePermissionError",
    "assign_role_to_user",
    "ensure_default_user_role",
    "ensure_owner_role",
    "get_access_snapshot",
    "get_role",
    "get_user_active_assignments",
    "get_user_permission_codes",
    "get_user_role_names",
    "list_permissions",
    "list_roles",
    "normalise_permission_code",
    "normalise_role_name",
    "require_permission",
    "require_role",
    "revoke_role_from_user",
    "seed_default_roles_and_permissions",
    "user_has_any_permission",
    "user_has_permission",
    "user_has_role",
    "users_with_role",
]