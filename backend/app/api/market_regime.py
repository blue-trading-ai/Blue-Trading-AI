from __future__ import annotations

import logging
from typing import Any

from fastapi import APIRouter, HTTPException, Query, status

from app.services.market_regime_service import (
    apply_market_regime_confidence,
    get_market_regime_configuration,
)


logger = logging.getLogger(__name__)

MAXIMUM_SYMBOL_LENGTH = 32
MAXIMUM_TIMEFRAME_LENGTH = 16
MAXIMUM_DIRECTION_LENGTH = 16
MAXIMUM_CONFIRMATIONS = 100

ALLOWED_SYMBOL_CHARACTERS = set(
    "ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789._-/"
)
ALLOWED_TIMEFRAME_CHARACTERS = set(
    "ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789._-"
)
ALLOWED_DIRECTION_CHARACTERS = set(
    "ABCDEFGHIJKLMNOPQRSTUVWXYZ_"
)


router = APIRouter(
    prefix="/market-regime",
    tags=["Version 25 - Market Regime Intelligence"],
)


def _normalize_symbol(
    symbol: str,
) -> str:
    normalized = symbol.strip().upper()

    if not normalized:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Symbol cannot be empty.",
        )

    if len(normalized) > MAXIMUM_SYMBOL_LENGTH:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Symbol is too long.",
        )

    if any(
        character not in ALLOWED_SYMBOL_CHARACTERS
        for character in normalized
    ):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Symbol contains unsupported characters.",
        )

    return normalized


def _normalize_timeframe(
    timeframe: str,
) -> str:
    normalized = timeframe.strip().upper()

    if not normalized:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Timeframe cannot be empty.",
        )

    if len(normalized) > MAXIMUM_TIMEFRAME_LENGTH:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Timeframe is too long.",
        )

    if any(
        character not in ALLOWED_TIMEFRAME_CHARACTERS
        for character in normalized
    ):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Timeframe contains unsupported characters.",
        )

    return normalized


def _normalize_direction(
    direction: str,
) -> str:
    normalized = direction.strip().upper()

    if not normalized:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Direction cannot be empty.",
        )

    if len(normalized) > MAXIMUM_DIRECTION_LENGTH:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Direction is too long.",
        )

    if any(
        character not in ALLOWED_DIRECTION_CHARACTERS
        for character in normalized
    ):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Direction contains unsupported characters.",
        )

    return normalized


def _configuration() -> dict[str, Any]:
    try:
        result = get_market_regime_configuration()
    except ValueError as error:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                str(error)
                or "Invalid market-regime configuration."
            ),
        ) from error
    except HTTPException:
        raise
    except Exception as error:
        logger.exception(
            "Unable to load market-regime configuration."
        )

        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Unable to load market-regime configuration.",
        ) from error

    if not isinstance(
        result,
        dict,
    ):
        logger.error(
            "Market-regime configuration returned an invalid response type.",
            extra={
                "result_type": type(result).__name__,
            },
        )

        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Market-regime configuration is invalid.",
        )

    return result


@router.get("/")
def home() -> dict[str, Any]:
    return {
        "service": "AI Market Regime Intelligence",
        "version": "25.0.0",
        "analysis_only": True,
        "trade_execution_enabled": False,
    }


@router.get("/test")
def test() -> dict[str, str]:
    return {
        "status": "ok",
        "version": "25.0.0",
    }


@router.get("/configuration")
def configuration() -> dict[str, Any]:
    return _configuration()


@router.get("/supported-regimes")
def supported_regimes() -> Any:
    config = _configuration()

    if "supported_regimes" not in config:
        logger.error(
            "Market-regime configuration is missing supported_regimes."
        )

        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Supported market regimes are unavailable.",
        )

    supported = config["supported_regimes"]

    if not isinstance(
        supported,
        (
            list,
            tuple,
            set,
        ),
    ):
        logger.error(
            "supported_regimes has an invalid response type.",
            extra={
                "result_type": type(supported).__name__,
            },
        )

        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Supported market regimes are invalid.",
        )

    return (
        sorted(supported)
        if isinstance(
            supported,
            set,
        )
        else supported
    )


@router.get("/analyze/{symbol}")
def analyze(
    symbol: str,
    timeframe: str = Query(
        default="H1",
        min_length=1,
        max_length=MAXIMUM_TIMEFRAME_LENGTH,
        description="Market-analysis timeframe.",
    ),
) -> dict[str, Any]:
    normalized_symbol = _normalize_symbol(
        symbol
    )
    normalized_timeframe = _normalize_timeframe(
        timeframe
    )

    return {
        "symbol": normalized_symbol,
        "timeframe": normalized_timeframe,
        "message": (
            "Use the signal pipeline with OHLCV candles "
            "for full analysis."
        ),
        "analysis_only": True,
    }


@router.get("/confidence/{symbol}")
def confidence(
    symbol: str,
    timeframe: str = Query(
        default="H1",
        min_length=1,
        max_length=MAXIMUM_TIMEFRAME_LENGTH,
    ),
    confidence: float = Query(
        default=80.0,
        ge=0.0,
        le=100.0,
    ),
    direction: str = Query(
        default="BUY",
        min_length=1,
        max_length=MAXIMUM_DIRECTION_LENGTH,
    ),
    confirmations: int = Query(
        default=3,
        ge=0,
        le=MAXIMUM_CONFIRMATIONS,
    ),
) -> dict[str, Any]:
    normalized_symbol = _normalize_symbol(
        symbol
    )
    normalized_timeframe = _normalize_timeframe(
        timeframe
    )
    normalized_direction = _normalize_direction(
        direction
    )

    try:
        result = apply_market_regime_confidence(
            confidence=confidence,
            candles=[],
            signal_direction=normalized_direction,
            confirmations=confirmations,
            symbol=normalized_symbol,
            timeframe=normalized_timeframe,
        )
    except ValueError as error:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                str(error)
                or "Invalid market-regime confidence request."
            ),
        ) from error
    except HTTPException:
        raise
    except Exception as error:
        logger.exception(
            "Market-regime confidence evaluation failed.",
            extra={
                "symbol": normalized_symbol,
                "timeframe": normalized_timeframe,
            },
        )

        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Market-regime confidence evaluation failed.",
        ) from error

    if not isinstance(
        result,
        dict,
    ):
        logger.error(
            "Market-regime service returned an invalid response type.",
            extra={
                "result_type": type(result).__name__,
            },
        )

        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Market-regime confidence returned an invalid response.",
        )

    return result


__all__ = [
    "analyze",
    "confidence",
    "configuration",
    "home",
    "router",
    "supported_regimes",
    "test",
]