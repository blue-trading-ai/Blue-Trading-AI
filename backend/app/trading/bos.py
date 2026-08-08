"""
Break of Structure Detection

Detects:
- Bullish BOS: price closes above the previous swing high
- Bearish BOS: price closes below the previous swing low
- No BOS: price remains inside the structure

BOS is normally a continuation confirmation.
"""

from __future__ import annotations

import math
from typing import Any, Final, Mapping

from app.trading.market_structure import detect_market_structure


MINIMUM_PRICE_POINTS: Final[int] = 6
MAXIMUM_PRICE_POINTS: Final[int] = 100_000
MAXIMUM_LOOKBACK: Final[int] = 100
MAXIMUM_CONFIRMATION_BUFFER: Final[float] = 1_000_000.0


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

    resolved_prices: list[
        float
    ] = []

    for value in prices:
        try:
            number = float(
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
                number
            )
            or number <= 0.0
        ):
            return []

        resolved_prices.append(
            number
        )

    return resolved_prices


def _normalise_lookback(
    lookback: Any,
) -> int | None:
    if isinstance(
        lookback,
        bool,
    ):
        return None

    try:
        resolved = int(
            lookback
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


def _normalise_confirmation_buffer(
    confirmation_buffer: Any,
) -> float | None:
    try:
        resolved = float(
            confirmation_buffer
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
        > MAXIMUM_CONFIRMATION_BUFFER
    ):
        return None

    return resolved


def _finite_positive_or_none(
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


def detect_bos(
    prices: list,
    lookback: int = 2,
    confirmation_buffer: float = 0.0,
) -> dict:
    """
    Detect a bullish or bearish Break of Structure.

    Args:
        prices:
            Candle closing prices ordered from oldest to newest.

        lookback:
            Swing-detection lookback used by market_structure.py.

        confirmation_buffer:
            Extra distance required beyond the swing level.

    Returns:
        Dictionary containing BOS status, direction and broken level.
    """

    default_result = {
        "detected": False,
        "direction": "NONE",
        "level": None,
        "break_price": None,
        "distance": None,
        "previous_structure": "RANGE",
    }

    resolved_prices = (
        _normalise_prices(
            prices
        )
    )
    resolved_lookback = (
        _normalise_lookback(
            lookback
        )
    )
    resolved_buffer = (
        _normalise_confirmation_buffer(
            confirmation_buffer
        )
    )

    if (
        len(
            resolved_prices
        ) < MINIMUM_PRICE_POINTS
        or resolved_lookback is None
        or resolved_buffer is None
    ):
        return default_result

    market_structure = (
        detect_market_structure(
            resolved_prices,
            lookback=resolved_lookback,
        )
    )

    if not isinstance(
        market_structure,
        Mapping,
    ):
        return default_result

    market_structure = dict(
        market_structure
    )

    structure = str(
        market_structure.get(
            "structure",
            "RANGE",
        )
        or "RANGE"
    ).strip().upper()

    last_high = (
        _finite_positive_or_none(
            market_structure.get(
                "last_high"
            )
        )
    )
    last_low = (
        _finite_positive_or_none(
            market_structure.get(
                "last_low"
            )
        )
    )

    current_close = (
        resolved_prices[
            -1
        ]
    )
    previous_close = (
        resolved_prices[
            -2
        ]
    )

    default_result[
        "break_price"
    ] = current_close
    default_result[
        "previous_structure"
    ] = structure

    if (
        last_high is None
        or last_low is None
    ):
        return default_result

    bullish_break_level = (
        last_high
        + resolved_buffer
    )
    bearish_break_level = (
        last_low
        - resolved_buffer
    )

    if (
        not math.isfinite(
            bullish_break_level
        )
        or not math.isfinite(
            bearish_break_level
        )
        or bearish_break_level <= 0.0
    ):
        return default_result

    bullish_bos = (
        previous_close
        <= bullish_break_level
        and current_close
        > bullish_break_level
    )

    bearish_bos = (
        previous_close
        >= bearish_break_level
        and current_close
        < bearish_break_level
    )

    if bullish_bos:
        distance = (
            current_close
            - last_high
        )

        return {
            "detected": True,
            "direction": "BULLISH_BOS",
            "level": last_high,
            "break_price": current_close,
            "distance": round(
                max(
                    distance,
                    0.0,
                ),
                5,
            ),
            "previous_structure": structure,
        }

    if bearish_bos:
        distance = (
            last_low
            - current_close
        )

        return {
            "detected": True,
            "direction": "BEARISH_BOS",
            "level": last_low,
            "break_price": current_close,
            "distance": round(
                max(
                    distance,
                    0.0,
                ),
                5,
            ),
            "previous_structure": structure,
        }

    return default_result


__all__ = [
    "MAXIMUM_CONFIRMATION_BUFFER",
    "MAXIMUM_LOOKBACK",
    "MAXIMUM_PRICE_POINTS",
    "MINIMUM_PRICE_POINTS",
    "detect_bos",
]