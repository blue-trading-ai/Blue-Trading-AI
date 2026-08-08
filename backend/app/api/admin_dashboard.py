from __future__ import annotations

from typing import Any

from fastapi import (
    APIRouter,
    Depends,
    Query,
)
from sqlalchemy.orm import Session

from app.core.permission_dependencies import (
    require_all_permissions_dependency,
    require_any_permission_dependency,
    require_permission_dependency,
)
from app.database.connection import get_db
from app.models.role_permission import (
    PERMISSION_AUDIT_READ,
    PERMISSION_ROLE_READ,
    PERMISSION_SYSTEM_READ,
    PERMISSION_USER_READ,
)
from app.services.admin_dashboard_service import (
    get_account_token_statistics,
    get_admin_dashboard_snapshot,
    get_recent_security_events,
    get_role_statistics,
    get_security_statistics,
    get_session_statistics,
    get_user_statistics,
)


ADMIN_DASHBOARD_VERSION = 43


router = APIRouter(
    prefix="/admin/dashboard",
    tags=["Admin Dashboard - Version 43"],
)


dashboard_home_guard = require_any_permission_dependency(
    PERMISSION_SYSTEM_READ,
    PERMISSION_USER_READ,
    PERMISSION_ROLE_READ,
    PERMISSION_AUDIT_READ,
)

dashboard_overview_guard = (
    require_all_permissions_dependency(
        PERMISSION_SYSTEM_READ,
        PERMISSION_USER_READ,
        PERMISSION_ROLE_READ,
        PERMISSION_AUDIT_READ,
    )
)


@router.get(
    "/",
    dependencies=[
        Depends(dashboard_home_guard),
    ],
)
def dashboard_home() -> dict[str, Any]:
    """
    Return safe dashboard capability metadata.
    """

    return {
        "status": "ok",
        "admin_dashboard_version": (
            ADMIN_DASHBOARD_VERSION
        ),
        "dashboard_enabled": True,
        "permission_protected": True,
        "sensitive_secrets_exposed": False,
        "overview_requires_all_dashboard_permissions": True,
    }


@router.get(
    "/overview",
    dependencies=[
        Depends(
            dashboard_overview_guard
        ),
    ],
)
def dashboard_overview(
    security_window_hours: int = Query(
        default=24,
        ge=1,
        le=720,
    ),
    recent_event_limit: int = Query(
        default=20,
        ge=1,
        le=100,
    ),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    """
    Return the complete admin dashboard snapshot.

    This aggregate endpoint requires every permission represented by
    its combined user, role, system, and security-audit data.
    """

    snapshot = (
        get_admin_dashboard_snapshot(
            db,
            security_window_hours=(
                security_window_hours
            ),
            recent_event_limit=(
                recent_event_limit
            ),
        )
    )

    return {
        "status": "success",
        "dashboard_version": (
            ADMIN_DASHBOARD_VERSION
        ),
        "snapshot": snapshot,
    }


@router.get(
    "/users",
    dependencies=[
        Depends(
            require_permission_dependency(
                PERMISSION_USER_READ
            )
        )
    ],
)
def dashboard_users(
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    """
    Return user-account totals.
    """

    return {
        "status": "success",
        "statistics": (
            get_user_statistics(db)
        ),
    }


@router.get(
    "/sessions",
    dependencies=[
        Depends(
            require_permission_dependency(
                PERMISSION_SYSTEM_READ
            )
        )
    ],
)
def dashboard_sessions(
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    """
    Return secure-session and refresh-token totals.
    """

    return {
        "status": "success",
        "statistics": (
            get_session_statistics(db)
        ),
    }


@router.get(
    "/security",
    dependencies=[
        Depends(
            require_permission_dependency(
                PERMISSION_AUDIT_READ
            )
        )
    ],
)
def dashboard_security(
    hours: int = Query(
        default=24,
        ge=1,
        le=720,
    ),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    """
    Return recent security-event totals.
    """

    return {
        "status": "success",
        "statistics": (
            get_security_statistics(
                db,
                hours=hours,
            )
        ),
    }


@router.get(
    "/roles",
    dependencies=[
        Depends(
            require_permission_dependency(
                PERMISSION_ROLE_READ
            )
        )
    ],
)
def dashboard_roles(
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    """
    Return role and assignment totals.
    """

    return {
        "status": "success",
        "statistics": (
            get_role_statistics(db)
        ),
    }


@router.get(
    "/account-tokens",
    dependencies=[
        Depends(
            require_permission_dependency(
                PERMISSION_SYSTEM_READ
            )
        )
    ],
)
def dashboard_account_tokens(
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    """
    Return verification and password-reset token totals.
    """

    return {
        "status": "success",
        "statistics": (
            get_account_token_statistics(
                db
            )
        ),
    }


@router.get(
    "/recent-events",
    dependencies=[
        Depends(
            require_permission_dependency(
                PERMISSION_AUDIT_READ
            )
        )
    ],
)
def dashboard_recent_events(
    limit: int = Query(
        default=20,
        ge=1,
        le=100,
    ),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    """
    Return safe recent security audit metadata.
    """

    events = get_recent_security_events(
        db,
        limit=limit,
    )

    return {
        "status": "success",
        "count": len(events),
        "events": events,
    }


__all__ = [
    "ADMIN_DASHBOARD_VERSION",
    "dashboard_home_guard",
    "dashboard_overview_guard",
    "router",
]