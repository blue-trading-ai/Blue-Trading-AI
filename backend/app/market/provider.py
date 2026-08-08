"""
Blue-Trading-AI
Twelve Data Market Provider

Responsibilities:
- Normalize Blue-Trading-AI symbols for Twelve Data.
- Normalize interval formats.
- Retrieve OHLCV candles.
- Validate provider responses.
- Return candles from oldest to newest.

Important:
- Market analysis only.
- No broker connection.
- No trade execution.
"""

from __future__ import annotations

import math
from typing import Any, Final

import requests

from app.core.config import settings


BASE_URL: Final = "https://api.twelvedata.com/time_series"

DEFAULT_INTERVAL: Final = "1h"
DEFAULT_OUTPUTSIZE: Final = 50
MINIMUM_OUTPUTSIZE: Final = 1
MAXIMUM_OUTPUTSIZE: Final = 5000
REQUEST_TIMEOUT_SECONDS: Final = 15
MAXIMUM_SYMBOL_LENGTH: Final = 32
MAXIMUM_DATETIME_LENGTH: Final = 64
MAXIMUM_PROVIDER_ERROR_LENGTH: Final = 500


SYMBOL_MAPPING: Final = {
    # Precious metals
    "XAUUSD": "XAU/USD",
    "XAGUSD": "XAG/USD",

    # Major forex pairs
    "EURUSD": "EUR/USD",
    "GBPUSD": "GBP/USD",
    "USDJPY": "USD/JPY",
    "USDCHF": "USD/CHF",
    "USDCAD": "USD/CAD",
    "AUDUSD": "AUD/USD",
    "NZDUSD": "NZD/USD",

    # Forex crosses
    "EURGBP": "EUR/GBP",
    "EURJPY": "EUR/JPY",
    "GBPJPY": "GBP/JPY",
    "AUDJPY": "AUD/JPY",
    "CADJPY": "CAD/JPY",
    "CHFJPY": "CHF/JPY",

    # Cryptocurrency
    "BTCUSD": "BTC/USD",
    "ETHUSD": "ETH/USD",
    "BNBUSD": "BNB/USD",
    "SOLUSD": "SOL/USD",
    "XRPUSD": "XRP/USD",
}


INTERVAL_MAPPING: Final = {
    # Minute intervals
    "1m": "1min",
    "1min": "1min",
    "M1": "1min",

    "5m": "5min",
    "5min": "5min",
    "M5": "5min",

    "15m": "15min",
    "15min": "15min",
    "M15": "15min",

    "30m": "30min",
    "30min": "30min",
    "M30": "30min",

    "45m": "45min",
    "45min": "45min",
    "M45": "45min",

    # Hour intervals
    "1h": "1h",
    "H1": "1h",

    "2h": "2h",
    "H2": "2h",

    "4h": "4h",
    "H4": "4h",

    "8h": "8h",
    "H8": "8h",

    # Daily, weekly and monthly
    "1d": "1day",
    "1day": "1day",
    "D1": "1day",
    "DAILY": "1day",

    "1w": "1week",
    "1wk": "1week",
    "1week": "1week",
    "W1": "1week",
    "WEEKLY": "1week",

    "1mo": "1month",
    "1mn": "1month",
    "1month": "1month",
    "MN": "1month",
    "MONTHLY": "1month",
}

SUPPORTED_PROVIDER_INTERVALS: Final = frozenset(
    INTERVAL_MAPPING.values()
)


def _safe_finite_float(
    value: Any,
    *,
    minimum: float | None = None,
) -> float | None:
    """Return a finite float, optionally enforcing a minimum."""

    try:
        parsed = float(value)
    except (TypeError, ValueError, OverflowError):
        return None

    if not math.isfinite(parsed):
        return None

    if minimum is not None and parsed < minimum:
        return None

    return parsed


def _normalize_outputsize(
    outputsize: Any,
) -> int:
    """Normalize candle count while rejecting booleans and invalid values."""

    if isinstance(outputsize, bool):
        return DEFAULT_OUTPUTSIZE

    try:
        normalized = int(outputsize)
    except (TypeError, ValueError, OverflowError):
        normalized = DEFAULT_OUTPUTSIZE

    return max(
        MINIMUM_OUTPUTSIZE,
        min(
            normalized,
            MAXIMUM_OUTPUTSIZE,
        ),
    )


def normalize_provider_symbol(
    symbol: str,
) -> str:
    """
    Convert an internal Blue-Trading-AI symbol into the
    format expected by Twelve Data.

    Examples:
        XAUUSD -> XAU/USD
        GBPUSD -> GBP/USD
        BTCUSD -> BTC/USD
        AAPL   -> AAPL
    """

    normalized = (
        str(symbol or "")
        .strip()
        .upper()
        .replace("/", "")
        .replace("-", "")
        .replace("_", "")
        .replace(" ", "")
    )

    if not normalized:
        return ""

    if len(normalized) > MAXIMUM_SYMBOL_LENGTH:
        return ""

    if not normalized.isalnum():
        return ""

    return SYMBOL_MAPPING.get(
        normalized,
        normalized,
    )


