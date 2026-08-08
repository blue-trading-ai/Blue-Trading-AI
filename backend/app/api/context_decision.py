from __future__ import annotations

import logging
from typing import Any, Literal

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.services.context_aware_decision_service import (
    evaluate_context_aware_decision,
)


logger = logging.getLogger(__name__)

Decision = Literal[
    "BUY",
    "SELL",
    "WAIT",
]


router = APIRouter(
    prefix="/context-decision",
    tags=["Context-Aware Decision Intelligence"],
)


class DecisionResultInput(BaseModel):
    """Validated Decision Intelligence result."""

    model_config = ConfigDict(
        extra="forbid",
        str_strip_whitespace=True,
    )

    decision: Decision = Field(
        ...,
        description="Original decision: BUY, SELL, or WAIT.",
        examples=["BUY"],
    )

    confidence: float = Field(
        ...,
        ge=0.0,
        le=100.0,
        description="Decision confidence from 0 to 100.",
        examples=[90.0],
    )

    confirmations_count: int = Field(
        ...,
        ge=0,
        le=100,
        description="Number of supporting confirmations.",
        examples=[6],
    )

    grade: str | None = Field(
        default=None,
        min_length=1,
        max_length=10,
        description="Optional Decision Intelligence grade.",
        examples=["A"],
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
        "grade",
        mode="after",
    )
    @classmethod
    def normalize_grade(
        cls,
        value: str | None,
    ) -> str | None:
        if value is None:
            return None

        return value.upper()


class ContextAwareDecisionRequest(BaseModel):
    """Validated context-aware decision request."""

    model_config = ConfigDict(
        extra="forbid",
    )

    decision_result: DecisionResultInput

    trend_score: float = Field(
        ...,
        ge=0.0,
        le=100.0,
        description="Current market trend score.",
        examples=[85.0],
    )

    volatility_score: float = Field(
        ...,
        ge=0.0,
        le=100.0,
        description="Current market volatility score.",
        examples=[35.0],
    )

    conflicting_factors_count: int = Field(
        default=0,
        ge=0,
        le=100,
        description="Number of conflicting analysis factors.",
        examples=[1],
    )


@router.get("/")
def context_decision_home() -> dict[str, Any]:
    """
    Confirm that the Version 14 API is available.
    """

    return {
        "status": "success",
        "message": (
            "Blue-Trading-AI Context-Aware "
            "Decision API is working"
        ),
        "project": "Blue-Trading-AI",
        "safety_version": 14,
        "broker_connection_enabled": False,
        "trade_execution_enabled": False,
    }


@router.get("/test")
def context_decision_test() -> dict[str, Any]:
    """
    Display the Version 14 integration features.
    """

    return {
        "status": "success",
        "module": "context_aware_decision_intelligence",
        "project": "Blue-Trading-AI",
        "safety_version": 14,
        "features": [
            "decision_intelligence_integration",
            "market_context_integration",
            "minimum_confidence_protection",
            "minimum_confirmation_protection",
            "high_risk_context_protection",
            "weak_signal_quality_protection",
            "unsupported_context_protection",
            "automatic_wait_decision",
            "no_broker_connection",
            "no_trade_execution",
        ],
        "minimum_confidence": 80.0,
        "minimum_confirmations": 3,
        "supported_decisions": [
            "BUY",
            "SELL",
            "WAIT",
        ],
    }


@router.post("/evaluate")
def evaluate_context_decision(
    request: ContextAwareDecisionRequest,
) -> dict[str, Any]:
    """
    Combine a Decision Intelligence result
    with the current market context.

    A BUY or SELL is changed to WAIT when any
    Version 14 safety requirement fails.
    """

    try:
        result = evaluate_context_aware_decision(
            decision_result=(
                request.decision_result.model_dump()
            ),
            trend_score=request.trend_score,
            volatility_score=(
                request.volatility_score
            ),
            conflicting_factors_count=(
                request.conflicting_factors_count
            ),
        )
    except ValueError as error:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                str(error)
                or "Invalid context-aware decision input."
            ),
        ) from error
    except HTTPException:
        raise
    except Exception as error:
        logger.exception(
            "Context-aware decision evaluation failed."
        )

        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=(
                "Context-aware decision evaluation failed."
            ),
        ) from error

    if not isinstance(
        result,
        dict,
    ):
        logger.error(
            "Context-aware decision service returned an invalid response type.",
            extra={
                "result_type": type(result).__name__,
            },
        )

        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=(
                "Context-aware decision returned an invalid response."
            ),
        )

    return result


__all__ = [
    "ContextAwareDecisionRequest",
    "DecisionResultInput",
    "evaluate_context_decision",
    "router",
]