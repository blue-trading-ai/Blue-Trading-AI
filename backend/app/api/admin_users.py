from __future__ import annotations

from typing import Any, Literal

from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
    Path,
    Query,
    Request,
    status,
)
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.dependencies import get_current_user, get_db
from app.models.account_action_token import (
    TOKEN_REVOKE_ACCOUNT_BLOCKED,
    TOKEN_REVOKE_OWNER_ACTION,
)
from app.models.auth_session import (
    SESSION_REVOKE_ACCOUNT_BLOCKED,
    SESSION_REVOKE_OWNER_ACTION,
)
from app.models.refresh_token import (
    REFRESH_REVOKE_ACCOUNT_BLOCKED,
    REFRESH_REVOKE_OWNER_ACTION,
)
from app.models.security_audit_log import (
    AUDIT_EVENT_ACCOUNT_UNLOCKED,
    AUDIT_EVENT_USER_APPROVED,
    AUDIT_EVENT_USER_PENDING,
    AUDIT_EVENT_USER_REJECTED,
    AUDIT_EVENT_USER_SUSPENDED,
    AUDIT_OUTCOME_SUCCESS,
)
from app.models.user import (
    ACCOUNT_STATUS_APPROVED,
    ACCOUNT_STATUS_PENDING,
    ACCOUNT_STATUS_REJECTED,
    ACCOUNT_STATUS_SUSPENDED,
    SUPPORTED_ACCOUNT_STATUSES,
    User,
)
from app.services.account_action_token_service import (
    revoke_all_user_tokens,
)
from app.services.auth_session_service import (
    revoke_all_user_sessions,
)
from app.services.refresh_token_service import (
    revoke_all_user_refresh_tokens,
)
from app.services.role_permission_service import (
    InvalidRoleAssignmentError,
    PermissionDeniedError,
    ensure_default_user_role,
    get_access_snapshot,
    seed_default_roles_and_permissions,
)
from app.services.security_audit_service import (
    create_security_audit_log,
)


ADMIN_VERSION = 42
MAX_ADMIN_OFFSET = 100_000


router = APIRouter(
    prefix="/admin/users",
    tags=["Owner User Management - Version 42"],
)


def _normalise_email(
    email: str | None,
) -> str:
    return str(
        email or ""
    ).strip().lower()


def _mask_email(
    email: str | None,
) -> str | None:
    resolved = _normalise_email(
        email
    )

    if not resolved:
        return None

    local, separator, domain = (
        resolved.partition("@")
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


def _is_owner(
    user: User,
) -> bool:
    return (
        _normalise_email(
            user.email
        )
        == settings.owner_email_normalised
    )


def _validated_user_id(
    user: User,
    *,
    unauthorized: bool = False,
) -> int:
    """
    Return one strictly validated persisted user identifier.
    """

    status_code = (
        status.HTTP_401_UNAUTHORIZED
        if unauthorized
        else status.HTTP_409_CONFLICT
    )

    if user.id is None or isinstance(
        user.id,
        bool,
    ):
        raise HTTPException(
            status_code=status_code,
            detail=(
                "Authentication is invalid."
                if unauthorized
                else "User identity is invalid."
            ),
        )

    try:
        resolved = int(
            user.id
        )
    except (
        TypeError,
        ValueError,
        OverflowError,
    ) as exc:
        raise HTTPException(
            status_code=status_code,
            detail=(
                "Authentication is invalid."
                if unauthorized
                else "User identity is invalid."
            ),
        ) from exc

    if resolved < 1:
        raise HTTPException(
            status_code=status_code,
            detail=(
                "Authentication is invalid."
                if unauthorized
                else "User identity is invalid."
            ),
        )

    return resolved


def require_owner(
    current_user: User = Depends(
        get_current_user
    ),
    db: Session = Depends(get_db),
) -> User:
    """
    Allow only the exact configured owner account.
    """

    current_user_id = _validated_user_id(
        current_user,
        unauthorized=True,
    )

    if not _is_owner(
        current_user
    ):
        raise HTTPException(
            status_code=(
                status.HTTP_403_FORBIDDEN
            ),
            detail=(
                "Only the Blue-Trading-AI owner can manage "
                "user access."
            ),
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
                "Owner access could not be validated."
            ),
        ) from exc

    if not snapshot.is_owner:
        raise HTTPException(
            status_code=(
                status.HTTP_403_FORBIDDEN
            ),
            detail=(
                "Only the Blue-Trading-AI owner can manage "
                "user access."
            ),
        )

    return current_user


