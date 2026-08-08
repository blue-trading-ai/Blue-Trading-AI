from __future__ import annotations

import logging
from typing import Any, Literal

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    field_validator,
)

from app.core.dependencies import require_approved_user
from app.services.multi_timeframe_intelligence_service import (
    evaluate_multi_timeframe_intelligence,
)


logger = logging.getLogger(__name__)

SUPPORTED_TIMEFRAMES = (
    "MN",
    "W1",
    "D1",
    "H4",
    "H1",
    "M30",
    "M15",
    "M5",
)
MAXIMUM_TIMEFRAME_ENTRIES = len(
    SUPPORTED_TIMEFRAMES
)


router = APIRouter(
    prefix="/multi-timeframe",
    tags=["Multi-Timeframe Intelligence"],
)


class TimeframeAnalysisInput(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
        str_strip_whitespace=True,
    )

    direction: str = Field(
        default="WAIT",
        min_length=1,
        max_length=16,
        description="BUY, SELL, BULLISH, BEARISH, UP, DOWN or WAIT",
    )

    trend_strength: float = Field(
        default=0.0,
        ge=0.0,
        le=100.0,
    )

    momentum_score: float = Field(
        default=0.0,
        ge=0.0,
        le=100.0,
    )

    bos_detected: bool = False
    choch_detected: bool = False

    institutional_bias: str = Field(
        default="WAIT",
        min_length=1,
        max_length=16,
        description="BUY, SELL, UP, DOWN or WAIT",
    )

    premium_discount_zone: str = Field(
        default="EQUILIBRIUM",
        min_length=1,
        max_length=16,
        description="PREMIUM, DISCOUNT or EQUILIBRIUM",
    )

    @field_validator(
        "direction",
    )
    @classmethod
    def normalize_direction(
        cls,
        value: str,
    ) -> str:
        normalized = value.strip().upper()

        aliases = {
            "BULLISH": "BUY",
            "LONG": "BUY",
            "UP": "BUY",
            "BEARISH": "SELL",
            "SHORT": "SELL",
            "DOWN": "SELL",
            "NEUTRAL": "WAIT",
            "NO_TRADE": "WAIT",
        }

        normalized = aliases.get(
            normalized,
            normalized,
        )

        if normalized not in {
            "BUY",
            "SELL",
            "WAIT",
        }:
            raise ValueError(
                "direction must resolve to BUY, SELL or WAIT"
            )

        return normalized

    @field_validator(
        "institutional_bias",
    )
    @classmethod
    def normalize_institutional_bias(
        cls,
        value: str,
    ) -> str:
        normalized = value.strip().upper()

        aliases = {
            "BULLISH": "BUY",
            "LONG": "BUY",
            "UP": "BUY",
            "BEARISH": "SELL",
            "SHORT": "SELL",
            "DOWN": "SELL",
            "NEUTRAL": "WAIT",
            "NO_TRADE": "WAIT",
        }

        normalized = aliases.get(
            normalized,
            normalized,
        )

        if normalized not in {
            "BUY",
            "SELL",
            "WAIT",
        }:
            raise ValueError(
                "institutional_bias must resolve to BUY, SELL or WAIT"
            )

        return normalized

    @field_validator(
        "premium_discount_zone",
    )
    @classmethod
    def normalize_zone(
        cls,
        value: str,
    ) -> str:
        normalized = value.strip().upper()

        if normalized not in {
            "PREMIUM",
            "DISCOUNT",
            "EQUILIBRIUM",
        }:
            raise ValueError(
                "premium_discount_zone must be PREMIUM, DISCOUNT or EQUILIBRIUM"
            )

        return normalized


class MultiTimeframeRequest(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
        str_strip_whitespace=True,
    )

    requested_direction: str = Field(
        default="WAIT",
        min_length=1,
        max_length=16,
        description="Requested BUY or SELL signal direction",
    )

    execution_timeframe: str = Field(
        default="M15",
        min_length=1,
        max_length=8,
        description="Execution timeframe such as M15, M30 or H1",
    )

    timeframe_data: dict[
        str,
        TimeframeAnalysisInput,
    ] = Field(
        ...,
        min_length=1,
        max_length=MAXIMUM_TIMEFRAME_ENTRIES,
    )

    @field_validator(
        "requested_direction",
    )
    @classmethod
    def normalize_requested_direction(
        cls,
        value: str,
    ) -> str:
        normalized = value.strip().upper()

        aliases = {
            "BULLISH": "BUY",
            "LONG": "BUY",
            "UP": "BUY",
            "BEARISH": "SELL",
            "SHORT": "SELL",
            "DOWN": "SELL",
            "NEUTRAL": "WAIT",
            "NO_TRADE": "WAIT",
        }

        normalized = aliases.get(
            normalized,
            normalized,
        )

        if normalized not in {
            "BUY",
            "SELL",
            "WAIT",
        }:
            raise ValueError(
                "requested_direction must resolve to BUY, SELL or WAIT"
            )

        return normalized

    @field_validator(
        "execution_timeframe",
    )
    @classmethod
    def normalize_execution_timeframe(
        cls,
        value: str,
    ) -> str:
        normalized = value.strip().upper()

        if normalized not in SUPPORTED_TIMEFRAMES:
            raise ValueError(
                "Unsupported execution_timeframe"
            )

        return normalized

    @field_validator(
        "timeframe_data",
    )
    @classmethod
    def normalize_timeframe_data(
        cls,
        value: dict[
            str,
            TimeframeAnalysisInput,
        ],
    ) -> dict[
        str,
        TimeframeAnalysisInput,
    ]:
        normalized: dict[
            str,
            TimeframeAnalysisInput,
        ] = {}

        for key, payload in value.items():
            timeframe = str(
                key
            ).strip().upper()

            if timeframe not in SUPPORTED_TIMEFRAMES:
                raise ValueError(
                    f"Unsupported timeframe key: {key}"
                )

            if timeframe in normalized:
                raise ValueError(
                    f"Duplicate timeframe key after normalization: {timeframe}"
                )

            normalized[
                timeframe
            ] = payload

        return normalized


