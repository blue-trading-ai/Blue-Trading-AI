"""
Trendline Detection Engine.

Candles must be ordered from oldest to newest and contain:
open, high, low, close.

The engine detects:
- Bullish trendline from rising swing lows
- Bearish trendline from falling swing highs
- Trendline break
- Retest confirmation
"""

from __future__ import annotations

import math
from typing import Any, Final, Mapping


MINIMUM_CANDLES: Final[int] = 10
MAXIMUM_CANDLES: Final[int] = 100_000
MAXIMUM_LOOKBACK: Final[int] = 5_000
MAXIMUM_SWING_STRENGTH: Final[int] = 100
MAXIMUM_BREAK_TOLERANCE: Final[float] = 0.10
MAXIMUM_RETEST_TOLERANCE: Final[float] = 0.10


def _default_result(
    status: str = "NO_TRENDLINE",
) -> dict:
    return {
        "detected": False,
        "status": status,
        "direction": "NONE",
        "trendline_type": "NONE",
        "slope": None,
        "start_index": None,
        "end_index": None,
        "start_price": None,
        "end_price": None,
        "projected_price": None,
        "current_price": None,
        "break_detected": False,
        "break_direction": "NONE",
        "retest_detected": False,
        "distance_to_trendline": None,
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
        minimum
        <= resolved
        <= maximum
    ):
        return None

    return resolved


