"""ATR and Volatility Filter for Blue-Trading-AI."""

from __future__ import annotations

import math
from typing import Any, Final, Mapping


MINIMUM_PERIOD: Final[int] = 1
MAXIMUM_PERIOD: Final[int] = 5_000
MAXIMUM_CANDLES: Final[int] = 100_000

MINIMUM_LOW_THRESHOLD_PERCENT: Final[float] = 0.0
MAXIMUM_LOW_THRESHOLD_PERCENT: Final[float] = 100.0
MINIMUM_HIGH_THRESHOLD_PERCENT: Final[float] = 0.0001
MAXIMUM_HIGH_THRESHOLD_PERCENT: Final[float] = 100.0

EXTREME_MULTIPLIER: Final[float] = 1.75


def _default_result(
    status: str = "INSUFFICIENT_DATA",
) -> dict:
    return {
        "detected": False,
        "status": status,
        "atr": None,
        "atr_percent": None,
        "volatility": "UNKNOWN",
        "trade_environment": "UNKNOWN",
        "too_low": False,
        "too_high": False,
        "normal": False,
        "strength": 0,
        "actionable": False,
    }


def _finite_positive_float(
    value: Any,
) -> float | None:
    try:
        resolved = float(value)
    except (
        TypeError,
        ValueError,
        OverflowError,
    ):
        return None

    if (
        not math.isfinite(resolved)
        or resolved <= 0.0
    ):
        return None

    return resolved


def _normalise_positive_int(
    value: Any,
    *,
    minimum: int,
    maximum: int,
) -> int | None:
    if isinstance(value, bool):
        return None

    try:
        resolved = int(value)
    except (
        TypeError,
        ValueError,
        OverflowError,
    ):
        return None

    if not (
        minimum <= resolved <= maximum
    ):
        return None

    return resolved


def _normalise_threshold(
    value: Any,
    *,
    minimum: float,
    maximum: float,
) -> float | None:
    try:
        resolved = float(value)
    except (
        TypeError,
        ValueError,
        OverflowError,
    ):
        return None

    if not math.isfinite(resolved):
        return None

    if not (
        minimum <= resolved <= maximum
    ):
        return None

    return resolved