def _public_user(
    user: User,
) -> dict[str, Any]:
    return {
        "id": user.id,
        "username": user.username,
        "email": user.email,
        "is_owner": _is_owner(user),
        "is_active": bool(
            user.is_active
        ),
        "account_status": (
            user.account_status
        ),
        "is_approved": bool(
            user.is_approved
        ),
        "can_access_platform": bool(
            user.can_access_platform
        ),
        "approved_at": user.approved_at,
        "approved_by": user.approved_by,
        "rejected_at": user.rejected_at,
        "suspended_at": user.suspended_at,
        "access_status_updated_at": (
            user.access_status_updated_at
        ),
        "failed_login_attempts": int(
            user.failed_login_attempts
            or 0
        ),
        "last_failed_login_at": (
            user.last_failed_login_at
        ),
        "locked_until": user.locked_until,
        "is_login_locked": bool(
            user.is_login_locked
        ),
        "lockout_seconds_remaining": int(
            user.lockout_seconds_remaining
        ),
        "last_login_at": (
            user.last_login_at
        ),
        "created_at": user.created_at,
    }


def _get_user_or_404(
    db: Session,
    user_id: int,
    *,
    lock_for_update: bool = False,
) -> User:
    query = (
        db.query(User)
        .filter(
            User.id == user_id
        )
    )

    if lock_for_update:
        query = query.with_for_update()

    user = query.first()

    if user is None:
        raise HTTPException(
            status_code=(
                status.HTTP_404_NOT_FOUND
            ),
            detail="User not found.",
        )

    return user


def _protect_owner_account(
    target_user: User,
    action: str,
) -> None:
    """
    Prevent accidental owner lockout.
    """

    if (
        _is_owner(target_user)
        and action
        in {
            "reject",
            "suspend",
            "pending",
        }
    ):
        raise HTTPException(
            status_code=(
                status.HTTP_409_CONFLICT
            ),
            detail=(
                "The owner account cannot be rejected, "
                "suspended, or returned to pending."
            ),
        )


def _commit_or_500(
    db: Session,
    *,
    message: str,
) -> None:
    try:
        db.commit()
    except SQLAlchemyError as exc:
        db.rollback()
        raise HTTPException(
            status_code=(
                status.HTTP_500_INTERNAL_SERVER_ERROR
            ),
            detail=message,
        ) from exc


def _stage_audit_event(
    *,
    db: Session,
    event_type: str,
    request: Request,
    owner: User,
    target_user: User,
    message: str,
    details: dict[str, Any],
) -> None:
    log = create_security_audit_log(
        db=db,
        event_type=event_type,
        outcome=(
            AUDIT_OUTCOME_SUCCESS
        ),
        request=request,
        actor_user=owner,
        target_user=target_user,
        message=message,
        details=details,
        is_security_sensitive=True,
        commit=False,
    )

    if log is None:
        raise HTTPException(
            status_code=(
                status.HTTP_500_INTERNAL_SERVER_ERROR
            ),
            detail=(
                "The security audit event could not be recorded."
            ),
        )


@router.get("/")
def admin_home(
    owner: User = Depends(
        require_owner
    ),
) -> dict[str, Any]:
    return {
        "status": "success",
        "message": (
            "Blue-Trading-AI owner user management "
            "is working."
        ),
        "admin_version": ADMIN_VERSION,
        "owner_email": _mask_email(
            owner.email
        ),
        "supported_statuses": sorted(
            SUPPORTED_ACCOUNT_STATUSES
        ),
        "failed_login_tracking_enabled": True,
        "temporary_login_lockout_enabled": True,
        "owner_manual_unlock_enabled": True,
        "security_audit_logging_enabled": True,
        "session_revocation_enabled": True,
        "roles_and_permissions_enabled": True,
        "owner_role_protected": True,
    }


@router.get("")
def list_users(
    account_status: Literal[
        "PENDING",
        "APPROVED",
        "REJECTED",
        "SUSPENDED",
    ]
    | None = Query(
        default=None
    ),
    limit: int = Query(
        default=100,
        ge=1,
        le=500,
    ),
    offset: int = Query(
        default=0,
        ge=0,
        le=MAX_ADMIN_OFFSET,
    ),
    db: Session = Depends(get_db),
    _: User = Depends(require_owner),
) -> dict[str, Any]:
    query = db.query(User)

    if account_status is not None:
        query = query.filter(
            User.account_status
            == account_status
        )

    total = int(
        query.count()
    )

    users = (
        query.order_by(
            User.created_at.desc(),
            User.id.desc(),
        )
        .offset(offset)
        .limit(limit)
        .all()
    )

    return {
        "status": "success",
        "total": total,
        "limit": limit,
        "offset": offset,
        "account_status_filter": (
            account_status
        ),
        "users": [
            _public_user(user)
            for user in users
        ],
    }


