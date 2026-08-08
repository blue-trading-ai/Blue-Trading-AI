"""
Blue-Trading-AI
Version 20 - Multi-Timeframe Market Pipeline API

Endpoints:

- GET  /multi-timeframe-pipeline/
- GET  /multi-timeframe-pipeline/test
- GET  /multi-timeframe-pipeline/{symbol}
- POST /multi-timeframe-pipeline/

Important:

- Analysis only.
- No broker connection.
- No automatic trade execution.
"""

from __future__ import annotations

import logging
from typing import Any, Final

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    field_validator,
)

from app.core.dependencies import require_approved_user
from app.services.multi_timeframe_pipeline_service import (
    DEFAULT_TIMEFRAMES,
    prepare_multi_timeframe_market_data,
)


logger = logging.getLogger(__name__)

MAXIMUM_SYMBOL_LENGTH: Final[int] = 30
MAXIMUM_TIMEFRAME_LENGTH: Final[int] = 16
MAXIMUM_TIMEFRAMES: Final[int] = 8
MINIMUM_CANDLES: Final[int] = 20
DEFAULT_MINIMUM_CANDLES: Final[int] = 50
MAXIMUM_CANDLES: Final[int] = 5000

ALLOWED_SYMBOL_CHARACTERS: Final[frozenset[str]] = frozenset(
    "ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789.*-/"
)
ALLOWED_TIMEFRAME_CHARACTERS: Final[frozenset[str]] = frozenset(
    "ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789.*-"
)


router = APIRouter(
    prefix="/multi-timeframe-pipeline",
    tags=["Multi-Timeframe Market Pipeline"],
)


def _normalize_symbol(
    symbol: str,
) -> str:
    normalized = str(
        symbol or ""
    ).strip().upper()

    if not normalized:
        raise ValueError(
            "symbol is required"
        )

    if len(normalized) > MAXIMUM_SYMBOL_LENGTH:
        raise ValueError(
            "symbol is too long"
        )

    if any(
        character not in ALLOWED_SYMBOL_CHARACTERS
        for character in normalized
    ):
        raise ValueError(
            "symbol contains unsupported characters"
        )

    return normalized


def _normalize_timeframes(
    timeframes: list[str] | None,
) -> list[str] | None:
    if timeframes is None:
        return None

    if not isinstance(
        timeframes,
        list,
    ):
        raise ValueError(
            "timeframes must be a list"
        )

    if len(timeframes) > MAXIMUM_TIMEFRAMES:
        raise ValueError(
            f"At most {MAXIMUM_TIMEFRAMES} timeframes are allowed"
        )

    normalized: list[str] = []

    for raw_value in timeframes:
        timeframe = str(
            raw_value or ""
        ).strip().upper()

        if not timeframe:
            raise ValueError(
                "timeframe values cannot be empty"
            )

        if len(timeframe) > MAXIMUM_TIMEFRAME_LENGTH:
            raise ValueError(
                "timeframe value is too long"
            )

        if any(
            character not in ALLOWED_TIMEFRAME_CHARACTERS
            for character in timeframe
        ):
            raise ValueError(
                "timeframe contains unsupported characters"
            )

        if timeframe not in normalized:
            normalized.append(
                timeframe
            )

    if not normalized:
        return None

    return normalized


def _call_pipeline(
    *,
    symbol: str,
    timeframes: list[str] | None,
    minimum_candles: int,
    require_all_timeframes: bool,
) -> dict[str, Any]:
    try:
        normalized_symbol = _normalize_symbol(
            symbol
        )
        normalized_timeframes = _normalize_timeframes(
            timeframes
        )

        result = prepare_multi_timeframe_market_data(
            symbol=normalized_symbol,
            timeframes=normalized_timeframes,
            minimum_candles=minimum_candles,
            require_all_timeframes=(
                require_all_timeframes is True
            ),
        )
    except ValueError as error:
        logger.warning(
            "Invalid Multi-Timeframe Market Pipeline request: %s",
            error,
        )

        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                "Invalid Multi-Timeframe Market Pipeline request."
            ),
        ) from error
    except HTTPException:
        raise
    except Exception as error:
        logger.exception(
            "Multi-Timeframe Market Pipeline failed.",
            extra={
                "symbol": str(symbol or "")[
                    :MAXIMUM_SYMBOL_LENGTH
                ],
                "timeframes": (
                    timeframes[:MAXIMUM_TIMEFRAMES]
                    if isinstance(timeframes, list)
                    else None
                ),
                "minimum_candles": minimum_candles,
                "require_all_timeframes": (
                    require_all_timeframes is True
                ),
            },
        )

        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Multi-Timeframe Market Pipeline failed.",
        ) from error

    if not isinstance(
        result,
        dict,
    ):
        logger.error(
            "Multi-Timeframe Market Pipeline returned an invalid response type.",
            extra={
                "symbol": normalized_symbol,
                "result_type": type(result).__name__,
            },
        )

        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=(
                "Multi-Timeframe Market Pipeline returned an invalid response."
            ),
        )

    return result