def _normalise_candle(
    candle: Any,
) -> dict[str, float] | None:
    if not isinstance(candle, Mapping):
        return None

    resolved: dict[str, float] = {}

    for field in (
        "high",
        "low",
        "close",
    ):
        value = _finite_positive_float(
            candle.get(field)
        )

        if value is None:
            return None

        resolved[field] = value

    candle_high = resolved["high"]
    candle_low = resolved["low"]
    candle_close = resolved["close"]

    if candle_high < candle_low:
        return None

    if not (
        candle_low <= candle_close <= candle_high
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

    if len(candles) > MAXIMUM_CANDLES:
        return []

    output: list[dict[str, float]] = []

    for candle in candles:
        resolved = _normalise_candle(candle)

        if resolved is None:
            return []

        output.append(resolved)

    return output


def _valid_candle(
    candle: object,
) -> bool:
    return (
        _normalise_candle(candle)
        is not None
    )


def detect_atr_volatility(
    candles,
    period=14,
    low_threshold_percent=0.15,
    high_threshold_percent=1.50,
):
    """
    Calculate ATR and classify current volatility.

    Volatility classes:
    - LOW: weak movement; avoid many setups
    - NORMAL: acceptable trading environment
    - HIGH: elevated movement; use wider risk controls
    - EXTREME: potentially unstable market
    """

    if not isinstance(
        candles,
        (list, tuple),
    ):
        return _default_result(
            "INVALID_OHLC_DATA"
        )

    resolved_period = _normalise_positive_int(
        period,
        minimum=MINIMUM_PERIOD,
        maximum=MAXIMUM_PERIOD,
    )

    if resolved_period is None:
        return _default_result(
            "INVALID_CONFIGURATION"
        )

    if len(candles) < resolved_period + 1:
        return _default_result()

    resolved_candles = _normalise_candles(
        candles
    )

    if not resolved_candles:
        return _default_result(
            "INVALID_OHLC_DATA"
        )

    resolved_low_threshold = _normalise_threshold(
        low_threshold_percent,
        minimum=MINIMUM_LOW_THRESHOLD_PERCENT,
        maximum=MAXIMUM_LOW_THRESHOLD_PERCENT,
    )
    resolved_high_threshold = _normalise_threshold(
        high_threshold_percent,
        minimum=MINIMUM_HIGH_THRESHOLD_PERCENT,
        maximum=MAXIMUM_HIGH_THRESHOLD_PERCENT,
    )

    if (
        resolved_low_threshold is None
        or resolved_high_threshold is None
        or resolved_low_threshold
        >= resolved_high_threshold
    ):
        return _default_result(
            "INVALID_CONFIGURATION"
        )

    true_ranges: list[float] = []

    for index in range(
        1,
        len(resolved_candles),
    ):
        current = resolved_candles[index]
        previous_close = resolved_candles[
            index - 1
        ]["close"]

        true_range = max(
            current["high"]
            - current["low"],
            abs(
                current["high"]
                - previous_close
            ),
            abs(
                current["low"]
                - previous_close
            ),
        )

        if (
            not math.isfinite(true_range)
            or true_range < 0.0
        ):
            return _default_result(
                "INVALID_OHLC_DATA"
            )

        true_ranges.append(
            float(true_range)
        )

    atr_values = true_ranges[
        -resolved_period:
    ]

    if len(atr_values) < resolved_period:
        return _default_result()

    atr = (
        sum(atr_values)
        / len(atr_values)
    )

    if (
        not math.isfinite(atr)
        or atr < 0.0
    ):
        return _default_result(
            "INVALID_ATR"
        )

    current_price = float(
        resolved_candles[-1]["close"]
    )

    if (
        not math.isfinite(current_price)
        or current_price <= 0.0
    ):
        return _default_result(
            "INVALID_PRICE"
        )

    atr_percent = (
        atr / current_price
    ) * 100.0

    if (
        not math.isfinite(atr_percent)
        or atr_percent < 0.0
    ):
        return _default_result(
            "INVALID_ATR"
        )

    extreme_threshold = (
        resolved_high_threshold
        * EXTREME_MULTIPLIER
    )

    if not math.isfinite(
        extreme_threshold
    ):
        return _default_result(
            "INVALID_CONFIGURATION"
        )

    too_low = (
        atr_percent
        < resolved_low_threshold
    )
    too_high = (
        atr_percent
        > extreme_threshold
    )

    if too_low:
        volatility = "LOW"
        trade_environment = "WEAK"
        strength = 20
        actionable = False

    elif (
        atr_percent
        <= resolved_high_threshold
    ):
        volatility = "NORMAL"
        trade_environment = "FAVORABLE"
        strength = 80
        actionable = True

    elif (
        atr_percent
        <= extreme_threshold
    ):
        volatility = "HIGH"
        trade_environment = "CAUTION"
        strength = 60
        actionable = True

    else:
        volatility = "EXTREME"
        trade_environment = "UNSTABLE"
        strength = 30
        actionable = False

    return {
        "detected": True,
        "status": "ACTIVE",
        "atr": round(
            atr,
            6,
        ),
        "atr_percent": round(
            atr_percent,
            4,
        ),
        "volatility": volatility,
        "trade_environment": (
            trade_environment
        ),
        "too_low": too_low,
        "too_high": too_high,
        "normal": (
            volatility == "NORMAL"
        ),
        "strength": strength,
        "actionable": actionable,
    }


__all__ = [
    "EXTREME_MULTIPLIER",
    "MAXIMUM_CANDLES",
    "MAXIMUM_PERIOD",
    "MINIMUM_PERIOD",
    "detect_atr_volatility",
]