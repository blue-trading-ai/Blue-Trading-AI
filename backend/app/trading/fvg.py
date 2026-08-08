"""
Smart Money Concept Fair Value Gap Detection.

Bullish FVG:
The third candle's low is above the first candle's high.

Bearish FVG:
The third candle's high is below the first candle's low.

Candles must be ordered from oldest to newest.
"""

from __future__ import annotations

import math
from typing import Any, Final, Mapping


MINIMUM_CANDLES: Final[int] = 3
MAXIMUM_CANDLES: Final[int] = 100_000
MAXIMUM_LOOKBACK: Final[int] = 5_000
MAXIMUM_MINIMUM_GAP: Final[float] = 1_000_000.0


def _default_result(
    status: str = "NO_FVG",
) -> dict:
    return {
        "detected": False,
        "direction": "NONE",
        "status": status,
        "zone_high": None,
        "zone_low": None,
        "gap_size": None,
        "candle_index": None,
        "filled": False,
        "price_inside_zone": False,
        "current_price": None,
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
        MINIMUM_CANDLES
        <= resolved
        <= MAXIMUM_LOOKBACK
    ):
        return None

    return resolved


def _normalise_minimum_gap(
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

    if (
        resolved < 0.0
        or resolved
        > MAXIMUM_MINIMUM_GAP
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


def detect_fair_value_gap(
    candles: list,
    lookback: int = 30,
    minimum_gap: float = 0.0,
) -> dict:
    """
    Detect the most recent Fair Value Gap.

    Args:
        candles:
            OHLC candles ordered from oldest to newest.

        lookback:
            Maximum recent candles to scan.

        minimum_gap:
            Minimum price distance required for the gap.

    Returns:
        Details of the most recent bullish or bearish FVG.
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
    resolved_minimum_gap = (
        _normalise_minimum_gap(
            minimum_gap
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
        or resolved_minimum_gap is None
    ):
        result = _default_result(
            "INVALID_CONFIGURATION"
        )
        result[
            "current_price"
        ] = current_price

        return result

    start_index = max(
        2,
        len(
            resolved_candles
        )
        - resolved_lookback,
    )

    detected_gaps: list[
        dict[str, Any]
    ] = []

    for index in range(
        start_index,
        len(
            resolved_candles
        ),
    ):
        candle_1 = (
            resolved_candles[
                index - 2
            ]
        )
        candle_3 = (
            resolved_candles[
                index
            ]
        )

        candle_1_high = float(
            candle_1[
                "high"
            ]
        )
        candle_1_low = float(
            candle_1[
                "low"
            ]
        )
        candle_3_high = float(
            candle_3[
                "high"
            ]
        )
        candle_3_low = float(
            candle_3[
                "low"
            ]
        )

        bullish_gap_size = (
            candle_3_low
            - candle_1_high
        )

        if (
            math.isfinite(
                bullish_gap_size
            )
            and bullish_gap_size
            > resolved_minimum_gap
        ):
            detected_gaps.append(
                {
                    "direction": (
                        "BULLISH_FVG"
                    ),
                    "zone_high": (
                        candle_3_low
                    ),
                    "zone_low": (
                        candle_1_high
                    ),
                    "gap_size": (
                        bullish_gap_size
                    ),
                    "candle_index": (
                        index
                    ),
                }
            )

        bearish_gap_size = (
            candle_1_low
            - candle_3_high
        )

        if (
            math.isfinite(
                bearish_gap_size
            )
            and bearish_gap_size
            > resolved_minimum_gap
        ):
            detected_gaps.append(
                {
                    "direction": (
                        "BEARISH_FVG"
                    ),
                    "zone_high": (
                        candle_1_low
                    ),
                    "zone_low": (
                        candle_3_high
                    ),
                    "gap_size": (
                        bearish_gap_size
                    ),
                    "candle_index": (
                        index
                    ),
                }
            )

    if not detected_gaps:
        result = _default_result()
        result[
            "current_price"
        ] = current_price

        return result

    latest_gap = (
        detected_gaps[
            -1
        ]
    )

    direction = str(
        latest_gap[
            "direction"
        ]
    )
    zone_high = float(
        latest_gap[
            "zone_high"
        ]
    )
    zone_low = float(
        latest_gap[
            "zone_low"
        ]
    )
    gap_index = int(
        latest_gap[
            "candle_index"
        ]
    )
    gap_size = float(
        latest_gap[
            "gap_size"
        ]
    )

    if (
        not math.isfinite(
            zone_high
        )
        or not math.isfinite(
            zone_low
        )
        or not math.isfinite(
            gap_size
        )
        or zone_low <= 0.0
        or zone_high <= 0.0
        or zone_low > zone_high
        or gap_size <= 0.0
    ):
        result = _default_result(
            "INVALID_GAP"
        )
        result[
            "current_price"
        ] = current_price

        return result

    later_candles = (
        resolved_candles[
            gap_index + 1:
        ]
    )

    filled = False

    if direction == "BULLISH_FVG":
        filled = any(
            candle[
                "low"
            ]
            <= zone_low
            for candle in later_candles
        )

    elif direction == "BEARISH_FVG":
        filled = any(
            candle[
                "high"
            ]
            >= zone_high
            for candle in later_candles
        )

    else:
        result = _default_result(
            "INVALID_GAP_DIRECTION"
        )
        result[
            "current_price"
        ] = current_price

        return result

    price_inside_zone = (
        zone_low
        <= current_price
        <= zone_high
    )

    status = (
        "FILLED"
        if filled
        else "ACTIVE"
    )

    return {
        "detected": True,
        "direction": direction,
        "status": status,
        "zone_high": zone_high,
        "zone_low": zone_low,
        "gap_size": round(
            gap_size,
            5,
        ),
        "candle_index": gap_index,
        "filled": filled,
        "price_inside_zone": (
            price_inside_zone
        ),
        "current_price": (
            current_price
        ),
    }


__all__ = [
    "MAXIMUM_CANDLES",
    "MAXIMUM_LOOKBACK",
    "MAXIMUM_MINIMUM_GAP",
    "MINIMUM_CANDLES",
    "detect_fair_value_gap",
]