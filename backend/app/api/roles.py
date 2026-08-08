from __future__ import annotations

from typing import Any

from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
    Path,
    status,
)
from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    field_validator,
)
from sqlalchemy.orm import Session

from app.core.dependencies import (
    get_current_user,
)
from app.core.permission_dependencies import (
    require_permission_dependency,
)
from app.database.connection import get_db
from app.models.role_permission import (
    MAX_REVOKE_REASON_LENGTH,
    PERMISSION_ROLE_ASSIGN,
    PERMISSION_ROLE_READ,
    ROLE_NAME_PATTERN,
    ROLE_OWNER,
)
from app.models.user import User
from app.services.role_permission_service import (
    InvalidRoleAssignmentError,
    OwnerRoleProtectionError,
    PermissionDeniedError,
    RoleNotFoundError,
    assign_role_to_user,
    get_access_snapshot,
    get_user_active_assignments,
    list_permissions,
    list_roles,
    normalise_role_name,
    revoke_role_from_user,
)


ROLE_API_VERSION = 42


router = APIRouter(
    prefix="/roles",
    tags=[
        "Roles and Permissions - Version 42"
    ],
)


def _clean_single_line(
    value: str,
    *,
    maximum_length: int,
) -> str:
    """
    Return printable single-line request text.

    Control characters are replaced to prevent audit or log injection.
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


class RoleAssignmentRequest(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
        str_strip_whitespace=True,
    )

    role_name: str = Field(
        ...,
        min_length=2,
        max_length=40,
    )

    @field_validator("role_name")
    @classmethod
    def validate_role_name(
        cls,
        value: str,
    ) -> str:
        resolved = _clean_single_line(
            value,
            maximum_length=40,
        ).upper()

        if (
            not resolved
            or not ROLE_NAME_PATTERN.fullmatch(
                resolved
            )
        ):
            raise ValueError(
                "Role name is invalid."
            )

        return resolved


class RoleRevocationRequest(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
        str_strip_whitespace=True,
    )

    role_name: str = Field(
        ...,
        min_length=2,
        max_length=40,
    )

    reason: str = Field(
        default="OWNER_ACTION",
        min_length=2,
        max_length=MAX_REVOKE_REASON_LENGTH,
    )

    @field_validator("role_name")
    @classmethod
    def validate_role_name(
        cls,
        value: str,
    ) -> str:
        resolved = _clean_single_line(
            value,
            maximum_length=40,
        ).upper()

        if (
            not resolved
            or not ROLE_NAME_PATTERN.fullmatch(
                resolved
            )
        ):
            raise ValueError(
                "Role name is invalid."
            )

        return resolved

    @field_validator("reason")
    @classmethod
    def validate_reason(
        cls,
        value: str,
    ) -> str:
        resolved = _clean_single_line(
            value,
            maximum_length=(
                MAX_REVOKE_REASON_LENGTH
            ),
        )

        if not resolved:
            raise ValueError(
                "Revocation reason is required."
            )

        return resolved


def _authenticated_user_id(
    current_user: User,
) -> int:
    """
    Return one strictly validated authenticated user ID.
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


def _get_user_or_404(
    db: Session,
    *,
    user_id: int,
) -> User:
    user = (
        db.query(User)
        .filter(
            User.id == user_id
        )
        .first()
    )

    if user is None:
        raise HTTPException(
            status_code=(
                status.HTTP_404_NOT_FOUND
            ),
            detail="User does not exist.",
        )

    return user


@router.get("/")
def role_api_home(
    _: User = Depends(
        get_current_user
    ),
) -> dict[str, Any]:
    return {
        "status": "ok",
        "role_api_version": (
            ROLE_API_VERSION
        ),
        "roles_enabled": True,
        "permissions_enabled": True,
        "owner_role_protected": True,
        "role_assignment_auditable": True,
    }


