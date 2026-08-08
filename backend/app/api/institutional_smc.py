from __future__ import annotations

import logging
from typing import Any, Literal

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.services.institutional_smc_service import (
    evaluate_institutional_smc,
)


logger = logging.getLogger(__name__)

Direction = Literal[
    "BULLISH",
    "BEARISH",
    "BUY",
    "SELL",
    "NEUTRAL",
]


router = APIRouter(
    prefix="/institutional-smc",
    tags=["Institutional Smart Money"],
)


class InstitutionalSMCRequest(BaseModel):
    """Validated institutional Smart Money input."""

    model_config = ConfigDict(
        extra="forbid",
        str_strip_whitespace=True,
    )

    market_direction: Direction
    current_price: float = Field(
        ...,
        gt=0.0,
    )
    range_high: float = Field(
        ...,
        gt=0.0,
    )
    range_low: float = Field(
        ...,
        gt=0.0,
    )

    fvg_detected: bool = False
    fvg_direction: Direction = "NEUTRAL"
    fvg_gap_size_percent: float = Field(
        default=0.0,
        ge=0.0,
        le=100.0,
    )
    fvg_mitigated: bool = False

    order_block_detected: bool = False
    order_block_direction: Direction = "NEUTRAL"
    order_block_displacement_score: float = Field(
        default=0.0,
        ge=0.0,
        le=100.0,
    )
    order_block_freshness_score: float = Field(
        default=0.0,
        ge=0.0,
        le=100.0,
    )
    order_block_respected: bool = False

    liquidity_sweep_detected: bool = False
    liquidity_sweep_direction: Direction = "NEUTRAL"

    equal_high_detected: bool = False
    equal_low_detected: bool = False

    inducement_detected: bool = False
    mitigation_block_detected: bool = False
    breaker_block_detected: bool = False

    structure_alignment: bool = False

    @field_validator(
        "market_direction",
        "fvg_direction",
        "order_block_direction",
        "liquidity_sweep_direction",
        mode="before",
    )
    @classmethod
    def normalize_direction(
        cls,
        value: Any,
    ) -> Any:
        if isinstance(
            value,
            str,
        ):
            return value.strip().upper()

        return value

    @model_validator(
        mode="after",
    )
    def validate_range(
        self,
    ) -> "InstitutionalSMCRequest":
        if self.range_high <= self.range_low:
            raise ValueError(
                "range_high must be greater than range_low."
            )

        if not (
            self.range_low
            <= self.current_price
            <= self.range_high
        ):
            raise ValueError(
                "current_price must be inside the supplied range."
            )

        return self


@router.get("/")
def home() -> dict[str, Any]:
    return {
        "status": "success",
        "project": "Blue-Trading-AI",
        "module": "Institutional Smart Money Engine",
        "safety_version": 15,
        "broker_connection_enabled": False,
        "trade_execution_enabled": False,
    }


@router.get("/test")
def test() -> dict[str, Any]:
    return {
        "status": "success",
        "project": "Blue-Trading-AI",
        "module": "Institutional Smart Money Engine",
        "safety_version": 15,
        "features": [
            "Premium Discount Analysis",
            "Fair Value Gap",
            "Order Block Strength",
            "Liquidity Sweep",
            "Equal High Low",
            "Inducement",
            "Mitigation Block",
            "Breaker Block",
            "Institutional Score",
            "Institutional Grade",
        ],
    }


@router.post("/analyze")
def analyze(
    request: InstitutionalSMCRequest,
) -> dict[str, Any]:
    try:
        result = evaluate_institutional_smc(
            **request.model_dump()
        )
    except ValueError as error:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                str(error)
                or "Invalid Institutional SMC input."
            ),
        ) from error
    except HTTPException:
        raise
    except Exception as error:
        logger.exception(
            "Institutional SMC evaluation failed."
        )

        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Institutional SMC evaluation failed.",
        ) from error

    if not isinstance(
        result,
        dict,
    ):
        logger.error(
            "Institutional SMC service returned an invalid response type.",
            extra={
                "result_type": type(result).__name__,
            },
        )

        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=(
                "Institutional SMC returned an invalid response."
            ),
        )

    return result


__all__ = [
    "InstitutionalSMCRequest",
    "analyze",
    "home",
    "router",
    "test",
]