from __future__ import annotations

import math
from typing import Any, Final


MINIMUM_PATTERN_PRICES: Final[int] = 20
DOUBLE_PATTERN_TOLERANCE: Final[float] = 0.002
MAXIMUM_PRICE_POINTS: Final[int] = 100_000


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


def _safe_positive_float(
    value: Any,
) -> float | None:
    if value is None:
        return None

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


def detect_double_bottom(
    prices,
):
    resolved_prices = _normalise_prices(
        prices
    )

    if len(
        resolved_prices
    ) < MINIMUM_PATTERN_PRICES:
        return False

    first_low = min(
        resolved_prices[:10]
    )
    second_low = min(
        resolved_prices[10:]
    )

    if first_low <= 0.0:
        return False

    difference = abs(
        first_low
        - second_low
    )

    return (
        difference
        / first_low
        < DOUBLE_PATTERN_TOLERANCE
    )


def detect_double_top(
    prices,
):
    resolved_prices = _normalise_prices(
        prices
    )

    if len(
        resolved_prices
    ) < MINIMUM_PATTERN_PRICES:
        return False

    first_high = max(
        resolved_prices[:10]
    )
    second_high = max(
        resolved_prices[10:]
    )

    if first_high <= 0.0:
        return False

    difference = abs(
        first_high
        - second_high
    )

    return (
        difference
        / first_high
        < DOUBLE_PATTERN_TOLERANCE
    )


def detect_breakout(
    current_price,
    support,
    resistance,
):
    resolved_current_price = (
        _safe_positive_float(
            current_price
        )
    )
    resolved_support = (
        _safe_positive_float(
            support
        )
    )
    resolved_resistance = (
        _safe_positive_float(
            resistance
        )
    )

    if (
        resolved_current_price is None
        or resolved_support is None
        or resolved_resistance is None
    ):
        return "NO BREAKOUT"

    if (
        resolved_current_price
        > resolved_resistance
    ):
        return "BULLISH BREAKOUT"

    if (
        resolved_current_price
        < resolved_support
    ):
        return "BEARISH BREAKOUT"

    return "NO BREAKOUT"


__all__ = [
    "DOUBLE_PATTERN_TOLERANCE",
    "MAXIMUM_PRICE_POINTS",
    "MINIMUM_PATTERN_PRICES",
    "detect_breakout",
    "detect_double_bottom",
    "detect_double_top",
]