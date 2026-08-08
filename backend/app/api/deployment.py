from __future__ import annotations

from typing import Any

from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
    status,
)

from app.core.permission_dependencies import (
    require_permission_dependency,
)
from app.models.role_permission import (
    PERMISSION_SYSTEM_MANAGE,
    PERMISSION_SYSTEM_READ,
)
from app.services.deployment_validation_service import (
    MINIMUM_SECRET_LENGTH,
    RECOMMENDED_SECRET_LENGTH,
    run_deployment_validation,
)


DEPLOYMENT_API_VERSION = 49


router = APIRouter(
    prefix="/deployment",
    tags=["Deployment Preparation - Version 49"],
)


def _run_validation_or_500() -> dict[str, Any]:
    """
    Run deployment validation without exposing internal exceptions.
    """

    try:
        validation = (
            run_deployment_validation()
        )
    except Exception as exc:
        raise HTTPException(
            status_code=(
                status.HTTP_500_INTERNAL_SERVER_ERROR
            ),
            detail=(
                "Deployment validation could not be completed."
            ),
        ) from exc

    if not isinstance(
        validation,
        dict,
    ):
        raise HTTPException(
            status_code=(
                status.HTTP_500_INTERNAL_SERVER_ERROR
            ),
            detail=(
                "Deployment validation returned an invalid result."
            ),
        )

    return validation


def _integer_value(
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
def deployment_home() -> dict[str, Any]:
    return {
        "status": "ok",
        "deployment_api_version": (
            DEPLOYMENT_API_VERSION
        ),
        "validation_is_read_only": True,
        "broker_execution_enabled": False,
        "permission_protected": True,
        "minimum_secret_length": (
            MINIMUM_SECRET_LENGTH
        ),
        "recommended_secret_length": (
            RECOMMENDED_SECRET_LENGTH
        ),
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
def deployment_status() -> dict[str, Any]:
    """
    Return a bounded deployment-readiness summary.
    """

    validation = (
        _run_validation_or_500()
    )

    deployment_ready = bool(
        validation.get(
            "deployment_ready",
            False,
        )
    )

    production_mode_detected = bool(
        validation.get(
            "production_mode_detected",
            False,
        )
    )

    passed_checks = _integer_value(
        validation,
        "passed_checks",
    )

    failed_checks = _integer_value(
        validation,
        "failed_checks",
    )

    total_checks = _integer_value(
        validation,
        "total_checks",
    )

    if total_checks < (
        passed_checks
        + failed_checks
    ):
        total_checks = (
            passed_checks
            + failed_checks
        )

    critical_failures = _integer_value(
        validation,
        "critical_failures",
    )

    return {
        "status": "success",
        "deployment_version": (
            DEPLOYMENT_API_VERSION
        ),
        "deployment_ready": (
            deployment_ready
        ),
        "production_mode_detected": (
            production_mode_detected
        ),
        "passed_checks": passed_checks,
        "failed_checks": failed_checks,
        "total_checks": total_checks,
        "critical_failures": (
            critical_failures
        ),
    }


@router.post(
    "/validate",
    dependencies=[
        Depends(
            require_permission_dependency(
                PERMISSION_SYSTEM_MANAGE
            )
        )
    ],
)
def validate_deployment() -> dict[str, Any]:
    """
    Run the complete deployment validation.

    Full validation details require system-management permission.
    """

    validation = (
        _run_validation_or_500()
    )

    return {
        "status": "success",
        "message": (
            "Deployment validation completed."
        ),
        "deployment_version": (
            DEPLOYMENT_API_VERSION
        ),
        "validation": validation,
    }


__all__ = [
    "DEPLOYMENT_API_VERSION",
    "router",
]