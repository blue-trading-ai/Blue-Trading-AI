from __future__ import annotations

from collections.abc import Callable
from typing import Annotated

from fastapi import (
    Depends,
    HTTPException,
    status,
)
from sqlalchemy.orm import Session

from app.core.dependencies import (
    get_current_user,
)
from app.database.connection import get_db
from app.models.user import User
from app.services.role_permission_service import (
    AccessSnapshot,
    InvalidRoleAssignmentError,
    PermissionDeniedError,
    get_access_snapshot,
    normalise_permission_code,
    normalise_role_name,
    require_permission,
    require_role,
)


DatabaseSession = Annotated[
    Session,
    Depends(get_db),
]

CurrentUser = Annotated[
    User,
    Depends(get_current_user),
]


def _current_user_id(
    current_user: User,
) -> int:
    """
    Return one validated authenticated user ID.
    """

    if current_user.id is None:
        raise HTTPException(
            status_code=(
                status.HTTP_401_UNAUTHORIZED
            ),
            detail="Authentication is required.",
        )

    if isinstance(
        current_user.id,
        bool,
    ):
        raise HTTPException(
            status_code=(
                status.HTTP_401_UNAUTHORIZED
            ),
            detail="Authentication is invalid.",
        )

    try:
        resolved = int(
            current_user.id
        )
    except (
        TypeError,
        ValueError,
        OverflowError,
    ) as exc:
        raise HTTPException(
            status_code=(
                status.HTTP_401_UNAUTHORIZED
            ),
            detail="Authentication is invalid.",
        ) from exc

    if resolved < 1:
        raise HTTPException(
            status_code=(
                status.HTTP_401_UNAUTHORIZED
            ),
            detail="Authentication is invalid.",
        )

    return resolved


def get_current_access_snapshot(
    current_user: CurrentUser,
    db: DatabaseSession,
) -> AccessSnapshot:
    """
    Return the authenticated user's current roles and permissions.
    """

    try:
        return get_access_snapshot(
            db,
            user_id=_current_user_id(
                current_user
            ),
        )
    except (
        PermissionDeniedError,
        InvalidRoleAssignmentError,
    ) as exc:
        raise HTTPException(
            status_code=(
                status.HTTP_403_FORBIDDEN
            ),
            detail=(
                "Your current access permissions "
                "could not be validated."
            ),
        ) from exc


CurrentAccess = Annotated[
    AccessSnapshot,
    Depends(
        get_current_access_snapshot
    ),
]


def require_role_dependency(
    role_name: str,
) -> Callable[..., AccessSnapshot]:
    """
    Build a FastAPI dependency requiring one active role.
    """

    try:
        resolved_role = (
            normalise_role_name(
                role_name
            )
        )
    except InvalidRoleAssignmentError as exc:
        raise ValueError(
            "Required role name is invalid."
        ) from exc

    def dependency(
        current_user: CurrentUser,
        db: DatabaseSession,
    ) -> AccessSnapshot:
        try:
            return require_role(
                db,
                user_id=_current_user_id(
                    current_user
                ),
                role_name=resolved_role,
            )
        except (
            PermissionDeniedError,
            InvalidRoleAssignmentError,
        ) as exc:
            raise HTTPException(
                status_code=(
                    status.HTTP_403_FORBIDDEN
                ),
                detail=(
                    "You do not have the required role "
                    "for this action."
                ),
            ) from exc

    return dependency