@router.get("/{user_id}")
def get_user(
    user_id: int = Path(
        ...,
        ge=1,
    ),
    db: Session = Depends(get_db),
    _: User = Depends(require_owner),
) -> dict[str, Any]:
    user = _get_user_or_404(
        db,
        user_id,
    )

    return {
        "status": "success",
        "user": _public_user(user),
    }


@router.post("/{user_id}/approve")
def approve_user(
    request: Request,
    user_id: int = Path(
        ...,
        ge=1,
    ),
    db: Session = Depends(get_db),
    owner: User = Depends(require_owner),
) -> dict[str, Any]:
    user = _get_user_or_404(
        db,
        user_id,
        lock_for_update=True,
    )

    owner_id = _validated_user_id(
        owner,
        unauthorized=True,
    )
    target_user_id = _validated_user_id(
        user
    )

    seed_default_roles_and_permissions(
        db,
        commit=False,
    )

    already_approved = (
        user.account_status
        == ACCOUNT_STATUS_APPROVED
        and bool(user.is_active)
    )

    if not already_approved:
        user.approve(
            approved_by=owner.email
        )

    role_assignment = (
        ensure_default_user_role(
            db,
            user_id=target_user_id,
            assigned_by_user_id=owner_id,
            commit=False,
        )
    )

    access_snapshot = (
        get_access_snapshot(
            db,
            user_id=target_user_id,
        )
    )

    if not already_approved:
        _stage_audit_event(
            db=db,
            event_type=(
                AUDIT_EVENT_USER_APPROVED
            ),
            request=request,
            owner=owner,
            target_user=user,
            message=(
                "User approved successfully."
            ),
            details={
                "new_status": (
                    user.account_status
                ),
                "assigned_role": (
                    role_assignment.role.name
                    if (
                        role_assignment.role
                        is not None
                    )
                    else "USER"
                ),
                "roles": list(
                    access_snapshot.roles
                ),
                "permissions": list(
                    access_snapshot.permissions
                ),
            },
        )

    _commit_or_500(
        db,
        message=(
            "User approval could not be completed."
        ),
    )

    db.refresh(user)
    db.refresh(role_assignment)

    return {
        "status": "success",
        "message": (
            "User is already approved."
            if already_approved
            else "User approved successfully."
        ),
        "role_assignment": (
            role_assignment.to_public_dict()
        ),
        "access": (
            get_access_snapshot(
                db,
                user_id=target_user_id,
            ).to_dict()
        ),
        "user": _public_user(user),
    }


def _block_or_limit_user(
    *,
    db: Session,
    request: Request,
    owner: User,
    user_id: int,
    action: Literal[
        "reject",
        "suspend",
        "pending",
    ],
) -> dict[str, Any]:
    user = _get_user_or_404(
        db,
        user_id,
        lock_for_update=True,
    )

    _protect_owner_account(
        user,
        action,
    )

    target_user_id = _validated_user_id(
        user
    )

    status_map = {
        "reject": (
            ACCOUNT_STATUS_REJECTED
        ),
        "suspend": (
            ACCOUNT_STATUS_SUSPENDED
        ),
        "pending": (
            ACCOUNT_STATUS_PENDING
        ),
    }

    existing_status = status_map[
        action
    ]

    if (
        user.account_status
        == existing_status
    ):
        messages = {
            "reject": (
                "User is already rejected."
            ),
            "suspend": (
                "User is already suspended."
            ),
            "pending": (
                "User is already pending approval."
            ),
        }

        return {
            "status": "success",
            "message": messages[action],
            "user": _public_user(user),
        }

    if action == "reject":
        user.reject()
        session_reason = (
            SESSION_REVOKE_ACCOUNT_BLOCKED
        )
        refresh_reason = (
            REFRESH_REVOKE_ACCOUNT_BLOCKED
        )
        token_reason = (
            TOKEN_REVOKE_ACCOUNT_BLOCKED
        )
        event_type = (
            AUDIT_EVENT_USER_REJECTED
        )
        success_message = (
            "User rejected successfully."
        )
    elif action == "suspend":
        user.suspend()
        session_reason = (
            SESSION_REVOKE_ACCOUNT_BLOCKED
        )
        refresh_reason = (
            REFRESH_REVOKE_ACCOUNT_BLOCKED
        )
        token_reason = (
            TOKEN_REVOKE_ACCOUNT_BLOCKED
        )
        event_type = (
            AUDIT_EVENT_USER_SUSPENDED
        )
        success_message = (
            "User suspended successfully."
        )
    else:
        user.set_pending()
        session_reason = (
            SESSION_REVOKE_OWNER_ACTION
        )
        refresh_reason = (
            REFRESH_REVOKE_OWNER_ACTION
        )
        token_reason = (
            TOKEN_REVOKE_OWNER_ACTION
        )
        event_type = (
            AUDIT_EVENT_USER_PENDING
        )
        success_message = (
            "User returned to pending approval."
        )

    revoked_sessions = (
        revoke_all_user_sessions(
            db,
            user_id=target_user_id,
            reason=session_reason,
            commit=False,
        )
    )

    revoked_refresh_tokens = (
        revoke_all_user_refresh_tokens(
            db,
            user_id=target_user_id,
            reason=refresh_reason,
            commit=False,
        )
    )

    revoked_action_tokens = (
        revoke_all_user_tokens(
            db,
            user_id=target_user_id,
            reason=token_reason,
            commit=False,
        )
    )

    _stage_audit_event(
        db=db,
        event_type=event_type,
        request=request,
        owner=owner,
        target_user=user,
        message=success_message,
        details={
            "new_status": (
                user.account_status
            ),
            "revoked_sessions": (
                revoked_sessions
            ),
            "revoked_refresh_tokens": (
                revoked_refresh_tokens
            ),
            "revoked_action_tokens": (
                revoked_action_tokens
            ),
        },
    )

    _commit_or_500(
        db,
        message=(
            "The user access change could not be completed."
        ),
    )

    db.refresh(user)

    return {
        "status": "success",
        "message": success_message,
        "revoked_sessions": (
            revoked_sessions
        ),
        "revoked_refresh_tokens": (
            revoked_refresh_tokens
        ),
        "revoked_action_tokens": (
            revoked_action_tokens
        ),
        "user": _public_user(user),
    }


