"""
Smart Money Concept Premium, Equilibrium, and Discount Zone Detection.

The latest trading range is defined using a recent swing high and swing low.

Premium Zone:
Price is above the 50% equilibrium level.
This generally favors SELL setups.

Discount Zone:
Price is below the 50% equilibrium level.
This generally favors BUY setups.

Equilibrium Zone:
Price is near the 50% midpoint.
"""

from __future__ import annotations

import math
from typing import Any, Final, Mapping


MINIMUM_CANDLES: Final[int] = 5
MAXIMUM_CANDLES: Final[int] = 100_000
MAXIMUM_LOOKBACK: Final[int] = 5_000
MAXIMUM_EQUILIBRIUM_TOLERANCE: Final[float] = 0.25


def _default_result(
    status: str = "NO_RANGE",
) -> dict:
    return {
        "detected": False,
        "status": status,
        "zone": "NONE",
        "swing_high": None,
        "swing_low": None,
        "equilibrium": None,
        "premium_start": None,
        "discount_end": None,
        "current_price": None,
        "range_size": None,
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


def _normalise_equilibrium_tolerance(
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

    if not math.isfinite(
        resolved
    ):
        return None

    if not (
        0.0
        <= resolved
        <= MAXIMUM_EQUILIBRIUM_TOLERANCE
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


def detect_premium_discount_zone(
    candles: list,
    lookback: int = 30,
    equilibrium_tolerance: float = 0.05,
) -> dict:
    """
    Detect whether current price is in Premium, Equilibrium, or Discount.

    Args:
        candles:
            OHLC candles ordered from oldest to newest.

        lookback:
            Number of recent candles used to define the trading range.

        equilibrium_tolerance:
            Percentage of the total range treated as the equilibrium band.
            Default 0.05 means 5% above and below the midpoint.

    Returns:
        Trading range and current zone information.
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
    resolved_tolerance = (
        _normalise_equilibrium_tolerance(
            equilibrium_tolerance
        )
    )

    current_price = float(
        resolved_candles[
            -1
        ][
            "close"
        ]
    )

    if (
        resolved_lookback is None
        or resolved_tolerance is None
    ):
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

    equilibrium = (
        swing_low
        + (
            range_size
            * 0.5
        )
    )

    tolerance_value = (
        range_size
        * resolved_tolerance
    )

    equilibrium_low = (
        equilibrium
        - tolerance_value
    )
    equilibrium_high = (
        equilibrium
        + tolerance_value
    )

    if (
        not all(
            math.isfinite(
                value
            )
            for value in (
                equilibrium,
                equilibrium_low,
                equilibrium_high,
            )
        )
        or equilibrium_low <= 0.0
    ):
        result = _default_result(
            "INVALID_RANGE"
        )
        result[
            "current_price"
        ] = current_price

        return result

    if (
        current_price
        > equilibrium_high
    ):
        zone = "PREMIUM"

    elif (
        current_price
        < equilibrium_low
    ):
        zone = "DISCOUNT"

    else:
        zone = "EQUILIBRIUM"

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

    return {
        "detected": True,
        "status": "ACTIVE",
        "zone": zone,
        "swing_high": swing_high,
        "swing_low": swing_low,
        "equilibrium": equilibrium,
        "premium_start": (
            equilibrium_high
        ),
        "discount_end": (
            equilibrium_low
        ),
        "current_price": (
            current_price
        ),
        "range_size": round(
            range_size,
            5,
        ),
        "position_percent": round(
            position_percent,
            2,
        ),
        "high_index": high_index,
        "low_index": low_index,
    }


__all__ = [
    "MAXIMUM_CANDLES",
    "MAXIMUM_EQUILIBRIUM_TOLERANCE",
    "MAXIMUM_LOOKBACK",
    "MINIMUM_CANDLES",
    "detect_premium_discount_zone",
]