def normalize_provider_interval(
    interval: str,
) -> str:
    """
    Convert an internal interval into the format expected
    by Twelve Data.

    Unsupported intervals return an empty string so direct
    service callers cannot send arbitrary values upstream.
    """

    raw_interval = str(
        interval or DEFAULT_INTERVAL
    ).strip()

    if not raw_interval:
        raw_interval = DEFAULT_INTERVAL

    resolved = INTERVAL_MAPPING.get(
        raw_interval,
        INTERVAL_MAPPING.get(
            raw_interval.upper(),
            "",
        ),
    )

    if resolved not in SUPPORTED_PROVIDER_INTERVALS:
        return ""

    return resolved


def _provider_error_response(
    *,
    message: str,
    requested_symbol: str,
    provider_symbol: str,
    requested_interval: str,
    provider_interval: str,
    error_code: Any = None,
) -> dict[str, Any]:
    """Produce a consistent provider error response."""

    safe_message = str(
        message or "Market-data provider error."
    ).strip()[:MAXIMUM_PROVIDER_ERROR_LENGTH]

    return {
        "status": "error",
        "error": safe_message,
        "error_code": error_code,
        "requested_symbol": requested_symbol,
        "provider_symbol": provider_symbol,
        "requested_interval": requested_interval,
        "provider_interval": provider_interval,
        "candles": [],
        "prices": [],
        "broker_connection_enabled": False,
        "trade_execution_enabled": False,
    }


