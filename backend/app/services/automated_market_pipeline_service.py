"""
Blue-Trading-AI
Version 20 - Automated Market Analysis Pipeline

Part 1:
- Fetch market data automatically.
- Validate candle data.
- Normalize OHLCV candles.
- Protect the analysis engines from invalid data.

Important:
- Analysis and signal generation only.
- No broker connection.
- No automatic trade execution.
"""

from __future__ import annotations

import logging
import math
from datetime import datetime, timezone
from typing import Any, Final

from app.market.provider import get_market_data


logger = logging.getLogger(__name__)

PROJECT_NAME: Final = "Blue-Trading-AI"
SAFETY_VERSION: Final = 20

BROKER_CONNECTION_ENABLED: Final = False
TRADE_EXECUTION_ENABLED: Final = False

SUPPORTED_TIMEFRAMES: Final[frozenset[str]] = frozenset(
    {
        "M5",
        "M15",
        "M30",
        "H1",
        "H4",
        "D1",
        "W1",
        "MN",
    }
)

MINIMUM_REQUIRED_CANDLES: Final = 50
MINIMUM_ALLOWED_CANDLES: Final = 20
MAXIMUM_ALLOWED_CANDLES: Final = 5000
MAX_SYMBOL_LENGTH: Final = 32
MAX_INVALID_CANDLE_DETAILS: Final = 10


def _safe_float(
    value: Any,
    default: float = 0.0,
) -> float:
    """Convert a value to a finite float."""

    try:
        converted = float(value)
    except (TypeError, ValueError, OverflowError):
        return default

    if not math.isfinite(converted):
        return default

    return converted


def _normalize_symbol(
    symbol: str,
) -> str:
    """
    Normalize a market symbol.

    Examples:
    XAU/USD -> XAUUSD
    BTC-USD -> BTCUSD
    GBP_USD -> GBPUSD
    """

    normalized = str(
        symbol or ""
    ).strip().upper()

    for character in (
        "/",
        "-",
        "_",
        " ",
    ):
        normalized = normalized.replace(
            character,
            "",
        )

    return normalized


def _normalize_timeframe(
    timeframe: str,
) -> str:
    """
    Normalize timeframe values.

    Examples:
    15m -> M15
    1h  -> H1
    4h  -> H4
    1d  -> D1
    """

    value = str(
        timeframe or ""
    ).strip().upper()

    timeframe_mapping = {
        "5M": "M5",
        "M5": "M5",
        "15M": "M15",
        "M15": "M15",
        "30M": "M30",
        "M30": "M30",
        "1H": "H1",
        "H1": "H1",
        "4H": "H4",
        "H4": "H4",
        "1D": "D1",
        "D1": "D1",
        "DAILY": "D1",
        "1W": "W1",
        "W1": "W1",
        "WEEKLY": "W1",
        "1MN": "MN",
        "MN": "MN",
        "MONTHLY": "MN",
    }

    return timeframe_mapping.get(
        value,
        value,
    )


def _provider_timeframe(
    timeframe: str,
) -> str:
    """Convert internal timeframes to provider intervals."""

    mapping = {
        "M5": "5min",
        "M15": "15min",
        "M30": "30min",
        "H1": "1h",
        "H4": "4h",
        "D1": "1day",
        "W1": "1week",
        "MN": "1month",
    }

    return mapping.get(
        timeframe,
        timeframe,
    )


def _extract_candle_list(
    market_data: Any,
) -> list[dict[str, Any]]:
    """Extract candles from common provider response formats."""

    if isinstance(
        market_data,
        list,
    ):
        return [
            item
            for item in market_data
            if isinstance(
                item,
                dict,
            )
        ]

    if not isinstance(
        market_data,
        dict,
    ):
        return []

    possible_fields = (
        "candles",
        "data",
        "prices",
        "market_data",
        "results",
        "values",
    )

    for field in possible_fields:
        value = market_data.get(
            field
        )

        if isinstance(
            value,
            list,
        ):
            return [
                item
                for item in value
                if isinstance(
                    item,
                    dict,
                )
            ]

    return []


def _normalize_candle(
    candle: dict[str, Any],
    index: int,
) -> dict[str, Any]:
    """Normalize one OHLCV candle."""

    timestamp = (
        candle.get("timestamp")
        or candle.get("time")
        or candle.get("datetime")
        or candle.get("date")
        or candle.get("t")
        or index
    )

    open_price = _safe_float(
        candle.get(
            "open",
            candle.get("o"),
        )
    )

    high_price = _safe_float(
        candle.get(
            "high",
            candle.get("h"),
        )
    )

    low_price = _safe_float(
        candle.get(
            "low",
            candle.get("l"),
        )
    )

    close_price = _safe_float(
        candle.get(
            "close",
            candle.get("c"),
        )
    )

    volume = _safe_float(
        candle.get(
            "volume",
            candle.get(
                "v",
                0,
            ),
        )
    )

    return {
        "timestamp": timestamp,
        "open": open_price,
        "high": high_price,
        "low": low_price,
        "close": close_price,
        "volume": volume,
    }


