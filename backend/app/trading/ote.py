"""
Smart Money Concept Optimal Trade Entry (OTE) Detection.

OTE is commonly measured using the 62% to 79% Fibonacci retracement zone
of the latest significant dealing range.

Bullish OTE:
Price retraces into the 62%–79% discount area of a bullish range.

Bearish OTE:
Price retraces into the 62%–79% premium area of a bearish range.

Candles must be ordered from oldest to newest.
"""

from __future__ import annotations

import math
from typing import Any, Final, Mapping


MINIMUM_CANDLES: Final[int] = 5
MAXIMUM_CANDLES: Final[int] = 100_000
MAXIMUM_LOOKBACK: Final[int] = 5_000

FIBONACCI_62: Final[float] = 0.62
FIBONACCI_705: Final[float] = 0.705
FIBONACCI_79: Final[float] = 0.79


def _default_result(
    status: str = "NO_OTE",
) -> dict:
    return {
        "detected": False,
        "status": status,
        "direction": "NONE",
        "swing_high": None,
        "swing_low": None,
        "range_direction": "NONE",
        "ote_zone_high": None,
        "ote_zone_low": None,
        "fib_62": None,
        "fib_705": None,
        "fib_79": None,
        "current_price": None,
        "price_inside_zone": False,
        "position_percent": None,
        "high_index": None,
        "low_index": None,
    }


def _finite_positive_float(
    value: Any,
) -> float | None:
    try:
        resolved = float(
            value
        )
    except (
        TypeError,
        ValueError,
        OverflowError,
    ):
        return None

    if (
        not math.isfinite(
            resolved
        )
        or resolved <= 0.0
    ):
        return None

    return resolved


def _normalise_lookback(
    value: Any,
) -> int | None:
    if isinstance(
        value,
        bool,
    ):
        return None

    try:
        resolved = int(
            value
        )
    except (
        TypeError,
        ValueError,
        OverflowError,
    ):
        return None

    if not (
        1
        <= resolved
        <= MAXIMUM_LOOKBACK
    ):
        return None

    return resolved


def _normalise_candle(
    candle: Any,
) -> dict[str, float] | None:
    if not isinstance(
        candle,
        Mapping,
    ):
        return None

    required_fields = (
        "open",
        "high",
        "low",
        "close",
    )

    resolved: dict[
        str,
        float,
    ] = {}

    for field in required_fields:
        value = _finite_positive_float(
            candle.get(
                field
            )
        )

        if value is None:
            return None

        resolved[
            field
        ] = value

    candle_high = resolved[
        "high"
    ]
    candle_low = resolved[
        "low"
    ]
    candle_open = resolved[
        "open"
    ]
    candle_close = resolved[
        "close"
    ]

    if candle_high < candle_low:
        return None

    if not (
        candle_low
        <= candle_open
        <= candle_high
    ):
        return None

    if not (
        candle_low
        <= candle_close
        <= candle_high
    ):
        return None

    return resolved


def _normalise_candles(
    candles: Any,
) -> list[dict[str, float]]:
    if not isinstance(
        candles,
        (list, tuple),
    ):
        return []

    if len(
        candles
    ) > MAXIMUM_CANDLES:
        return []

    output: list[
        dict[str, float]
    ] = []

    for candle in candles:
        resolved = _normalise_candle(
            candle
        )

        if resolved is None:
            return []

        output.append(
            resolved
        )

    return output


def _valid_candle(
    candle: object,
) -> bool:
    return (
        _normalise_candle(
            candle
        )
        is not None
    )


