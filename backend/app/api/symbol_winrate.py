"""
Blue-Trading-AI
Version 26
API - Symbol Win Rate
"""

from __future__ import annotations

import logging
from typing import Any, Final

from fastapi import APIRouter, HTTPException, status

from app.services.symbol_winrate_service import (
    get_symbol_winrate_configuration,
    symbol_winrate_intelligence,
)


logger = logging.getLogger(__name__)

SYMBOL_WINRATE_API_VERSION: Final = "26.0.0"
MAXIMUM_SYMBOL_LENGTH: Final = 20

SUPPORTED_SYMBOLS: Final[tuple[str, ...]] = (
    "XAUUSD",
    "XAGUSD",
    "BTCUSD",
    "ETHUSD",
    "EURUSD",
    "GBPUSD",
    "USDJPY",
    "USDCHF",
    "AUDUSD",
    "NZDUSD",
    "USDCAD",
    "EURJPY",
    "GBPJPY",
    "EURGBP",
    "NAS100",
    "US30",
    "SPX500",
)


router = APIRouter(
    prefix="/symbol-winrate",
    tags=["Symbol Win Rate"],
)


def _normalize_symbol(
    symbol: str,
) -> str:
    normalized = str(
        symbol or ""
    ).strip().upper()

    if not normalized:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Symbol is required.",
        )

    if len(
        normalized
    ) > MAXIMUM_SYMBOL_LENGTH:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Symbol is too long.",
        )

    if not normalized.isalnum():
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Symbol contains unsupported characters.",
        )

    return normalized


def _safe_statistics_payload(
    symbol: str,
) -> dict[str, Any]:
    normalized_symbol = _normalize_symbol(
        symbol
    )

    try:
        stats = symbol_winrate_intelligence.get_symbol_statistics(
            normalized_symbol
        )
    except ValueError as error:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=(
                str(error)
                or "Invalid symbol win-rate request."
            ),
        ) from error
    except KeyError as error:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Symbol statistics were not found.",
        ) from error
    except Exception as error:
        logger.exception(
            "Symbol win-rate statistics lookup failed.",
            extra={
                "symbol": normalized_symbol,
            },
        )

        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Unable to load symbol win-rate statistics.",
        ) from error

    if stats is None or not hasattr(
        stats,
        "to_dict",
    ):
        logger.error(
            "Symbol win-rate service returned an invalid statistics object.",
            extra={
                "symbol": normalized_symbol,
                "result_type": type(
                    stats
                ).__name__,
            },
        )

        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Symbol win-rate service returned an invalid response.",
        )

    payload = stats.to_dict()

    if not isinstance(
        payload,
        dict,
    ):
        logger.error(
            "Symbol win-rate statistics payload is invalid.",
            extra={
                "symbol": normalized_symbol,
                "payload_type": type(
                    payload
                ).__name__,
            },
        )

        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Symbol win-rate service returned an invalid response.",
        )

    return payload


@router.get("/")
def home() -> dict[str, Any]:
    return {
        "status": "success",
        "module": "Symbol Win Rate API",
        "version": SYMBOL_WINRATE_API_VERSION,
    }


@router.get("/test")
def test() -> dict[str, Any]:
    return {
        "status": "success",
        "message": "Symbol Win Rate API is working",
        "safety_version": 26,
    }


@router.get("/configuration")
def configuration() -> dict[str, Any]:
    try:
        config = get_symbol_winrate_configuration()
    except Exception as error:
        logger.exception(
            "Symbol win-rate configuration lookup failed."
        )

        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Unable to load symbol win-rate configuration.",
        ) from error

    if not isinstance(
        config,
        dict,
    ):
        logger.error(
            "Symbol win-rate configuration returned an invalid response type.",
            extra={
                "result_type": type(
                    config
                ).__name__,
            },
        )

        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Symbol win-rate configuration returned an invalid response.",
        )

    return dict(
        config
    )


@router.get("/supported-symbols")
def supported_symbols() -> dict[str, Any]:
    return {
        "symbols": list(
            SUPPORTED_SYMBOLS
        )
    }


@router.get("/statistics/{symbol}")
def statistics(
    symbol: str,
) -> dict[str, Any]:
    return _safe_statistics_payload(
        symbol
    )


@router.get("/confidence/{symbol}")
def confidence(
    symbol: str,
) -> dict[str, Any]:
    normalized_symbol = _normalize_symbol(
        symbol
    )

    try:
        stats = symbol_winrate_intelligence.get_symbol_statistics(
            normalized_symbol
        )
    except ValueError as error:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=(
                str(error)
                or "Invalid symbol win-rate request."
            ),
        ) from error
    except KeyError as error:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Symbol statistics were not found.",
        ) from error
    except Exception as error:
        logger.exception(
            "Symbol win-rate confidence lookup failed.",
            extra={
                "symbol": normalized_symbol,
            },
        )

        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Unable to load symbol confidence adjustment.",
        ) from error

    required_attributes = (
        "symbol",
        "win_rate",
        "confidence_adjustment",
        "sample_size_sufficient",
    )

    if stats is None or any(
        not hasattr(
            stats,
            attribute,
        )
        for attribute in required_attributes
    ):
        logger.error(
            "Symbol win-rate confidence response is invalid.",
            extra={
                "symbol": normalized_symbol,
                "result_type": type(
                    stats
                ).__name__,
            },
        )

        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Symbol win-rate service returned an invalid response.",
        )

    return {
        "symbol": stats.symbol,
        "win_rate": stats.win_rate,
        "confidence_adjustment": (
            stats.confidence_adjustment
        ),
        "sample_size_sufficient": bool(
            stats.sample_size_sufficient
        ),
    }


@router.get("/all")
def all_statistics() -> dict[str, Any]:
    try:
        data = symbol_winrate_intelligence.get_all_statistics()
    except Exception as error:
        logger.exception(
            "Symbol win-rate all-statistics lookup failed."
        )

        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Unable to load symbol win-rate statistics.",
        ) from error

    if not isinstance(
        data,
        dict,
    ):
        logger.error(
            "Symbol win-rate service returned invalid all-statistics data.",
            extra={
                "result_type": type(
                    data
                ).__name__,
            },
        )

        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Symbol win-rate service returned an invalid response.",
        )

    statistics_payload: dict[
        str,
        dict[str, Any],
    ] = {}

    for key, value in data.items():
        if value is None or not hasattr(
            value,
            "to_dict",
        ):
            continue

        payload = value.to_dict()

        if isinstance(
            payload,
            dict,
        ):
            statistics_payload[
                str(
                    key
                ).strip().upper()
            ] = payload

    return {
        "count": len(
            statistics_payload
        ),
        "statistics": statistics_payload,
    }


__all__ = [
    "MAXIMUM_SYMBOL_LENGTH",
    "SUPPORTED_SYMBOLS",
    "SYMBOL_WINRATE_API_VERSION",
    "all_statistics",
    "confidence",
    "configuration",
    "home",
    "router",
    "statistics",
    "supported_symbols",
    "test",
]