def _validate_candle(
    candle: dict[str, Any],
) -> list[str]:
    """Validate one normalized candle and return safe errors."""

    errors: list[str] = []

    open_price = candle["open"]
    high_price = candle["high"]
    low_price = candle["low"]
    close_price = candle["close"]
    volume = candle["volume"]

    if open_price <= 0:
        errors.append(
            "Open price must be greater than zero."
        )

    if high_price <= 0:
        errors.append(
            "High price must be greater than zero."
        )

    if low_price <= 0:
        errors.append(
            "Low price must be greater than zero."
        )

    if close_price <= 0:
        errors.append(
            "Close price must be greater than zero."
        )

    if volume < 0:
        errors.append(
            "Volume cannot be negative."
        )

    if high_price < low_price:
        errors.append(
            "High price cannot be lower than low price."
        )

    if high_price < open_price:
        errors.append(
            "High price cannot be lower than open price."
        )

    if high_price < close_price:
        errors.append(
            "High price cannot be lower than close price."
        )

    if low_price > open_price:
        errors.append(
            "Low price cannot be higher than open price."
        )

    if low_price > close_price:
        errors.append(
            "Low price cannot be higher than close price."
        )

    return errors


def _base_response(
    *,
    status: str,
    symbol: str,
    timeframe: str,
    data_ready: bool,
    blocking_reasons: list[str],
    warnings: list[str],
    provider_interval: str | None = None,
) -> dict[str, Any]:
    response: dict[str, Any] = {
        "status": status,
        "project": PROJECT_NAME,
        "module": (
            "Automated Market Analysis Pipeline"
        ),
        "safety_version": SAFETY_VERSION,
        "symbol": symbol,
        "timeframe": timeframe,
        "data_ready": data_ready,
        "blocking_reasons": blocking_reasons,
        "warnings": warnings,
        "broker_connection_enabled": (
            BROKER_CONNECTION_ENABLED
        ),
        "trade_execution_enabled": (
            TRADE_EXECUTION_ENABLED
        ),
    }

    if provider_interval is not None:
        response["provider_interval"] = (
            provider_interval
        )

    return response


