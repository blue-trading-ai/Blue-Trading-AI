"""
Blue-Trading-AI
Version 20 — Automated Market Analysis Pipeline API

This router:
- Accepts a symbol and timeframe.
- Retrieves market data automatically.
- Normalizes and validates OHLCV candles.
- Returns prepared market data for analysis.

Important:
- No broker connection.
- No automatic trade execution.
"""

from __future__ import annotations

import logging
from typing import Any, Final, Literal

from fastapi import APIRouter, HTTPException, Path as ApiPath, Query, status
from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.services.automated_market_pipeline_service import (
    MINIMUM_REQUIRED_CANDLES,
    prepare_automated_market_data,
)


logger = logging.getLogger(__name__)

SUPPORTED_TIMEFRAMES: Final[tuple[str, ...]] = (
    "M5",
    "M15",
    "M30",
    "H1",
    "H4",
    "D1",
    "W1",
    "MN",
)

SymbolPattern = r"^[A-Za-z0-9][A-Za-z0-9._:/-]{0,31}$"
Timeframe = Literal[
    "M5",
    "M15",
    "M30",
    "H1",
    "H4",
    "D1",
    "W1",
    "MN",
]


router = APIRouter(
    prefix="/automated-market",
    tags=["Automated Market Pipeline"],
)


class AutomatedMarketRequest(BaseModel):
    """Request body for automated market-data preparation."""

    model_config = ConfigDict(
        extra="forbid",
        str_strip_whitespace=True,
    )

    symbol: str = Field(
        ...,
        min_length=1,
        max_length=32,
        pattern=SymbolPattern,
        examples=["XAUUSD"],
        description="Market symbol to analyse.",
    )

    timeframe: Timeframe = Field(
        default="M15",
        examples=["M15"],
        description=(
            "Supported timeframes: "
            "M5, M15, M30, H1, H4, D1, W1, MN."
        ),
    )

    minimum_candles: int = Field(
        default=MINIMUM_REQUIRED_CANDLES,
        ge=20,
        le=5000,
        description="Minimum number of valid candles required.",
    )

    @field_validator(
        "symbol",
        mode="after",
    )
    @classmethod
    def normalize_symbol(
        cls,
        value: str,
    ) -> str:
        return value.upper()


def _prepare_market_data(
    *,
    symbol: str,
    timeframe: str,
    minimum_candles: int,
) -> dict[str, Any]:
    """
    Call the pipeline service and translate safe validation failures.

    Unexpected internal exceptions are logged server-side without exposing
    implementation details to API clients.
    """

    try:
        result = prepare_automated_market_data(
            symbol=symbol,
            timeframe=timeframe,
            minimum_candles=minimum_candles,
        )
    except ValueError as error:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(error) or "Invalid market-data request.",
        ) from error
    except HTTPException:
        raise
    except Exception as error:
        logger.exception(
            "Automated market-data preparation failed.",
            extra={
                "symbol": symbol,
                "timeframe": timeframe,
                "minimum_candles": minimum_candles,
            },
        )

        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Automated market-data preparation failed.",
        ) from error

    if not isinstance(
        result,
        dict,
    ):
        logger.error(
            "Automated market-data service returned an invalid response type.",
            extra={
                "symbol": symbol,
                "timeframe": timeframe,
                "result_type": type(result).__name__,
            },
        )

        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Automated market-data preparation returned an invalid response.",
        )

    return result


@router.get("/")
def automated_market_pipeline_home() -> dict[str, Any]:
    """Confirm that the Version 20 router is working."""

    return {
        "status": "success",
        "message": (
            "Blue-Trading-AI Automated Market Pipeline "
            "API is working"
        ),
        "project": "Blue-Trading-AI",
        "module": "Automated Market Analysis Pipeline",
        "safety_version": 20,
        "broker_connection_enabled": False,
        "trade_execution_enabled": False,
    }


@router.get("/test")
def automated_market_pipeline_test() -> dict[str, Any]:
    """Display Version 20 pipeline features and safety rules."""

    return {
        "status": "success",
        "project": "Blue-Trading-AI",
        "module": "Automated Market Analysis Pipeline",
        "safety_version": 20,
        "features": [
            "automatic_market_data_retrieval",
            "symbol_normalization",
            "timeframe_normalization",
            "provider_interval_conversion",
            "ohlcv_candle_normalization",
            "invalid_candle_removal",
            "minimum_candle_validation",
            "latest_price_extraction",
            "price_change_calculation",
            "safe_data_blocking",
            "no_broker_connection",
            "no_trade_execution",
        ],
        "supported_timeframes": list(
            SUPPORTED_TIMEFRAMES
        ),
        "minimum_required_candles": (
            MINIMUM_REQUIRED_CANDLES
        ),
        "broker_connection_enabled": False,
        "trade_execution_enabled": False,
    }


@router.get("/prepare/{symbol}")
def prepare_market_data_get(
    symbol: str = ApiPath(
        ...,
        min_length=1,
        max_length=32,
        pattern=SymbolPattern,
        description="Market symbol to analyse.",
        examples=["XAUUSD"],
    ),
    timeframe: Timeframe = Query(
        default="M15",
        description="Market timeframe.",
    ),
    minimum_candles: int = Query(
        default=MINIMUM_REQUIRED_CANDLES,
        ge=20,
        le=5000,
        description="Minimum valid candles required.",
    ),
) -> dict[str, Any]:
    """
    Retrieve and prepare market data using a GET request.

    Example:
    /automated-market/prepare/XAUUSD?timeframe=M15
    """

    return _prepare_market_data(
        symbol=symbol.strip().upper(),
        timeframe=timeframe,
        minimum_candles=minimum_candles,
    )


@router.post("/prepare")
def prepare_market_data_post(
    request: AutomatedMarketRequest,
) -> dict[str, Any]:
    """Retrieve and prepare market data using a POST request."""

    return _prepare_market_data(
        symbol=request.symbol,
        timeframe=request.timeframe,
        minimum_candles=request.minimum_candles,
    )