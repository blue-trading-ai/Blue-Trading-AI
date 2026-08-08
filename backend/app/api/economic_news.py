from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, HTTPException, Path as ApiPath, Query, status

from app.services.economic_news_service import (
    analyze_economic_news,
    apply_economic_news_confidence,
    get_economic_news_calendar,
    get_economic_news_configuration,
    get_high_impact_economic_news,
    get_upcoming_economic_news,
)


logger = logging.getLogger(__name__)


router = APIRouter(
    prefix="/economic-news",
    tags=["Economic News"],
)


def _validate_service_result(
    result: Any,
    operation: str,
) -> Any:
    """
    Validate service output while allowing
    existing dictionary and list response shapes.
    """

    if isinstance(
        result,
        (
            dict,
            list,
        ),
    ):
        return result

    logger.error(
        "Economic News service returned an invalid response type.",
        extra={
            "operation": operation,
            "result_type": type(result).__name__,
        },
    )

    raise HTTPException(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        detail="Economic News service returned an invalid response.",
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

    allowed_characters = set(
        "ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789._-/"
    )

    if any(
        character not in allowed_characters
        for character in normalized
    ):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Symbol contains unsupported characters.",
        )

    return normalized


@router.get("/")
def home() -> dict[str, Any]:
    return {
        "project": "Blue-Trading-AI",
        "module": "Economic News Intelligence",
        "version": 23,
        "status": "running",
        "analysis_only": True,
    }


@router.get("/test")
def test() -> dict[str, Any]:
    return {
        "success": True,
        "message": "Economic News API is working.",
    }


@router.get("/configuration")
def configuration() -> Any:
    try:
        result = get_economic_news_configuration()
    except ValueError as error:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(error) or "Invalid Economic News configuration request.",
        ) from error
    except HTTPException:
        raise
    except Exception as error:
        logger.exception(
            "Failed to load Economic News configuration."
        )

        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Economic News configuration could not be loaded.",
        ) from error

    return _validate_service_result(
        result,
        "configuration",
    )


@router.get("/calendar")
def calendar() -> Any:
    try:
        result = get_economic_news_calendar()
    except ValueError as error:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(error) or "Invalid Economic News calendar request.",
        ) from error
    except HTTPException:
        raise
    except Exception as error:
        logger.exception(
            "Failed to load Economic News calendar."
        )

        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Economic News calendar could not be loaded.",
        ) from error

    return _validate_service_result(
        result,
        "calendar",
    )


@router.get("/upcoming")
def upcoming(
    hours: int = Query(
        default=24,
        ge=1,
        le=168,
    ),
) -> Any:
    try:
        result = get_upcoming_economic_news(
            hours_ahead=hours,
        )
    except ValueError as error:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(error) or "Invalid upcoming Economic News request.",
        ) from error
    except HTTPException:
        raise
    except Exception as error:
        logger.exception(
            "Failed to load upcoming Economic News."
        )

        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Upcoming Economic News could not be loaded.",
        ) from error

    return _validate_service_result(
        result,
        "upcoming",
    )


@router.get("/high-impact")
def high_impact(
    hours: int = Query(
        default=24,
        ge=1,
        le=168,
    ),
) -> Any:
    try:
        result = get_high_impact_economic_news(
            hours_ahead=hours,
        )
    except ValueError as error:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(error) or "Invalid high-impact Economic News request.",
        ) from error
    except HTTPException:
        raise
    except Exception as error:
        logger.exception(
            "Failed to load high-impact Economic News."
        )

        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="High-impact Economic News could not be loaded.",
        ) from error

    return _validate_service_result(
        result,
        "high-impact",
    )


@router.get("/analyze/{symbol}")
def analyze(
    symbol: str = ApiPath(
        ...,
        min_length=1,
        max_length=32,
    ),
) -> Any:
    normalized_symbol = _normalize_symbol(
        symbol
    )

    try:
        result = analyze_economic_news(
            symbol=normalized_symbol,
        )
    except ValueError as error:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(error) or "Invalid Economic News analysis request.",
        ) from error
    except HTTPException:
        raise
    except Exception as error:
        logger.exception(
            "Economic News analysis failed."
        )

        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Economic News analysis failed.",
        ) from error

    return _validate_service_result(
        result,
        "analyze",
    )


@router.get("/confidence/{symbol}")
def confidence(
    symbol: str = ApiPath(
        ...,
        min_length=1,
        max_length=32,
    ),
    confidence: float = Query(
        ...,
        ge=0.0,
        le=100.0,
    ),
) -> Any:
    normalized_symbol = _normalize_symbol(
        symbol
    )

    try:
        result = apply_economic_news_confidence(
            symbol=normalized_symbol,
            base_confidence=confidence,
        )
    except ValueError as error:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(error) or "Invalid Economic News confidence request.",
        ) from error
    except HTTPException:
        raise
    except Exception as error:
        logger.exception(
            "Economic News confidence adjustment failed."
        )

        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Economic News confidence adjustment failed.",
        ) from error

    return _validate_service_result(
        result,
        "confidence",
    )


@router.get("/server-time")
def server_time() -> dict[str, str]:
    return {
        "server_time": datetime.now(
            timezone.utc
        ).isoformat(),
    }


__all__ = [
    "analyze",
    "calendar",
    "confidence",
    "configuration",
    "high_impact",
    "home",
    "router",
    "server_time",
    "test",
    "upcoming",
]