def require_permission_dependency(
    permission_code: str,
) -> Callable[..., AccessSnapshot]:
    """
    Build a FastAPI dependency requiring one permission.

    The OWNER role automatically passes all permission checks.
    """

    try:
        resolved_permission = (
            normalise_permission_code(
                permission_code
            )
        )
    except PermissionDeniedError as exc:
        raise ValueError(
            "Required permission code is invalid."
        ) from exc

    def dependency(
        current_user: CurrentUser,
        db: DatabaseSession,
    ) -> AccessSnapshot:
        try:
            return require_permission(
                db,
                user_id=_current_user_id(
                    current_user
                ),
                permission_code=(
                    resolved_permission
                ),
            )
        except (
            PermissionDeniedError,
            InvalidRoleAssignmentError,
        ) as exc:
            raise HTTPException(
                status_code=(
                    status.HTTP_403_FORBIDDEN
                ),
                detail=(
                    "You do not have permission "
                    "to perform this action."
                ),
            ) from exc

    return dependency


def _normalise_permissions(
    permission_codes: tuple[str, ...],
) -> tuple[str, ...]:
    """
    Validate, normalize, and deduplicate permission codes.
    """

    if not permission_codes:
        raise ValueError(
            "At least one permission code is required."
        )

    resolved: list[str] = []
    seen: set[str] = set()

    for code in permission_codes:
        try:
            permission = (
                normalise_permission_code(
                    code
                )
            )
        except PermissionDeniedError as exc:
            raise ValueError(
                "One or more permission codes are invalid."
            ) from exc

        if permission not in seen:
            seen.add(permission)
            resolved.append(permission)

    if not resolved:
        raise ValueError(
            "At least one permission code is required."
        )

    return tuple(resolved)


def require_any_permission_dependency(
    *permission_codes: str,
) -> Callable[..., AccessSnapshot]:
    """
    Build a dependency allowing any one listed permission.
    """

    resolved_permissions = (
        _normalise_permissions(
            permission_codes
        )
    )

    def dependency(
        current_user: CurrentUser,
        db: DatabaseSession,
    ) -> AccessSnapshot:
        try:
            snapshot = get_access_snapshot(
                db,
                user_id=_current_user_id(
                    current_user
                ),
            )
        except (
            PermissionDeniedError,
            InvalidRoleAssignmentError,
        ) as exc:
            raise HTTPException(
                status_code=(
                    status.HTTP_403_FORBIDDEN
                ),
                detail=(
                    "You do not have any of the required "
                    "permissions for this action."
                ),
            ) from exc

        if snapshot.is_owner:
            return snapshot

        if any(
            snapshot.has_permission(
                code
            )
            for code in resolved_permissions
        ):
            return snapshot

        raise HTTPException(
            status_code=(
                status.HTTP_403_FORBIDDEN
            ),
            detail=(
                "You do not have any of the required "
                "permissions for this action."
            ),
        )

    return dependency


def require_all_permissions_dependency(
    *permission_codes: str,
) -> Callable[..., AccessSnapshot]:
    """
    Build a dependency requiring every listed permission.
    """

    resolved_permissions = (
        _normalise_permissions(
            permission_codes
        )
    )

    def dependency(
        current_user: CurrentUser,
        db: DatabaseSession,
    ) -> AccessSnapshot:
        try:
            snapshot = get_access_snapshot(
                db,
                user_id=_current_user_id(
                    current_user
                ),
            )
        except (
            PermissionDeniedError,
            InvalidRoleAssignmentError,
        ) as exc:
            raise HTTPException(
                status_code=(
                    status.HTTP_403_FORBIDDEN
                ),
                detail=(
                    "You do not have all required "
                    "permissions for this action."
                ),
            ) from exc

        if snapshot.is_owner:
            return snapshot

        if all(
            snapshot.has_permission(
                code
            )
            for code in resolved_permissions
        ):
            return snapshot

        raise HTTPException(
            status_code=(
                status.HTTP_403_FORBIDDEN
            ),
            detail=(
                "You do not have all required "
                "permissions for this action."
            ),
        )

    return dependency


__all__ = [
    "CurrentAccess",
    "CurrentUser",
    "DatabaseSession",
    "get_current_access_snapshot",
    "require_all_permissions_dependency",
    "require_any_permission_dependency",
    "require_permission_dependency",
    "require_role_dependency",
]