@router.get("/")
def multi_timeframe_home() -> dict[str, Any]:
    """Multi-Timeframe Intelligence API information."""

    return {
        "status": "success",
        "message": (
            "Blue-Trading-AI Multi-Timeframe "
            "Intelligence API is working"
        ),
        "project": "Blue-Trading-AI",
        "module": (
            "Multi-Timeframe Intelligence Engine"
        ),
        "safety_version": 17,
        "broker_connection_enabled": False,
        "trade_execution_enabled": False,
    }


@router.get("/test")
def multi_timeframe_test() -> dict[str, Any]:
    """Returns Version 17 feature information."""

    return {
        "status": "success",
        "project": "Blue-Trading-AI",
        "module": (
            "Multi-Timeframe Intelligence Engine"
        ),
        "safety_version": 17,
        "features": [
            "monthly_timeframe_analysis",
            "weekly_timeframe_analysis",
            "daily_timeframe_analysis",
            "h4_timeframe_analysis",
            "h1_timeframe_analysis",
            "m30_timeframe_analysis",
            "m15_timeframe_analysis",
            "m5_timeframe_analysis",
            "trend_strength_scoring",
            "momentum_scoring",
            "bos_confirmation",
            "choch_confirmation",
            "institutional_bias_alignment",
            "premium_discount_validation",
            "higher_timeframe_bias",
            "lower_timeframe_bias",
            "hierarchy_conflict_detection",
            "execution_timeframe_confirmation",
            "weighted_alignment_score",
            "automatic_wait_decision",
            "no_broker_connection",
            "no_trade_execution",
        ],
        "supported_timeframes": list(
            SUPPORTED_TIMEFRAMES
        ),
        "minimum_alignment_score": 75.0,
        "minimum_higher_timeframe_score": 70.0,
        "minimum_aligned_timeframes": 3,
        "supported_decisions": [
            "BUY",
            "SELL",
            "WAIT",
        ],
    }


@router.post("/analyze")
def analyze_multi_timeframe(
    request: MultiTimeframeRequest,
    _current_user: Any = Depends(
        require_approved_user
    ),
) -> dict[str, Any]:
    """
    Runs the Version 17 multi-timeframe
    intelligence evaluation.
    """

    converted_timeframe_data = {
        timeframe: data.model_dump()
        for timeframe, data
        in request.timeframe_data.items()
    }

    try:
        result = evaluate_multi_timeframe_intelligence(
            timeframe_data=converted_timeframe_data,
            requested_direction=(
                request.requested_direction
            ),
            execution_timeframe=(
                request.execution_timeframe
            ),
        )
    except ValueError as error:
        logger.warning(
            "Invalid Multi-Timeframe Intelligence request: %s",
            error,
        )

        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid Multi-Timeframe Intelligence request.",
        ) from error
    except HTTPException:
        raise
    except Exception as error:
        logger.exception(
            "Multi-Timeframe Intelligence evaluation failed.",
            extra={
                "requested_direction": request.requested_direction,
                "execution_timeframe": request.execution_timeframe,
            },
        )

        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Multi-Timeframe Intelligence evaluation failed.",
        ) from error

    if not isinstance(
        result,
        dict,
    ):
        logger.error(
            "Multi-Timeframe Intelligence service returned invalid response type.",
            extra={
                "result_type": type(result).__name__,
            },
        )

        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Multi-Timeframe Intelligence returned an invalid response.",
        )

    return result


__all__ = [
    "MultiTimeframeRequest",
    "SUPPORTED_TIMEFRAMES",
    "TimeframeAnalysisInput",
    "analyze_multi_timeframe",
    "multi_timeframe_home",
    "multi_timeframe_test",
    "router",
]