"""
Blue-Trading-AI
Version 20 - Automated Multi-Timeframe Market Pipeline

Responsibilities:
- Retrieve multiple market timeframes automatically.
- Validate each timeframe independently.
- Reuse the existing automated market-data pipeline.
- Combine all timeframe results into one trusted package.
- Block incomplete or invalid market datasets safely.

Important:
- Analysis and signal generation only.
- No broker connection.
- No automatic trade execution.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, Final, List, Optional

from app.services.automated_market_pipeline_service import (
    MINIMUM_REQUIRED_CANDLES,
    prepare_automated_market_data,
)


PROJECT_NAME: Final = "Blue-Trading-AI"
SAFETY_VERSION: Final = 20
MODULE_NAME: Final = "Automated Multi-Timeframe Market Pipeline"

BROKER_CONNECTION_ENABLED: Final = False
TRADE_EXECUTION_ENABLED: Final = False

MAXIMUM_SYMBOL_LENGTH: Final = 30
MINIMUM_CANDLES_FLOOR: Final = 20
MAXIMUM_CANDLES_LIMIT: Final = 5000
MAXIMUM_TIMEFRAME_COUNT: Final = 8


DEFAULT_TIMEFRAMES = [
    "M15",
    "M30",
    "H1",
    "H4",
    "D1",
]


SUPPORTED_TIMEFRAMES = {
    "M5",
    "M15",
    "M30",
    "H1",
    "H4",
    "D1",
    "W1",
    "MN",
}


TIMEFRAME_ORDER = {
    "M5": 1,
    "M15": 2,
    "M30": 3,
    "H1": 4,
    "H4": 5,
    "D1": 6,
    "W1": 7,
    "MN": 8,
}


def _normalize_symbol(symbol: str) -> str:
    """
    Normalize symbols into Blue-Trading-AI format.

    Examples:
        XAU/USD -> XAUUSD
        BTC-USD -> BTCUSD
        GBP_USD -> GBPUSD
    """

    normalized = str(symbol or "").strip().upper()

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

    if not normalized:
        return ""

    if len(normalized) > MAXIMUM_SYMBOL_LENGTH:
        return ""

    if not normalized.isalnum():
        return ""

    return normalized


def _normalize_timeframe(timeframe: str) -> str:
    """
    Normalize timeframe aliases.

    Examples:
        15m   -> M15
        1h    -> H1
        daily -> D1
    """

    value = str(timeframe or "").strip().upper()

    mapping = {
        "5M": "M5",
        "M5": "M5",
        "5MIN": "M5",

        "15M": "M15",
        "M15": "M15",
        "15MIN": "M15",

        "30M": "M30",
        "M30": "M30",
        "30MIN": "M30",

        "1H": "H1",
        "H1": "H1",

        "4H": "H4",
        "H4": "H4",

        "1D": "D1",
        "D1": "D1",
        "DAY": "D1",
        "DAILY": "D1",

        "1W": "W1",
        "W1": "W1",
        "WEEK": "W1",
        "WEEKLY": "W1",

        "1MN": "MN",
        "1MO": "MN",
        "MN": "MN",
        "MONTH": "MN",
        "MONTHLY": "MN",
    }

    normalized = mapping.get(
        value,
        value,
    )

    if normalized not in SUPPORTED_TIMEFRAMES:
        return ""

    return normalized


def _normalize_timeframes(
    timeframes: Optional[List[str]],
) -> List[str]:
    """
    Normalize, remove duplicates, validate, and sort
    requested timeframes.
    """

    requested_timeframes = (
        timeframes
        if timeframes
        else DEFAULT_TIMEFRAMES
    )

    normalized_timeframes: List[str] = []

    for timeframe in list(
        requested_timeframes
    )[:MAXIMUM_TIMEFRAME_COUNT]:
        normalized = _normalize_timeframe(
            timeframe
        )

        if normalized not in SUPPORTED_TIMEFRAMES:
            continue

        if normalized in normalized_timeframes:
            continue

        normalized_timeframes.append(
            normalized
        )

    normalized_timeframes.sort(
        key=lambda item: TIMEFRAME_ORDER.get(
            item,
            999,
        )
    )

    return normalized_timeframes


def _safe_bool(
    value: Any,
    default: bool = False,
) -> bool:
    if isinstance(value, bool):
        return value

    if isinstance(value, (int, float)) and not isinstance(value, bool):
        if value == 1:
            return True
        if value == 0:
            return False
        return default

    if isinstance(value, str):
        normalized = value.strip().lower()

        if normalized in {
            "true",
            "1",
            "yes",
            "ready",
            "approved",
            "pass",
            "passed",
        }:
            return True

        if normalized in {
            "false",
            "0",
            "no",
            "blocked",
            "rejected",
            "fail",
            "failed",
        }:
            return False

    return default


def _safe_int(
    value: Any,
    default: int = 0,
) -> int:
    if isinstance(value, bool):
        return default

    try:
        number = int(value)
    except (TypeError, ValueError, OverflowError):
        return default

    return max(
        0,
        min(
            number,
            MAXIMUM_CANDLES_LIMIT,
        ),
    )


def _build_timeframe_summary(
    timeframe: str,
    result: Dict[str, Any],
) -> Dict[str, Any]:
    """
    Create a compact summary for one timeframe.
    """

    if not isinstance(
        result,
        dict,
    ):
        result = {}

    data_ready = _safe_bool(
        result.get(
            "data_ready",
            False,
        )
    )

    return {
        "timeframe": timeframe,
        "ready": data_ready,
        "status": result.get(
            "status",
            "unknown",
        ),
        "provider_interval": result.get(
            "provider_interval"
        ),
        "received_candle_count": _safe_int(
            result.get(
                "received_candle_count",
                result.get(
                    "candle_count",
                    0,
                ),
            )
        ),
        "valid_candle_count": _safe_int(
            result.get(
                "valid_candle_count",
                0,
            )
        ),
        "invalid_candle_count": _safe_int(
            result.get(
                "invalid_candle_count",
                0,
            )
        ),
        "latest_price": result.get(
            "latest_price"
        ),
        "price_change": result.get(
            "price_change"
        ),
        "price_change_percentage": result.get(
            "price_change_percentage"
        ),
        "blocking_reasons": result.get(
            "blocking_reasons",
            [],
        ),
        "warnings": result.get(
            "warnings",
            [],
        ),
    }


def prepare_multi_timeframe_market_data(
    *,
    symbol: str,
    timeframes: Optional[List[str]] = None,
    minimum_candles: int = MINIMUM_REQUIRED_CANDLES,
    require_all_timeframes: bool = True,
) -> Dict[str, Any]:
    """
    Retrieve and prepare multiple market timeframes.

    Each timeframe is processed independently using the
    existing automated market-data preparation service.

    Args:
        symbol:
            Market symbol such as XAUUSD or BTCUSD.

        timeframes:
            Requested timeframes. Defaults to:
            M15, M30, H1, H4, D1.

        minimum_candles:
            Minimum number of valid candles required for
            each timeframe.

        require_all_timeframes:
            When True, every requested timeframe must be
            ready before overall_ready becomes True.

            When False, at least one valid timeframe is
            enough for overall_ready to become True.
    """

    normalized_symbol = _normalize_symbol(
        symbol
    )

    normalized_timeframes = _normalize_timeframes(
        timeframes
    )

    require_all_timeframes = _safe_bool(
        require_all_timeframes,
        default=True,
    )

    blocking_reasons: List[str] = []
    warnings: List[str] = []

    if not normalized_symbol:
        blocking_reasons.append(
            "A valid market symbol is required."
        )

    if not normalized_timeframes:
        blocking_reasons.append(
            "At least one supported timeframe is required."
        )

    try:
        minimum_candles = int(
            minimum_candles
        )
    except (TypeError, ValueError):
        minimum_candles = (
            MINIMUM_REQUIRED_CANDLES
        )

        warnings.append(
            "Invalid minimum candle value was replaced "
            f"with {MINIMUM_REQUIRED_CANDLES}."
        )

    if minimum_candles < 20:
        minimum_candles = 20

        warnings.append(
            "Minimum candle requirement was increased "
            "to 20."
        )

    if blocking_reasons:
        return {
            "status": "blocked",
            "project": PROJECT_NAME,
            "module": MODULE_NAME,
            "safety_version": SAFETY_VERSION,
            "generated_at": datetime.now(
                timezone.utc
            ).isoformat(),
            "symbol": normalized_symbol,
            "requested_timeframes": (
                normalized_timeframes
            ),
            "minimum_required_candles": (
                minimum_candles
            ),
            "require_all_timeframes": (
                require_all_timeframes
            ),
            "overall_ready": False,
            "timeframes": {},
            "blocking_reasons": blocking_reasons,
            "warnings": warnings,
            "broker_connection_enabled": False,
            "trade_execution_enabled": False,
        }

    timeframe_results: Dict[
        str,
        Dict[str, Any],
    ] = {}

    timeframe_summaries: Dict[
        str,
        Dict[str, Any],
    ] = {}

    ready_timeframes: List[str] = []
    blocked_timeframes: List[str] = []
    error_timeframes: List[str] = []

    for timeframe in normalized_timeframes:
        try:
            result = prepare_automated_market_data(
                symbol=normalized_symbol,
                timeframe=timeframe,
                minimum_candles=minimum_candles,
            )

            if not isinstance(
                result,
                dict,
            ):
                result = {
                    "status": "error",
                    "project": PROJECT_NAME,
                    "module": MODULE_NAME,
                    "safety_version": SAFETY_VERSION,
                    "symbol": normalized_symbol,
                    "timeframe": timeframe,
                    "data_ready": False,
                    "blocking_reasons": [
                        "Automated market-data service returned an invalid response."
                    ],
                    "warnings": [],
                    "broker_connection_enabled": False,
                    "trade_execution_enabled": False,
                }

        except Exception:
            result = {
                "status": "error",
                "project": PROJECT_NAME,
                "module": MODULE_NAME,
                "safety_version": SAFETY_VERSION,
                "symbol": normalized_symbol,
                "timeframe": timeframe,
                "data_ready": False,
                "blocking_reasons": [
                    "Unexpected timeframe processing error."
                ],
                "warnings": [],
                "broker_connection_enabled": False,
                "trade_execution_enabled": False,
            }

        timeframe_results[timeframe] = result

        summary = _build_timeframe_summary(
            timeframe,
            result,
        )

        timeframe_summaries[timeframe] = (
            summary
        )

        if summary["ready"]:
            ready_timeframes.append(
                timeframe
            )

        else:
            blocked_timeframes.append(
                timeframe
            )

            if summary["status"] == "error":
                error_timeframes.append(
                    timeframe
                )

    requested_count = len(
        normalized_timeframes
    )

    ready_count = len(
        ready_timeframes
    )

    blocked_count = len(
        blocked_timeframes
    )

    if require_all_timeframes:
        overall_ready = (
            requested_count > 0
            and ready_count == requested_count
        )

    else:
        overall_ready = ready_count > 0

    if not overall_ready:
        if require_all_timeframes:
            blocking_reasons.append(
                (
                    "Not all requested timeframes passed "
                    "market-data validation."
                )
            )

        else:
            blocking_reasons.append(
                (
                    "None of the requested timeframes "
                    "passed market-data validation."
                )
            )

    if blocked_timeframes:
        warnings.append(
            (
                f"{blocked_count} timeframe(s) were "
                "not ready."
            )
        )

    blocking_reasons = list(
        dict.fromkeys(
            blocking_reasons
        )
    )
    warnings = list(
        dict.fromkeys(
            warnings
        )
    )

    status = (
        "success"
        if overall_ready
        else "blocked"
    )

    return {
        "status": status,
        "project": PROJECT_NAME,
        "module": MODULE_NAME,
        "safety_version": SAFETY_VERSION,
        "generated_at": datetime.now(
            timezone.utc
        ).isoformat(),
        "symbol": normalized_symbol,
        "requested_timeframes": list(
            normalized_timeframes
        ),
        "minimum_required_candles": (
            minimum_candles
        ),
        "require_all_timeframes": (
            require_all_timeframes
        ),
        "overall_ready": overall_ready,
        "requested_timeframe_count": (
            requested_count
        ),
        "ready_timeframe_count": (
            ready_count
        ),
        "blocked_timeframe_count": (
            blocked_count
        ),
        "ready_timeframes": ready_timeframes,
        "blocked_timeframes": (
            blocked_timeframes
        ),
        "error_timeframes": error_timeframes,
        "timeframe_summary": (
            timeframe_summaries
        ),
        "timeframes": timeframe_results,
        "blocking_reasons": (
            blocking_reasons
        ),
        "warnings": warnings,
        "safety_rules": {
            "each_timeframe_is_validated": True,
            "invalid_candles_are_removed": True,
            "empty_data_blocks_timeframe": True,
            "minimum_required_candles": (
                minimum_candles
            ),
            "require_all_timeframes": (
                require_all_timeframes
            ),
            "broker_connection_enabled": (
                BROKER_CONNECTION_ENABLED
            ),
            "trade_execution_enabled": (
                TRADE_EXECUTION_ENABLED
            ),
        },
        "important_notice": (
            "Blue-Trading-AI retrieves multi-timeframe "
            "market data for analysis only. It does not "
            "connect to brokers or execute trades."
        ),
    }

__all__ = [
    "BROKER_CONNECTION_ENABLED",
    "DEFAULT_TIMEFRAMES",
    "MAXIMUM_CANDLES_LIMIT",
    "MAXIMUM_TIMEFRAME_COUNT",
    "MINIMUM_CANDLES_FLOOR",
    "MODULE_NAME",
    "PROJECT_NAME",
    "SAFETY_VERSION",
    "SUPPORTED_TIMEFRAMES",
    "TIMEFRAME_ORDER",
    "TRADE_EXECUTION_ENABLED",
    "prepare_multi_timeframe_market_data",
]