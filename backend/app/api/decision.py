from __future__ import annotations

import logging
from typing import Any, Final

from fastapi import APIRouter, Body, HTTPException, Query, status

from app.services.decision_intelligence_service import (
    evaluate_trade_decision,
)


logger = logging.getLogger(__name__)

SUPPORTED_REQUESTED_DIRECTIONS: Final[frozenset[str]] = frozenset(
    {
        "BUY",
        "SELL",
        "BULLISH",
        "BEARISH",
    }
)

MAXIMUM_FACTOR_COUNT: Final = 100


router = APIRouter(
    prefix="/decision",
    tags=["Decision Intelligence"],
)


@router.get("/")
def decision_home() -> dict[str, Any]:
    """
    Confirm that the Blue-Trading-AI
    Decision Intelligence API is available.
    """

    return {
        "status": "success",
        "message": (
            "Blue-Trading-AI Decision Intelligence "
            "API is working"
        ),
        "safety_version": 12,
    }


@router.get("/test")
def decision_test() -> dict[str, Any]:
    """
    Display the available Version 12 features.
    """

    return {
        "status": "success",
        "module": "decision_intelligence_engine",
        "project": "Blue-Trading-AI",
        "features": [
            "weighted_factor_scoring",
            "bullish_and_bearish_comparison",
            "market_structure_scoring",
            "bos_scoring",
            "choch_scoring",
            "trend_scoring",
            "support_resistance_scoring",
            "order_block_scoring",
            "fair_value_gap_scoring",
            "liquidity_scoring",
            "candlestick_scoring",
            "chart_pattern_scoring",
            "breakout_scoring",
            "multi_timeframe_scoring",
            "minimum_80_confidence",
            "minimum_3_confirmations",
            "conflicting_evidence_penalty",
            "trade_quality_grading",
            "decision_explanation",
            "no_broker_execution",
        ],
        "safety_version": 12,
    }


@router.post("/evaluate")
def evaluate_decision(
    requested_direction: str = Query(
        ...,
        min_length=3,
        max_length=10,
        description=(
            "Requested trade direction: "
            "BUY, SELL, BULLISH, or BEARISH."
        ),
    ),
    factors: dict[str, Any] = Body(
        ...,
        description=(
            "Technical-analysis factor directions."
        ),
    ),
) -> dict[str, Any]:
    """
    Evaluate technical-analysis factors and return
    a transparent BUY, SELL, or WAIT decision.

    Example factor values:
    BULLISH, BEARISH, BUY, SELL, or NEUTRAL.
    """

    normalized_direction = (
        requested_direction
        .strip()
        .upper()
    )

    if (
        normalized_direction
        not in SUPPORTED_REQUESTED_DIRECTIONS
    ):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=(
                "Requested direction must be BUY, SELL, "
                "BULLISH, or BEARISH."
            ),
        )

    if len(factors) > MAXIMUM_FACTOR_COUNT:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=(
                "Too many analysis factors were provided."
            ),
        )

    try:
        result = evaluate_trade_decision(
            requested_direction=normalized_direction,
            factors=factors,
        )
    except ValueError as error:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                str(error)
                or "Invalid decision-intelligence input."
            ),
        ) from error
    except HTTPException:
        raise
    except Exception as error:
        logger.exception(
            "Decision Intelligence evaluation failed."
        )

        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=(
                "Decision Intelligence evaluation failed."
            ),
        ) from error

    if not isinstance(
        result,
        dict,
    ):
        logger.error(
            "Decision Intelligence service returned an invalid response type.",
            extra={
                "result_type": type(result).__name__,
            },
        )

        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=(
                "Decision Intelligence returned an invalid response."
            ),
        )

    return result


__all__ = [
    "MAXIMUM_FACTOR_COUNT",
    "SUPPORTED_REQUESTED_DIRECTIONS",
    "decision_home",
    "decision_test",
    "evaluate_decision",
    "router",
]