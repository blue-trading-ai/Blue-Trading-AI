from __future__ import annotations

import logging
from typing import Any, Literal

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.services.ai_confluence_service import (
    evaluate_ai_confluence,
)


logger = logging.getLogger(__name__)

Decision = Literal["BUY", "SELL", "WAIT"]


router = APIRouter(
    prefix="/ai-confluence",
    tags=["AI Confluence Engine"],
)


class AIConfluenceRequest(BaseModel):
    """Validated input for the AI confluence engine."""

    model_config = ConfigDict(
        extra="forbid",
        str_strip_whitespace=True,
    )

    decision: Decision
    decision_confidence: float = Field(
        ge=0.0,
        le=100.0,
    )
    decision_confirmations: int = Field(
        ge=0,
        le=100,
    )

    context_decision: Decision
    context_approved: bool
    context_supports_trade: bool
    context_risk_environment: str = Field(
        min_length=1,
        max_length=50,
    )
    context_signal_quality: str = Field(
        min_length=1,
        max_length=50,
    )

    institutional_decision: Decision
    institutional_approved: bool
    institutional_score: float = Field(
        ge=0.0,
        le=100.0,
    )
    institutional_confirmations: int = Field(
        ge=0,
        le=100,
    )

    market_structure_direction: Decision = "WAIT"
    market_structure_confirmed: bool = False
    bos_detected: bool = False
    choch_detected: bool = False

    multi_timeframe_direction: Decision = "WAIT"
    multi_timeframe_alignment: bool = False

    trend_direction: Decision = "WAIT"
    trend_strength_score: float = Field(
        default=0.0,
        ge=0.0,
        le=100.0,
    )

    support_resistance_confirmed: bool = False

    candlestick_direction: Decision = "WAIT"
    candlestick_confirmed: bool = False

    breakout_confirmed: bool = False

    risk_reward_ratio: float = Field(
        default=0.0,
        ge=0.0,
        le=100.0,
    )
    stop_loss_valid: bool = False
    take_profit_valid: bool = False

    @field_validator(
        "decision",
        "context_decision",
        "institutional_decision",
        "market_structure_direction",
        "multi_timeframe_direction",
        "trend_direction",
        "candlestick_direction",
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
        "context_risk_environment",
        "context_signal_quality",
        mode="after",
    )
    @classmethod
    def normalize_label(
        cls,
        value: str,
    ) -> str:
        return value.upper()


@router.get("/")
def ai_confluence_home() -> dict[str, Any]:
    return {
        "status": "success",
        "message": (
            "Blue-Trading-AI AI Confluence API "
            "is working"
        ),
        "project": "Blue-Trading-AI",
        "module": "AI Confluence Engine",
        "safety_version": 16,
        "broker_connection_enabled": False,
        "trade_execution_enabled": False,
    }


@router.get("/test")
def ai_confluence_test() -> dict[str, Any]:
    return {
        "status": "success",
        "project": "Blue-Trading-AI",
        "module": "AI Confluence Engine",
        "safety_version": 16,
        "features": [
            "decision_intelligence_integration",
            "market_context_integration",
            "institutional_smc_integration",
            "market_structure_alignment",
            "bos_confirmation",
            "choch_confirmation",
            "multi_timeframe_alignment",
            "trend_confirmation",
            "support_resistance_confirmation",
            "candlestick_confirmation",
            "breakout_confirmation",
            "risk_management_validation",
            "final_confluence_score",
            "final_trade_grade",
            "automatic_wait_decision",
            "no_broker_connection",
            "no_trade_execution",
        ],
        "minimum_final_confidence": 80.0,
        "minimum_total_confirmations": 3,
        "minimum_confluence_score": 75.0,
        "minimum_institutional_score": 70.0,
        "minimum_risk_reward_ratio": 1.5,
        "supported_decisions": [
            "BUY",
            "SELL",
            "WAIT",
        ],
    }


@router.post("/evaluate")
def evaluate_confluence(
    request: AIConfluenceRequest,
) -> dict[str, Any]:
    try:
        result = evaluate_ai_confluence(
            **request.model_dump()
        )
    except ValueError as error:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(error) or "Invalid confluence input.",
        ) from error
    except HTTPException:
        raise
    except Exception as error:
        logger.exception(
            "AI confluence evaluation failed."
        )

        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="AI confluence evaluation failed.",
        ) from error

    if not isinstance(
        result,
        dict,
    ):
        logger.error(
            "AI confluence service returned an invalid response type.",
            extra={
                "result_type": type(result).__name__,
            },
        )

        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="AI confluence evaluation returned an invalid response.",
        )

    return result


__all__ = [
    "AIConfluenceRequest",
    "evaluate_confluence",
    "router",
]