@router.get("/me")
def get_my_access(
    current_user: User = Depends(
        get_current_user
    ),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    current_user_id = (
        _authenticated_user_id(
            current_user
        )
    )

    try:
        snapshot = get_access_snapshot(
            db,
            user_id=current_user_id,
        )
    except (
        InvalidRoleAssignmentError,
        PermissionDeniedError,
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

    return {
        "status": "success",
        "access": snapshot.to_dict(),
    }


@router.get(
    "/list",
    dependencies=[
        Depends(
            require_permission_dependency(
                PERMISSION_ROLE_READ
            )
        )
    ],
)
def get_roles(
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    roles = list_roles(
        db,
        active_only=True,
    )

    return {
        "status": "success",
        "count": len(roles),
        "roles": [
            role.to_public_dict()
            for role in roles
        ],
    }


@router.get(
    "/permissions",
    dependencies=[
        Depends(
            require_permission_dependency(
                PERMISSION_ROLE_READ
            )
        )
    ],
)
def get_permissions(
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    permissions = list_permissions(
        db,
        active_only=True,
    )

    return {
        "status": "success",
        "count": len(permissions),
        "permissions": [
            permission.to_public_dict()
            for permission in permissions
        ],
    }


@router.get(
    "/users/{user_id}",
    dependencies=[
        Depends(
            require_permission_dependency(
                PERMISSION_ROLE_READ
            )
        )
    ],
)
def get_user_roles(
    user_id: int = Path(
        ...,
        ge=1,
    ),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    _get_user_or_404(
        db,
        user_id=user_id,
    )

    assignments = (
        get_user_active_assignments(
            db,
            user_id=user_id,
        )
    )

    snapshot = get_access_snapshot(
        db,
        user_id=user_id,
    )

    return {
        "status": "success",
        "user_id": user_id,
        "roles": [
            assignment.to_public_dict()
            for assignment in assignments
        ],
        "access": snapshot.to_dict(),
    }


@router.post(
    "/users/{user_id}/assign",
    dependencies=[
        Depends(
            require_permission_dependency(
                PERMISSION_ROLE_ASSIGN
            )
        )
    ],
)
def assign_user_role(
    payload: RoleAssignmentRequest,
    user_id: int = Path(
        ...,
        ge=1,
    ),
    current_user: User = Depends(
        get_current_user
    ),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    current_user_id = (
        _authenticated_user_id(
            current_user
        )
    )

    if user_id == current_user_id:
        raise HTTPException(
            status_code=(
                status.HTTP_409_CONFLICT
            ),
            detail=(
                "You cannot change your own role "
                "through this endpoint."
            ),
        )

    try:
        assignment = assign_role_to_user(
            db,
            user_id=user_id,
            role_name=normalise_role_name(
                payload.role_name
            ),
            assigned_by_user_id=(
                current_user_id
            ),
            allow_owner_role=False,
            commit=True,
        )
    except RoleNotFoundError as exc:
        raise HTTPException(
            status_code=(
                status.HTTP_404_NOT_FOUND
            ),
            detail="Role does not exist.",
        ) from exc
    except OwnerRoleProtectionError as exc:
        raise HTTPException(
            status_code=(
                status.HTTP_403_FORBIDDEN
            ),
            detail=(
                "Owner role assignment is protected."
            ),
        ) from exc
    except (
        InvalidRoleAssignmentError,
        PermissionDeniedError,
    ) as exc:
        raise HTTPException(
            status_code=(
                status.HTTP_409_CONFLICT
            ),
            detail=str(exc),
        ) from exc

    snapshot = get_access_snapshot(
        db,
        user_id=user_id,
    )

    return {
        "status": "success",
        "message": (
            "Role assigned successfully."
        ),
        "assignment": (
            assignment.to_public_dict()
        ),
        "access": snapshot.to_dict(),
    }


@router.post(
    "/users/{user_id}/revoke",
    dependencies=[
        Depends(
            require_permission_dependency(
                PERMISSION_ROLE_ASSIGN
            )
        )
    ],
)
def revoke_user_role(
    payload: RoleRevocationRequest,
    user_id: int = Path(
        ...,
        ge=1,
    ),
    current_user: User = Depends(
        get_current_user
    ),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    current_user_id = (
        _authenticated_user_id(
            current_user
        )
    )

    if user_id == current_user_id:
        raise HTTPException(
            status_code=(
                status.HTTP_409_CONFLICT
            ),
            detail=(
                "You cannot revoke your own role "
                "through this endpoint."
            ),
        )

    try:
        assignment = revoke_role_from_user(
            db,
            user_id=user_id,
            role_name=normalise_role_name(
                payload.role_name
            ),
            reason=payload.reason,
            allow_owner_role=False,
            commit=True,
        )
    except RoleNotFoundError as exc:
        raise HTTPException(
            status_code=(
                status.HTTP_404_NOT_FOUND
            ),
            detail="Role does not exist.",
        ) from exc
    except OwnerRoleProtectionError as exc:
        raise HTTPException(
            status_code=(
                status.HTTP_403_FORBIDDEN
            ),
            detail=(
                "Owner role revocation is protected."
            ),
        ) from exc
    except (
        InvalidRoleAssignmentError,
        PermissionDeniedError,
    ) as exc:
        raise HTTPException(
            status_code=(
                status.HTTP_409_CONFLICT
            ),
            detail=str(exc),
        ) from exc

    snapshot = get_access_snapshot(
        db,
        user_id=user_id,
    )

    return {
        "status": "success",
        "message": (
            "Role revoked successfully."
        ),
        "assignment": (
            assignment.to_public_dict()
        ),
        "access": snapshot.to_dict(),
    }


__all__ = [
    "ROLE_API_VERSION",
    "RoleAssignmentRequest",
    "RoleRevocationRequest",
    "router",
]