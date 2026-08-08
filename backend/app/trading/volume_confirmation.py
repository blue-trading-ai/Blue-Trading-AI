"""Volume Confirmation Engine for Blue-Trading-AI.

This module evaluates whether current price movement is supported by sufficient
volume and whether volume behavior confirms bullish or bearish continuation.
"""

from __future__ import annotations

import math
from typing import Any, Final, Mapping


MINIMUM_CANDLES: Final[int] = 3
MAXIMUM_CANDLES: Final[int] = 100_000
MAXIMUM_PERIOD: Final[int] = 5_000
MINIMUM_HIGH_VOLUME_RATIO: Final[float] = 0.1
MAXIMUM_HIGH_VOLUME_RATIO: Final[float] = 100.0
MINIMUM_CLIMAX_RATIO: Final[float] = 0.1
MAXIMUM_CLIMAX_RATIO: Final[float] = 100.0


def _default_result(
    status: str = "NO_VOLUME_DATA",
) -> dict:
    return {
        "detected": False,
        "status": status,
        "direction": "NONE",
        "current_volume": None,
        "average_volume": None,
        "volume_ratio": None,
        "relative_volume": None,
        "volume_trend": "NONE",
        "price_direction": "NONE",
        "bullish_confirmation": False,
        "bearish_confirmation": False,
        "climax": False,
        "divergence": False,
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


def _finite_non_negative_float(
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
        or resolved < 0.0
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


def _normalise_ratio(
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
        "open",
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

    candle_open = resolved["open"]
    candle_high = resolved["high"]
    candle_low = resolved["low"]
    candle_close = resolved["close"]

    if candle_high < candle_low:
        return None

    if not (
        candle_low <= candle_open <= candle_high
    ):
        return None

    if not (
        candle_low <= candle_close <= candle_high
    ):
        return None

    for volume_key in (
        "volume",
        "tick_volume",
        "real_volume",
    ):
        if volume_key in candle:
            volume = _finite_non_negative_float(
                candle.get(volume_key)
            )
            if volume is not None:
                resolved[volume_key] = volume
            elif candle.get(volume_key) is not None:
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


def _extract_volume(
    candle: Mapping[str, Any],
) -> float | None:
    for key in (
        "volume",
        "tick_volume",
        "real_volume",
    ):
        if key not in candle:
            continue

        value = _finite_non_negative_float(
            candle.get(key)
        )

        if value is not None:
            return value

    return None


def detect_volume_confirmation(
    candles,
    period=20,
    high_volume_ratio=1.5,
    climax_ratio=2.5,
):
    """
    Evaluate relative volume and price-volume confirmation.

    Bullish confirmation:
    - bullish candle
    - current volume above average
    - volume ratio at least 1.2

    Bearish confirmation:
    - bearish candle
    - current volume above average
    - volume ratio at least 1.2
    """

    if not isinstance(
        candles,
        (list, tuple),
    ):
        return _default_result(
            "INSUFFICIENT_OHLC_DATA"
        )

    if len(candles) < MINIMUM_CANDLES:
        return _default_result(
            "INSUFFICIENT_DATA"
        )

    resolved_candles = _normalise_candles(
        candles
    )

    if not resolved_candles:
        return _default_result(
            "INSUFFICIENT_OHLC_DATA"
        )

    resolved_period = _normalise_positive_int(
        period,
        minimum=1,
        maximum=MAXIMUM_PERIOD,
    )
    resolved_high_volume_ratio = _normalise_ratio(
        high_volume_ratio,
        minimum=MINIMUM_HIGH_VOLUME_RATIO,
        maximum=MAXIMUM_HIGH_VOLUME_RATIO,
    )
    resolved_climax_ratio = _normalise_ratio(
        climax_ratio,
        minimum=MINIMUM_CLIMAX_RATIO,
        maximum=MAXIMUM_CLIMAX_RATIO,
    )

    if (
        resolved_period is None
        or resolved_high_volume_ratio is None
        or resolved_climax_ratio is None
    ):
        return _default_result(
            "INVALID_CONFIGURATION"
        )

    volumes = [
        _extract_volume(candle)
        for candle in resolved_candles
    ]

    if any(
        volume is None
        for volume in volumes
    ):
        return _default_result(
            "NO_VOLUME_DATA"
        )

    resolved_volumes = [
        float(volume)
        for volume in volumes
        if volume is not None
    ]

    current_volume = resolved_volumes[-1]

    history = (
        resolved_volumes[
            -resolved_period - 1:
            -1
        ]
        if len(resolved_volumes) > 1
        else []
    )

    if not history:
        result = _default_result(
            "INSUFFICIENT_VOLUME_HISTORY"
        )
        result["current_volume"] = (
            current_volume
        )
        return result

    average_volume = (
        sum(history)
        / len(history)
    )

    if (
        not math.isfinite(average_volume)
        or average_volume <= 0.0
    ):
        result = _default_result(
            "INVALID_VOLUME_DATA"
        )
        result["current_volume"] = (
            current_volume
        )
        result["average_volume"] = (
            average_volume
        )
        return result

    volume_ratio = (
        current_volume
        / average_volume
    )

    if not math.isfinite(volume_ratio):
        result = _default_result(
            "INVALID_VOLUME_DATA"
        )
        result["current_volume"] = (
            current_volume
        )
        result["average_volume"] = (
            average_volume
        )
        return result

    current = resolved_candles[-1]
    previous = resolved_candles[-2]

    if current["close"] > current["open"]:
        price_direction = "BULLISH"
    elif current["close"] < current["open"]:
        price_direction = "BEARISH"
    else:
        price_direction = "NEUTRAL"

    recent_window = resolved_volumes[-5:]
    earlier_window = (
        resolved_volumes[-10:-5]
        if len(resolved_volumes) >= 10
        else resolved_volumes[:-5]
    )

    recent_average = (
        sum(recent_window)
        / len(recent_window)
        if recent_window
        else current_volume
    )

    earlier_average = (
        sum(earlier_window)
        / len(earlier_window)
        if earlier_window
        else recent_average
    )

    if (
        not math.isfinite(recent_average)
        or not math.isfinite(earlier_average)
    ):
        return _default_result(
            "INVALID_VOLUME_DATA"
        )

    if (
        recent_average
        > earlier_average * 1.1
    ):
        volume_trend = "RISING"
    elif (
        recent_average
        < earlier_average * 0.9
    ):
        volume_trend = "FALLING"
    else:
        volume_trend = "STABLE"

    confirmation_ratio = max(
        1.2,
        resolved_high_volume_ratio,
    )

    bullish_confirmation = (
        price_direction == "BULLISH"
        and volume_ratio
        >= confirmation_ratio
        and current["close"]
        >= previous["close"]
    )

    bearish_confirmation = (
        price_direction == "BEARISH"
        and volume_ratio
        >= confirmation_ratio
        and current["close"]
        <= previous["close"]
    )

    climax = (
        volume_ratio
        >= resolved_climax_ratio
    )

    bullish_price_progress = (
        current["close"]
        > previous["close"]
    )
    bearish_price_progress = (
        current["close"]
        < previous["close"]
    )

    divergence = (
        volume_trend == "FALLING"
        and (
            bullish_price_progress
            or bearish_price_progress
        )
    )

    strength = 0

    if volume_ratio >= 1.2:
        strength += 35
    elif volume_ratio >= 1.0:
        strength += 20
    elif volume_ratio >= 0.8:
        strength += 10

    if volume_trend == "RISING":
        strength += 20
    elif volume_trend == "STABLE":
        strength += 10

    if (
        bullish_confirmation
        or bearish_confirmation
    ):
        strength += 30

    if climax:
        strength += 15

    if divergence:
        strength -= 20

    strength = max(
        0,
        min(
            100,
            int(strength),
        ),
    )

    if bullish_confirmation:
        direction = "BULLISH"
        status = "CONFIRMED"
    elif bearish_confirmation:
        direction = "BEARISH"
        status = "CONFIRMED"
    elif climax:
        direction = price_direction
        status = "CLIMAX"
    elif divergence:
        direction = "NEUTRAL"
        status = "DIVERGENCE"
    else:
        direction = "NEUTRAL"
        status = "WEAK"

    actionable = (
        status == "CONFIRMED"
        and strength >= 60
        and not divergence
    )

    relative_volume = (
        volume_ratio * 100.0
    )

    if not math.isfinite(relative_volume):
        return _default_result(
            "INVALID_VOLUME_DATA"
        )

    return {
        "detected": True,
        "status": status,
        "direction": direction,
        "current_volume": round(
            current_volume,
            4,
        ),
        "average_volume": round(
            average_volume,
            4,
        ),
        "volume_ratio": round(
            volume_ratio,
            4,
        ),
        "relative_volume": round(
            relative_volume,
            2,
        ),
        "volume_trend": volume_trend,
        "price_direction": price_direction,
        "bullish_confirmation": (
            bullish_confirmation
        ),
        "bearish_confirmation": (
            bearish_confirmation
        ),
        "climax": climax,
        "divergence": divergence,
        "strength": strength,
        "actionable": actionable,
    }


__all__ = [
    "MAXIMUM_CANDLES",
    "MAXIMUM_PERIOD",
    "MINIMUM_CANDLES",
    "detect_volume_confirmation",
]