def get_market_data(
    symbol: str,
    interval: str = DEFAULT_INTERVAL,
    outputsize: int = DEFAULT_OUTPUTSIZE,
) -> dict[str, Any]:
    """
    Fetch market data from Twelve Data.

    Candles are returned from oldest to newest.
    This function performs analysis-data retrieval only and never executes trades.
    """

    requested_symbol = str(
        symbol or ""
    ).strip().upper()[:MAXIMUM_SYMBOL_LENGTH]

    requested_interval = str(
        interval or DEFAULT_INTERVAL
    ).strip()[:32]

    provider_symbol = normalize_provider_symbol(
        requested_symbol
    )
    provider_interval = normalize_provider_interval(
        requested_interval
    )
    normalized_outputsize = _normalize_outputsize(
        outputsize
    )

    if not provider_symbol:
        return _provider_error_response(
            message="Invalid or unsupported market symbol format.",
            requested_symbol=requested_symbol,
            provider_symbol="",
            requested_interval=requested_interval,
            provider_interval=provider_interval,
        )

    if not provider_interval:
        return _provider_error_response(
            message="Unsupported market-data interval.",
            requested_symbol=requested_symbol,
            provider_symbol=provider_symbol,
            requested_interval=requested_interval,
            provider_interval="",
        )

    api_key = str(
        getattr(
            settings,
            "TWELVE_DATA_API_KEY",
            "",
        )
        or ""
    ).strip()

    if not api_key:
        return _provider_error_response(
            message=(
                "TWELVE_DATA_API_KEY is missing from "
                "the application configuration."
            ),
            requested_symbol=requested_symbol,
            provider_symbol=provider_symbol,
            requested_interval=requested_interval,
            provider_interval=provider_interval,
        )

    params = {
        "symbol": provider_symbol,
        "interval": provider_interval,
        "outputsize": normalized_outputsize,
        "apikey": api_key,
        "format": "JSON",
        "timezone": "UTC",
    }

    try:
        response = requests.get(
            BASE_URL,
            params=params,
            timeout=REQUEST_TIMEOUT_SECONDS,
        )
        response.raise_for_status()

    except requests.Timeout:
        return _provider_error_response(
            message="The Twelve Data request timed out.",
            requested_symbol=requested_symbol,
            provider_symbol=provider_symbol,
            requested_interval=requested_interval,
            provider_interval=provider_interval,
        )

    except requests.RequestException:
        # Never expose str(exc): requests exceptions can include the full
        # request URL, which may contain the API key in the query string.
        return _provider_error_response(
            message="Market data request failed.",
            requested_symbol=requested_symbol,
            provider_symbol=provider_symbol,
            requested_interval=requested_interval,
            provider_interval=provider_interval,
        )

    try:
        data = response.json()
    except ValueError:
        return _provider_error_response(
            message="Twelve Data returned an invalid JSON response.",
            requested_symbol=requested_symbol,
            provider_symbol=provider_symbol,
            requested_interval=requested_interval,
            provider_interval=provider_interval,
        )

    if not isinstance(data, dict):
        return _provider_error_response(
            message="Twelve Data returned an unexpected response format.",
            requested_symbol=requested_symbol,
            provider_symbol=provider_symbol,
            requested_interval=requested_interval,
            provider_interval=provider_interval,
        )

    # Twelve Data API-level errors may still use HTTP 200.
    if data.get("status") == "error":
        provider_message = str(
            data.get(
                "message",
                "Twelve Data market-data error.",
            )
        )[:MAXIMUM_PROVIDER_ERROR_LENGTH]

        return _provider_error_response(
            message=provider_message,
            error_code=data.get("code"),
            requested_symbol=requested_symbol,
            provider_symbol=provider_symbol,
            requested_interval=requested_interval,
            provider_interval=provider_interval,
        )

    raw_candles = data.get(
        "values",
        [],
    )

    if not isinstance(
        raw_candles,
        list,
    ):
        return _provider_error_response(
            message="Twelve Data returned an invalid candle collection.",
            requested_symbol=requested_symbol,
            provider_symbol=provider_symbol,
            requested_interval=requested_interval,
            provider_interval=provider_interval,
        )

    if not raw_candles:
        return _provider_error_response(
            message=(
                "No market candles were returned for "
                f"{provider_symbol} at {provider_interval}."
            ),
            requested_symbol=requested_symbol,
            provider_symbol=provider_symbol,
            requested_interval=requested_interval,
            provider_interval=provider_interval,
        )

    # Provider normally returns newest first. Keep only the requested
    # maximum and reverse to oldest -> newest.
    raw_candles = list(
        reversed(
            raw_candles[
                :normalized_outputsize
            ]
        )
    )

    candles: list[dict[str, Any]] = []
    rejected_candle_count = 0

    for candle in raw_candles:
        if not isinstance(
            candle,
            dict,
        ):
            rejected_candle_count += 1
            continue

        open_price = _safe_finite_float(
            candle.get("open"),
            minimum=0.0,
        )
        high_price = _safe_finite_float(
            candle.get("high"),
            minimum=0.0,
        )
        low_price = _safe_finite_float(
            candle.get("low"),
            minimum=0.0,
        )
        close_price = _safe_finite_float(
            candle.get("close"),
            minimum=0.0,
        )

        if (
            open_price is None
            or high_price is None
            or low_price is None
            or close_price is None
            or open_price <= 0.0
            or high_price <= 0.0
            or low_price <= 0.0
            or close_price <= 0.0
        ):
            rejected_candle_count += 1
            continue

        if high_price < low_price:
            rejected_candle_count += 1
            continue

        if high_price < max(
            open_price,
            close_price,
        ):
            rejected_candle_count += 1
            continue

        if low_price > min(
            open_price,
            close_price,
        ):
            rejected_candle_count += 1
            continue

        raw_datetime = candle.get(
            "datetime"
        )
        normalized_datetime = (
            str(raw_datetime).strip()[:MAXIMUM_DATETIME_LENGTH]
            if raw_datetime is not None
            else None
        )

        volume = _safe_finite_float(
            candle.get("volume"),
            minimum=0.0,
        )

        normalized_candle = {
            "datetime": normalized_datetime,
            "open": open_price,
            "high": high_price,
            "low": low_price,
            "close": close_price,
            "volume": (
                volume
                if volume is not None
                else 0.0
            ),
        }

        candles.append(
            normalized_candle
        )

    if not candles:
        return _provider_error_response(
            message=(
                "Twelve Data returned candles, but all "
                "candles failed OHLC validation."
            ),
            requested_symbol=requested_symbol,
            provider_symbol=provider_symbol,
            requested_interval=requested_interval,
            provider_interval=provider_interval,
        )

    prices = [
        candle["close"]
        for candle in candles
    ]
    current_price = prices[-1]

    metadata = data.get(
        "meta",
        {},
    )

    if not isinstance(
        metadata,
        dict,
    ):
        metadata = {}

    return {
        "status": "success",
        "symbol": requested_symbol,
        "provider_symbol": provider_symbol,
        "interval": requested_interval,
        "provider_interval": provider_interval,
        "current_price": current_price,
        "prices": prices,
        "candles": candles,
        "candle_count": len(candles),
        "rejected_candle_count": rejected_candle_count,
        "metadata": metadata,
        "broker_connection_enabled": False,
        "trade_execution_enabled": False,
    }


__all__ = [
    "BASE_URL",
    "DEFAULT_INTERVAL",
    "DEFAULT_OUTPUTSIZE",
    "INTERVAL_MAPPING",
    "MAXIMUM_OUTPUTSIZE",
    "SYMBOL_MAPPING",
    "SUPPORTED_PROVIDER_INTERVALS",
    "get_market_data",
    "normalize_provider_interval",
    "normalize_provider_symbol",
]