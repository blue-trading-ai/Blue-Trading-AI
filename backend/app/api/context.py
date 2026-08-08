"""Market Context Intelligence API for Blue-Trading-AI."""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Any

from fastapi import APIRouter, HTTPException, Query, status

from app.services.market_context_service import (
    analyze_market_context,
    get_current_session,
)


logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/context",
    tags=["Market Context Intelligence"],
)


@router.get("/")
def context_home() -> dict[str, Any]:
    """
    Confirm that the Blue-Trading-AI
    Market Context API is available.
    """

    return {
        "status": "success",
        "message": (
            "Blue-Trading-AI Market Context "
            "API is working"
        ),
        "safety_version": 13,
    }


@router.get("/test")
def context_test() -> dict[str, Any]:
    """
    Display the available Version 13 features.
    """

    return {
        "status": "success",
        "module": "market_context_intelligence",
        "project": "Blue-Trading-AI",
        "features": [
            "trend_strength_analysis",
            "market_condition_analysis",
            "volatility_analysis",
            "risk_environment_analysis",
            "signal_quality_classification",
            "asian_session_detection",
            "european_session_detection",
            "us_session_detection",
            "session_overlap_detection",
            "malaysia_timezone",
            "high_risk_context_protection",
            "weak_quality_protection",
            "no_broker_execution",
        ],
        "session_names": [
            "ASIAN",
            "EUROPEAN",
            "US",
        ],
        "timezone": "Asia/Kuala_Lumpur",
        "safety_version": 13,
    }


@router.get("/session")
def current_session() -> dict[str, Any]:
    """
    Return the current Blue-Trading-AI market
    session using Malaysia Time.
    """

    try:
        session = get_current_session()
    except ValueError as error:
        logger.warning(
            "Invalid market-session request: %s",
            error,
        )

        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid market-session request.",
        ) from error
    except HTTPException:
        raise
    except Exception as error:
        logger.exception(
            "Unable to determine the current market session."
        )

        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Current market session could not be determined.",
        ) from error

    if not isinstance(
        session,
        (str, dict),
    ):
        logger.error(
            "Market-context service returned an invalid session type.",
            extra={
                "result_type": type(session).__name__,
            },
        )

        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Current market session returned an invalid response.",
        )

    return {
        "status": "success",
        "project": "Blue-Trading-AI",
        "safety_version": 13,
        "session": session,
    }


@router.post("/analyze")
def analyze_context(
    trend_score: float = Query(
        ...,
        ge=0.0,
        le=100.0,
        description="Trend score from 0 to 100.",
    ),
    volatility_score: float = Query(
        ...,
        ge=0.0,
        le=100.0,
        description="Volatility score from 0 to 100.",
    ),
    confidence: float = Query(
        ...,
        ge=0.0,
        le=100.0,
        description="Decision confidence from 0 to 100.",
    ),
    confirmations_count: int = Query(
        ...,
        ge=0,
        le=100,
        description="Number of supporting confirmations.",
    ),
    conflicting_factors_count: int = Query(
        default=0,
        ge=0,
        le=100,
        description="Number of conflicting factors.",
    ),
    current_datetime: datetime | None = Query(
        default=None,
        description=(
            "Optional ISO datetime for testing. "
            "Leave empty to use current Malaysia Time."
        ),
    ),
) -> dict[str, Any]:
    """
    Produce the full Blue-Trading-AI
    market-context analysis.

    All inputs are query parameters to preserve the existing API contract.
    """

    try:
        result = analyze_market_context(
            trend_score=trend_score,
            volatility_score=volatility_score,
            confidence=confidence,
            confirmations_count=confirmations_count,
            conflicting_factors_count=(
                conflicting_factors_count
            ),
            current_datetime=current_datetime,
        )
    except ValueError as error:
        logger.warning(
            "Invalid market-context input: %s",
            error,
        )

        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid market-context input.",
        ) from error
    except HTTPException:
        raise
    except Exception as error:
        logger.exception(
            "Market-context analysis failed."
        )

        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Market-context analysis failed.",
        ) from error

    if not isinstance(
        result,
        dict,
    ):
        logger.error(
            "Market-context service returned an invalid response type.",
            extra={
                "result_type": type(result).__name__,
            },
        )

        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Market-context analysis returned an invalid response.",
        )

    return result


__all__ = [
    "analyze_context",
    "context_home",
    "context_test",
    "current_session",
    "router",
]