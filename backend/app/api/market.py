from __future__ import annotations

import logging
from typing import Any

from fastapi import APIRouter, HTTPException, Query, status

from app.market.provider import get_market_data


logger = logging.getLogger(__name__)

MAXIMUM_SYMBOL_LENGTH = 32
MAXIMUM_INTERVAL_LENGTH = 16

ALLOWED_SYMBOL_CHARACTERS = set(
    "ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789._-/:"
)
ALLOWED_INTERVAL_CHARACTERS = set(
    "ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789._-"
)


router = APIRouter(
    prefix="/market",
    tags=["Market Data"],
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


def _normalize_interval(
    interval: str,
) -> str:
    normalized = interval.strip().lower()

    if not normalized:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Interval cannot be empty.",
        )

    if len(normalized) > MAXIMUM_INTERVAL_LENGTH:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Interval is too long.",
        )

    if any(
        character.upper() not in ALLOWED_INTERVAL_CHARACTERS
        for character in normalized
    ):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Interval contains unsupported characters.",
        )

    return normalized


@router.get("/test")
def market_test() -> dict[str, str]:
    return {
        "message": "Market API is working",
    }


@router.get("/{symbol:path}")
def market_price(
    symbol: str,
    interval: str = Query(
        default="1h",
        min_length=1,
        max_length=MAXIMUM_INTERVAL_LENGTH,
        description="Market-data interval, for example 1h.",
    ),
) -> dict[str, Any]:
    normalized_symbol = _normalize_symbol(
        symbol
    )
    normalized_interval = _normalize_interval(
        interval
    )

    try:
        data = get_market_data(
            normalized_symbol,
            normalized_interval,
        )
    except ValueError as error:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                str(error)
                or "Invalid market-data request."
            ),
        ) from error
    except HTTPException:
        raise
    except Exception as error:
        logger.exception(
            "Market-data provider request failed.",
            extra={
                "symbol": normalized_symbol,
                "interval": normalized_interval,
            },
        )

        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Market-data provider request failed.",
        ) from error

    if not isinstance(
        data,
        dict,
    ):
        logger.error(
            "Market-data provider returned an invalid response type.",
            extra={
                "symbol": normalized_symbol,
                "interval": normalized_interval,
                "result_type": type(data).__name__,
            },
        )

        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Market-data provider returned an invalid response.",
        )

    provider_error = data.get(
        "error"
    )

    if provider_error:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(
                provider_error
            )[:500],
        )

    return {
        "status": "success",
        "data": data,
    }


__all__ = [
    "market_price",
    "market_test",
    "router",
]