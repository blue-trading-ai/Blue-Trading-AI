from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from typing import Any
from zoneinfo import ZoneInfo

from fastapi import APIRouter, HTTPException, Path as ApiPath, Query, status

from app.services.economic_news_service import (
    analyze_economic_news,
    apply_economic_news_confidence,
    get_economic_news_calendar,
    get_economic_news_configuration,
    get_high_impact_economic_news,
    get_upcoming_economic_news,
)
from app.services.economic_news_provider import (
    EconomicNewsProviderError,
    refresh_forex_factory_current_week,
)

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/economic-news",
    tags=["Economic News"],
)

NEWS_TIMEZONE = ZoneInfo("Asia/Kuala_Lumpur")


def _refresh_live_weekly_news() -> dict[str, Any]:
    """
    Refresh the current Forex Factory week before serving
    calendar/news-dependent API responses.

    A provider failure is surfaced as 503 so callers do not
    mistake stale or empty in-memory news for a healthy live feed.
    """
    try:
        return refresh_forex_factory_current_week(
            force=False
        )
    except EconomicNewsProviderError as error:
        logger.exception(
            "Live Economic News provider refresh failed."
        )
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=(
                "Live Economic News provider is temporarily unavailable."
            ),
        ) from error


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


def _normalize_csv_values(
    value: str | None,
) -> list[str] | None:
    if value is None:
        return None

    values = [
        item.strip().upper()
        for item in value.split(",")
        if item.strip()
    ]

    return values or None


def _start_of_week(
    current_datetime: datetime,
) -> datetime:
    local_datetime = current_datetime.astimezone(
        NEWS_TIMEZONE
    )

    start = local_datetime - timedelta(
        days=local_datetime.weekday()
    )

    return start.replace(
        hour=0,
        minute=0,
        second=0,
        microsecond=0,
    )


def _end_of_week(
    current_datetime: datetime,
) -> datetime:
    return _start_of_week(
        current_datetime
    ) + timedelta(
        days=6,
        hours=23,
        minutes=59,
        seconds=59,
        microseconds=999999,
    )


def _start_of_month(
    current_datetime: datetime,
) -> datetime:
    local_datetime = current_datetime.astimezone(
        NEWS_TIMEZONE
    )

    return local_datetime.replace(
        day=1,
        hour=0,
        minute=0,
        second=0,
        microsecond=0,
    )


def _end_of_month(
    current_datetime: datetime,
) -> datetime:
    start = _start_of_month(
        current_datetime
    )

    if start.month == 12:
        next_month = start.replace(
            year=start.year + 1,
            month=1,
        )
    else:
        next_month = start.replace(
            month=start.month + 1,
        )

    return next_month - timedelta(
        microseconds=1
    )


def _calendar_response(
    *,
    period: str,
    start_datetime: datetime,
    end_datetime: datetime,
    currencies: list[str] | None,
    impacts: list[str] | None,
    provider_refresh: dict[str, Any] | None = None,
) -> dict[str, Any]:
    events = get_economic_news_calendar(
        start_datetime=start_datetime,
        end_datetime=end_datetime,
        currencies=currencies,
        impacts=impacts,
    )

    validated_events = _validate_service_result(
        events,
        f"{period}-calendar",
    )

    if not isinstance(
        validated_events,
        list,
    ):
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Economic News calendar returned an invalid response.",
        )

    return {
        "project": "Blue-Trading-AI",
        "module": "Economic News Intelligence",
        "version": 23,
        "period": period,
        "timezone": "Asia/Kuala_Lumpur",
        "start_datetime": start_datetime.isoformat(),
        "end_datetime": end_datetime.isoformat(),
        "currencies": currencies or [],
        "impacts": impacts or [],
        "event_count": len(validated_events),
        "events": validated_events,
        "provider_refresh": provider_refresh,
    }


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
def calendar(
    start_datetime: datetime | None = Query(
        default=None,
    ),
    end_datetime: datetime | None = Query(
        default=None,
    ),
    currencies: str | None = Query(
        default=None,
        description="Comma-separated currencies, for example USD,EUR,GBP.",
    ),
    impacts: str | None = Query(
        default=None,
        description="Comma-separated impact levels: LOW,MEDIUM,HIGH.",
    ),
) -> Any:
    try:
        _refresh_live_weekly_news()

        result = get_economic_news_calendar(
            start_datetime=start_datetime,
            end_datetime=end_datetime,
            currencies=_normalize_csv_values(
                currencies
            ),
            impacts=_normalize_csv_values(
                impacts
            ),
        )
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


@router.get("/calendar/weekly")
def weekly_calendar(
    currencies: str | None = Query(
        default=None,
        description="Comma-separated currencies.",
    ),
    impacts: str | None = Query(
        default=None,
        description="Comma-separated impact levels.",
    ),
) -> dict[str, Any]:
    now = datetime.now(
        NEWS_TIMEZONE
    )

    try:
        provider_refresh = _refresh_live_weekly_news()

        return _calendar_response(
            period="WEEKLY",
            start_datetime=_start_of_week(now),
            end_datetime=_end_of_week(now),
            currencies=_normalize_csv_values(
                currencies
            ),
            impacts=_normalize_csv_values(
                impacts
            ),
            provider_refresh=provider_refresh,
        )
    except ValueError as error:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(error) or "Invalid weekly Economic News calendar request.",
        ) from error
    except HTTPException:
        raise
    except Exception as error:
        logger.exception(
            "Failed to load weekly Economic News calendar."
        )

        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Weekly Economic News calendar could not be loaded.",
        ) from error


@router.get("/calendar/monthly")
def monthly_calendar(
    currencies: str | None = Query(
        default=None,
        description="Comma-separated currencies.",
    ),
    impacts: str | None = Query(
        default=None,
        description="Comma-separated impact levels.",
    ),
) -> dict[str, Any]:
    now = datetime.now(
        NEWS_TIMEZONE
    )

    try:
        provider_refresh = _refresh_live_weekly_news()

        return _calendar_response(
            period="MONTHLY",
            start_datetime=_start_of_month(now),
            end_datetime=_end_of_month(now),
            currencies=_normalize_csv_values(
                currencies
            ),
            impacts=_normalize_csv_values(
                impacts
            ),
        )
    except ValueError as error:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(error) or "Invalid monthly Economic News calendar request.",
        ) from error
    except HTTPException:
        raise
    except Exception as error:
        logger.exception(
            "Failed to load monthly Economic News calendar."
        )

        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Monthly Economic News calendar could not be loaded.",
        ) from error


@router.get("/upcoming")
def upcoming(
    hours: int = Query(
        default=24,
        ge=1,
        le=168,
    ),
) -> Any:
    try:
        _refresh_live_weekly_news()

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
        _refresh_live_weekly_news()

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
        _refresh_live_weekly_news()

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
        _refresh_live_weekly_news()

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
    "monthly_calendar",
    "router",
    "server_time",
    "test",
    "upcoming",
    "weekly_calendar",
]