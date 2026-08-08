from __future__ import annotations

import logging
from typing import Any, Literal

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.services.dynamic_confidence_service import (
    evaluate_dynamic_confidence,
    rank_trading_signals,
)


logger = logging.getLogger(__name__)

Decision = Literal[
    "BUY",
    "SELL",
    "WAIT",
]

MAXIMUM_SIGNAL_BATCH_SIZE = 100
MAXIMUM_TEXT_LIST_ITEMS = 100
MAXIMUM_TEXT_ITEM_LENGTH = 250


router = APIRouter(
    prefix="/dynamic-confidence",
    tags=["Dynamic Confidence & Signal Ranking"],
)


class DynamicConfidenceRequest(BaseModel):
    """Validated dynamic-confidence input."""

    model_config = ConfigDict(
        extra="forbid",
        str_strip_whitespace=True,
    )

    signal_id: str = Field(
        default="",
        max_length=128,
        description="Unique signal identifier.",
    )

    symbol: str = Field(
        default="UNKNOWN",
        min_length=1,
        max_length=32,
        description="Trading symbol such as XAUUSD.",
    )

    timeframe: str = Field(
        default="M15",
        min_length=1,
        max_length=16,
        description="Signal timeframe.",
    )

    decision: Decision = Field(
        default="WAIT",
        description="BUY, SELL or WAIT.",
    )

    base_confidence: float = Field(
        default=0.0,
        ge=0.0,
        le=100.0,
    )

    confirmations: int = Field(
        default=0,
        ge=0,
        le=100,
    )

    ai_confluence_score: float = Field(
        default=0.0,
        ge=0.0,
        le=100.0,
    )

    multi_timeframe_score: float = Field(
        default=0.0,
        ge=0.0,
        le=100.0,
    )

    institutional_score: float = Field(
        default=0.0,
        ge=0.0,
        le=100.0,
    )

    context_score: float = Field(
        default=0.0,
        ge=0.0,
        le=100.0,
    )

    market_structure_score: float = Field(
        default=0.0,
        ge=0.0,
        le=100.0,
    )

    trend_score: float = Field(
        default=0.0,
        ge=0.0,
        le=100.0,
    )

    momentum_score: float = Field(
        default=0.0,
        ge=0.0,
        le=100.0,
    )

    risk_reward_ratio: float = Field(
        default=0.0,
        ge=0.0,
        le=100.0,
    )

    context_approved: bool = False
    institutional_approved: bool = False
    multi_timeframe_approved: bool = False
    risk_management_approved: bool = False
    direction_alignment: bool = False

    hierarchy_conflict: bool = False
    high_risk_environment: bool = False
    weak_signal_quality: bool = False

    blocking_reasons: list[str] = Field(
        default_factory=list,
        max_length=MAXIMUM_TEXT_LIST_ITEMS,
    )

    warnings: list[str] = Field(
        default_factory=list,
        max_length=MAXIMUM_TEXT_LIST_ITEMS,
    )

    @field_validator(
        "decision",
        mode="before",
    )
    @classmethod
    def normalize_decision(
        cls,
        value: Any,
    ) -> Any:
        if isinstance(
            value,
            str,
        ):
            return value.strip().upper()

        return value

    @field_validator(
        "symbol",
        "timeframe",
        mode="after",
    )
    @classmethod
    def normalize_market_label(
        cls,
        value: str,
    ) -> str:
        return value.upper()

    @field_validator(
        "blocking_reasons",
        "warnings",
        mode="after",
    )
    @classmethod
    def validate_text_items(
        cls,
        values: list[str],
    ) -> list[str]:
        normalized: list[str] = []

        for item in values:
            value = str(
                item
            ).strip()

            if not value:
                continue

            if len(
                value
            ) > MAXIMUM_TEXT_ITEM_LENGTH:
                value = value[
                    :MAXIMUM_TEXT_ITEM_LENGTH
                ]

            normalized.append(
                value
            )

        return normalized


class SignalRankingRequest(BaseModel):
    """Validated multi-signal ranking request."""

    model_config = ConfigDict(
        extra="forbid",
    )

    signals: list[DynamicConfidenceRequest] = Field(
        ...,
        min_length=1,
        max_length=MAXIMUM_SIGNAL_BATCH_SIZE,
    )

    maximum_results: int = Field(
        default=10,
        ge=1,
        le=100,
    )


@router.get("/")
def dynamic_confidence_home() -> dict[str, Any]:
    """
    Dynamic Confidence and Signal Ranking API information.
    """

    return {
        "status": "success",
        "message": (
            "Blue-Trading-AI Dynamic Confidence "
            "and Signal Ranking API is working"
        ),
        "project": "Blue-Trading-AI",
        "module": (
            "Dynamic Confidence & Signal Ranking Engine"
        ),
        "safety_version": 18,
        "broker_connection_enabled": False,
        "trade_execution_enabled": False,
    }


