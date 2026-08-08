"""
Blue-Trading-AI
Version 29
app/api/learning_analytics.py

FastAPI endpoints for Learning Analytics and Confidence Calibration.

Analysis only:
- No broker connection
- No automatic order placement
- No trade execution
"""

from __future__ import annotations

import logging
from typing import Any

from fastapi import APIRouter, HTTPException, status

from app.services.learning_analytics_service import (
    get_confidence_calibration,
    get_direction_performance,
    get_learning_analytics_summary,
    get_learning_health,
    get_market_condition_performance,
    get_risk_reward_performance,
    get_session_performance,
    get_streak_analysis,
    get_symbol_performance,
)


logger = logging.getLogger(__name__)


router = APIRouter(
    prefix="/learning-analytics",
    tags=["Learning Analytics V29"],
)


def _call_service(
    operation: str,
    service_call: Any,
) -> Any:
    """Call one analytics service function with safe API error handling."""

    try:
        result = service_call()
    except ValueError as error:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                str(error)
                or "Invalid learning-analytics request."
            ),
        ) from error
    except HTTPException:
        raise
    except Exception as error:
        logger.exception(
            "Learning analytics operation failed.",
            extra={
                "operation": operation,
            },
        )

        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Learning analytics operation failed.",
        ) from error

    if not isinstance(
        result,
        (
            dict,
            list,
        ),
    ):
        logger.error(
            "Learning analytics service returned an invalid response type.",
            extra={
                "operation": operation,
                "result_type": type(result).__name__,
            },
        )

        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=(
                "Learning analytics returned an invalid response."
            ),
        )

    return result


@router.get("/")
def learning_analytics_home() -> dict[str, Any]:
    """Return Version 29 analytics-engine information."""

    return {
        "status": "success",
        "project": "Blue-Trading-AI",
        "version": "29.0.0",
        "safety_version": 29,
        "module": (
            "Learning Analytics and Confidence Calibration"
        ),
        "features": [
            "symbol_performance_analytics",
            "asian_session_performance",
            "european_session_performance",
            "us_session_performance",
            "market_condition_performance",
            "buy_sell_performance",
            "confidence_band_calibration",
            "risk_reward_performance",
            "win_loss_streak_analysis",
            "learning_health_score",
            "learning_recommendations",
        ],
        "minimum_completed_trades": 20,
        "maximum_confidence_adjustment": 4,
        "timeframe_performance_enabled": False,
        "strategy_optimization_enabled": False,
        "strategy_ranking_enabled": False,
        "analysis_only": True,
        "broker_connection_enabled": False,
        "trade_execution_enabled": False,
    }


@router.get("/health")
def learning_analytics_health() -> dict[str, Any]:
    """Return a lightweight Version 29 health response."""

    return {
        "status": "healthy",
        "project": "Blue-Trading-AI",
        "version": 29,
        "service": "learning_analytics",
        "analytics_ready": True,
        "analysis_only": True,
    }


@router.get("/summary")
def learning_analytics_summary() -> dict[str, Any]:
    """Return the full Version 29 learning analytics summary."""

    result = _call_service(
        "summary",
        get_learning_analytics_summary,
    )

    if not isinstance(
        result,
        dict,
    ):
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=(
                "Learning analytics summary returned an invalid response."
            ),
        )

    return result


@router.get("/symbols")
def symbol_performance() -> dict[str, Any]:
    """Return performance grouped by symbol."""

    return {
        "status": "success",
        "version": 29,
        "data": _call_service(
            "symbols",
            get_symbol_performance,
        ),
    }


@router.get("/sessions")
def session_performance() -> dict[str, Any]:
    """Return Asian, European, and US session performance."""

    return {
        "status": "success",
        "version": 29,
        "data": _call_service(
            "sessions",
            get_session_performance,
        ),
    }


@router.get("/market-conditions")
def market_condition_performance() -> dict[str, Any]:
    """Return performance grouped by market condition."""

    return {
        "status": "success",
        "version": 29,
        "data": _call_service(
            "market-conditions",
            get_market_condition_performance,
        ),
    }


@router.get("/directions")
def direction_performance() -> dict[str, Any]:
    """Return BUY and SELL performance."""

    return {
        "status": "success",
        "version": 29,
        "data": _call_service(
            "directions",
            get_direction_performance,
        ),
    }


@router.get("/confidence-calibration")
def confidence_calibration() -> dict[str, Any]:
    """Return confidence-band calibration statistics."""

    return {
        "status": "success",
        "version": 29,
        "data": _call_service(
            "confidence-calibration",
            get_confidence_calibration,
        ),
    }


@router.get("/risk-reward")
def risk_reward_performance() -> dict[str, Any]:
    """Return Risk:Reward performance bands."""

    return {
        "status": "success",
        "version": 29,
        "data": _call_service(
            "risk-reward",
            get_risk_reward_performance,
        ),
    }


@router.get("/streaks")
def streak_analysis() -> dict[str, Any]:
    """Return current and historical win/loss streaks."""

    return {
        "status": "success",
        "version": 29,
        "data": _call_service(
            "streaks",
            get_streak_analysis,
        ),
    }


@router.get("/health-score")
def learning_health_score() -> dict[str, Any]:
    """Return the Version 29 learning health score and grade."""

    return {
        "status": "success",
        "version": 29,
        "data": _call_service(
            "health-score",
            get_learning_health,
        ),
    }


__all__ = [
    "confidence_calibration",
    "direction_performance",
    "learning_analytics_health",
    "learning_analytics_home",
    "learning_analytics_summary",
    "learning_health_score",
    "market_condition_performance",
    "risk_reward_performance",
    "router",
    "session_performance",
    "streak_analysis",
    "symbol_performance",
]