def _normalise_tolerance(
    value: Any,
    *,
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
        0.0
        <= resolved
        <= maximum
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

    candle_high = resolved["high"]
    candle_low = resolved["low"]
    candle_open = resolved["open"]
    candle_close = resolved["close"]

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

    if len(candles) > MAXIMUM_CANDLES:
        return []

    output: list[dict[str, float]] = []

    for candle in candles:
        resolved = _normalise_candle(
            candle
        )

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


def _find_swing_lows(
    candles: list,
    strength: int = 2,
) -> list:
    resolved_strength = (
        _normalise_positive_int(
            strength,
            minimum=1,
            maximum=MAXIMUM_SWING_STRENGTH,
        )
    )

    if resolved_strength is None:
        return []

    if len(candles) < (
        resolved_strength * 2
        + 1
    ):
        return []

    swings: list[dict[str, Any]] = []

    for index in range(
        resolved_strength,
        len(candles) - resolved_strength,
    ):
        low = candles[index]["low"]

        left = all(
            low
            < candles[
                index - offset
            ]["low"]
            for offset in range(
                1,
                resolved_strength + 1,
            )
        )

        right = all(
            low
            <= candles[
                index + offset
            ]["low"]
            for offset in range(
                1,
                resolved_strength + 1,
            )
        )

        if left and right:
            swings.append(
                {
                    "index": index,
                    "price": float(low),
                }
            )

    return swings


def _find_swing_highs(
    candles: list,
    strength: int = 2,
) -> list:
    resolved_strength = (
        _normalise_positive_int(
            strength,
            minimum=1,
            maximum=MAXIMUM_SWING_STRENGTH,
        )
    )

    if resolved_strength is None:
        return []

    if len(candles) < (
        resolved_strength * 2
        + 1
    ):
        return []

    swings: list[dict[str, Any]] = []

    for index in range(
        resolved_strength,
        len(candles) - resolved_strength,
    ):
        high = candles[index]["high"]

        left = all(
            high
            > candles[
                index - offset
            ]["high"]
            for offset in range(
                1,
                resolved_strength + 1,
            )
        )

        right = all(
            high
            >= candles[
                index + offset
            ]["high"]
            for offset in range(
                1,
                resolved_strength + 1,
            )
        )

        if left and right:
            swings.append(
                {
                    "index": index,
                    "price": float(high),
                }
            )

    return swings


def _project_line(
    first_index: int,
    first_price: float,
    second_index: int,
    second_price: float,
    target_index: int,
) -> tuple[float, float]:
    try:
        resolved_first_index = int(
            first_index
        )
        resolved_second_index = int(
            second_index
        )
        resolved_target_index = int(
            target_index
        )
    except (
        TypeError,
        ValueError,
        OverflowError,
    ):
        return 0.0, float("nan")

    resolved_first_price = (
        _finite_positive_float(
            first_price
        )
    )
    resolved_second_price = (
        _finite_positive_float(
            second_price
        )
    )

    if (
        resolved_first_price is None
        or resolved_second_price is None
    ):
        return 0.0, float("nan")

    index_distance = (
        resolved_second_index
        - resolved_first_index
    )

    if index_distance == 0:
        return (
            0.0,
            resolved_second_price,
        )

    slope = (
        resolved_second_price
        - resolved_first_price
    ) / index_distance

    projected = (
        resolved_first_price
        + slope
        * (
            resolved_target_index
            - resolved_first_index
        )
    )

    if (
        not math.isfinite(slope)
        or not math.isfinite(projected)
    ):
        return 0.0, float("nan")

    return slope, projected


def detect_trendline(
    candles: list,
    lookback: int = 50,
    swing_strength: int = 2,
    break_tolerance: float = 0.001,
    retest_tolerance: float = 0.002,
) -> dict:
    """
    Detect the most relevant bullish or bearish trendline.

    Bullish trendline:
        Two latest rising swing lows.

    Bearish trendline:
        Two latest falling swing highs.

    Break:
        Current close crosses beyond the projected trendline.

    Retest:
        Current candle trades back near a broken trendline.
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

    resolved_candles = (
        _normalise_candles(candles)
    )

    if not resolved_candles:
        return _default_result(
            "INSUFFICIENT_OHLC_DATA"
        )

    resolved_lookback = (
        _normalise_positive_int(
            lookback,
            minimum=1,
            maximum=MAXIMUM_LOOKBACK,
        )
    )
    resolved_strength = (
        _normalise_positive_int(
            swing_strength,
            minimum=1,
            maximum=MAXIMUM_SWING_STRENGTH,
        )
    )
    resolved_break_tolerance = (
        _normalise_tolerance(
            break_tolerance,
            maximum=MAXIMUM_BREAK_TOLERANCE,
        )
    )
    resolved_retest_tolerance = (
        _normalise_tolerance(
            retest_tolerance,
            maximum=MAXIMUM_RETEST_TOLERANCE,
        )
    )

    current_price = float(
        resolved_candles[-1]["close"]
    )

    if (
        resolved_lookback is None
        or resolved_strength is None
        or resolved_break_tolerance is None
        or resolved_retest_tolerance is None
    ):
        result = _default_result(
            "INVALID_CONFIGURATION"
        )
        result["current_price"] = (
            current_price
        )
        return result

    minimum_for_swings = (
        resolved_strength * 2
        + 1
    )

    if resolved_lookback < minimum_for_swings:
        result = _default_result(
            "INSUFFICIENT_SWING_WINDOW"
        )
        result["current_price"] = (
            current_price
        )
        return result

    selected = (
        resolved_candles[
            -resolved_lookback:
        ]
        if resolved_lookback
        < len(resolved_candles)
        else resolved_candles
    )

    offset = (
        len(resolved_candles)
        - len(selected)
    )

    swing_lows = _find_swing_lows(
        selected,
        resolved_strength,
    )
    swing_highs = _find_swing_highs(
        selected,
        resolved_strength,
    )

    for swing in swing_lows:
        swing["index"] += offset

    for swing in swing_highs:
        swing["index"] += offset

    current_index = (
        len(resolved_candles)
        - 1
    )
    current_high = float(
        resolved_candles[-1]["high"]
    )
    current_low = float(
        resolved_candles[-1]["low"]
    )

    candidates: list[
        dict[str, Any]
    ] = []

    if len(swing_lows) >= 2:
        first = swing_lows[-2]
        second = swing_lows[-1]

        if (
            second["price"]
            > first["price"]
        ):
            slope, projected = (
                _project_line(
                    first["index"],
                    first["price"],
                    second["index"],
                    second["price"],
                    current_index,
                )
            )

            if (
                math.isfinite(projected)
                and projected > 0.0
            ):
                tolerance = (
                    abs(projected)
                    * resolved_break_tolerance
                )
                retest_range = (
                    abs(projected)
                    * resolved_retest_tolerance
                )

                break_detected = (
                    current_price
                    < projected
                    - tolerance
                )

                retest_detected = (
                    break_detected
                    and current_high
                    >= projected
                    - retest_range
                    and current_low
                    <= projected
                    + retest_range
                )

                distance = (
                    current_price
                    - projected
                )

                if math.isfinite(distance):
                    candidates.append(
                        {
                            "detected": True,
                            "status": (
                                "BROKEN_RETESTED"
                                if retest_detected
                                else "BROKEN"
                                if break_detected
                                else "ACTIVE"
                            ),
                            "direction": "BULLISH",
                            "trendline_type": (
                                "ASCENDING_SUPPORT"
                            ),
                            "slope": slope,
                            "start_index": (
                                first["index"]
                            ),
                            "end_index": (
                                second["index"]
                            ),
                            "start_price": (
                                first["price"]
                            ),
                            "end_price": (
                                second["price"]
                            ),
                            "projected_price": (
                                projected
                            ),
                            "current_price": (
                                current_price
                            ),
                            "break_detected": (
                                break_detected
                            ),
                            "break_direction": (
                                "BEARISH_BREAK"
                                if break_detected
                                else "NONE"
                            ),
                            "retest_detected": (
                                retest_detected
                            ),
                            "distance_to_trendline": (
                                distance
                            ),
                        }
                    )

    if len(swing_highs) >= 2:
        first = swing_highs[-2]
        second = swing_highs[-1]

        if (
            second["price"]
            < first["price"]
        ):
            slope, projected = (
                _project_line(
                    first["index"],
                    first["price"],
                    second["index"],
                    second["price"],
                    current_index,
                )
            )

            if (
                math.isfinite(projected)
                and projected > 0.0
            ):
                tolerance = (
                    abs(projected)
                    * resolved_break_tolerance
                )
                retest_range = (
                    abs(projected)
                    * resolved_retest_tolerance
                )

                break_detected = (
                    current_price
                    > projected
                    + tolerance
                )

                retest_detected = (
                    break_detected
                    and current_high
                    >= projected
                    - retest_range
                    and current_low
                    <= projected
                    + retest_range
                )

                distance = (
                    current_price
                    - projected
                )

                if math.isfinite(distance):
                    candidates.append(
                        {
                            "detected": True,
                            "status": (
                                "BROKEN_RETESTED"
                                if retest_detected
                                else "BROKEN"
                                if break_detected
                                else "ACTIVE"
                            ),
                            "direction": "BEARISH",
                            "trendline_type": (
                                "DESCENDING_RESISTANCE"
                            ),
                            "slope": slope,
                            "start_index": (
                                first["index"]
                            ),
                            "end_index": (
                                second["index"]
                            ),
                            "start_price": (
                                first["price"]
                            ),
                            "end_price": (
                                second["price"]
                            ),
                            "projected_price": (
                                projected
                            ),
                            "current_price": (
                                current_price
                            ),
                            "break_detected": (
                                break_detected
                            ),
                            "break_direction": (
                                "BULLISH_BREAK"
                                if break_detected
                                else "NONE"
                            ),
                            "retest_detected": (
                                retest_detected
                            ),
                            "distance_to_trendline": (
                                distance
                            ),
                        }
                    )

    if not candidates:
        result = _default_result()
        result["current_price"] = (
            current_price
        )
        return result

    priority = {
        "BROKEN_RETESTED": 3,
        "BROKEN": 2,
        "ACTIVE": 1,
    }

    candidates.sort(
        key=lambda item: (
            priority.get(
                str(item["status"]),
                0,
            ),
            int(item["end_index"]),
        ),
        reverse=True,
    )

    return dict(candidates[0])


__all__ = [
    "MAXIMUM_BREAK_TOLERANCE",
    "MAXIMUM_CANDLES",
    "MAXIMUM_LOOKBACK",
    "MAXIMUM_RETEST_TOLERANCE",
    "MAXIMUM_SWING_STRENGTH",
    "MINIMUM_CANDLES",
    "detect_trendline",
]