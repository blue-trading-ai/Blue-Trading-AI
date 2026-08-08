from __future__ import annotations

from typing import Any

from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
    status,
)
from sqlalchemy.orm import Session

from app.core.permission_dependencies import (
    require_permission_dependency,
)
from app.database.connection import get_db
from app.models.role_permission import (
    PERMISSION_SYSTEM_MANAGE,
    PERMISSION_SYSTEM_READ,
)
from app.services.production_readiness_audit_service import (
    run_production_readiness_audit,
)


READINESS_API_VERSION = 48


router = APIRouter(
    prefix="/readiness",
    tags=["Production Readiness - Version 48"],
)


def _run_readiness_audit_or_500(
    db: Session,
) -> dict[str, Any]:
    """
    Run the readiness audit without exposing internal exceptions.
    """

    try:
        audit = (
            run_production_readiness_audit(
                db
            )
        )
    except Exception as exc:
        raise HTTPException(
            status_code=(
                status.HTTP_500_INTERNAL_SERVER_ERROR
            ),
            detail=(
                "Production-readiness audit could not be completed."
            ),
        ) from exc

    if not isinstance(
        audit,
        dict,
    ):
        raise HTTPException(
            status_code=(
                status.HTTP_500_INTERNAL_SERVER_ERROR
            ),
            detail=(
                "Production-readiness audit returned an invalid result."
            ),
        )

    return audit


def _safe_non_negative_int(
    payload: dict[str, Any],
    key: str,
) -> int:
    value = payload.get(
        key,
        0,
    )

    if isinstance(
        value,
        bool,
    ):
        return 0

    try:
        resolved = int(
            value or 0
        )
    except (
        TypeError,
        ValueError,
        OverflowError,
    ):
        return 0

    return max(
        0,
        resolved,
    )


@router.get(
    "/",
    dependencies=[
        Depends(
            require_permission_dependency(
                PERMISSION_SYSTEM_READ
            )
        )
    ],
)
def readiness_home() -> dict[str, Any]:
    return {
        "status": "ok",
        "readiness_api_version": (
            READINESS_API_VERSION
        ),
        "audit_is_read_only": True,
        "broker_execution_enabled": False,
        "permission_protected": True,
    }


@router.get(
    "/status",
    dependencies=[
        Depends(
            require_permission_dependency(
                PERMISSION_SYSTEM_READ
            )
        )
    ],
)
def readiness_status(
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    """
    Return a bounded on-demand readiness summary.
    """

    audit = (
        _run_readiness_audit_or_500(
            db
        )
    )

    passed_checks = (
        _safe_non_negative_int(
            audit,
            "passed_checks",
        )
    )

    failed_checks = (
        _safe_non_negative_int(
            audit,
            "failed_checks",
        )
    )

    total_checks = (
        _safe_non_negative_int(
            audit,
            "total_checks",
        )
    )

    if total_checks < (
        passed_checks
        + failed_checks
    ):
        total_checks = (
            passed_checks
            + failed_checks
        )

    return {
        "status": "success",
        "readiness_version": (
            READINESS_API_VERSION
        ),
        "production_ready": bool(
            audit.get(
                "production_ready",
                False,
            )
        ),
        "passed_checks": (
            passed_checks
        ),
        "failed_checks": (
            failed_checks
        ),
        "total_checks": (
            total_checks
        ),
    }


@router.post(
    "/audit",
    dependencies=[
        Depends(
            require_permission_dependency(
                PERMISSION_SYSTEM_MANAGE
            )
        )
    ],
)
def run_readiness_audit(
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    """
    Run the complete production-readiness audit.

    Full readiness details require system-management permission.
    """

    audit = (
        _run_readiness_audit_or_500(
            db
        )
    )

    return {
        "status": "success",
        "message": (
            "Production-readiness audit completed."
        ),
        "readiness_version": (
            READINESS_API_VERSION
        ),
        "audit": audit,
    }


__all__ = [
    "READINESS_API_VERSION",
    "router",
]