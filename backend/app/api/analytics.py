from __future__ import annotations

import logging
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.database.connection import get_db
from app.services.performance_analytics_service import (
    get_performance_analytics,
)


logger = logging.getLogger(__name__)


router = APIRouter(
    prefix="/analytics",
    tags=["Performance Analytics"],
)


@router.get("/")
def analytics_home() -> dict[str, Any]:
    """
    Confirm that the analytics API is working.
    """

    return {
        "status": "success",
        "message": (
            "Blue-Trading-AI Performance Analytics API is working"
        ),
        "safety_version": 9,
    }


@router.get("/test")
def analytics_test() -> dict[str, Any]:
    """
    Return analytics module capabilities.
    """

    return {
        "status": "success",
        "module": "performance_analytics",
        "features": [
            "overall_performance",
            "daily_win_rate",
            "weekly_win_rate",
            "monthly_win_rate",
            "symbol_performance",
            "direction_performance",
            "trade_quality_performance",
        ],
        "timeframe_win_rate_enabled": False,
        "safety_version": 9,
    }


@router.get("/performance")
def performance_analytics(
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    """
    Return complete trading performance analytics.

    Timeframe win rate is intentionally excluded.
    """

    try:
        result = get_performance_analytics(
            db=db,
        )
    except SQLAlchemyError as error:
        logger.exception(
            "Database error while loading performance analytics."
        )

        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=(
                "Performance analytics are temporarily unavailable."
            ),
        ) from error
    except ValueError as error:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                str(error)
                or "Invalid analytics request."
            ),
        ) from error
    except HTTPException:
        raise
    except Exception as error:
        logger.exception(
            "Unexpected error while loading performance analytics."
        )

        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Performance analytics could not be loaded.",
        ) from error

    if not isinstance(
        result,
        dict,
    ):
        logger.error(
            "Performance analytics service returned an invalid response type.",
            extra={
                "result_type": type(result).__name__,
            },
        )

        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=(
                "Performance analytics returned an invalid response."
            ),
        )

    return result


__all__ = [
    "analytics_home",
    "analytics_test",
    "performance_analytics",
    "router",
]