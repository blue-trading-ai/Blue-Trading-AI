from __future__ import annotations

import math
from typing import Any, Final

from app.trading.indicators import (
    calculate_ema,
    calculate_moving_average,
    calculate_rsi,
    detect_trend,
    find_support_resistance,
)


MAXIMUM_SYMBOL_LENGTH: Final[int] = 40
MAXIMUM_PRICE_POINTS: Final[int] = 100_000


def _normalise_symbol(
    value: Any,
) -> str:
    symbol = str(
        value or ""
    ).strip().upper()

    if not symbol:
        raise ValueError(
            "Symbol is required."
        )

    if len(
        symbol
    ) > MAXIMUM_SYMBOL_LENGTH:
        raise ValueError(
            "Symbol is too long."
        )

    allowed = set(
        "ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789._-/"
    )

    if any(
        character not in allowed
        for character in symbol
    ):
        raise ValueError(
            "Symbol contains unsupported characters."
        )

    return symbol


def _normalise_prices(
    prices: Any,
) -> list[float]:
    if not isinstance(
        prices,
        list,
    ) or not prices:
        raise ValueError(
            "No price data available."
        )

    if len(
        prices
    ) > MAXIMUM_PRICE_POINTS:
        raise ValueError(
            "Price history exceeds the supported safety limit."
        )

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
        ) as exc:
            raise ValueError(
                "Price data contains an invalid value."
            ) from exc

        if (
            not math.isfinite(
                number
            )
            or number <= 0.0
        ):
            raise ValueError(
                "Price data contains an invalid value."
            )

        resolved_prices.append(
            number
        )

    return resolved_prices


def _optional_finite_float(
    value: Any,
) -> float | None:
    if value is None:
        return None

    try:
        number = float(
            value
        )
    except (
        TypeError,
        ValueError,
        OverflowError,
    ):
        return None

    if not math.isfinite(
        number
    ):
        return None

    return number


def analyze_market(
    symbol: str,
    prices: list,
) -> dict:
    """
    Analyze one market using the existing indicator stack.

    Returns the same public fields used by the signal engine.
    """

    try:
        resolved_symbol = (
            _normalise_symbol(
                symbol
            )
        )
        resolved_prices = (
            _normalise_prices(
                prices
            )
        )
    except ValueError as error:
        return {
            "error": str(
                error
            ),
        }

    try:
        trend = detect_trend(
            resolved_prices
        )

        moving_average = (
            calculate_moving_average(
                resolved_prices
            )
        )

        ema = calculate_ema(
            resolved_prices
        )

        rsi = calculate_rsi(
            resolved_prices
        )

        support, resistance = (
            find_support_resistance(
                resolved_prices
            )
        )

    except Exception:
        return {
            "error": (
                "Market indicator analysis failed."
            ),
        }

    trend = str(
        trend or "SIDEWAYS"
    ).strip().upper()

    if trend not in {
        "UPTREND",
        "DOWNTREND",
        "SIDEWAYS",
    }:
        trend = "SIDEWAYS"

    moving_average = (
        _optional_finite_float(
            moving_average
        )
    )
    ema = _optional_finite_float(
        ema
    )
    rsi = _optional_finite_float(
        rsi
    )
    support = _optional_finite_float(
        support
    )
    resistance = (
        _optional_finite_float(
            resistance
        )
    )

    if rsi is not None:
        rsi = max(
            0.0,
            min(
                100.0,
                rsi,
            ),
        )

    if (
        support is not None
        and support <= 0.0
    ):
        support = None

    if (
        resistance is not None
        and resistance <= 0.0
    ):
        resistance = None

    if (
        trend == "UPTREND"
        and rsi is not None
        and rsi < 70.0
    ):
        market_condition = (
            "BULLISH"
        )

    elif (
        trend == "DOWNTREND"
        and rsi is not None
        and rsi > 30.0
    ):
        market_condition = (
            "BEARISH"
        )

    else:
        market_condition = (
            "SIDEWAYS"
        )

    return {
        "symbol": resolved_symbol,
        "market_condition": (
            market_condition
        ),
        "trend": trend,
        "moving_average": (
            moving_average
        ),
        "ema": ema,
        "rsi": rsi,
        "support": support,
        "resistance": resistance,
    }


__all__ = [
    "MAXIMUM_PRICE_POINTS",
    "MAXIMUM_SYMBOL_LENGTH",
    "analyze_market",
]