"""
Market Structure Detection

Detects:
- Higher High (HH)
- Higher Low (HL)
- Lower High (LH)
- Lower Low (LL)

Returns:
- HH-HL
- LH-LL
- MIXED
- RANGE
"""

from __future__ import annotations

import math
from typing import Any, Final


MAXIMUM_PRICE_POINTS: Final[int] = 100_000
MAXIMUM_LOOKBACK: Final[int] = 100


def _normalise_lookback(
    lookback: Any,
) -> int:
    if isinstance(
        lookback,
        bool,
    ):
        raise ValueError(
            "lookback must be an integer."
        )

    try:
        resolved = int(
            lookback
        )
    except (
        TypeError,
        ValueError,
        OverflowError,
    ) as exc:
        raise ValueError(
            "lookback must be an integer."
        ) from exc

    if resolved < 1:
        raise ValueError(
            "lookback must be at least 1."
        )

    if resolved > MAXIMUM_LOOKBACK:
        raise ValueError(
            "lookback exceeds the supported safety limit."
        )

    return resolved


def _normalise_prices(
    prices: Any,
) -> list[float]:
    if not isinstance(
        prices,
        (list, tuple),
    ):
        return []

    if len(
        prices
    ) > MAXIMUM_PRICE_POINTS:
        return []

    output: list[
        float
    ] = []

    for value in prices:
        try:
            resolved = float(
                value
            )
        except (
            TypeError,
            ValueError,
            OverflowError,
        ):
            return []

        if (
            not math.isfinite(
                resolved
            )
            or resolved <= 0.0
        ):
            return []

        output.append(
            resolved
        )

    return output


def find_swings(
    prices: list,
    lookback: int = 2,
) -> tuple:
    swing_highs: list[
        dict[str, Any]
    ] = []
    swing_lows: list[
        dict[str, Any]
    ] = []

    try:
        resolved_lookback = (
            _normalise_lookback(
                lookback
            )
        )
    except ValueError:
        return (
            swing_highs,
            swing_lows,
        )

    resolved_prices = (
        _normalise_prices(
            prices
        )
    )

    minimum_required = (
        resolved_lookback * 2
    ) + 1

    if len(
        resolved_prices
    ) < minimum_required:
        return (
            swing_highs,
            swing_lows,
        )

    for index in range(
        resolved_lookback,
        len(
            resolved_prices
        )
        - resolved_lookback,
    ):
        current_price = (
            resolved_prices[
                index
            ]
        )

        left_prices = (
            resolved_prices[
                index
                - resolved_lookback:
                index
            ]
        )

        right_prices = (
            resolved_prices[
                index + 1:
                index
                + resolved_lookback
                + 1
            ]
        )

        if (
            current_price
            > max(
                left_prices
            )
            and current_price
            > max(
                right_prices
            )
        ):
            swing_highs.append(
                {
                    "index": index,
                    "price": current_price,
                }
            )

        if (
            current_price
            < min(
                left_prices
            )
            and current_price
            < min(
                right_prices
            )
        ):
            swing_lows.append(
                {
                    "index": index,
                    "price": current_price,
                }
            )

    return (
        swing_highs,
        swing_lows,
    )


def detect_market_structure(
    prices: list,
    lookback: int = 2,
) -> dict:
    default_result = {
        "structure": "RANGE",
        "trend": "RANGE",
        "HH": False,
        "HL": False,
        "LH": False,
        "LL": False,
        "last_high": None,
        "previous_high": None,
        "last_low": None,
        "previous_low": None,
        "swing_highs": [],
        "swing_lows": [],
    }

    try:
        resolved_lookback = (
            _normalise_lookback(
                lookback
            )
        )
    except ValueError:
        return default_result

    resolved_prices = (
        _normalise_prices(
            prices
        )
    )

    minimum_required = (
        resolved_lookback * 2
    ) + 1

    if len(
        resolved_prices
    ) < minimum_required:
        return default_result

    swing_highs, swing_lows = (
        find_swings(
            resolved_prices,
            resolved_lookback,
        )
    )

    default_result[
        "swing_highs"
    ] = swing_highs
    default_result[
        "swing_lows"
    ] = swing_lows

    if (
        len(
            swing_highs
        ) < 2
        or len(
            swing_lows
        ) < 2
    ):
        return default_result

    previous_high = float(
        swing_highs[
            -2
        ][
            "price"
        ]
    )
    last_high = float(
        swing_highs[
            -1
        ][
            "price"
        ]
    )

    previous_low = float(
        swing_lows[
            -2
        ][
            "price"
        ]
    )
    last_low = float(
        swing_lows[
            -1
        ][
            "price"
        ]
    )

    is_higher_high = (
        last_high
        > previous_high
    )
    is_lower_high = (
        last_high
        < previous_high
    )

    is_higher_low = (
        last_low
        > previous_low
    )
    is_lower_low = (
        last_low
        < previous_low
    )

    structure = "MIXED"
    trend = "RANGE"

    if (
        is_higher_high
        and is_higher_low
    ):
        structure = "HH-HL"
        trend = "UPTREND"

    elif (
        is_lower_high
        and is_lower_low
    ):
        structure = "LH-LL"
        trend = "DOWNTREND"

    return {
        "structure": structure,
        "trend": trend,
        "HH": is_higher_high,
        "HL": is_higher_low,
        "LH": is_lower_high,
        "LL": is_lower_low,
        "last_high": last_high,
        "previous_high": (
            previous_high
        ),
        "last_low": last_low,
        "previous_low": (
            previous_low
        ),
        "swing_highs": swing_highs,
        "swing_lows": swing_lows,
    }


__all__ = [
    "MAXIMUM_LOOKBACK",
    "MAXIMUM_PRICE_POINTS",
    "detect_market_structure",
    "find_swings",
]