@router.get("/test")
def dynamic_confidence_test() -> dict[str, Any]:
    """
    Return Version 18 feature information.
    """

    return {
        "status": "success",
        "project": "Blue-Trading-AI",
        "module": (
            "Dynamic Confidence & Signal Ranking Engine"
        ),
        "safety_version": 18,
        "features": [
            "dynamic_confidence_calculation",
            "confidence_inflation_prevention",
            "maximum_confidence_cap",
            "maximum_positive_adjustment_cap",
            "ai_confluence_weighting",
            "multi_timeframe_weighting",
            "institutional_score_weighting",
            "market_context_weighting",
            "market_structure_weighting",
            "trend_weighting",
            "momentum_weighting",
            "risk_reward_weighting",
            "confirmation_weighting",
            "conflict_penalties",
            "risk_environment_penalties",
            "weak_quality_penalties",
            "signal_grading",
            "signal_strength_classification",
            "multiple_signal_ranking",
            "approved_signals_rank_first",
            "automatic_wait_decision",
            "no_broker_connection",
            "no_trade_execution",
        ],
        "minimum_approval_confidence": 80.0,
        "minimum_ranking_score": 75.0,
        "minimum_confirmations": 3,
        "minimum_risk_reward_ratio": 1.5,
        "maximum_dynamic_confidence": 98.0,
        "maximum_confidence_increase": 8.0,
        "supported_decisions": [
            "BUY",
            "SELL",
            "WAIT",
        ],
    }


@router.post("/evaluate")
def evaluate_signal_confidence(
    request: DynamicConfidenceRequest,
) -> dict[str, Any]:
    """
    Evaluate one signal and recalculate
    its dynamic confidence and ranking score.
    """

    try:
        result = evaluate_dynamic_confidence(
            signal_id=request.signal_id,
            symbol=request.symbol,
            timeframe=request.timeframe,
            decision=request.decision,
            base_confidence=request.base_confidence,
            confirmations=request.confirmations,
            ai_confluence_score=(
                request.ai_confluence_score
            ),
            multi_timeframe_score=(
                request.multi_timeframe_score
            ),
            institutional_score=(
                request.institutional_score
            ),
            context_score=request.context_score,
            market_structure_score=(
                request.market_structure_score
            ),
            trend_score=request.trend_score,
            momentum_score=request.momentum_score,
            risk_reward_ratio=(
                request.risk_reward_ratio
            ),
            context_approved=(
                request.context_approved
            ),
            institutional_approved=(
                request.institutional_approved
            ),
            multi_timeframe_approved=(
                request.multi_timeframe_approved
            ),
            risk_management_approved=(
                request.risk_management_approved
            ),
            direction_alignment=(
                request.direction_alignment
            ),
            hierarchy_conflict=(
                request.hierarchy_conflict
            ),
            high_risk_environment=(
                request.high_risk_environment
            ),
            weak_signal_quality=(
                request.weak_signal_quality
            ),
            blocking_reasons=(
                request.blocking_reasons
            ),
            warnings=request.warnings,
        )
    except ValueError as error:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                str(error)
                or "Invalid dynamic-confidence input."
            ),
        ) from error
    except HTTPException:
        raise
    except Exception as error:
        logger.exception(
            "Dynamic-confidence evaluation failed."
        )

        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Dynamic-confidence evaluation failed.",
        ) from error

    if not isinstance(
        result,
        dict,
    ):
        logger.error(
            "Dynamic-confidence service returned an invalid response type.",
            extra={
                "result_type": type(result).__name__,
            },
        )

        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=(
                "Dynamic-confidence evaluation returned "
                "an invalid response."
            ),
        )

    return result


@router.post("/rank")
def rank_signals(
    request: SignalRankingRequest,
) -> dict[str, Any]:
    """
    Evaluate and rank multiple signals.
    """

    converted_signals = [
        signal.model_dump()
        for signal in request.signals
    ]

    try:
        result = rank_trading_signals(
            signals=converted_signals,
            maximum_results=(
                request.maximum_results
            ),
        )
    except ValueError as error:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                str(error)
                or "Invalid signal-ranking input."
            ),
        ) from error
    except HTTPException:
        raise
    except Exception as error:
        logger.exception(
            "Dynamic signal ranking failed."
        )

        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Dynamic signal ranking failed.",
        ) from error

    if not isinstance(
        result,
        dict,
    ):
        logger.error(
            "Signal-ranking service returned an invalid response type.",
            extra={
                "result_type": type(result).__name__,
            },
        )

        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Signal ranking returned an invalid response.",
        )

    return result


__all__ = [
    "DynamicConfidenceRequest",
    "SignalRankingRequest",
    "dynamic_confidence_home",
    "dynamic_confidence_test",
    "evaluate_signal_confidence",
    "rank_signals",
    "router",
]