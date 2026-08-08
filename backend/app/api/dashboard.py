from __future__ import annotations

import logging
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.database.connection import get_db
from app.services.dashboard_service import (
    get_dashboard_summary,
)


logger = logging.getLogger(__name__)


router = APIRouter(
    prefix="/dashboard",
    tags=["Dashboard"],
)


@router.get("/")
def dashboard_home() -> dict[str, Any]:
    return {
        "status": "success",
        "message": (
            "Blue-Trading-AI Dashboard API "
            "is working"
        ),
        "safety_version": 10,
    }


@router.get("/test")
def dashboard_test() -> dict[str, Any]:
    return {
        "status": "success",
        "module": "dashboard_summary",
        "features": [
            "overall_summary",
            "today_performance",
            "weekly_performance",
            "monthly_performance",
            "best_performing_symbol",
            "best_performing_direction",
            "learning_status",
        ],
        "safety_version": 10,
    }


@router.get("/summary")
def dashboard_summary(
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    try:
        result = get_dashboard_summary(
            db=db,
        )
    except SQLAlchemyError as error:
        logger.exception(
            "Database error while loading dashboard summary."
        )

        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Dashboard data is temporarily unavailable.",
        ) from error
    except ValueError as error:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(error) or "Invalid dashboard request.",
        ) from error
    except HTTPException:
        raise
    except Exception as error:
        logger.exception(
            "Unexpected error while loading dashboard summary."
        )

        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Dashboard summary could not be loaded.",
        ) from error

    if not isinstance(
        result,
        dict,
    ):
        logger.error(
            "Dashboard service returned an invalid response type.",
            extra={
                "result_type": type(result).__name__,
            },
        )

        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Dashboard summary returned an invalid response.",
        )

    return result


__all__ = [
    "dashboard_home",
    "dashboard_summary",
    "dashboard_test",
    "router",
]