def prepare_automated_market_data(
    *,
    symbol: str,
    timeframe: str,
    minimum_candles: int = MINIMUM_REQUIRED_CANDLES,
) -> dict[str, Any]:
    """
    Fetch, normalize, and validate market data.

    This function prepares trusted candle data for downstream analysis.
    It does not connect to brokers or execute trades.
    """

    normalized_symbol = _normalize_symbol(
        symbol
    )

    normalized_timeframe = _normalize_timeframe(
        timeframe
    )

    blocking_reasons: list[str] = []
    warnings: list[str] = []

    if not normalized_symbol:
        blocking_reasons.append(
            "A valid market symbol is required."
        )
    elif len(
        normalized_symbol
    ) > MAX_SYMBOL_LENGTH:
        blocking_reasons.append(
            "Market symbol is too long."
        )
    elif not normalized_symbol.replace(
        ".",
        "",
    ).isalnum():
        blocking_reasons.append(
            "Market symbol contains unsupported characters."
        )

    if (
        normalized_timeframe
        not in SUPPORTED_TIMEFRAMES
    ):
        blocking_reasons.append(
            (
                "Unsupported timeframe: "
                f"{normalized_timeframe}."
            )
        )

    if isinstance(
        minimum_candles,
        bool,
    ) or not isinstance(
        minimum_candles,
        int,
    ):
        blocking_reasons.append(
            "Minimum candles must be an integer."
        )
    elif (
        minimum_candles
        < MINIMUM_ALLOWED_CANDLES
    ):
        minimum_candles = (
            MINIMUM_ALLOWED_CANDLES
        )
        warnings.append(
            (
                "Minimum candle requirement was "
                f"increased to {MINIMUM_ALLOWED_CANDLES}."
            )
        )
    elif (
        minimum_candles
        > MAXIMUM_ALLOWED_CANDLES
    ):
        blocking_reasons.append(
            (
                "Minimum candle requirement cannot exceed "
                f"{MAXIMUM_ALLOWED_CANDLES}."
            )
        )

    if blocking_reasons:
        return _base_response(
            status="blocked",
            symbol=normalized_symbol,
            timeframe=normalized_timeframe,
            data_ready=False,
            blocking_reasons=blocking_reasons,
            warnings=warnings,
        )

    provider_interval = _provider_timeframe(
        normalized_timeframe
    )

    try:
        raw_market_data = get_market_data(
            normalized_symbol,
            provider_interval,
        )
    except Exception:
        logger.exception(
            "Market-data provider request failed.",
            extra={
                "symbol": normalized_symbol,
                "timeframe": normalized_timeframe,
                "provider_interval": provider_interval,
            },
        )

        return _base_response(
            status="error",
            symbol=normalized_symbol,
            timeframe=normalized_timeframe,
            provider_interval=provider_interval,
            data_ready=False,
            blocking_reasons=[
                "Market data could not be retrieved."
            ],
            warnings=warnings,
        )

    extracted_candles = _extract_candle_list(
        raw_market_data
    )

    if not extracted_candles:
        provider_reported_error = (
            isinstance(
                raw_market_data,
                dict,
            )
            and bool(
                raw_market_data.get(
                    "error"
                )
            )
        )

        blocking_message = (
            "The market-data provider reported an error."
            if provider_reported_error
            else (
                "The market-data provider returned "
                "no candles."
            )
        )

        response = _base_response(
            status="blocked",
            symbol=normalized_symbol,
            timeframe=normalized_timeframe,
            provider_interval=provider_interval,
            data_ready=False,
            blocking_reasons=[
                blocking_message
            ],
            warnings=warnings,
        )

        response["candle_count"] = 0
        return response

    normalized_candles: list[
        dict[str, Any]
    ] = []

    invalid_candles: list[
        dict[str, Any]
    ] = []

    for index, candle in enumerate(
        extracted_candles
    ):
        normalized_candle = _normalize_candle(
            candle,
            index,
        )

        candle_errors = _validate_candle(
            normalized_candle
        )

        if candle_errors:
            invalid_candles.append(
                {
                    "index": index,
                    "timestamp": (
                        normalized_candle[
                            "timestamp"
                        ]
                    ),
                    "errors": candle_errors,
                }
            )
            continue

        normalized_candles.append(
            normalized_candle
        )

    valid_candle_count = len(
        normalized_candles
    )

    invalid_candle_count = len(
        invalid_candles
    )

    if (
        valid_candle_count
        < minimum_candles
    ):
        blocking_reasons.append(
            (
                f"At least {minimum_candles} valid candles "
                "are required, but only "
                f"{valid_candle_count} were available."
            )
        )

    if invalid_candle_count > 0:
        warnings.append(
            (
                f"{invalid_candle_count} invalid candles "
                "were removed."
            )
        )

    latest_candle = (
        normalized_candles[-1]
        if normalized_candles
        else None
    )

    previous_candle = (
        normalized_candles[-2]
        if len(
            normalized_candles
        )
        >= 2
        else None
    )

    if (
        latest_candle is not None
        and previous_candle is not None
    ):
        previous_close = float(
            previous_candle["close"]
        )

        latest_close = float(
            latest_candle["close"]
        )

        price_change = (
            latest_close
            - previous_close
        )

        price_change_percentage = (
            (
                price_change
                / previous_close
            )
            * 100
            if previous_close > 0
            else 0.0
        )
    else:
        price_change = 0.0
        price_change_percentage = 0.0

    data_ready = not blocking_reasons

    return {
        "status": (
            "success"
            if data_ready
            else "blocked"
        ),
        "project": PROJECT_NAME,
        "module": (
            "Automated Market Analysis Pipeline"
        ),
        "safety_version": SAFETY_VERSION,
        "generated_at": datetime.now(
            timezone.utc
        ).isoformat(),
        "symbol": normalized_symbol,
        "timeframe": normalized_timeframe,
        "provider_interval": provider_interval,
        "data_ready": data_ready,
        "minimum_required_candles": (
            minimum_candles
        ),
        "received_candle_count": len(
            extracted_candles
        ),
        "valid_candle_count": (
            valid_candle_count
        ),
        "invalid_candle_count": (
            invalid_candle_count
        ),
        "latest_price": (
            latest_candle["close"]
            if latest_candle
            else None
        ),
        "latest_candle": latest_candle,
        "previous_candle": (
            previous_candle
        ),
        "price_change": round(
            price_change,
            8,
        ),
        "price_change_percentage": round(
            price_change_percentage,
            4,
        ),
        "candles": normalized_candles,
        "invalid_candle_details": (
            invalid_candles[
                :MAX_INVALID_CANDLE_DETAILS
            ]
        ),
        "blocking_reasons": (
            blocking_reasons
        ),
        "warnings": warnings,
        "safety_rules": {
            "minimum_required_candles": (
                minimum_candles
            ),
            "invalid_candles_are_removed": True,
            "empty_market_data_blocks_analysis": True,
            "unsupported_timeframe_blocks_analysis": True,
            "broker_connection_enabled": (
                BROKER_CONNECTION_ENABLED
            ),
            "trade_execution_enabled": (
                TRADE_EXECUTION_ENABLED
            ),
        },
        "important_notice": (
            "Blue-Trading-AI retrieves market data for "
            "analysis only. It does not connect to brokers "
            "or execute trades."
        ),
    }