class MultiTimeframeRequest(BaseModel):
    """Request body for automated multi-timeframe market-data preparation."""

    model_config = ConfigDict(
        extra="forbid",
        str_strip_whitespace=True,
    )

    symbol: str = Field(
        ...,
        min_length=3,
        max_length=MAXIMUM_SYMBOL_LENGTH,
        examples=["XAUUSD"],
    )

    timeframes: list[str] | None = Field(
        default=None,
        max_length=MAXIMUM_TIMEFRAMES,
        examples=[
            [
                "M15",
                "M30",
                "H1",
                "H4",
                "D1",
            ]
        ],
    )

    minimum_candles: int = Field(
        default=DEFAULT_MINIMUM_CANDLES,
        ge=MINIMUM_CANDLES,
        le=MAXIMUM_CANDLES,
    )

    require_all_timeframes: bool = Field(
        default=True,
    )

    @field_validator(
        "symbol",
    )
    @classmethod
    def normalize_symbol(
        cls,
        value: str,
    ) -> str:
        return _normalize_symbol(
            value
        )

    @field_validator(
        "timeframes",
    )
    @classmethod
    def normalize_timeframes(
        cls,
        value: list[str] | None,
    ) -> list[str] | None:
        return _normalize_timeframes(
            value
        )


@router.get("/")
def multi_timeframe_home() -> dict[str, Any]:
    """Multi-timeframe pipeline information endpoint."""

    return {
        "status": "success",
        "project": "Blue-Trading-AI",
        "module": "Automated Multi-Timeframe Market Pipeline",
        "version": 20,
        "api_prefix": "/multi-timeframe-pipeline",
        "default_timeframes": list(
            DEFAULT_TIMEFRAMES
        ),
        "minimum_required_candles": DEFAULT_MINIMUM_CANDLES,
        "broker_connection_enabled": False,
        "trade_execution_enabled": False,
        "important_notice": (
            "This module prepares multi-timeframe market data "
            "for analysis only. It does not connect to brokers "
            "or execute trades."
        ),
    }


@router.get("/test")
def test_multi_timeframe_pipeline() -> dict[str, Any]:
    """Confirm that the multi-timeframe pipeline router is loaded."""

    return {
        "status": "success",
        "message": (
            "Multi-Timeframe Market Pipeline API is working."
        ),
        "project": "Blue-Trading-AI",
        "module": "Automated Multi-Timeframe Market Pipeline",
        "version": 20,
        "api_prefix": "/multi-timeframe-pipeline",
        "default_timeframes": list(
            DEFAULT_TIMEFRAMES
        ),
        "broker_connection_enabled": False,
        "trade_execution_enabled": False,
    }


@router.get("/{symbol}")
def get_multi_timeframe_market_data(
    symbol: str,
    timeframes: list[str] | None = Query(
        default=None,
        description=(
            "Repeat the query parameter for multiple timeframes. "
            "Example: ?timeframes=M15&timeframes=H1&timeframes=H4"
        ),
    ),
    minimum_candles: int = Query(
        default=DEFAULT_MINIMUM_CANDLES,
        ge=MINIMUM_CANDLES,
        le=MAXIMUM_CANDLES,
    ),
    require_all_timeframes: bool = Query(
        default=True,
    ),
    _current_user: Any = Depends(
        require_approved_user
    ),
) -> dict[str, Any]:
    """Prepare market data for one symbol across multiple timeframes."""

    return _call_pipeline(
        symbol=symbol,
        timeframes=timeframes,
        minimum_candles=minimum_candles,
        require_all_timeframes=require_all_timeframes,
    )


@router.post("/")
def post_multi_timeframe_market_data(
    request: MultiTimeframeRequest,
    _current_user: Any = Depends(
        require_approved_user
    ),
) -> dict[str, Any]:
    """Prepare multi-timeframe market data using a JSON request body."""

    return _call_pipeline(
        symbol=request.symbol,
        timeframes=request.timeframes,
        minimum_candles=request.minimum_candles,
        require_all_timeframes=request.require_all_timeframes,
    )


__all__ = [
    "DEFAULT_MINIMUM_CANDLES",
    "MAXIMUM_CANDLES",
    "MAXIMUM_TIMEFRAMES",
    "MINIMUM_CANDLES",
    "MultiTimeframeRequest",
    "get_multi_timeframe_market_data",
    "multi_timeframe_home",
    "post_multi_timeframe_market_data",
    "router",
    "test_multi_timeframe_pipeline",
]