@router.post("/{user_id}/reject")
def reject_user(
    request: Request,
    user_id: int = Path(
        ...,
        ge=1,
    ),
    db: Session = Depends(get_db),
    owner: User = Depends(require_owner),
) -> dict[str, Any]:
    return _block_or_limit_user(
        db=db,
        request=request,
        owner=owner,
        user_id=user_id,
        action="reject",
    )


@router.post("/{user_id}/suspend")
def suspend_user(
    request: Request,
    user_id: int = Path(
        ...,
        ge=1,
    ),
    db: Session = Depends(get_db),
    owner: User = Depends(require_owner),
) -> dict[str, Any]:
    return _block_or_limit_user(
        db=db,
        request=request,
        owner=owner,
        user_id=user_id,
        action="suspend",
    )


@router.post("/{user_id}/pending")
def return_user_to_pending(
    request: Request,
    user_id: int = Path(
        ...,
        ge=1,
    ),
    db: Session = Depends(get_db),
    owner: User = Depends(require_owner),
) -> dict[str, Any]:
    return _block_or_limit_user(
        db=db,
        request=request,
        owner=owner,
        user_id=user_id,
        action="pending",
    )


@router.post("/{user_id}/unlock")
def unlock_user_login(
    request: Request,
    user_id: int = Path(
        ...,
        ge=1,
    ),
    db: Session = Depends(get_db),
    owner: User = Depends(require_owner),
) -> dict[str, Any]:
    user = _get_user_or_404(
        db,
        user_id,
        lock_for_update=True,
    )

    target_user_id = _validated_user_id(
        user
    )
    owner_id = _validated_user_id(
        owner,
        unauthorized=True,
    )

    if (
        _is_owner(user)
        and target_user_id != owner_id
    ):
        raise HTTPException(
            status_code=(
                status.HTTP_409_CONFLICT
            ),
            detail="Owner identity mismatch.",
        )

    was_locked = bool(
        user.is_login_locked
    )
    previous_attempts = int(
        user.failed_login_attempts
        or 0
    )

    user.unlock_login()

    _stage_audit_event(
        db=db,
        event_type=(
            AUDIT_EVENT_ACCOUNT_UNLOCKED
        ),
        request=request,
        owner=owner,
        target_user=user,
        message=(
            "User login lockout cleared successfully."
        ),
        details={
            "was_locked": was_locked,
            "previous_failed_login_attempts": (
                previous_attempts
            ),
        },
    )

    _commit_or_500(
        db,
        message=(
            "The user lockout could not be cleared."
        ),
    )

    db.refresh(user)

    return {
        "status": "success",
        "message": (
            "User login lockout cleared successfully."
            if (
                was_locked
                or previous_attempts > 0
            )
            else "User was not locked."
        ),
        "was_locked": was_locked,
        "previous_failed_login_attempts": (
            previous_attempts
        ),
        "user": _public_user(user),
    }


__all__ = [
    "ADMIN_VERSION",
    "MAX_ADMIN_OFFSET",
    "require_owner",
    "router",
]