def detect_optimal_trade_entry(
    candles: list,
    lookback: int = 30,
) -> dict:
    """
    Detect whether current price is inside a bullish or bearish OTE zone.

    Args:
        candles:
            OHLC candles ordered from oldest to newest.

        lookback:
            Number of recent candles used to define the range.

    Returns:
        OTE zone and current-price relationship.
    """

    if not isinstance(
        candles,
        (list, tuple),
    ):
        return _default_result(
            "INSUFFICIENT_OHLC_DATA"
        )

    if len(
        candles
    ) < MINIMUM_CANDLES:
        return _default_result(
            "INSUFFICIENT_DATA"
        )

    resolved_candles = (
        _normalise_candles(
            candles
        )
    )

    if not resolved_candles:
        return _default_result(
            "INSUFFICIENT_OHLC_DATA"
        )

    resolved_lookback = (
        _normalise_lookback(
            lookback
        )
    )

    current_price = float(
        resolved_candles[
            -1
        ][
            "close"
        ]
    )

    if resolved_lookback is None:
        result = _default_result(
            "INVALID_CONFIGURATION"
        )
        result[
            "current_price"
        ] = current_price

        return result

    selected = (
        resolved_candles[
            -resolved_lookback:
        ]
        if resolved_lookback
        < len(
            resolved_candles
        )
        else resolved_candles
    )

    if not selected:
        result = _default_result(
            "INVALID_RANGE"
        )
        result[
            "current_price"
        ] = current_price

        return result

    offset = (
        len(
            resolved_candles
        )
        - len(
            selected
        )
    )

    high_relative_index = max(
        range(
            len(
                selected
            )
        ),
        key=lambda index: (
            selected[
                index
            ][
                "high"
            ]
        ),
    )

    low_relative_index = min(
        range(
            len(
                selected
            )
        ),
        key=lambda index: (
            selected[
                index
            ][
                "low"
            ]
        ),
    )

    high_index = (
        offset
        + high_relative_index
    )
    low_index = (
        offset
        + low_relative_index
    )

    swing_high = float(
        resolved_candles[
            high_index
        ][
            "high"
        ]
    )
    swing_low = float(
        resolved_candles[
            low_index
        ][
            "low"
        ]
    )

    range_size = (
        swing_high
        - swing_low
    )

    if (
        not math.isfinite(
            range_size
        )
        or range_size <= 0.0
    ):
        result = _default_result(
            "INVALID_RANGE"
        )
        result[
            "current_price"
        ] = current_price

        return result

    if low_index < high_index:
        range_direction = (
            "BULLISH_RANGE"
        )

        fib_62 = (
            swing_high
            - (
                range_size
                * FIBONACCI_62
            )
        )
        fib_705 = (
            swing_high
            - (
                range_size
                * FIBONACCI_705
            )
        )
        fib_79 = (
            swing_high
            - (
                range_size
                * FIBONACCI_79
            )
        )

        ote_zone_high = (
            fib_62
        )
        ote_zone_low = (
            fib_79
        )
        direction = (
            "BULLISH_OTE"
        )

    elif high_index < low_index:
        range_direction = (
            "BEARISH_RANGE"
        )

        fib_62 = (
            swing_low
            + (
                range_size
                * FIBONACCI_62
            )
        )
        fib_705 = (
            swing_low
            + (
                range_size
                * FIBONACCI_705
            )
        )
        fib_79 = (
            swing_low
            + (
                range_size
                * FIBONACCI_79
            )
        )

        ote_zone_high = (
            fib_79
        )
        ote_zone_low = (
            fib_62
        )
        direction = (
            "BEARISH_OTE"
        )

    else:
        result = _default_result(
            "UNDEFINED_RANGE_DIRECTION"
        )
        result[
            "current_price"
        ] = current_price

        return result

    calculated_values = (
        fib_62,
        fib_705,
        fib_79,
        ote_zone_high,
        ote_zone_low,
    )

    if (
        not all(
            math.isfinite(
                value
            )
            and value > 0.0
            for value in calculated_values
        )
        or ote_zone_low
        > ote_zone_high
    ):
        result = _default_result(
            "INVALID_OTE_ZONE"
        )
        result[
            "current_price"
        ] = current_price

        return result

    price_inside_zone = (
        ote_zone_low
        <= current_price
        <= ote_zone_high
    )

    position_percent = (
        (
            current_price
            - swing_low
        )
        / range_size
    ) * 100.0

    if not math.isfinite(
        position_percent
    ):
        result = _default_result(
            "INVALID_RANGE"
        )
        result[
            "current_price"
        ] = current_price

        return result

    status = (
        "ACTIVE"
        if price_inside_zone
        else "OUTSIDE_OTE"
    )

    return {
        "detected": True,
        "status": status,
        "direction": direction,
        "swing_high": swing_high,
        "swing_low": swing_low,
        "range_direction": (
            range_direction
        ),
        "ote_zone_high": (
            ote_zone_high
        ),
        "ote_zone_low": (
            ote_zone_low
        ),
        "fib_62": fib_62,
        "fib_705": fib_705,
        "fib_79": fib_79,
        "current_price": (
            current_price
        ),
        "price_inside_zone": (
            price_inside_zone
        ),
        "position_percent": round(
            position_percent,
            2,
        ),
        "high_index": high_index,
        "low_index": low_index,
    }


__all__ = [
    "FIBONACCI_62",
    "FIBONACCI_705",
    "FIBONACCI_79",
    "MAXIMUM_CANDLES",
    "MAXIMUM_LOOKBACK",
    "MINIMUM_CANDLES",
    "detect_optimal_trade_entry",
]