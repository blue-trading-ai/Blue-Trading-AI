from __future__ import annotations

import logging
from datetime import datetime
from typing import Any

from fastapi import (
    APIRouter,
    HTTPException,
    Query,
    status,
)

from app.services.market_session_service import (
    analyze_market_session,
    apply_market_session_confidence,
    get_current_market_sessions,
    get_market_session_configuration,
)


logger = logging.getLogger(__name__)

MAXIMUM_SYMBOL_LENGTH = 32
ALLOWED_SYMBOL_CHARACTERS = set(
    "ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789._-/"
)


# ============================================================
# BLUE-TRADING-AI
# VERSION 22
# MARKET SESSION API
# ============================================================

router = APIRouter(
    prefix="/market-session",
    tags=["Market Session"],
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


def _validate_dict_result(
    result: Any,
    operation: str,
) -> dict[str, Any]:
    if isinstance(
        result,
        dict,
    ):
        return result

    logger.error(
        "Market Session service returned an invalid response type.",
        extra={
            "operation": operation,
            "result_type": type(result).__name__,
        },
    )

    raise HTTPException(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        detail="Market Session returned an invalid response.",
    )


@router.get("/")
async def home() -> dict[str, Any]:
    return {
        "project": "Blue-Trading-AI",
        "version": 22,
        "module": "Market Session Intelligence",
        "status": "running",
    }


@router.get("/test")
async def test() -> dict[str, Any]:
    return {
        "status": "success",
        "message": "Market Session API Working",
        "project": "Blue-Trading-AI",
        "version": 22,
    }


@router.get("/configuration")
async def configuration() -> dict[str, Any]:
    try:
        config = get_market_session_configuration()
    except ValueError as error:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                str(error)
                or "Invalid Market Session configuration."
            ),
        ) from error
    except HTTPException:
        raise
    except Exception as error:
        logger.exception(
            "Unable to load Market Session configuration."
        )

        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Unable to load Market Session configuration.",
        ) from error

    return {
        "status": "success",
        "configuration": _validate_dict_result(
            config,
            "configuration",
        ),
    }


@router.get("/active")
async def active_sessions(
    current_datetime: datetime | None = Query(
        default=None,
    ),
) -> dict[str, Any]:
    try:
        sessions = get_current_market_sessions(
            current_datetime=current_datetime,
        )
    except ValueError as error:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                str(error)
                or "Invalid market-session datetime."
            ),
        ) from error
    except HTTPException:
        raise
    except Exception as error:
        logger.exception(
            "Unable to resolve active market sessions."
        )

        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Unable to resolve active market sessions.",
        ) from error

    if not isinstance(
        sessions,
        list,
    ):
        logger.error(
            "Market Session active-session service returned invalid type.",
            extra={
                "result_type": type(sessions).__name__,
            },
        )

        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Active market sessions returned an invalid response.",
        )

    return {
        "status": "success",
        "count": len(sessions),
        "active_sessions": sessions,
    }


@router.get("/analyze/{symbol}")
async def analyze(
    symbol: str,
    current_datetime: datetime | None = Query(
        default=None,
    ),
) -> dict[str, Any]:
    normalized_symbol = _normalize_symbol(
        symbol
    )

    try:
        result = analyze_market_session(
            symbol=normalized_symbol,
            current_datetime=current_datetime,
        )
    except ValueError as error:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                str(error)
                or "Invalid Market Session analysis request."
            ),
        ) from error
    except HTTPException:
        raise
    except Exception as error:
        logger.exception(
            "Market Session analysis failed.",
            extra={
                "symbol": normalized_symbol,
            },
        )

        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Market Session analysis failed.",
        ) from error

    return {
        "status": "success",
        "data": _validate_dict_result(
            result,
            "analyze",
        ),
    }


@router.get("/confidence/{symbol}")
async def confidence(
    symbol: str,
    base_confidence: float = Query(
        ...,
        ge=0.0,
        le=100.0,
    ),
    current_datetime: datetime | None = Query(
        default=None,
    ),
) -> dict[str, Any]:
    normalized_symbol = _normalize_symbol(
        symbol
    )

    try:
        result = apply_market_session_confidence(
            symbol=normalized_symbol,
            base_confidence=base_confidence,
            current_datetime=current_datetime,
        )
    except ValueError as error:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                str(error)
                or "Invalid Market Session confidence request."
            ),
        ) from error
    except HTTPException:
        raise
    except Exception as error:
        logger.exception(
            "Market Session confidence evaluation failed.",
            extra={
                "symbol": normalized_symbol,
            },
        )

        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Market Session confidence evaluation failed.",
        ) from error

    return {
        "status": "success",
        "data": _validate_dict_result(
            result,
            "confidence",
        ),
    }


__all__ = [
    "active_sessions",
    "analyze",
    "confidence",
    "configuration",
    "home",
    "router",
    "test",
]